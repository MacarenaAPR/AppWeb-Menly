from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from .models import UsuarioRestaurante,ImagenRestaurante, HorarioAtencion, MetodoPago, Mesa, RespaldoRestaurante
from rest_framework import serializers
from .models import Producto, ProductoVariante, Categoria, Reserva, Restaurante, Plan, Icono, SolicitudEspecial, Notificacion, PedidoWhatsApp, PedidoEspecial, PedidoManual, PedidoManualItem, ReporteMetrica
from .utils import crear_notificacion_pedido_especial
from .services.pedidos_whatsapp import (
    crear_pedido_whatsapp,
    generar_mensaje_legacy,
    generar_mensaje_whatsapp,
    generar_whatsapp_url,
    get_tracking_url,
    normalizar_productos_pedido,
    obtener_whatsapp_destino,
)
from .services.estado_restaurante import calcular_estado_abierto, calcular_estado_restaurante
from .services.estados_pedidos import obtener_transiciones_permitidas
from django.contrib.auth.models import User
from urllib.parse import quote
from django.db import transaction
from django.db.models import Max
import logging

logger = logging.getLogger(__name__)


class ContactoPlanesSerializer(serializers.Serializer):
    nombre = serializers.CharField(
        max_length=120,
        required=True,
        error_messages={"blank": "El nombre es obligatorio.", "required": "El nombre es obligatorio."},
    )
    restaurante = serializers.CharField(
        max_length=160,
        required=True,
        error_messages={
            "blank": "El nombre del restaurante es obligatorio.",
            "required": "El nombre del restaurante es obligatorio.",
        },
    )
    correo = serializers.EmailField(
        required=True,
        error_messages={
            "blank": "El correo es obligatorio.",
            "required": "El correo es obligatorio.",
            "invalid": "Ingresa un correo válido.",
        },
    )
    telefono = serializers.CharField(
        max_length=40,
        required=True,
        error_messages={"blank": "El teléfono es obligatorio.", "required": "El teléfono es obligatorio."},
    )
    ciudad = serializers.CharField(
        max_length=120,
        required=True,
        error_messages={"blank": "La ciudad es obligatoria.", "required": "La ciudad es obligatoria."},
    )
    plan_interes = serializers.ChoiceField(
        choices=["Básico", "Pro", "No estoy seguro"],
        required=True,
        error_messages={
            "blank": "Selecciona un plan de interés.",
            "required": "Selecciona un plan de interés.",
            "invalid_choice": "Selecciona una opción válida.",
        },
    )
    mensaje = serializers.CharField(
        required=True,
        error_messages={"blank": "El mensaje es obligatorio.", "required": "El mensaje es obligatorio."},
    )


class MetodoPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoPago
        fields = ["id", "nombre", "codigo", "activo", "orden"]
        read_only_fields = ["id", "codigo"]


class MetodoPagoPublicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoPago
        fields = ["id", "codigo", "nombre"]


class RespaldoRestauranteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RespaldoRestaurante
        fields = [
            "id",
            "fecha_respaldo",
            "responsable",
            "nombre_responsable",
            "nombre_restaurante",
            "datos_json",
        ]
        read_only_fields = fields

class UsuarioRestauranteCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    rol = serializers.ChoiceField(choices=["admin", "empleado"])

    def validate(self, data):
        request = self.context["request"]
        restaurante = request.user.perfil_restaurante.restaurante
        rol = data["rol"]

        usuarios_activos = UsuarioRestaurante.objects.filter(
            restaurante=restaurante,
            activo=True
        )

        if usuarios_activos.count() >= 4:
            raise serializers.ValidationError(
                "Este restaurante ya alcanzó el máximo de usuarios permitidos."
            )

        if rol == "admin" and usuarios_activos.filter(rol="admin").count() >= 1:
            raise serializers.ValidationError(
                "Este restaurante ya tiene un administrador."
            )

        if rol == "empleado" and usuarios_activos.filter(rol="empleado").count() >= 2:
            raise serializers.ValidationError(
                "Este restaurante ya tiene el máximo de empleados permitidos."
            )

        if User.objects.filter(username=data["username"]).exists():
            raise serializers.ValidationError(
                "Este nombre de usuario ya existe."
            )

        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError(
                "Este correo ya está registrado."
            )

        return data

    def create(self, validated_data):
        request = self.context["request"]
        dueno_perfil = request.user.perfil_restaurante
        restaurante = dueno_perfil.restaurante

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("nombre", "")
        )

        usuario_restaurante = UsuarioRestaurante.objects.create(
            user=user,
            restaurante=restaurante,
            rol=validated_data["rol"],
            activo=True,
            creado_por=dueno_perfil
        )

        return usuario_restaurante

class UsuarioRestauranteListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    nombre = serializers.CharField(source="user.first_name", read_only=True)

    class Meta:
        model = UsuarioRestaurante
        fields = [
            "id",
            "email",
            "username",
            "nombre",
            "rol",
            "activo",
            "fecha_creacion",
        ]

class MesaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mesa
        fields = [
            "id",
            "numero",
            "nombre",
            "activa",
        ]

class HorarioSerializer(serializers.ModelSerializer):
    dia_nombre = serializers.CharField(source="get_dia_display", read_only=True)

    class Meta:
        model = HorarioAtencion
        fields = [
            "id",
            "dia",
            "dia_nombre",
            "hora_apertura",
            "hora_cierre",
            "cerrado",
            "activo",
        ]

    def validate(self, data):
        if self.instance:
            cerrado = data.get("cerrado", self.instance.cerrado)
            hora_apertura = data.get("hora_apertura", self.instance.hora_apertura)
            hora_cierre = data.get("hora_cierre", self.instance.hora_cierre)
        else:
            cerrado = data.get("cerrado", False)
            hora_apertura = data.get("hora_apertura")
            hora_cierre = data.get("hora_cierre")

        if not cerrado:
            if not hora_apertura:
                raise serializers.ValidationError({
                    "hora_apertura": "La hora de apertura es obligatoria si el dia no esta cerrado."
                })

            if not hora_cierre:
                raise serializers.ValidationError({
                    "hora_cierre": "La hora de cierre es obligatoria si el dia no esta cerrado."
                })

            if hora_cierre == hora_apertura:
                raise serializers.ValidationError({
                    "hora_cierre": "La hora de cierre debe ser distinta de la hora de apertura."
                })

        return data

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = [
            "id",
            "nombre",
            "orden",
            "activa",
            "icono",
        ]


def serializar_plan_restaurante(restaurante):
    plan = getattr(restaurante, "plan", None)

    if plan:
        return {
            "id": plan.id,
            "nombre": plan.nombre,
            "slug": plan.slug,
        }

    plan_basico = Plan.objects.filter(slug="basico", activo=True).first()
    if plan_basico:
        return {
            "id": plan_basico.id,
            "nombre": plan_basico.nombre,
            "slug": plan_basico.slug,
        }

    return {
        "id": None,
        "nombre": "Básico",
        "slug": "basico",
    }


class RestauranteConfigSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    abierto_ahora = serializers.SerializerMethodField()
    estado_apertura = serializers.SerializerMethodField()

    class Meta:
        model = Restaurante
        fields = [
            "notificar_reservas",
            "email_notificacion",
            "id",
            "nombre_empresa",
            "telefono",
            "email_contacto",
            "direccion",
            "ciudad",
            "sitio_web",
            "whatsapp",
            "instagram",
            "facebook",
            "google_maps",
            "link_delivery",
            "delivery_activo",
            "abierto",
            "abierto_ahora",
            "estado_apertura",
            "apertura_excepcional_hasta",
            "descripcion",
            "logo",
            "logo_url",
            "plan",
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "pedidos_pos",
            "metricas_activas",
            "slogan",
        ]
        read_only_fields = [
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "pedidos_pos",
            "metricas_activas",
            "plan",
            "abierto_ahora",
            "estado_apertura",
            "apertura_excepcional_hasta",
        ]

    def get_logo_url(self, obj):
        if not obj.logo:
            return None

        try:
            return obj.logo.url
        except Exception:
            return None

    def get_plan(self, obj):
        return serializar_plan_restaurante(obj)

    def get_abierto_ahora(self, obj):
        return calcular_estado_abierto(obj)

    def get_estado_apertura(self, obj):
        return calcular_estado_restaurante(obj)


class ImagenRestaurantePublicaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagenRestaurante
        fields = ["id", "label", "url", "orden"]

    def get_url(self, obj):
        return obj.imagen.url if obj.imagen else None

class RestaurantePublicoDetalleSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    horarios = serializers.SerializerMethodField()
    metodos_pago = serializers.SerializerMethodField()
    imagenes = serializers.SerializerMethodField()
    abierto_ahora = serializers.SerializerMethodField()
    estado_apertura = serializers.SerializerMethodField()

    class Meta:
        model = Restaurante
        fields = [
            "id",
            "nombre_empresa",
            "slug",
            "telefono",
            "email_contacto",
            "direccion",
            "ciudad",
            "descripcion",
            "whatsapp",
            "instagram",
            "facebook",
            "google_maps",
            "sitio_web",
            "link_delivery",
            "delivery_activo",
            "abierto",
            "abierto_ahora",
            "estado_apertura",
            "apertura_excepcional_hasta",
            "logo_url",
            "horarios",
            "metodos_pago",
            "imagenes",
            "imgen_principal",
            "mensaje_bienvenida",
            "theme_color",
            "imgen_form",
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "pedidos_pos",
            "metricas_activas",
            "slogan",
        ]

    def get_logo_url(self, obj):
        if not obj.logo:
            return None

        try:
            request = self.context.get("request")
            url = obj.logo.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None
        
    def get_imagenes(self, obj):
        imagenes = obj.imagenes.filter(activa=True)
        return ImagenRestaurantePublicaSerializer(imagenes, many=True).data
    
    def get_horarios(self, obj):
        horarios = obj.horarios.filter(activo=True).order_by("dia")
        return HorarioSerializer(horarios, many=True).data

    def get_metodos_pago(self, obj):
        metodos_pago = obj.metodos_pago.filter(activo=True).order_by("orden", "id")
        return MetodoPagoPublicoSerializer(metodos_pago, many=True).data

    def get_abierto_ahora(self, obj):
        return calcular_estado_abierto(obj)

    def get_estado_apertura(self, obj):
        return calcular_estado_restaurante(obj)
    
class ReservaPublicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = [
            "id",
            "nombre_cliente",
            "telefono",
            "email",
            "fecha",
            "hora",
            "cantidad_personas",
            "mensaje",
        ]


class SolicitudEspecialPublicaSerializer(serializers.ModelSerializer):
    restaurante_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = SolicitudEspecial
        fields = [
            "id",
            "restaurante_id",
            "nombre",
            "apellido",
            "fecha_evento",
            "telefono_contacto",
            "email_contacto",
            "descripcion_solicitud",
            "estado",
            "fecha_creacion",
        ]
        read_only_fields = ["id", "estado", "fecha_creacion"]

    def validate(self, data):
        for field in [
            "nombre",
            "apellido",
            "telefono_contacto",
            "email_contacto",
            "descripcion_solicitud",
        ]:
            if not str(data.get(field) or "").strip():
                raise serializers.ValidationError({
                    field: "Este campo es obligatorio."
                })

        return data

    def create(self, validated_data):
        validated_data.pop("restaurante_id", None)
        return super().create(validated_data)


class PedidoWhatsAppProductoInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    variante_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    cantidad = serializers.IntegerField(min_value=1, max_value=99)


class PedidoWhatsAppCreateSerializer(serializers.Serializer):
    nombre_cliente = serializers.CharField(max_length=120, trim_whitespace=True)
    telefono_cliente = serializers.CharField(max_length=30, trim_whitespace=True)
    tipo_entrega = serializers.ChoiceField(choices=PedidoWhatsApp.TIPOS_ENTREGA)
    direccion_entrega = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    metodo_pago_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    productos = PedidoWhatsAppProductoInputSerializer(many=True)

    def validate(self, data):
        restaurante = self.context["restaurante"]
        tipo_entrega = data.get("tipo_entrega")
        direccion_entrega = (data.get("direccion_entrega") or "").strip()

        if tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and not direccion_entrega:
            raise serializers.ValidationError({
                "direccion_entrega": "Debe ingresar una direccion para delivery."
            })

        if tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and not restaurante.delivery_activo:
            raise serializers.ValidationError({
                "tipo_entrega": "El delivery no esta activo para este restaurante."
            })

        data["direccion_entrega"] = direccion_entrega or None

        metodos_activos = MetodoPago.objects.filter(restaurante=restaurante, activo=True)
        metodo_pago_id = data.get("metodo_pago_id")
        if metodos_activos.exists() and not metodo_pago_id:
            raise serializers.ValidationError({
                "metodo_pago_id": "Selecciona un metodo de pago."
            })

        metodo_pago = None
        if metodo_pago_id:
            metodo_pago = metodos_activos.filter(id=metodo_pago_id).first()
            if not metodo_pago:
                raise serializers.ValidationError({
                    "metodo_pago_id": "El metodo de pago no es valido para este restaurante."
                })

        data["metodo_pago"] = metodo_pago
        data["metodo_pago_nombre"] = metodo_pago.nombre if metodo_pago else ""

        if not restaurante.carrito_whatsapp_activo:
            raise serializers.ValidationError({
                "carrito": "El carrito por WhatsApp no está activo para este restaurante."
            })

        whatsapp_destino = obtener_whatsapp_destino(restaurante)
        if not whatsapp_destino:
            raise serializers.ValidationError({
                "whatsapp": "El restaurante no tiene un número de WhatsApp configurado."
            })
        if not any(ch.isdigit() for ch in whatsapp_destino):
            raise serializers.ValidationError({
                "whatsapp": "El número de WhatsApp del restaurante no es válido."
            })

        productos_solicitados = data.get("productos") or []
        if not productos_solicitados:
            raise serializers.ValidationError({
                "productos": "Agrega al menos un producto al pedido."
            })

        snapshot, total = normalizar_productos_pedido(restaurante, productos_solicitados)
        if snapshot is None:
            raise serializers.ValidationError({
                "productos": "Uno o más productos no pertenecen a este restaurante o no están disponibles."
            })

        data["productos_snapshot"] = snapshot
        data["total"] = total
        data["whatsapp_destino"] = whatsapp_destino
        return data

    def create(self, validated_data):
        restaurante = self.context["restaurante"]
        return crear_pedido_whatsapp(
            restaurante,
            dict(validated_data),
            request=self.context.get("request"),
        )

    def generar_mensaje(self, pedido):
        return generar_mensaje_whatsapp(pedido, request=self.context.get("request"))

    def get_tracking_url(self, pedido):
        return get_tracking_url(pedido, request=self.context.get("request"))

    def generar_mensaje_con_tracking(self, pedido):
        return self.generar_mensaje(pedido)

    def generar_mensaje_legacy(self, pedido):
        return generar_mensaje_legacy(pedido)

    def generar_whatsapp_url(self, telefono, mensaje):
        return generar_whatsapp_url(telefono, mensaje)

    def to_representation(self, pedido):
        return {
            "pedido_id": pedido.id,
            "numero_pedido": pedido.numero_pedido,
            "tracking_token": pedido.tracking_token,
            "tracking_url": self.get_tracking_url(pedido),
            "total": int(pedido.total),
            "metodo_pago_nombre": pedido.metodo_pago_nombre,
            "mensaje_whatsapp": pedido.mensaje_whatsapp_generado,
            "whatsapp_url": getattr(
                pedido,
                "whatsapp_url",
                self.generar_whatsapp_url(pedido.whatsapp_destino, pedido.mensaje_whatsapp_generado)
            ),
        }


class PedidoWhatsAppDashboardSerializer(serializers.ModelSerializer):
    tipo_entrega_display = serializers.CharField(source="get_tipo_entrega_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    productos = PedidoWhatsAppProductoInputSerializer(many=True, required=False, write_only=True)
    transiciones_permitidas = serializers.SerializerMethodField()

    class Meta:
        model = PedidoWhatsApp
        fields = [
            "id",
            "numero_pedido",
            "nombre_cliente",
            "telefono_cliente",
            "tipo_entrega",
            "tipo_entrega_display",
            "direccion_entrega",
            "metodo_pago",
            "metodo_pago_nombre",
            "productos_snapshot",
            "productos",
            "total",
            "estado",
            "estado_display",
            "transiciones_permitidas",
            "fecha_creacion",
            "fecha_actualizacion_estado",
            "mensaje_whatsapp_generado",
            "whatsapp_destino",
        ]
        read_only_fields = [
            "id",
            "numero_pedido",
            "nombre_cliente",
            "telefono_cliente",
            "tipo_entrega",
            "tipo_entrega_display",
            "metodo_pago",
            "metodo_pago_nombre",
            "productos_snapshot",
            "total",
            "estado_display",
            "estado",
            "transiciones_permitidas",
            "fecha_creacion",
            "fecha_actualizacion_estado",
            "mensaje_whatsapp_generado",
            "whatsapp_destino",
        ]

    def get_transiciones_permitidas(self, pedido):
        return obtener_transiciones_permitidas(pedido, "whatsapp", "panel")


    def validate(self, data):
        if "direccion_entrega" in data:
            direccion_entrega = (data.get("direccion_entrega") or "").strip()
            if self.instance and self.instance.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and not direccion_entrega:
                raise serializers.ValidationError({
                    "direccion_entrega": "Debe ingresar una direccion para delivery."
                })
            data["direccion_entrega"] = direccion_entrega or None

        productos_solicitados = data.pop("productos", None)
        if productos_solicitados is None:
            return data

        restaurante = self.context.get("restaurante") or getattr(self.instance, "restaurante", None)
        if not restaurante:
            raise serializers.ValidationError({"productos": "No se pudo validar el restaurante del pedido."})

        if not productos_solicitados:
            raise serializers.ValidationError({"productos": "Agrega al menos un producto."})

        snapshot, total = normalizar_productos_pedido(restaurante, productos_solicitados)
        if snapshot is None:
            raise serializers.ValidationError({
                "productos": "Uno o mas productos, variantes o disponibilidades no son validos."
            })

        data["productos_snapshot"] = snapshot
        data["total"] = total
        return data

    def update(self, instance, validated_data):
        productos_editados = "productos_snapshot" in validated_data

        for attr in ["direccion_entrega", "productos_snapshot", "total"]:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])

        if productos_editados:
            instance.mensaje_whatsapp_generado = PedidoWhatsAppCreateSerializer().generar_mensaje(instance)

        instance.save()
        return instance


class PedidoWhatsAppEstadoUpdateSerializer(serializers.Serializer):
    estado = serializers.CharField(max_length=30, trim_whitespace=True)

    def create(self, validated_data):
        raise NotImplementedError("Este serializer solo actualiza pedidos existentes.")


class PedidoWhatsAppSeguimientoPublicoSerializer(serializers.ModelSerializer):
    restaurante_nombre = serializers.CharField(source="restaurante.nombre_empresa", read_only=True)
    tipo_entrega_display = serializers.CharField(source="get_tipo_entrega_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    items = serializers.SerializerMethodField()
    observaciones_cliente = serializers.SerializerMethodField()
    telefono_whatsapp_restaurante = serializers.CharField(source="whatsapp_destino", read_only=True)
    whatsapp_contacto_url = serializers.SerializerMethodField()

    class Meta:
        model = PedidoWhatsApp
        fields = [
            "restaurante_nombre",
            "numero_pedido",
            "estado",
            "estado_display",
            "fecha_creacion",
            "fecha_actualizacion_estado",
            "tipo_entrega",
            "tipo_entrega_display",
            "metodo_pago_nombre",
            "total",
            "items",
            "observaciones_cliente",
            "telefono_whatsapp_restaurante",
            "whatsapp_contacto_url",
        ]

    def get_items(self, pedido):
        return [
            {
                "nombre": item.get("nombre", ""),
                "variante_nombre": item.get("variante_nombre", ""),
                "cantidad": item.get("cantidad", 0),
                "precio_unitario": item.get("precio_unitario", 0),
                "subtotal": item.get("subtotal", 0),
            }
            for item in pedido.productos_snapshot or []
        ]

    def get_observaciones_cliente(self, pedido):
        if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY:
            return pedido.direccion_entrega or ""
        return ""

    def get_whatsapp_contacto_url(self, pedido):
        numero = "".join(ch for ch in str(pedido.whatsapp_destino) if ch.isdigit())
        if not numero:
            return ""
        mensaje = quote(f"Hola, quiero consultar por mi pedido #{pedido.numero_pedido}.")
        return f"https://wa.me/{numero}?text={mensaje}"


class PedidoEspecialItemSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=160, trim_whitespace=True)
    descripcion = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    cantidad = serializers.IntegerField(min_value=1, max_value=999)
    precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=0, min_value=0)


class PedidoEspecialSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    transiciones_permitidas = serializers.SerializerMethodField()
    items = PedidoEspecialItemSerializer(many=True)
    solicitud_especial_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = PedidoEspecial
        fields = [
            "id",
            "numero_pedido",
            "solicitud_especial",
            "solicitud_especial_id",
            "nombre_cliente",
            "telefono_cliente",
            "email_cliente",
            "descripcion_original",
            "items",
            "total",
            "fecha_entrega",
            "estado",
            "estado_display",
            "transiciones_permitidas",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = [
            "id",
            "numero_pedido",
            "solicitud_especial",
            "total",
            "estado_display",
            "estado",
            "transiciones_permitidas",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        extra_kwargs = {
            "nombre_cliente": {"required": False, "allow_blank": True},
            "telefono_cliente": {"required": False, "allow_blank": True},
            "email_cliente": {"required": False, "allow_blank": True},
            "descripcion_original": {"required": False, "allow_blank": True},
        }

    def get_transiciones_permitidas(self, pedido):
        return obtener_transiciones_permitidas(pedido, "especial", "panel")

    def _normalizar_items(self, items):
        normalizados = []
        total = 0

        for item in items:
            precio = item["precio_unitario"]
            cantidad = item["cantidad"]
            subtotal = precio * cantidad
            total += subtotal
            normalizados.append({
                "nombre": item["nombre"],
                "descripcion": item.get("descripcion", ""),
                "cantidad": cantidad,
                "precio_unitario": int(precio),
                "subtotal": int(subtotal),
            })

        return normalizados, total

    def validate(self, data):
        restaurante = self.context["restaurante"]
        solicitud_id = data.pop("solicitud_especial_id", None)

        if solicitud_id:
            solicitud = SolicitudEspecial.objects.filter(
                id=solicitud_id,
                restaurante=restaurante
            ).first()
            if not solicitud:
                raise serializers.ValidationError({
                    "solicitud_especial_id": "La solicitud no pertenece a este restaurante."
                })
            if solicitud.estado != "aceptada":
                raise serializers.ValidationError({
                    "solicitud_especial_id": "Solo se pueden convertir solicitudes aceptadas."
                })
            data["solicitud_especial"] = solicitud

            data.setdefault("nombre_cliente", solicitud.nombre)
            data.setdefault("telefono_cliente", solicitud.telefono_contacto)
            data.setdefault("email_cliente", solicitud.email_contacto)
            data.setdefault("descripcion_original", solicitud.descripcion_solicitud)

        if self.partial and "items" not in data:
            return data

        items = data.get("items") or []
        if not items:
            raise serializers.ValidationError({"items": "Agrega al menos un ítem."})

        items_normalizados, total = self._normalizar_items(items)
        data["items"] = items_normalizados
        data["total"] = total

        for field in ["nombre_cliente", "telefono_cliente", "fecha_entrega"]:
            if not data.get(field):
                raise serializers.ValidationError({field: "Este campo es obligatorio."})

        return data

    def create(self, validated_data):
        restaurante = self.context["restaurante"]

        with transaction.atomic():
            Restaurante.objects.select_for_update().get(id=restaurante.id)
            ultimo_numero = PedidoEspecial.objects.filter(
                restaurante=restaurante
            ).aggregate(maximo=Max("numero_pedido"))["maximo"] or 0

            pedido = PedidoEspecial.objects.create(
                restaurante=restaurante,
                numero_pedido=ultimo_numero + 1,
                **validated_data
            )

            logger.info(
                "Pedido especial creado",
                extra={
                    "pedido_especial_id": pedido.id,
                    "pedido_especial_estado": pedido.estado,
                    "pedido_especial_solicitud_id": pedido.solicitud_especial_id,
                },
            )

            try:
                crear_notificacion_pedido_especial(pedido)
            except Exception:
                logger.exception(
                    "Error creando notificacion persistente de pedido especial",
                    extra={"pedido_especial_id": pedido.id, "restaurante_id": restaurante.id},
                )

            return pedido

    def update(self, instance, validated_data):
        validated_data.pop("solicitud_especial", None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

        return instance


class PedidoManualItemInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(min_value=1)
    variante_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    cantidad = serializers.IntegerField(min_value=1, max_value=999)
    observaciones = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class PedidoManualItemSerializer(serializers.ModelSerializer):
    producto_id = serializers.IntegerField(read_only=True)
    variante_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = PedidoManualItem
        fields = [
            "id",
            "producto_id",
            "variante_id",
            "nombre_producto",
            "variante_nombre",
            "precio_unitario",
            "cantidad",
            "subtotal",
            "observaciones",
        ]
        read_only_fields = fields


class PedidoManualSerializer(serializers.ModelSerializer):
    origen_display = serializers.CharField(source="get_origen_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    tipo_entrega_display = serializers.CharField(source="get_tipo_entrega_display", read_only=True)
    items = PedidoManualItemSerializer(many=True, read_only=True)
    items_input = PedidoManualItemInputSerializer(many=True, write_only=True, required=False)
    creado_por_nombre = serializers.SerializerMethodField()
    tracking_url = serializers.SerializerMethodField()
    cliente_nombre = serializers.CharField(source="nombre_cliente", read_only=True)
    cliente_telefono = serializers.CharField(source="telefono_cliente", read_only=True)
    transiciones_permitidas = serializers.SerializerMethodField()

    class Meta:
        model = PedidoManual
        fields = [
            "id",
            "numero_pedido",
            "tracking_token",
            "tracking_url",
            "origen",
            "origen_display",
            "estado",
            "estado_display",
            "transiciones_permitidas",
            "nombre_cliente",
            "telefono_cliente",
            "cliente_nombre",
            "cliente_telefono",
            "tipo_entrega",
            "tipo_entrega_display",
            "direccion",
            "numero_mesa",
            "observaciones",
            "subtotal",
            "total",
            "creado_por",
            "creado_por_nombre",
            "fecha_creacion",
            "fecha_actualizacion",
            "items",
            "items_input",
        ]
        read_only_fields = [
            "id",
            "numero_pedido",
            "tracking_token",
            "tracking_url",
            "origen",
            "origen_display",
            "estado_display",
            "estado",
            "transiciones_permitidas",
            "cliente_nombre",
            "cliente_telefono",
            "subtotal",
            "total",
            "creado_por",
            "creado_por_nombre",
            "fecha_creacion",
            "fecha_actualizacion",
            "items",
        ]
        extra_kwargs = {
            "nombre_cliente": {"required": False, "allow_blank": True},
            "telefono_cliente": {"required": False, "allow_blank": True},
            "direccion": {"required": False, "allow_blank": True},
            "numero_mesa": {"required": False, "allow_blank": True},
            "observaciones": {"required": False, "allow_blank": True},
        }

    def get_creado_por_nombre(self, pedido):
        if not pedido.creado_por:
            return None
        return pedido.creado_por.get_full_name() or pedido.creado_por.username

    def get_tracking_url(self, pedido):
        return get_tracking_url(pedido, request=self.context.get("request"))

    def get_transiciones_permitidas(self, pedido):
        return obtener_transiciones_permitidas(pedido, "manual", "panel")

    def to_internal_value(self, data):
        if "items" in data and "items_input" not in data:
            data = data.copy()
            data["items_input"] = data.get("items")
        return super().to_internal_value(data)

    def validate(self, data):
        tipo_entrega = data.get("tipo_entrega", getattr(self.instance, "tipo_entrega", None))
        direccion = (data.get("direccion", getattr(self.instance, "direccion", "")) or "").strip()
        numero_mesa = (data.get("numero_mesa", getattr(self.instance, "numero_mesa", "")) or "").strip()

        if tipo_entrega == PedidoManual.TIPO_DELIVERY and not direccion:
            raise serializers.ValidationError({"direccion": "Debe ingresar una direccion para delivery."})

        if tipo_entrega == PedidoManual.TIPO_MESA and not numero_mesa:
            raise serializers.ValidationError({"numero_mesa": "Debe ingresar el numero de mesa."})

        data["direccion"] = direccion
        data["numero_mesa"] = numero_mesa
        for campo in ["nombre_cliente", "telefono_cliente", "observaciones"]:
            if campo in data:
                data[campo] = (data.get(campo) or "").strip()

        items = data.pop("items_input", None)
        if not self.instance and not items:
            raise serializers.ValidationError({"items": "Agrega al menos un producto al pedido."})
        if self.instance and items is None:
            return data
        if not items:
            raise serializers.ValidationError({"items": "Agrega al menos un producto al pedido."})

        restaurante = self.context["restaurante"]
        snapshot, total = normalizar_productos_pedido(restaurante, items)
        if snapshot is None:
            raise serializers.ValidationError({
                "items": "Selecciona una variante activa y valida para cada producto que la requiera."
            })

        producto_ids = {item["producto_id"] for item in snapshot}
        productos = Producto.objects.filter(
            restaurante=restaurante,
            id__in=producto_ids,
        ).in_bulk()
        observaciones = {
            (item["producto_id"], item.get("variante_id")): item.get("observaciones", "")
            for item in items
        }
        items_normalizados = []
        for item in snapshot:
            producto_id = item["producto_id"]
            variante_id = item.get("variante_id")
            items_normalizados.append({
                "producto": productos[producto_id],
                "variante_id": variante_id,
                "nombre_producto": item["nombre"],
                "variante_nombre": item.get("variante_nombre", ""),
                "precio_unitario": item["precio_unitario"],
                "cantidad": item["cantidad"],
                "subtotal": item["subtotal"],
                "observaciones": observaciones.get((producto_id, variante_id), ""),
            })

        data["items_normalizados"] = items_normalizados
        data["subtotal"] = total
        data["total"] = total
        return data

    def create(self, validated_data):
        restaurante = self.context["restaurante"]
        usuario = self.context.get("usuario")
        items = validated_data.pop("items_normalizados")

        with transaction.atomic():
            Restaurante.objects.select_for_update().get(id=restaurante.id)
            ultimo_numero = PedidoManual.objects.filter(
                restaurante=restaurante
            ).aggregate(maximo=Max("numero_pedido"))["maximo"] or 0

            pedido = PedidoManual.objects.create(
                restaurante=restaurante,
                numero_pedido=ultimo_numero + 1,
                origen=PedidoManual.ORIGEN_MENLY,
                creado_por=usuario,
                **validated_data,
            )
            PedidoManualItem.objects.bulk_create([
                PedidoManualItem(pedido=pedido, **item)
                for item in items
            ])
        return pedido

    def update(self, instance, validated_data):
        items = validated_data.pop("items_normalizados", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if items is not None:
                instance.items.all().delete()
                PedidoManualItem.objects.bulk_create([
                    PedidoManualItem(pedido=instance, **item)
                    for item in items
                ])

        return instance


class PedidoManualSeguimientoPublicoSerializer(serializers.ModelSerializer):
    restaurante_nombre = serializers.CharField(source="restaurante.nombre_empresa", read_only=True)
    tipo_entrega_display = serializers.CharField(source="get_tipo_entrega_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    items = serializers.SerializerMethodField()
    observaciones_cliente = serializers.SerializerMethodField()
    fecha_actualizacion_estado = serializers.DateTimeField(source="fecha_actualizacion", read_only=True)

    class Meta:
        model = PedidoManual
        fields = [
            "restaurante_nombre",
            "numero_pedido",
            "estado",
            "estado_display",
            "fecha_creacion",
            "fecha_actualizacion_estado",
            "tipo_entrega",
            "tipo_entrega_display",
            "total",
            "items",
            "observaciones_cliente",
        ]

    def get_items(self, pedido):
        return [
            {
                "nombre": item.nombre_producto,
                "variante_nombre": item.variante_nombre,
                "cantidad": item.cantidad,
                "subtotal": int(item.subtotal),
            }
            for item in pedido.items.all()
        ]

    def get_observaciones_cliente(self, pedido):
        if pedido.tipo_entrega == PedidoManual.TIPO_DELIVERY:
            return pedido.direccion or ""
        if pedido.tipo_entrega == PedidoManual.TIPO_MESA and pedido.numero_mesa:
            return f"Mesa {pedido.numero_mesa}"
        return ""


class SolicitudEspecialDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudEspecial
        fields = [
            "id",
            "nombre",
            "apellido",
            "fecha_evento",
            "telefono_contacto",
            "email_contacto",
            "descripcion_solicitud",
            "estado",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]

    def validate(self, data):
        for field in [
            "nombre",
            "apellido",
            "fecha_evento",
            "telefono_contacto",
            "email_contacto",
            "descripcion_solicitud",
        ]:
            if field in data and not str(data.get(field) or "").strip():
                raise serializers.ValidationError({
                    field: "Este campo es obligatorio."
                })

        estado = data.get("estado")
        if estado and estado not in dict(SolicitudEspecial.ESTADOS):
            raise serializers.ValidationError({
                "estado": "Estado de solicitud inválido."
            })

        return data

class ReservaManualSerializer(serializers.ModelSerializer):
    mesa_asignada = serializers.PrimaryKeyRelatedField(
        queryset=Mesa.objects.none(),
        required=False,
        allow_null=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        restaurante = self.context.get("restaurante")

        if restaurante:
            self.fields["mesa_asignada"].queryset = Mesa.objects.filter(
                restaurante=restaurante,
                activa=True
            )

    class Meta:
        model = Reserva
        fields = [
            "nombre_cliente",
            "telefono",
            "email",
            "fecha",
            "hora",
            "cantidad_personas",
            "mensaje",
            "mesa_asignada",
            "observacion_admin",
        ]

class ReservaDashboardSerializer(serializers.ModelSerializer):
    creada_por_email = serializers.SerializerMethodField()
    gestionada_por_email = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            "id",
            "nombre_cliente",
            "telefono",
            "email",
            "fecha",
            "hora",
            "cantidad_personas",
            "mensaje",
            "estado",
            "mesa_asignada",
            "observacion_admin",
            "fecha_creacion",
            "fecha_actualizacion",
            "creada_por_email",
            "gestionada_por_email",
        ]

    def get_creada_por_email(self, obj):
        return obj.creada_por.user.email if obj.creada_por else None

    def get_gestionada_por_email(self, obj):
        return obj.gestionada_por.user.email if obj.gestionada_por else None


class NotificacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Notificacion
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "titulo",
            "mensaje",
            "fecha_creacion",
            "leida",
            "fecha_lectura",
            "referencia_id",
            "referencia_modelo",
        ]
        read_only_fields = fields


class NotificacionDetalleSerializer(NotificacionSerializer):
    detalle = serializers.SerializerMethodField()

    class Meta(NotificacionSerializer.Meta):
        fields = NotificacionSerializer.Meta.fields + ["detalle"]

    def get_detalle(self, obj):
        if obj.referencia_modelo == Notificacion.MODELO_RESERVA:
            reserva = Reserva.objects.filter(
                id=obj.referencia_id,
                restaurante=obj.restaurante
            ).select_related("creada_por__user", "gestionada_por__user").first()
            return ReservaDashboardSerializer(reserva).data if reserva else None

        if obj.referencia_modelo == Notificacion.MODELO_SOLICITUD_ESPECIAL:
            solicitud = SolicitudEspecial.objects.filter(
                id=obj.referencia_id,
                restaurante=obj.restaurante
            ).first()
            return SolicitudEspecialDashboardSerializer(solicitud).data if solicitud else None

        if obj.referencia_modelo == Notificacion.MODELO_PEDIDO_WHATSAPP:
            pedido = PedidoWhatsApp.objects.filter(
                id=obj.referencia_id,
                restaurante=obj.restaurante
            ).first()
            return PedidoWhatsAppDashboardSerializer(pedido).data if pedido else None

        if obj.referencia_modelo == Notificacion.MODELO_PEDIDO_ESPECIAL:
            pedido = PedidoEspecial.objects.filter(
                id=obj.referencia_id,
                restaurante=obj.restaurante
            ).first()
            return PedidoEspecialSerializer(pedido).data if pedido else None

        return None


class ReporteMetricaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    generado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ReporteMetrica
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "periodo_mes",
            "periodo_anio",
            "titulo",
            "resumen",
            "datos",
            "fecha_generacion",
            "generado_por",
            "generado_por_nombre",
            "archivo_pdf",
            "activo",
        ]
        read_only_fields = [
            "id",
            "tipo_display",
            "fecha_generacion",
            "generado_por",
            "generado_por_nombre",
            "archivo_pdf",
            "activo",
        ]

    def get_generado_por_nombre(self, obj):
        if not obj.generado_por:
            return None
        return obj.generado_por.get_full_name() or obj.generado_por.username


class ProductoVarianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductoVariante
        fields = [
            "id", "nombre", "descripcion", "precio", "activo", "orden",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value

    def validate_nombre(self, value):
        nombre = value.strip()
        if not nombre:
            raise serializers.ValidationError("El nombre es obligatorio.")
        producto = self.context.get("producto") or getattr(self.instance, "producto", None)
        if producto:
            duplicada = ProductoVariante.objects.filter(
                producto=producto,
                nombre__iexact=nombre,
            )
            if self.instance:
                duplicada = duplicada.exclude(pk=self.instance.pk)
            if duplicada.exists():
                raise serializers.ValidationError("Ya existe una variante con este nombre.")
        return nombre


class ProductoCreateSerializer(serializers.ModelSerializer):
    variantes = ProductoVarianteSerializer(many=True, read_only=True)
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all()
    )

    class Meta:
        model = Producto
        fields = [
            "id",
            "categoria",
            "nombre",
            "descripcion",
            "condiciones",
            "precio",
            "imagen",
            "disponible",
            "destacado",
            "orden",
            "fecha_creacion",
            "variantes",
        ]

    def validate_categoria(self, categoria):
        request = self.context["request"]

        perfil = request.user.perfil_restaurante
        restaurante = perfil.restaurante

        if categoria.restaurante != restaurante:
            raise serializers.ValidationError(
                "La categoría no pertenece a tu restaurante."
            )

        return categoria

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField(
            write_only=True,
            required=True,
            error_messages={
                "required": "El correo electrónico es obligatorio.",
                "blank": "El correo electrónico es obligatorio.",
                "invalid": "Ingresa un correo electrónico válido.",
            },
        )
        self.fields["password"].error_messages.update({
            "required": "La contraseña es obligatoria.",
            "blank": "La contraseña es obligatoria.",
        })

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        password = attrs.get("password")

        if not email:
            raise serializers.ValidationError({
                "email": "El correo electrónico es obligatorio."
            })

        if not password:
            raise serializers.ValidationError({
                "password": "La contraseña es obligatoria."
            })

        user = User.objects.filter(email__iexact=email).first()

        if not user or not user.is_active or not user.check_password(password):
            raise AuthenticationFailed("Correo o contraseña incorrectos")

        refresh = self.get_token(user)

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        self.user = user

        try:
            perfil = user.perfil_restaurante
            restaurante = perfil.restaurante

            if not perfil.activo:
                raise AuthenticationFailed("Usuario desactivado.")

            data["user"] = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }

            data["restaurante"] = {
                "id": restaurante.id,
                "nombre_empresa": restaurante.nombre_empresa,
                "slug": restaurante.slug,
                "rol": perfil.rol,
                "activo": restaurante.activo,
            }

        except UsuarioRestaurante.DoesNotExist:
            raise AuthenticationFailed(
                "Este usuario no tiene un restaurante activo asignado."
            )

        return data

class IconoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Icono
        fields = ["id", "nombre", "clase_css"]
