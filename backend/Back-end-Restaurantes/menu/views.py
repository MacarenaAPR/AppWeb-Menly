from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import cache_control
import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from .serializers import CustomTokenObtainPairSerializer,ReservaManualSerializer, ProductoCreateSerializer, ReservaPublicaSerializer, ReservaDashboardSerializer, SolicitudEspecialPublicaSerializer, SolicitudEspecialDashboardSerializer
from .serializers import NotificacionSerializer, NotificacionDetalleSerializer
from .serializers import PedidoWhatsAppCreateSerializer, PedidoWhatsAppDashboardSerializer, PedidoWhatsAppEstadoUpdateSerializer, PedidoWhatsAppSeguimientoPublicoSerializer, PedidoEspecialSerializer
from .serializers import ReporteMetricaSerializer
from .serializers import IconoSerializer, RestauranteConfigSerializer, RestaurantePublicoDetalleSerializer, HorarioSerializer, MetodoPagoSerializer, MesaSerializer, CategoriaSerializer, RespaldoRestauranteSerializer
from .serializers import serializar_plan_restaurante
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import UsuarioRestaurante,Icono, Categoria, Restaurante,Producto, BitacoraProducto, Reserva, SolicitudEspecial, Notificacion, PedidoWhatsApp, PedidoEspecial, ReporteMetrica
from .models import HorarioAtencion, MetodoPago, Mesa, RespaldoRestaurante
from django.db.models import Count, Q, Prefetch
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.generics import CreateAPIView, UpdateAPIView
from django.db import IntegrityError, transaction
from django.utils.timezone import localtime, now
from datetime import datetime, timedelta
from calendar import monthrange
from rest_framework.throttling import AnonRateThrottle
from rest_framework.pagination import PageNumberPagination
from menu.permissions import CanManageConfiguracion, CanManageUsuarios,CanViewBitacora,CanManageProductos,CanManageReservas,CanManageMesas,CanManageHorarios,CanManageMetodosPago,CanManageRespaldos
from menu.permissions import MENSAJE_CUENTA_INACTIVA
from menu.utils import validar_horario_reserva, notificar_nueva_reserva, notificar_nueva_solicitud_especial
from menu.utils import crear_notificacion_reserva, crear_notificacion_solicitud_especial
from menu.cache_utils import get_cached_menu, invalidate_menu_cache, set_cached_menu
from menu.services.metricas.productos import productos_mas_clickeados
from menu.services.metricas.reportes import (
    construir_reporte_anual,
    construir_reporte_mensual,
)
from menu.services.metricas.resumen import (
    construir_payload_pedidos_compat,
    construir_resumen_metricas,
)


logger = logging.getLogger(__name__)


class IconosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        iconos = Icono.objects.filter(activo=True).order_by("orden")
        serializer = IconoSerializer(iconos, many=True)
        return Response(serializer.data)

class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"


class PublicReservaRateThrottle(AnonRateThrottle):
    scope = "public_reservas"


class PublicSolicitudEspecialRateThrottle(AnonRateThrottle):
    scope = "public_solicitudes_especiales"


class ProductoClickRateThrottle(AnonRateThrottle):
    scope = "producto_click"


class ReservasPagination(PageNumberPagination):
    page_size = 10


class HistorialPagination(PageNumberPagination):
    page_size = 20


class ProductosPagination(PageNumberPagination):
    page_size = 8


class DefaultListPagination(PageNumberPagination):
    page_size = 10


def respuesta_duplicado(mensaje):
    return Response({"error": mensaje}, status=status.HTTP_400_BAD_REQUEST)


def respuesta_cuenta_inactiva():
    return Response({"error": MENSAJE_CUENTA_INACTIVA}, status=status.HTTP_403_FORBIDDEN)


def bloquear_si_cuenta_inactiva(perfil):
    if not perfil.restaurante.activo:
        return respuesta_cuenta_inactiva()

    return None


def respuesta_publica_restaurante_inactivo():
    return {
        "error": "El restaurante se encuentra inactivo.",
        "detalle": "El propietario no ha regularizado la suscripción. Contacta al soporte de Menly para reactivar la cuenta.",
        "estado": "inactivo",
    }


def contiene_solo_campos(request, campos_permitidos):
    return set(request.data.keys()).issubset(set(campos_permitidos))


def paginated_response(request, queryset, serialize_page, pagination_class=DefaultListPagination):
    paginator = pagination_class()
    requested_page_size = request.query_params.get("page_size")
    if requested_page_size:
        try:
            paginator.page_size = min(max(int(requested_page_size), 1), 50)
        except (TypeError, ValueError):
            paginator.page_size = paginator.page_size
    page = paginator.paginate_queryset(queryset, request)

    if page is not None:
        return paginator.get_paginated_response(serialize_page(page))

    return Response(serialize_page(queryset))


def fecha_iso(valor):
    return valor.isoformat() if valor else None


def sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha.day, monthrange(anio, mes)[1])

    return fecha.replace(year=anio, month=mes, day=dia)


def calcular_estado_suscripcion(restaurante):
    fecha_base = restaurante.fecha_creacion.date()
    fecha_vencimiento = sumar_meses(fecha_base, 1)
    hoy = now().date()
    dias_restantes = (fecha_vencimiento - hoy).days

    return {
        "fecha_vencimiento": fecha_vencimiento.isoformat(),
        "dias_restantes": dias_restantes,
        "por_vencer": 0 <= dias_restantes <= 3,
        "vencida": dias_restantes < 0,
    }


def construir_datos_respaldo(restaurante):
    productos = Producto.objects.filter(
        restaurante=restaurante
    ).select_related("categoria").order_by("categoria__orden", "orden", "id")

    reservas = restaurante.reservas.select_related(
        "creada_por__user",
        "gestionada_por__user"
    ).order_by("-fecha_creacion")

    usuarios = restaurante.usuarios.select_related("user").all()

    return {
        "restaurante": RestauranteConfigSerializer(restaurante).data,
        "categorias": CategoriaSerializer(
            Categoria.objects.filter(restaurante=restaurante).order_by("orden", "id"),
            many=True
        ).data,
        "productos": [
            {
                "id": p.id,
                "categoria": p.categoria.nombre,
                "nombre": p.nombre,
                "descripcion": p.descripcion,
                "condiciones": p.condiciones,
                "precio": str(p.precio),
                "imagen": p.imagen.url if p.imagen else None,
                "disponible": p.disponible,
                "destacado": p.destacado,
                "orden": p.orden,
                "fecha_creacion": fecha_iso(p.fecha_creacion),
            }
            for p in productos
        ],
        "mesas": MesaSerializer(restaurante.mesas.all(), many=True).data,
        "horarios": HorarioSerializer(restaurante.horarios.all(), many=True).data,
        "metodos_pago": MetodoPagoSerializer(restaurante.metodos_pago.all(), many=True).data,
        "reservas": ReservaDashboardSerializer(reservas, many=True).data,
        "usuarios": [
            {
                "id": u.id,
                "username": u.user.username,
                "email": u.user.email,
                "rol": u.rol,
                "activo": u.activo,
                "fecha_creacion": fecha_iso(u.fecha_creacion),
            }
            for u in usuarios
        ],
    }


def normalizar_email(email):
    return (email or "").strip().lower()


ESTADOS_RESERVA_ACTIVA = ["pendiente", "confirmada"]
RESTAURANTE_FEATURE_FLAGS = [
    "reservas_activas",
    "solicitudes_especiales_activas",
    "carrito_whatsapp_activo",
    "metricas_activas",
]


def serializar_flags_restaurante(restaurante):
    return {
        campo: getattr(restaurante, campo)
        for campo in RESTAURANTE_FEATURE_FLAGS
    }


def existe_reserva_duplicada(restaurante, fecha, hora, email, telefono, reserva_id=None):
    reservas_activas = Reserva.objects.filter(
        restaurante=restaurante,
        fecha=fecha,
        hora=hora,
        estado__in=ESTADOS_RESERVA_ACTIVA,
    )

    if reserva_id:
        reservas_activas = reservas_activas.exclude(id=reserva_id)

    condiciones = Q()
    email = normalizar_email(email)
    telefono = (telefono or "").strip()

    if email:
        condiciones |= Q(email__iexact=email)

    if telefono:
        condiciones |= Q(telefono=telefono)

    if not condiciones:
        return False

    return reservas_activas.filter(condiciones).exists()


def existe_reserva_publica_para_cliente_en_fecha(restaurante, fecha, email, telefono):
    reservas_activas = Reserva.objects.filter(
        restaurante=restaurante,
        fecha=fecha,
        estado__in=ESTADOS_RESERVA_ACTIVA,
    )

    condiciones = Q()
    email = normalizar_email(email)
    telefono = (telefono or "").strip()

    if email:
        condiciones |= Q(email__iexact=email)

    if telefono:
        condiciones |= Q(telefono=telefono)

    if not condiciones:
        return False

    return reservas_activas.filter(condiciones).exists()


def valores_mesa_asignada(mesa):
    valores = {
        str(mesa.id),
        str(mesa.numero),
        str(mesa).strip(),
    }

    if mesa.nombre:
        valores.add(mesa.nombre.strip())

    return [valor for valor in valores if valor]


def existe_mesa_ocupada(restaurante, mesa, fecha, hora, reserva_id=None):
    reservas = Reserva.objects.filter(
        restaurante=restaurante,
        fecha=fecha,
        hora=hora,
        estado__in=ESTADOS_RESERVA_ACTIVA,
        mesa_asignada__in=valores_mesa_asignada(mesa),
    )

    if reserva_id:
        reservas = reservas.exclude(id=reserva_id)

    return reservas.exists()


def buscar_mesa_asignada(restaurante, valor):
    valor = str(valor).strip()
    mesa_filtro = Q(nombre__iexact=valor)

    if valor.isdigit():
        numero = int(valor)
        mesa_filtro |= Q(id=numero) | Q(numero=numero)

    return Mesa.objects.filter(
        mesa_filtro,
        restaurante=restaurante,
        activa=True
    ).first()


def validar_email_usuario(restaurante, email, user_id=None):
    from django.contrib.auth.models import User

    email = normalizar_email(email)

    if not email:
        return "El email es obligatorio."

    mismo_restaurante = UsuarioRestaurante.objects.filter(
        restaurante=restaurante,
        user__email__iexact=email,
    )

    if user_id:
        mismo_restaurante = mismo_restaurante.exclude(user_id=user_id)

    if mismo_restaurante.exists():
        return "Ya existe un usuario con ese correo en este restaurante."

    usuario_global = User.objects.filter(email__iexact=email)

    if user_id:
        usuario_global = usuario_global.exclude(id=user_id)

    if usuario_global.exists():
        return "Este correo ya existe en el sistema (puede pertenecer a otro usuario o superuser). Usa otro correo."

    return None


def valor_booleano(valor):
    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):
        return valor.lower() in ["true", "1", "si", "sí", "on"]

    return bool(valor)


@transaction.atomic
def reordenar_producto(producto, categoria, nuevo_orden):
    restaurante = producto.restaurante
    categoria_anterior_id = producto.categoria_id

    productos_destino = list(
        Producto.objects.select_for_update()
        .filter(restaurante=restaurante, categoria=categoria)
        .exclude(id=producto.id)
        .order_by("orden", "id")
    )

    if nuevo_orden < 1:
        nuevo_orden = 1

    if nuevo_orden > len(productos_destino) + 1:
        nuevo_orden = len(productos_destino) + 1

    if producto.id:
        producto.orden = -100000 - producto.id
        producto.categoria = categoria
        producto.save(update_fields=["orden", "categoria"])
    else:
        orden_temporal = -100000 - Producto.objects.filter(restaurante=restaurante).count() - 1

        while Producto.objects.filter(
            restaurante=restaurante,
            categoria=categoria,
            orden=orden_temporal
        ).exists():
            orden_temporal -= 1

        producto.orden = orden_temporal
        producto.categoria = categoria
        producto.save()

    productos_destino.insert(nuevo_orden - 1, producto)

    for item in productos_destino:
        item.orden = -100000 - item.id
        item.save(update_fields=["orden"])

    for indice, item in enumerate(productos_destino, start=1):
        if item.orden != indice:
            item.orden = indice
            item.save(update_fields=["orden"])

    if categoria_anterior_id and categoria_anterior_id != categoria.id:
        productos_origen = Producto.objects.select_for_update().filter(
            restaurante=restaurante,
            categoria_id=categoria_anterior_id,
        ).order_by("orden", "id")

        for indice, item in enumerate(productos_origen, start=1):
            if item.orden != indice:
                item.orden = indice
                item.save(update_fields=["orden"])

    return producto

#METODOS DE PAGO
class MetodosPagoView(APIView):
    permission_classes = [IsAuthenticated, CanManageMetodosPago]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        metodos = MetodoPago.objects.filter(restaurante=restaurante)
        serializer = MetodoPagoSerializer(metodos, many=True)

        return Response(serializer.data)

    def post(self, request):
        perfil = get_perfil_activo(request)

        if perfil.rol == "admin" and not contiene_solo_campos(request, ["activo"]):
            return Response(
                {"error": "Admin solo puede activar o desactivar metodos de pago"},
                status=status.HTTP_403_FORBIDDEN
            )

        if perfil.rol not in ["dueno", "admin"]:
            return Response(
                {"error": "No tienes permiso para crear métodos de pago"},
                status=status.HTTP_403_FORBIDDEN
            )

        restaurante = perfil.restaurante

        serializer = MetodoPagoSerializer(data=request.data)

        if serializer.is_valid():
            nombre = serializer.validated_data.get("nombre")

            if MetodoPago.objects.filter(
                restaurante=restaurante,
                nombre__iexact=nombre
            ).exists():
                return Response(
                    {"error": "Ya existe un metodo de pago con ese nombre en este restaurante."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                serializer.save(restaurante=restaurante)
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe un metodo de pago con ese nombre en este restaurante."
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MetodoPagoDetalleView(APIView):
    permission_classes = [IsAuthenticated, CanManageMetodosPago]

    def patch(self, request, pk):
        perfil = get_perfil_activo(request)

        if perfil.rol != "dueno":
            return Response(
                {"error": "No tienes permiso para editar métodos de pago"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            metodo = MetodoPago.objects.get(
                id=pk,
                restaurante=perfil.restaurante
            )
        except MetodoPago.DoesNotExist:
            return Response(
                {"error": "Método de pago no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = MetodoPagoSerializer(
            metodo,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            nombre = serializer.validated_data.get("nombre")

            if nombre and MetodoPago.objects.filter(
                restaurante=perfil.restaurante,
                nombre__iexact=nombre
            ).exclude(id=metodo.id).exists():
                return Response(
                    {"error": "Ya existe un metodo de pago con ese nombre en este restaurante."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                serializer.save()
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe un metodo de pago con ese nombre en este restaurante."
                )
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        perfil = get_perfil_activo(request)

        if perfil.rol != "dueno":
            return Response(
                {"error": "No tienes permiso para eliminar métodos de pago"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            metodo = MetodoPago.objects.get(
                id=pk,
                restaurante=perfil.restaurante
            )
        except MetodoPago.DoesNotExist:
            return Response(
                {"error": "Método de pago no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        metodo.delete()
        return Response(
            {"mensaje": "Método de pago eliminado correctamente"}
        )


#PERFIL ACTIVO PARA LOGIN
def get_perfil_activo(request):
    return get_object_or_404(
        UsuarioRestaurante,
        user=request.user,
        activo=True
    )

def es_dueno(perfil):
    return perfil.rol == "dueno"

# PERMISOS DE LOS USUARIOS
class UsuariosView(APIView):
    permission_classes = [IsAuthenticated, CanManageUsuarios]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        usuarios = UsuarioRestaurante.objects.filter(
            restaurante=restaurante
        ).select_related("user").order_by("id")

        def serialize_usuarios(items):
            return [
                {
                    "id": u.id,
                    "email": u.user.email,
                    "username": u.user.username,
                    "rol": u.rol,
                    "activo": u.activo,
                }
                for u in items
            ]

        return paginated_response(request, usuarios, serialize_usuarios)

    def post(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        if perfil.rol != "dueno":
            return Response({"error": "No autorizado"}, status=403)

        username = request.data.get("username")
        email = normalizar_email(request.data.get("email"))
        password = request.data.get("password")
        rol = request.data.get("rol")

        from django.contrib.auth.models import User
        from .permissions import validate_user_limits

        if rol not in ["admin", "empleado"]:
            return Response({"error": "Rol invalido"}, status=400)

        try:
            validate_user_limits(restaurante, rol=rol)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Usuario ya existe"}, status=400)

        error_email = validar_email_usuario(restaurante, email)
        if error_email:
            return Response({"error": error_email}, status=400)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        UsuarioRestaurante.objects.create(
            user=user,
            restaurante=restaurante,
            rol=rol,
            activo=True,
            creado_por=perfil
        )

        return Response({"message": "Usuario creado"}, status=201)

    def patch(self, request, user_id):
        perfil = get_perfil_activo(request)

        if perfil.rol != "dueno":
            return Response({"error": "No autorizado"}, status=403)

        usuario = get_object_or_404(
            UsuarioRestaurante,
            id=user_id,
            restaurante=perfil.restaurante
        )

        if "rol" in request.data:
            return Response(
                {"error": "Este endpoint no permite cambiar roles."},
                status=400
            )

        campos_edicion = ["username", "email", "password"]
        if any(campo in request.data for campo in campos_edicion):
            user = usuario.user
            username = request.data.get("username", user.username)
            email = normalizar_email(request.data.get("email", user.email))
            password = request.data.get("password")

            from django.contrib.auth.models import User

            if User.objects.filter(username=username).exclude(id=user.id).exists():
                return Response({"error": "Usuario ya existe"}, status=400)

            error_email = validar_email_usuario(
                perfil.restaurante,
                email,
                user_id=user.id
            )
            if error_email:
                return Response({"error": error_email}, status=400)

            user.username = username
            user.email = email

            if password:
                user.set_password(password)

            user.save()

            return Response({"message": "Usuario actualizado"})

        if usuario.id == perfil.id:
            return Response(
                {"error": "No puedes desactivar tu propio usuario."},
                status=400
            )

        if not usuario.activo:
            from .permissions import validate_user_limits

            try:
                validate_user_limits(
                    perfil.restaurante,
                    rol=usuario.rol,
                    exclude_usuario_id=usuario.id
                )
            except ValueError as e:
                return Response({"error": str(e)}, status=400)

        usuario.activo = not usuario.activo
        usuario.save()

        usuario.user.is_active = usuario.activo
        usuario.user.save(update_fields=["is_active"])

        return Response({
            "message": "Estado actualizado",
            "activo": usuario.activo
        })

    def delete(self, request, user_id):
        perfil = get_perfil_activo(request)

        if perfil.rol != "dueno":
            return Response({"error": "No autorizado"}, status=403)

        usuario = get_object_or_404(
            UsuarioRestaurante,
            id=user_id,
            restaurante=perfil.restaurante
        )

        if usuario.id == perfil.id:
            return Response(
                {"error": "No puedes eliminar tu propio usuario."},
                status=400
            )

        usuario.user.delete()

        return Response({"message": "Usuario eliminado"})
#SUBIR FOTO
from rest_framework.parsers import MultiPartParser, FormParser

class UploadLogoView(APIView):
    permission_classes = [IsAuthenticated, CanManageConfiguracion]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        file = request.FILES.get("logo")

        if not file:
            return Response({"error": "No file"}, status=400)

        restaurante.logo = file
        restaurante.save()

        return Response({"logo": restaurante.logo.url})

# CONFIGURACION DE RESTAURANTE
class ConfiguracionRestauranteView(APIView):
    permission_classes = [IsAuthenticated, CanManageConfiguracion]

    def get_restaurante(self, request):
        perfil = get_perfil_activo(request)
        return perfil.restaurante

    def get(self, request):
        restaurante = self.get_restaurante(request)

        data = {
            "restaurante": RestauranteConfigSerializer(restaurante).data,
            "horarios": HorarioSerializer(restaurante.horarios.all(), many=True).data,
            "metodos_pago": MetodoPagoSerializer(restaurante.metodos_pago.all(), many=True).data,
            "mesas": MesaSerializer(restaurante.mesas.all(), many=True).data,
        }

        return Response(data)

    def patch(self, request):
        restaurante = self.get_restaurante(request)

        serializer = RestauranteConfigSerializer(
            restaurante,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=400)

class CategoriasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = get_perfil_activo(request)

        categorias = Categoria.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("orden", "id")

        serializer = CategoriaSerializer(categorias, many=True)
        return Response(serializer.data)

    def post(self, request):
        perfil = get_perfil_activo(request)
        bloqueo = bloquear_si_cuenta_inactiva(perfil)
        if bloqueo:
            return bloqueo

        if not es_dueno(perfil):
            return Response({"error": "No autorizado"}, status=403)

        serializer = CategoriaSerializer(data=request.data)

        if serializer.is_valid():
            nombre = serializer.validated_data.get("nombre")

            if Categoria.objects.filter(
                restaurante=perfil.restaurante,
                nombre__iexact=nombre
            ).exists():
                return Response(
                    {"error": "Ya existe una categoria con ese nombre en este restaurante."},
                    status=400
                )

            try:
                serializer.save(restaurante=perfil.restaurante)
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe una categoria con ese nombre en este restaurante."
                )
            invalidate_menu_cache(perfil.restaurante)
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

class CategoriaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get_categoria(self, perfil, categoria_id):
        return get_object_or_404(
            Categoria,
            id=categoria_id,
            restaurante=perfil.restaurante
        )

    def patch(self, request, categoria_id):
        perfil = get_perfil_activo(request)
        bloqueo = bloquear_si_cuenta_inactiva(perfil)
        if bloqueo:
            return bloqueo

        if perfil.rol == "admin" and not contiene_solo_campos(request, ["activa"]):
            return Response(
                {"error": "Admin solo puede activar o desactivar categorias."},
                status=403
            )

        if perfil.rol not in ["dueno", "admin"]:
            return Response({"error": "No autorizado"}, status=403)

        categoria = self.get_categoria(perfil, categoria_id)
        serializer = CategoriaSerializer(categoria, data=request.data, partial=True)

        if serializer.is_valid():
            nombre = serializer.validated_data.get("nombre")

            if nombre and Categoria.objects.filter(
                restaurante=perfil.restaurante,
                nombre__iexact=nombre
            ).exclude(id=categoria.id).exists():
                return Response(
                    {"error": "Ya existe una categoria con ese nombre en este restaurante."},
                    status=400
                )

            try:
                serializer.save()
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe una categoria con ese nombre en este restaurante."
                )
            invalidate_menu_cache(perfil.restaurante)
            return Response(serializer.data)

        return Response(serializer.errors, status=400)

    def delete(self, request, categoria_id):
        perfil = get_perfil_activo(request)
        bloqueo = bloquear_si_cuenta_inactiva(perfil)
        if bloqueo:
            return bloqueo

        if not es_dueno(perfil):
            return Response({"error": "No autorizado"}, status=403)

        categoria = self.get_categoria(perfil, categoria_id)

        if categoria.productos.exists():
            return Response(
                {"error": "No puedes eliminar una categoria con productos asociados."},
                status=400
            )

        restaurante = categoria.restaurante
        categoria.delete()
        invalidate_menu_cache(restaurante)
        return Response({"message": "Categoria eliminada correctamente"})

class MesasView(APIView):
    permission_classes = [IsAuthenticated, CanManageMesas]

    def get(self, request):
        perfil = get_perfil_activo(request)

        mesas = Mesa.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("numero", "id")

        serializer = MesaSerializer(mesas, many=True)
        return Response(serializer.data)

    def post(self, request):
        perfil = get_perfil_activo(request)

        serializer = MesaSerializer(data=request.data)

        if serializer.is_valid():
            numero = serializer.validated_data.get("numero")

            if Mesa.objects.filter(
                restaurante=perfil.restaurante,
                numero=numero
            ).exists():
                return Response(
                    {"error": "Ya existe una mesa con ese numero en este restaurante."},
                    status=400
                )

            try:
                serializer.save(restaurante=perfil.restaurante)
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe una mesa con ese numero en este restaurante."
                )
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

class MesaDetalleView(APIView):
    permission_classes = [IsAuthenticated, CanManageMesas]

    def get_mesa(self, perfil, mesa_id):
        return get_object_or_404(
            Mesa,
            id=mesa_id,
            restaurante=perfil.restaurante
        )

    def patch(self, request, mesa_id):
        perfil = get_perfil_activo(request)
        mesa = self.get_mesa(perfil, mesa_id)

        if perfil.rol == "admin" and not contiene_solo_campos(request, ["activa"]):
            return Response(
                {"error": "Admin solo puede activar o desactivar mesas."},
                status=403
            )

        serializer = MesaSerializer(mesa, data=request.data, partial=True)

        if serializer.is_valid():
            numero = serializer.validated_data.get("numero")

            if numero is not None and Mesa.objects.filter(
                restaurante=perfil.restaurante,
                numero=numero
            ).exclude(id=mesa.id).exists():
                return Response(
                    {"error": "Ya existe una mesa con ese numero en este restaurante."},
                    status=400
                )

            try:
                serializer.save()
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe una mesa con ese numero en este restaurante."
                )
            return Response(serializer.data)

        return Response(serializer.errors, status=400)

    def delete(self, request, mesa_id):
        perfil = get_perfil_activo(request)
        mesa = self.get_mesa(perfil, mesa_id)

        # No existe FK entre Reserva y Mesa; Reserva usa mesa_asignada como texto.
        # Por seguridad se aplica eliminacion logica por defecto.
        mesa.delete()
        return Response({"message": "Mesa eliminada correctamente."})

class HorariosView(APIView):
    permission_classes = [IsAuthenticated, CanManageHorarios]

    def get(self, request):
        perfil = get_perfil_activo(request)

        horarios = HorarioAtencion.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("dia", "id")

        serializer = HorarioSerializer(horarios, many=True)
        return Response(serializer.data)

    def post(self, request):
        perfil = get_perfil_activo(request)

        serializer = HorarioSerializer(data=request.data)

        if serializer.is_valid():
            dia = serializer.validated_data.get("dia")

            if HorarioAtencion.objects.filter(
                restaurante=perfil.restaurante,
                dia=dia
            ).exists():
                return Response(
                    {"error": "Ya existe un horario para ese dia en este restaurante."},
                    status=400
                )

            try:
                serializer.save(restaurante=perfil.restaurante)
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe un horario para ese dia en este restaurante."
                )
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)

class HorarioDetalleView(APIView):
    permission_classes = [IsAuthenticated, CanManageHorarios]

    def get_horario(self, perfil, horario_id):
        return get_object_or_404(
            HorarioAtencion,
            id=horario_id,
            restaurante=perfil.restaurante
        )

    def patch(self, request, horario_id):
        perfil = get_perfil_activo(request)
        horario = self.get_horario(perfil, horario_id)

        if perfil.rol == "admin" and not contiene_solo_campos(request, ["cerrado"]):
            return Response(
                {"error": "Admin solo puede abrir o cerrar horarios."},
                status=403
            )

        serializer = HorarioSerializer(horario, data=request.data, partial=True)

        if serializer.is_valid():
            dia = serializer.validated_data.get("dia")

            if dia is not None and HorarioAtencion.objects.filter(
                restaurante=perfil.restaurante,
                dia=dia
            ).exclude(id=horario.id).exists():
                return Response(
                    {"error": "Ya existe un horario para ese dia en este restaurante."},
                    status=400
                )

            try:
                serializer.save()
            except IntegrityError:
                return respuesta_duplicado(
                    "Ya existe un horario para ese dia en este restaurante."
                )
            return Response(serializer.data)

        return Response(serializer.errors, status=400)

    def delete(self, request, horario_id):
        perfil = get_perfil_activo(request)
        horario = self.get_horario(perfil, horario_id)

        horario.activo = False
        horario.save(update_fields=["activo"])

        return Response({"message": "Horario desactivado correctamente."})

# RESERVAS
class CrearReservaPublicaView(APIView):

    permission_classes = [AllowAny]
    throttle_classes = [PublicReservaRateThrottle]

    def post(self, request, slug):
        restaurante = get_object_or_404(Restaurante, slug=slug)

        if not restaurante.activo:
            logger.info("Reserva publica rechazada por restaurante inactivo", extra={"slug": slug})
            return Response(
                respuesta_publica_restaurante_inactivo(),
                status=status.HTTP_403_FORBIDDEN
            )

        if not restaurante.reservas_activas:
            logger.info("Reserva publica rechazada por modulo inactivo", extra={"slug": slug})
            return Response(
                {"error": "Las reservas no están disponibles para este restaurante."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ReservaPublicaSerializer(data=request.data)

        if serializer.is_valid():
            fecha = serializer.validated_data.get("fecha")
            hoy = now().date()
            hora = serializer.validated_data.get("hora")

            if not validar_horario_reserva(
                restaurante,
                fecha,
                hora
            ):
                return Response(
        {"error": "La hora seleccionada está fuera del horario de atención."},
        status=status.HTTP_400_BAD_REQUEST
    )

            if fecha <= hoy:
                return Response(
                    {"error": "Solo se pueden crear reservas desde mañana en adelante."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Futuro: validar captcha aqui antes de crear la reserva publica.
            if existe_reserva_publica_para_cliente_en_fecha(
                restaurante,
                fecha,
                serializer.validated_data.get("email"),
                serializer.validated_data.get("telefono"),
            ):
                return Response(
                    {"error": "Ya existe una reserva registrada para este cliente en esa fecha."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            reserva = serializer.save(
                restaurante=restaurante,
                estado="pendiente"
            )

            logger.info("Reserva publica creada", extra={"slug": slug, "reserva_id": reserva.id})
            try:
                crear_notificacion_reserva(reserva)
            except Exception:
                logger.error(
                    "Error creando notificacion persistente de reserva publica",
                    extra={"slug": slug, "reserva_id": reserva.id},
                    exc_info=True
                )

            try:
                notificar_nueva_reserva(reserva)
            except Exception:
                logger.error("Error en notificacion de reserva publica", extra={"slug": slug}, exc_info=True)
                raise

            return Response(
                {
                    "message": "Solicitud de reserva enviada correctamente.",
                    "reserva": ReservaDashboardSerializer(reserva).data
                },
                status=status.HTTP_201_CREATED
            )

        logger.info("Reserva publica invalida", extra={"slug": slug})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CrearSolicitudEspecialPublicaView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicSolicitudEspecialRateThrottle]

    def post(self, request, slug):
        restaurante = get_object_or_404(Restaurante, slug=slug)

        if not restaurante.activo:
            logger.info("Solicitud especial rechazada por restaurante inactivo", extra={"slug": slug})
            return Response(
                respuesta_publica_restaurante_inactivo(),
                status=status.HTTP_403_FORBIDDEN
            )

        if not restaurante.solicitudes_especiales_activas:
            logger.info("Solicitud especial rechazada por modulo inactivo", extra={"slug": slug})
            return Response(
                {"error": "Las solicitudes especiales no están disponibles para este restaurante."},
                status=status.HTTP_403_FORBIDDEN
            )

        restaurante_id = request.data.get("restaurante_id")
        if restaurante_id not in (None, "") and str(restaurante_id) != str(restaurante.id):
            logger.warning(
                "Solicitud especial rechazada por restaurante_id inconsistente",
                extra={"slug": slug, "restaurante_id": restaurante_id}
            )
            return Response(
                {"error": "El restaurante de la solicitud no coincide con la landing actual."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SolicitudEspecialPublicaSerializer(data=request.data)

        if serializer.is_valid():
            solicitud = serializer.save(restaurante=restaurante, estado="pendiente")
            logger.info(
                "Solicitud especial publica creada",
                extra={"slug": slug, "solicitud_id": solicitud.id}
            )
            try:
                crear_notificacion_solicitud_especial(solicitud)
            except Exception:
                logger.error(
                    "Error creando notificacion persistente de solicitud especial publica",
                    extra={"slug": slug, "solicitud_id": solicitud.id},
                    exc_info=True
                )

            try:
                notificar_nueva_solicitud_especial(solicitud)
            except Exception:
                logger.error(
                    "Error en notificacion de solicitud especial publica",
                    extra={"slug": slug},
                    exc_info=True
                )
                raise

            return Response(
                {
                    "message": "Solicitud enviada. El restaurante se pondrá en contacto contigo.",
                    "solicitud": SolicitudEspecialPublicaSerializer(solicitud).data,
                },
                status=status.HTTP_201_CREATED
            )

        logger.info("Solicitud especial publica invalida", extra={"slug": slug})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CrearPedidoWhatsAppPublicoView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, slug):
        restaurante = get_object_or_404(Restaurante, slug=slug)

        if not restaurante.activo:
            return Response(
                respuesta_publica_restaurante_inactivo(),
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = PedidoWhatsAppCreateSerializer(
            data=request.data,
            context={"restaurante": restaurante, "request": request}
        )

        if serializer.is_valid():
            pedido = serializer.save()
            logger.info(
                "Pedido WhatsApp publico creado",
                extra={"slug": slug, "pedido_id": pedido.id}
            )
            return Response(serializer.to_representation(pedido), status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SeguimientoPedidoWhatsAppPublicoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, tracking_token):
        pedido = get_object_or_404(
            PedidoWhatsApp.objects.select_related("restaurante"),
            tracking_token=tracking_token
        )
        return Response(PedidoWhatsAppSeguimientoPublicoSerializer(pedido).data)


def get_perfil_solicitudes_especiales(request):
    perfil = get_object_or_404(
        UsuarioRestaurante,
        user=request.user,
        activo=True
    )

    if not perfil.restaurante.solicitudes_especiales_activas:
        raise PermissionDenied("El módulo de solicitudes especiales no está activo para este restaurante.")

    return perfil


class SolicitudesEspecialesDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_solicitudes_especiales(request)
        solicitudes = SolicitudEspecial.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("-fecha_creacion")

        return paginated_response(
            request,
            solicitudes,
            lambda page: SolicitudEspecialDashboardSerializer(page, many=True).data,
            DefaultListPagination
        )

    def post(self, request):
        perfil = get_perfil_solicitudes_especiales(request)
        serializer = SolicitudEspecialDashboardSerializer(data=request.data)

        if serializer.is_valid():
            solicitud = serializer.save(
                restaurante=perfil.restaurante,
                estado=request.data.get("estado") or "pendiente"
            )
            return Response(
                {
                    "message": "Solicitud especial creada correctamente.",
                    "solicitud": SolicitudEspecialDashboardSerializer(solicitud).data,
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SolicitudEspecialDetalleDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get_solicitud(self, request, solicitud_id):
        perfil = get_perfil_solicitudes_especiales(request)
        return get_object_or_404(
            SolicitudEspecial,
            id=solicitud_id,
            restaurante=perfil.restaurante
        )

    def get(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        return Response(SolicitudEspecialDashboardSerializer(solicitud).data)

    def patch(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        serializer = SolicitudEspecialDashboardSerializer(
            solicitud,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            solicitud = serializer.save()
            return Response({
                "message": "Solicitud especial actualizada correctamente.",
                "solicitud": SolicitudEspecialDashboardSerializer(solicitud).data,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, solicitud_id):
        solicitud = self.get_solicitud(request, solicitud_id)
        solicitud.estado = "rechazada"
        solicitud.save(update_fields=["estado", "fecha_actualizacion"])
        return Response({
            "message": "Solicitud especial rechazada correctamente.",
            "solicitud": SolicitudEspecialDashboardSerializer(solicitud).data,
        })


class NotificacionesDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        notificaciones = Notificacion.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("-fecha_creacion")

        leida = request.query_params.get("leida")
        if leida is not None:
            notificaciones = notificaciones.filter(
                leida=str(leida).lower() in ["1", "true", "si", "sÃ­"]
            )

        data = NotificacionSerializer(notificaciones, many=True).data
        pendientes = Notificacion.objects.filter(
            restaurante=perfil.restaurante,
            leida=False
        ).count()

        return Response({
            "pendientes": pendientes,
            "results": data,
        })


class NotificacionesContadorView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        pendientes = Notificacion.objects.filter(
            restaurante=perfil.restaurante,
            leida=False
        ).count()

        return Response({"pendientes": pendientes})


class NotificacionDetalleView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get_notificacion(self, request, notificacion_id):
        perfil = get_perfil_activo(request)
        return get_object_or_404(
            Notificacion,
            id=notificacion_id,
            restaurante=perfil.restaurante
        )

    def get(self, request, notificacion_id):
        notificacion = self.get_notificacion(request, notificacion_id)
        return Response(NotificacionDetalleSerializer(notificacion).data)


class NotificacionMarcarLeidaView(NotificacionDetalleView):
    def patch(self, request, notificacion_id):
        notificacion = self.get_notificacion(request, notificacion_id)

        if not notificacion.leida:
            notificacion.leida = True
            notificacion.fecha_lectura = now()
            notificacion.save(update_fields=["leida", "fecha_lectura"])

        pendientes = Notificacion.objects.filter(
            restaurante=notificacion.restaurante,
            leida=False
        ).count()

        return Response({
            "message": "Notificacion marcada como leida.",
            "pendientes": pendientes,
            "notificacion": NotificacionDetalleSerializer(notificacion).data,
        })


def metricas_pedidos_whatsapp(restaurante):
    return construir_payload_pedidos_compat(restaurante)["whatsapp"]


def metricas_pedidos_especiales(restaurante):
    return construir_payload_pedidos_compat(restaurante)["especiales"]


def plan_slug_restaurante(restaurante):
    plan = getattr(restaurante, "plan", None)
    return plan.slug if plan else "basico"


def validar_plan_reportes(restaurante, nombre_reporte):
    if plan_slug_restaurante(restaurante) in ["pro", "full_pro"]:
        return None

    return Response(
        {"error": f"El {nombre_reporte} estÃ¡ disponible solo para planes Pro y Full Pro."},
        status=status.HTTP_403_FORBIDDEN
    )


def calcular_reporte_mensual(restaurante):
    return construir_reporte_mensual(restaurante)


def calcular_reporte_anual(restaurante):
    return construir_reporte_anual(restaurante)


class PedidosWhatsAppDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        hoy = localtime(now()).date()
        pedidos = PedidoWhatsApp.objects.filter(
            restaurante=perfil.restaurante,
            fecha_creacion__date=hoy
        ).order_by("-fecha_creacion", "-id")

        return paginated_response(
            request,
            pedidos,
            lambda page: PedidoWhatsAppDashboardSerializer(page, many=True).data
        )


class PedidoWhatsAppDetalleDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get_pedido(self, request, pedido_id):
        perfil = get_perfil_activo(request)
        return get_object_or_404(PedidoWhatsApp, id=pedido_id, restaurante=perfil.restaurante)

    def get(self, request, pedido_id):
        pedido = self.get_pedido(request, pedido_id)
        return Response(PedidoWhatsAppDashboardSerializer(pedido).data)

    def patch(self, request, pedido_id):
        pedido = self.get_pedido(request, pedido_id)
        serializer = PedidoWhatsAppDashboardSerializer(
            pedido,
            data=request.data,
            partial=True,
            context={"restaurante": pedido.restaurante, "request": request}
        )

        if serializer.is_valid():
            pedido = serializer.save()
            return Response({
                "message": "Pedido WhatsApp actualizado correctamente.",
                "pedido": PedidoWhatsAppDashboardSerializer(pedido).data,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidoWhatsAppEstadoDashboardView(PedidoWhatsAppDetalleDashboardView):
    def patch(self, request, pedido_id):
        pedido = self.get_pedido(request, pedido_id)
        serializer = PedidoWhatsAppEstadoUpdateSerializer(
            pedido,
            data=request.data,
            context={"usuario": request.user},
        )

        if serializer.is_valid():
            pedido = serializer.save()
            return Response({
                "message": "Estado del pedido actualizado correctamente.",
                "pedido": PedidoWhatsAppDashboardSerializer(pedido).data,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidosEspecialesDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        pedidos = PedidoEspecial.objects.filter(
            restaurante=perfil.restaurante
        ).exclude(
            estado=PedidoEspecial.ESTADO_ENTREGADO
        ).select_related("solicitud_especial").order_by("-fecha_creacion", "-id")

        return paginated_response(
            request,
            pedidos,
            lambda page: PedidoEspecialSerializer(page, many=True).data
        )

    def post(self, request):
        perfil = get_perfil_activo(request)
        serializer = PedidoEspecialSerializer(
            data=request.data,
            context={"restaurante": perfil.restaurante}
        )

        if serializer.is_valid():
            pedido = serializer.save()
            return Response({
                "message": "Pedido especial creado correctamente.",
                "pedido": PedidoEspecialSerializer(pedido).data,
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidoEspecialDetalleDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get_pedido(self, request, pedido_id):
        perfil = get_perfil_activo(request)
        return get_object_or_404(PedidoEspecial, id=pedido_id, restaurante=perfil.restaurante)

    def get(self, request, pedido_id):
        pedido = self.get_pedido(request, pedido_id)
        return Response(PedidoEspecialSerializer(pedido).data)

    def patch(self, request, pedido_id):
        pedido = self.get_pedido(request, pedido_id)
        serializer = PedidoEspecialSerializer(
            pedido,
            data=request.data,
            partial=True,
            context={"restaurante": pedido.restaurante}
        )

        if serializer.is_valid():
            pedido = serializer.save()
            return Response({
                "message": "Pedido especial actualizado correctamente.",
                "pedido": PedidoEspecialSerializer(pedido).data,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PedidosMetricasDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        return Response(construir_payload_pedidos_compat(perfil.restaurante))


class MetricasResumenView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        return Response(construir_resumen_metricas(perfil.restaurante))


class ReporteMensualMetricasView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        bloqueo = validar_plan_reportes(restaurante, "reporte mensual")
        if bloqueo:
            return bloqueo

        return Response(calcular_reporte_mensual(restaurante))


class ReporteAnualMetricasView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        bloqueo = validar_plan_reportes(restaurante, "reporte anual")
        if bloqueo:
            return bloqueo

        return Response(calcular_reporte_anual(restaurante))


class ReportesMetricasView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        reportes = ReporteMetrica.objects.filter(
            restaurante=perfil.restaurante,
            activo=True
        )

        tipo = request.query_params.get("tipo")
        anio = request.query_params.get("anio")
        mes = request.query_params.get("mes")

        if tipo in dict(ReporteMetrica.TIPOS):
            reportes = reportes.filter(tipo=tipo)
        if anio:
            reportes = reportes.filter(periodo_anio=str(anio))
        if mes:
            reportes = reportes.filter(periodo_mes=str(mes))

        return Response(ReporteMetricaSerializer(reportes, many=True).data)


class ReporteMetricaDetalleView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request, reporte_id):
        perfil = get_perfil_activo(request)
        reporte = get_object_or_404(
            ReporteMetrica,
            id=reporte_id,
            restaurante=perfil.restaurante,
            activo=True
        )

        return Response(ReporteMetricaSerializer(reporte).data)


class ReporteMetricaGuardarView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def post(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        bloqueo = validar_plan_reportes(restaurante, "guardado de reportes")
        if bloqueo:
            return bloqueo

        tipo = request.data.get("tipo")
        periodo_mes = request.data.get("periodo_mes")
        periodo_anio = request.data.get("periodo_anio")
        titulo = (request.data.get("titulo") or "").strip()
        resumen = request.data.get("resumen") or {}
        datos = request.data.get("datos") or {}

        if tipo not in dict(ReporteMetrica.TIPOS):
            return Response(
                {"tipo": "Tipo de reporte invalido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if tipo == ReporteMetrica.TIPO_MENSUAL and not periodo_mes:
            return Response(
                {"periodo_mes": "El periodo mensual es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if tipo == ReporteMetrica.TIPO_ANUAL and not periodo_anio:
            return Response(
                {"periodo_anio": "El periodo anual es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        filtros = {
            "restaurante": restaurante,
            "tipo": tipo,
            "activo": True,
        }
        if tipo == ReporteMetrica.TIPO_MENSUAL:
            filtros["periodo_mes"] = periodo_mes
            periodo_anio = str(periodo_mes).split("-")[0] if periodo_mes else periodo_anio
        else:
            filtros["periodo_anio"] = str(periodo_anio)
            periodo_mes = None

        reporte, creado = ReporteMetrica.objects.update_or_create(
            **filtros,
            defaults={
                "periodo_mes": periodo_mes,
                "periodo_anio": str(periodo_anio) if periodo_anio else None,
                "titulo": titulo or ("Reporte mensual Menly" if tipo == ReporteMetrica.TIPO_MENSUAL else "Reporte anual Menly"),
                "resumen": resumen,
                "datos": datos,
                "generado_por": request.user,
            }
        )

        return Response(
            {
                "message": "Reporte guardado correctamente." if creado else "Reporte actualizado correctamente.",
                "reporte": ReporteMetricaSerializer(reporte).data,
                "created": creado,
            },
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        )


class DashboardUltimosPedidosView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        perfil = get_perfil_activo(request)
        hoy = localtime(now()).date()
        pedidos = PedidoWhatsApp.objects.filter(
            restaurante=perfil.restaurante,
            fecha_creacion__date=hoy,
        ).order_by("-fecha_creacion", "-id")[:10]

        return Response([
            {
                "id": pedido.id,
                "numero_pedido": pedido.numero_pedido,
                "nombre_cliente": pedido.nombre_cliente,
                "tipo_entrega": pedido.tipo_entrega,
                "fecha_creacion": pedido.fecha_creacion,
                "hora_formateada": localtime(pedido.fecha_creacion).strftime("%H:%M"),
            }
            for pedido in pedidos
        ])


class ReservasDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def get(self, request):
        usuario_restaurante = get_object_or_404(
            UsuarioRestaurante,
            user=request.user,
            activo=True
        )

        reservas = Reserva.objects.filter(
            restaurante=usuario_restaurante.restaurante
        ).select_related(
            "creada_por__user",
            "gestionada_por__user",
        ).order_by("-fecha_creacion")

        return paginated_response(
            request,
            reservas,
            lambda page: ReservaDashboardSerializer(page, many=True).data,
            ReservasPagination
        )


class CrearReservaManualView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def post(self, request):
        usuario_restaurante = get_object_or_404(
            UsuarioRestaurante,
            user=request.user,
            activo=True
        )

        restaurante = usuario_restaurante.restaurante
        serializer = ReservaManualSerializer(
            data=request.data,
            context={"restaurante": restaurante}
        )

        if serializer.is_valid():
            fecha = serializer.validated_data.get("fecha")
            hoy = now().date()
            hora = serializer.validated_data.get("hora")

            if not validar_horario_reserva(
                restaurante,
                fecha,
                hora,
                permitir_sin_horario=True
            ):
                return Response(
                    {"error": "La hora seleccionada está fuera del horario de atención."},
                    status=status.HTTP_400_BAD_REQUEST
                    
                )
            if fecha < hoy:
                return Response(
                    {"error": "Solo se pueden crear reservas desde mañana en adelante."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if existe_reserva_duplicada(
                restaurante,
                fecha,
                hora,
                serializer.validated_data.get("email"),
                serializer.validated_data.get("telefono"),
            ):
                return Response(
                    {"error": "Ya existe una reserva registrada para esa fecha y hora."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            mesa = serializer.validated_data.get("mesa_asignada")
            if mesa and existe_mesa_ocupada(restaurante, mesa, fecha, hora):
                return Response(
                    {"error": "La mesa ya tiene una reserva para esa fecha y hora."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            reserva = serializer.save(
                restaurante=restaurante,
                creada_por=usuario_restaurante,
                estado="confirmada"
            )

            return Response(
                {
                    "message": "Reserva creada manualmente.",
                    "reserva": ReservaDashboardSerializer(reserva).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActualizarReservaView(APIView):
    permission_classes = [IsAuthenticated, CanManageReservas]

    def patch(self, request, reserva_id):
        usuario_restaurante = get_object_or_404(
            UsuarioRestaurante,
            user=request.user,
            activo=True
        )

        reserva = get_object_or_404(
            Reserva,
            id=reserva_id,
            restaurante=usuario_restaurante.restaurante
        )

        estado = request.data.get("estado")
        mesa_asignada = request.data.get("mesa_asignada")
        observacion_admin = request.data.get("observacion_admin")

        fecha = request.data.get("fecha")
        hora = request.data.get("hora")
        cantidad_personas = request.data.get("cantidad_personas")
        mensaje = request.data.get("mensaje")
        cambia_datos_reserva = any(
            campo in request.data
            for campo in ["fecha", "hora", "cantidad_personas", "mensaje"]
        )
        fecha_final = reserva.fecha
        hora_final = reserva.hora

        if cambia_datos_reserva:
            try:
                fecha_final = (
                    datetime.strptime(fecha, "%Y-%m-%d").date()
                    if fecha is not None
                    else reserva.fecha
                )
                hora_final = (
                    datetime.strptime(hora, "%H:%M").time()
                    if hora is not None
                    else reserva.hora
                )
            except ValueError:
                return Response(
                    {"error": "Formato de fecha u hora invalido."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 3. Validamos que la fecha no sea hoy ni anterior
            hoy = now().date()

            if fecha_final < hoy:
                return Response(
                    {"error": "No se puede modificar una reserva para una fecha pasada."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 4. Validamos horario de atención
            if not validar_horario_reserva(
                reserva.restaurante,
                fecha_final,
                hora_final,
                permitir_sin_horario=True
            ):
                return Response(
                {"error": "La hora seleccionada está fuera del horario de atención."},
                status=status.HTTP_400_BAD_REQUEST
            )

            if existe_reserva_duplicada(
                reserva.restaurante,
                fecha_final,
                hora_final,
                reserva.email,
                reserva.telefono,
                reserva_id=reserva.id,
            ):
                return Response(
                    {"error": "Ya existe una reserva registrada para esa fecha y hora."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if estado and estado not in dict(Reserva.ESTADOS):
            return Response(
                {"error": "Estado de reserva invalido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if mesa_asignada not in (None, ""):
            mesa = buscar_mesa_asignada(
                usuario_restaurante.restaurante,
                mesa_asignada
            )

            if not mesa:
                return Response(
                    {"error": "La mesa asignada no existe o no esta activa en este restaurante."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if existe_mesa_ocupada(
                usuario_restaurante.restaurante,
                mesa,
                fecha_final,
                hora_final,
                reserva_id=reserva.id,
            ):
                return Response(
                    {"error": "La mesa ya tiene una reserva para esa fecha y hora."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 5. Guardamos cambios permitidos
        if fecha is not None:
            reserva.fecha = fecha_final

        if hora is not None:
            reserva.hora = hora_final

        if cantidad_personas is not None:
            reserva.cantidad_personas = cantidad_personas

        if mensaje is not None:
            reserva.mensaje = mensaje

        if estado:
            reserva.estado = estado

        if mesa_asignada is not None:
            reserva.mesa_asignada = mesa_asignada

        if observacion_admin is not None:
            reserva.observacion_admin = observacion_admin

        reserva.gestionada_por = usuario_restaurante
        reserva.save()

        return Response({
            "message": "Reserva actualizada correctamente.",
            "reserva": ReservaDashboardSerializer(reserva).data
        })

#HISTORIAL
class HistorialBitacoraView(APIView):
    permission_classes = [IsAuthenticated, CanViewBitacora]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        historial = BitacoraProducto.objects.filter(
            restaurante=restaurante
        ).select_related("usuario").order_by("-fecha")

        def serialize_historial(items):
            return [
                {
                    "id": b.id,
                    "accion": b.accion,
                    "producto": b.producto_nombre,
                    "descripcion": b.descripcion,
                    "fecha": b.fecha,
                    "usuario": b.usuario.username if b.usuario else "Sistema"
                }
                for b in items
            ]

        return paginated_response(request, historial, serialize_historial, HistorialPagination)


class HistorialPedidosView(APIView):
    permission_classes = [IsAuthenticated, CanViewBitacora]

    def get(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante
        hoy = localtime(now()).date()
        busqueda = (request.query_params.get("search") or "").strip()
        estado = (request.query_params.get("estado") or "").strip()
        fecha_desde = (request.query_params.get("fecha_desde") or "").strip()
        fecha_hasta = (request.query_params.get("fecha_hasta") or "").strip()

        pedidos = PedidoWhatsApp.objects.filter(
            restaurante=restaurante,
            fecha_creacion__date__lt=hoy,
        ).order_by("-fecha_creacion", "-id")

        if busqueda:
            filtros_busqueda = (
                Q(nombre_cliente__icontains=busqueda)
                | Q(telefono_cliente__icontains=busqueda)
            )
            if busqueda.isdigit():
                filtros_busqueda |= Q(numero_pedido=int(busqueda))
            pedidos = pedidos.filter(filtros_busqueda)

        if estado and estado != "todos":
            pedidos = pedidos.filter(estado=estado)

        if fecha_desde:
            try:
                pedidos = pedidos.filter(
                    fecha_creacion__date__gte=datetime.strptime(fecha_desde, "%Y-%m-%d").date()
                )
            except ValueError:
                pass

        if fecha_hasta:
            try:
                pedidos = pedidos.filter(
                    fecha_creacion__date__lte=datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
                )
            except ValueError:
                pass

        def serialize_pedidos(items):
            return PedidoWhatsAppDashboardSerializer(items, many=True).data

        return paginated_response(request, pedidos, serialize_pedidos, HistorialPagination)


#PRODUCTOS
class ProductoListView(APIView):
    permission_classes = [IsAuthenticated, CanManageProductos]

    def get(self, request):
        perfil = get_perfil_activo(request)

        productos = Producto.objects.select_related("categoria").filter(
            restaurante=perfil.restaurante
        ).order_by("categoria__orden", "orden", "id")

        def serialize_productos(items):
            return [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "precio": str(p.precio),
                    "imagen": p.imagen.url if p.imagen else None,
                    "disponible": p.disponible,
                    "categoria": {
                        "id": p.categoria_id,
                        "nombre": p.categoria.nombre,
                        "activa": p.categoria.activa,
                    },
                    "fecha_creacion": p.fecha_creacion,
                    "destacado": p.destacado,
                    "orden": p.orden,
                }
                for p in items
            ]

        return paginated_response(request, productos, serialize_productos, ProductosPagination)


class ProductoUpdateView(UpdateAPIView):
    serializer_class = ProductoCreateSerializer
    permission_classes = [IsAuthenticated, CanManageProductos]
    lookup_field = "id"

    def get_queryset(self):
        perfil = UsuarioRestaurante.objects.filter(
            user=self.request.user,
            activo=True
        ).select_related("restaurante").first()

        if not perfil:
            return Producto.objects.none()

        return Producto.objects.filter(restaurante=perfil.restaurante)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        producto = self.get_object()

        nombre_anterior = producto.nombre
        precio_anterior = producto.precio
        descripcion_anterior = producto.descripcion
        condiciones_anterior = producto.condiciones
        disponible_anterior = producto.disponible
        destacado_anterior = producto.destacado
        orden_anterior = producto.orden
        categoria_anterior = producto.categoria.nombre
        imagen_anterior = producto.imagen.url if producto.imagen else None

        try:
            nuevo_orden = int(request.data.get("orden", producto.orden))
            nueva_categoria_id = int(request.data.get("categoria", producto.categoria_id))
        except (TypeError, ValueError):
            return Response(
                {"error": "Categoria u orden invalido."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        nueva_categoria = get_object_or_404(
            Categoria,
            id=nueva_categoria_id,
            restaurante=producto.restaurante
        )

        # actualizar datos normales
        producto.nombre = request.data.get("nombre", producto.nombre)
        producto.precio = request.data.get("precio", producto.precio)
        producto.descripcion = request.data.get("descripcion", producto.descripcion)
        producto.condiciones = request.data.get("condiciones", producto.condiciones)
        campos_producto_actualizados = [
            "nombre",
            "precio",
            "descripcion",
            "condiciones",
        ]

        if Producto.objects.filter(
            restaurante=producto.restaurante,
            nombre__iexact=producto.nombre
        ).exclude(id=producto.id).exists():
            return Response(
                {"error": "Ya existe un producto con ese nombre en este restaurante."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if "disponible" in request.data:
            producto.disponible = valor_booleano(request.data.get("disponible"))
            campos_producto_actualizados.append("disponible")

        if "destacado" in request.data:
            producto.destacado = valor_booleano(request.data.get("destacado"))
            campos_producto_actualizados.append("destacado")

        if "imagen" in request.FILES:
            producto.imagen = request.FILES["imagen"]
            campos_producto_actualizados.append("imagen")

        producto.save(update_fields=campos_producto_actualizados)

        # productos de la categoría
        producto = reordenar_producto(
            producto=producto,
            categoria=nueva_categoria,
            nuevo_orden=nuevo_orden,
        )

        # insertar en nueva posición


        # 🔥 fase 1: evitar choque (orden temporal)


        # 🔥 fase 2: orden real


        cambios = []

        if nombre_anterior != producto.nombre:
            cambios.append(f"Nombre: {nombre_anterior} → {producto.nombre}")

        if str(precio_anterior) != str(producto.precio):
            cambios.append(f"Precio: {precio_anterior} → {producto.precio}")

        if descripcion_anterior != producto.descripcion:
            cambios.append("Descripción actualizada")

        if condiciones_anterior != producto.condiciones:
            cambios.append("Condiciones actualizadas")

        if disponible_anterior != producto.disponible:
            estado_anterior = "Disponible" if disponible_anterior else "No disponible"
            estado_nuevo = "Disponible" if producto.disponible else "No disponible"
            cambios.append(f"Disponibilidad: {estado_anterior} → {estado_nuevo}")

        if destacado_anterior != producto.destacado:
            destacado_ant = "Destacado" if destacado_anterior else "No destacado"
            destacado_nuevo = "Destacado" if producto.destacado else "No destacado"
            cambios.append(f"Destacado: {destacado_ant} → {destacado_nuevo}")

        if orden_anterior != producto.orden:
            cambios.append(f"Orden: {orden_anterior} → {producto.orden}")

        if categoria_anterior != producto.categoria.nombre:
            cambios.append(f"Categoría: {categoria_anterior} → {producto.categoria.nombre}")

        imagen_nueva = producto.imagen.url if producto.imagen else None
        if imagen_anterior != imagen_nueva:
            cambios.append("Imagen actualizada")

        if cambios:
            BitacoraProducto.objects.create(
                restaurante=producto.restaurante,
                producto_id=producto.id,
                producto_nombre=producto.nombre,
                usuario=request.user,
                accion="EDITADO",
                descripcion="; ".join(cambios),
                valor_anterior="Edición de producto",
                valor_nuevo="; ".join(cambios)
            )
        invalidate_menu_cache(producto.restaurante)
        serializer = self.get_serializer(producto)
        return Response(serializer.data)

class ProductoCreateView(CreateAPIView):
    serializer_class = ProductoCreateSerializer
    permission_classes = [IsAuthenticated, CanManageProductos]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        perfil = get_perfil_activo(request)
        nombre = request.data.get("nombre")

        if nombre and Producto.objects.filter(
            restaurante=perfil.restaurante,
            nombre__iexact=nombre
        ).exists():
            return Response(
                {"error": "Ya existe un producto con ese nombre en este restaurante."},
                status=status.HTTP_400_BAD_REQUEST
            )

        restaurante = perfil.restaurante

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            nuevo_orden = int(serializer.validated_data.get("orden") or 1)
        except (TypeError, ValueError):
            return Response(
                {"error": "Orden invalido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        categoria = serializer.validated_data["categoria"]
        producto = Producto(
            restaurante=restaurante,
            categoria=categoria,
            nombre=serializer.validated_data["nombre"],
            precio=serializer.validated_data["precio"],
            descripcion=serializer.validated_data.get("descripcion", ""),
            condiciones=serializer.validated_data.get("condiciones", ""),
            imagen=serializer.validated_data.get("imagen"),
            disponible=serializer.validated_data.get("disponible", True),
            destacado=serializer.validated_data.get("destacado", False),
        )

        producto = reordenar_producto(
            producto=producto,
            categoria=categoria,
            nuevo_orden=nuevo_orden,
        )

        BitacoraProducto.objects.create(
            restaurante=restaurante,
            producto_id=producto.id,
            producto_nombre=producto.nombre,
            usuario=self.request.user,
            accion="CREADO",
            descripcion=f"Se creó el producto {producto.nombre}",
            valor_nuevo=f"Precio: {producto.precio}, Orden: {producto.orden}"
        )
        invalidate_menu_cache(restaurante)

        return Response(
            self.get_serializer(producto).data,
            status=status.HTTP_201_CREATED
        )

class EliminarProductoView(APIView):
    permission_classes = [IsAuthenticated, CanManageProductos]

    def delete(self, request, id):
        perfil = get_perfil_activo(request)
        producto = get_object_or_404(
            Producto,
            id=id,
            restaurante=perfil.restaurante
        )

        BitacoraProducto.objects.create(
            restaurante=producto.restaurante,
            producto_id=producto.id,
            producto_nombre=producto.nombre,
            usuario=request.user,
            accion="ELIMINADO",
            descripcion=f"Se eliminó el producto {producto.nombre}",
            valor_anterior=f"Precio: {producto.precio}, Categoría: {producto.categoria.nombre}",
            valor_nuevo="Producto eliminado"
        )
        restaurante = producto.restaurante
        producto.delete()
        invalidate_menu_cache(restaurante)

        return Response(
            {"message": "Producto eliminado correctamente"},
            status=status.HTTP_200_OK
        )

class ActualizarDisponibilidadProductoView(APIView):
    permission_classes = [IsAuthenticated, CanManageProductos]

    def patch(self, request, id):
        perfil = get_perfil_activo(request)
        producto = get_object_or_404(
            Producto,
            id=id,
            restaurante=perfil.restaurante
        )

        disponible = request.data.get("disponible")

        if disponible is None:
            return Response(
                {"error": "El campo 'disponible' es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto.disponible = disponible
        producto.save()
        invalidate_menu_cache(producto.restaurante)

        return Response(
            {
                "message": "Disponibilidad actualizada correctamente",
                "id": producto.id,
                "disponible": producto.disponible,
            },
            status=status.HTTP_200_OK
        )


#LOGIN Y LOGOUT DE USUARIOS
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response(
                    {"error": "Refresh token requerido"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Sesión cerrada correctamente"},
                status=status.HTTP_205_RESET_CONTENT
            )

        except TokenError:
            return Response(
                {"error": "Token inválido o expirado"},
                status=status.HTTP_400_BAD_REQUEST
            )

class CustomLoginView(TokenObtainPairView):
        serializer_class = CustomTokenObtainPairSerializer
        throttle_classes = [LoginRateThrottle]


class PasswordResetRequestView(APIView):
        permission_classes = [AllowAny]
        throttle_classes = [PasswordResetRateThrottle]

        GENERIC_MESSAGE = (
            "Si el correo está registrado, el administrador será notificado."
        )

        def post(self, request):
            email = (request.data.get("email") or "").strip().lower()

            if not email:
                return Response(
                    {"email": "El correo electrónico es obligatorio."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validate_email(email)
            except ValidationError:
                return Response(
                    {"email": "Ingresa un correo electrónico válido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.filter(email__iexact=email).first()
            perfil = None

            if user:
                try:
                    perfil = user.perfil_restaurante
                except UsuarioRestaurante.DoesNotExist:
                    perfil = None

            restaurante = perfil.restaurante if perfil else None
            admin_email = (
                getattr(settings, "ADMIN_NOTIFICATION_EMAIL", None)
                or settings.DEFAULT_FROM_EMAIL
            )

            if not admin_email:
                logger.warning(
                    "Solicitud de recuperación para %s sin email admin configurado.",
                    email,
                )
                return Response({"message": self.GENERIC_MESSAGE})

            usuario_encontrado = "Sí" if user else "No"
            detalles_usuario = (
                f"- username: {user.username}\n"
                f"- email: {user.email}\n"
                f"- restaurante asociado: {restaurante.nombre_empresa if restaurante else 'Sin restaurante'}\n"
                f"- rol: {perfil.rol if perfil else 'Sin rol'}\n"
                if user
                else "- Sin datos de usuario registrado.\n"
            )

            cuerpo = (
                "Se recibió una solicitud de recuperación de contraseña.\n\n"
                f"Correo solicitado:\n{email}\n\n"
                f"Usuario encontrado:\n{usuario_encontrado}\n\n"
                "Detalles:\n"
                f"{detalles_usuario}\n"
                "Acción sugerida:\n"
                "Contactar al usuario y restablecer la contraseña desde el panel admin de Django."
            )

            try:
                send_mail(
                    subject="Solicitud de recuperación de contraseña - Menly",
                    message=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "Error enviando notificación de recuperación para %s.",
                    email,
                )

            return Response({"message": self.GENERIC_MESSAGE})



class MiRestauranteView(APIView):

        permission_classes = [IsAuthenticated]

        def get(self, request):
            perfil = get_perfil_activo(request)

            restaurante = perfil.restaurante

            resumen = restaurante.productos.aggregate(
                        disponibles=Count("id", filter=Q(disponible=True)),
                        no_disponibles=Count("id", filter=Q(disponible=False)),
                        total=Count("id")
                    )
            categorias = Categoria.objects.filter(
                restaurante=restaurante,
                activa=True
            ).order_by("orden")
            categorias_todas = Categoria.objects.filter(
                restaurante=restaurante
            ).order_by("orden", "id")

            data_categorias = []
            todos_productos = Producto.objects.select_related("categoria").filter(
                restaurante=restaurante
            )
            data_productos = [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "precio": str(p.precio),
                    "imagen": p.imagen.url if p.imagen else None,
                    "disponible": p.disponible,
                    "categoria": {
                        "id": p.categoria_id,
                        "nombre": p.categoria.nombre,
                        "activa": p.categoria.activa,
                    },
                    "fecha_creacion": p.fecha_creacion,
                    "destacado": p.destacado,
                    "orden": p.orden
                }
                for p in todos_productos
            ]
            ultimas_actualizaciones = BitacoraProducto.objects.filter(
                restaurante=restaurante
            ).order_by("-fecha")[:10]

            for categoria in categorias:
                productos = Producto.objects.filter(
                    categoria=categoria,
                    restaurante=restaurante,
                    disponible=True
                ).order_by("orden")

                data_categorias.append({
                    "id": categoria.id,
                    "nombre": categoria.nombre,
                    "productos": [
                        {
                            "id": p.id,
                            "nombre": p.nombre,
                            "descripcion": p.descripcion,
                            "precio": str(p.precio),
                            "imagen": p.imagen.url if p.imagen else None,
                            "disponible": p.disponible,
                        }
                        for p in productos
                    ]
                })
            hoy = now().date()

            reservas_hoy = Reserva.objects.filter(
                restaurante=restaurante,
                fecha=hoy
            ).count()
            reservas_pendientes = Reserva.objects.filter(
                restaurante=restaurante,
                estado="pendiente"
            ).count()
            notificaciones_pendientes = Notificacion.objects.filter(
                restaurante=restaurante,
                leida=False
            ).count()

            return Response({
                "usuario": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "rol": perfil.rol,
                },

                "restaurante": {
                    "id": restaurante.id,
                    "nombre_empresa": restaurante.nombre_empresa,
                    "logo": request.build_absolute_uri(restaurante.logo.url) if restaurante.logo else None,
                    "direccion": restaurante.direccion,
                    "telefono": restaurante.telefono,
                    "slug": restaurante.slug,
                    "activo": restaurante.activo,
                    "imgen_principal": request.build_absolute_uri(restaurante.imgen_principal.url) if restaurante.imgen_principal else None,
                    "plan": serializar_plan_restaurante(restaurante),
                    **serializar_flags_restaurante(restaurante),
                },
                "cuenta_inactiva": not restaurante.activo,
                "mensaje_cuenta": (
                    "Cuenta inactiva. Contacta al soporte de Menly para reactivar tu cuenta."
                    if not restaurante.activo
                    else ""
                ),
                "resumen": {
                    "productos_disponibles": resumen["disponibles"],
                    "productos_no_disponibles": resumen["no_disponibles"],
                    "total_productos": resumen["total"],
                    "reservas_hoy": reservas_hoy,
                    "reservas_pendientes": reservas_pendientes,
                    "notificaciones_pendientes": notificaciones_pendientes,

                },
                "suscripcion": calcular_estado_suscripcion(restaurante),
                "categorias": data_categorias,
                "categorias_todas": [
                    {
                        "id": c.id,
                        "nombre": c.nombre,
                        "orden": c.orden,
                        "activa": c.activa,
                    }
                    for c in categorias_todas
                ],
                "productos":data_productos,
                "ultimas_actualizaciones": [
                    {
                        "id": b.id,
                        "accion": b.accion,
                        "producto": b.producto_nombre,
                        "descripcion": b.descripcion,
                        "fecha": b.fecha,
                    }
                    for b in ultimas_actualizaciones
                ]
            })


#PUBLICOS REQUESTS
@cache_control(public=True, max_age=300, stale_while_revalidate=60)
def menu_api(request, slug):
    restaurante = get_object_or_404(Restaurante, slug=slug)

    if not restaurante.activo:
        return JsonResponse(
            respuesta_publica_restaurante_inactivo(),
            status=status.HTTP_403_FORBIDDEN
        )

    cached_data = get_cached_menu(slug)
    if cached_data is not None:
        logger.info("Menu publico servido desde cache", extra={"slug": slug})
        return JsonResponse(cached_data, safe=False)

    productos_disponibles = Producto.objects.filter(
        disponible=True
    ).order_by("orden", "id")

    categorias = Categoria.objects.filter(
        restaurante=restaurante,
        activa=True
    ).select_related("icono").prefetch_related(
        Prefetch("productos", queryset=productos_disponibles)
    )

    categorias_data = []

    for categoria in categorias:
        categorias_data.append({
            "id": categoria.id,
            "nombre": categoria.nombre,
            "icono": categoria.icono.clase_css if categoria.icono else None,
            "productos": [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "precio": str(p.precio),
                    "condiciones": p.condiciones,
                    "imagen": p.imagen.url if p.imagen else None,
                    "destacado": p.destacado,
                }
                for p in categoria.productos.all()
            ]
        })

    data = {
        "restaurante": {
            "id": restaurante.id,
            "slug": restaurante.slug,
            **serializar_flags_restaurante(restaurante),
        },
        "categorias": categorias_data,
    }

    set_cached_menu(slug, data)
    logger.info("Menu publico cacheado", extra={"slug": slug})

    return JsonResponse(data)

class RestaurantePublicoDetalleView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        restaurante = get_object_or_404(
            Restaurante.objects.prefetch_related("horarios", "metodos_pago", "imagenes"),
            slug=slug,
        )

        if not restaurante.activo:
            return Response(
                respuesta_publica_restaurante_inactivo(),
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = RestaurantePublicoDetalleSerializer(
            restaurante,
            context={"request": request}
        )
        response = Response(serializer.data)
        response["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
        return response


class RespaldosRestauranteView(APIView):
    permission_classes = [IsAuthenticated, CanManageRespaldos]

    def get(self, request):
        perfil = get_perfil_activo(request)
        respaldos = RespaldoRestaurante.objects.filter(
            restaurante=perfil.restaurante
        ).order_by("-fecha_respaldo", "-id")

        return paginated_response(
            request,
            respaldos,
            lambda page: RespaldoRestauranteSerializer(page, many=True).data
        )

    @transaction.atomic
    def post(self, request):
        perfil = get_perfil_activo(request)
        restaurante = perfil.restaurante

        try:
            respaldo = RespaldoRestaurante.objects.create(
                restaurante=restaurante,
                responsable=perfil,
                nombre_responsable=perfil.user.get_full_name() or perfil.user.username,
                nombre_restaurante=restaurante.nombre_empresa,
                datos_json=construir_datos_respaldo(restaurante),
            )
        except Exception:
            return Response(
                {"error": "No se pudo crear el respaldo. Intenta nuevamente."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RespaldoRestauranteSerializer(respaldo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)




#PRODUCTOS MAS CLICKEADOS
class ProductoClickView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ProductoClickRateThrottle]

    def post(self, request, pk):
        try:
            producto = Producto.objects.get(id=pk, disponible=True)
        except Producto.DoesNotExist:
            return Response(
                {"error": "Producto no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        Producto.objects.filter(id=producto.id).update(clicks=F("clicks") + 1)

        return Response({"mensaje": "Click registrado"})

class ProductosMasClickeadosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = request.user.perfil_restaurante
        restaurante = perfil.restaurante
        return Response(productos_mas_clickeados(restaurante))

class UltimoRespaldoRestauranteView(APIView):
    permission_classes = [IsAuthenticated, CanManageRespaldos]

    def get(self, request):
        perfil = get_perfil_activo(request)
        respaldo = RespaldoRestaurante.objects.filter(
            restaurante=perfil.restaurante
        ).first()

        if not respaldo:
            return Response({"ultimo_respaldo": None})

        return Response({
            "ultimo_respaldo": RespaldoRestauranteSerializer(respaldo).data
        })
