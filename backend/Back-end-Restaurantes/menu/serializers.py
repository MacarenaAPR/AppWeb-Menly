from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from .models import UsuarioRestaurante,ImagenRestaurante, HorarioAtencion, MetodoPago, Mesa, RespaldoRestaurante
from rest_framework import serializers
from .models import Producto, Categoria, Reserva, Restaurante, Plan, Icono, SolicitudEspecial, Notificacion, PedidoWhatsApp, HistorialEstadoPedidoWhatsApp, PedidoEspecial, ReporteMetrica
from .utils import crear_notificacion_pedido_whatsapp, crear_notificacion_pedido_especial
from django.contrib.auth.models import User
from urllib.parse import quote
from django.db import transaction
from django.db.models import Max
import logging

logger = logging.getLogger(__name__)

class MetodoPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoPago
        fields = ["id", "nombre", "activo"]


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

            if hora_cierre <= hora_apertura:
                raise serializers.ValidationError({
                    "hora_cierre": "La hora de cierre debe ser mayor que la hora de apertura."
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
            "descripcion",
            "logo",
            "logo_url",
            "plan",
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "metricas_activas",
        ]
        read_only_fields = [
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "metricas_activas",
            "plan",
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
            "metricas_activas",
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
        metodos_pago = obj.metodos_pago.filter(activo=True).order_by("nombre")
        return MetodoPagoSerializer(metodos_pago, many=True).data
    
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
    cantidad = serializers.IntegerField(min_value=1, max_value=99)


class PedidoWhatsAppCreateSerializer(serializers.Serializer):
    nombre_cliente = serializers.CharField(max_length=120, trim_whitespace=True)
    telefono_cliente = serializers.CharField(max_length=30, trim_whitespace=True)
    tipo_entrega = serializers.ChoiceField(choices=PedidoWhatsApp.TIPOS_ENTREGA)
    direccion_entrega = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    productos = PedidoWhatsAppProductoInputSerializer(many=True)

    def validate(self, data):
        restaurante = self.context["restaurante"]
        tipo_entrega = data.get("tipo_entrega")
        direccion_entrega = (data.get("direccion_entrega") or "").strip()

        if tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and not direccion_entrega:
            raise serializers.ValidationError({
                "direccion_entrega": "Debe ingresar una direccion para delivery."
            })

        data["direccion_entrega"] = direccion_entrega or None

        if not restaurante.carrito_whatsapp_activo:
            raise serializers.ValidationError({
                "carrito": "El carrito por WhatsApp no está activo para este restaurante."
            })

        whatsapp_destino = (restaurante.whatsapp or restaurante.telefono or "").strip()
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

        cantidades_por_producto = {}
        for item in productos_solicitados:
            producto_id = item["producto_id"]
            cantidades_por_producto[producto_id] = (
                cantidades_por_producto.get(producto_id, 0) + item["cantidad"]
            )

        productos = Producto.objects.filter(
            restaurante=restaurante,
            disponible=True,
            id__in=cantidades_por_producto.keys()
        ).in_bulk()

        if len(productos) != len(cantidades_por_producto):
            raise serializers.ValidationError({
                "productos": "Uno o más productos no pertenecen a este restaurante o no están disponibles."
            })

        snapshot = []
        total = 0

        for producto_id, cantidad in cantidades_por_producto.items():
            producto = productos[producto_id]
            precio_unitario = producto.precio
            subtotal = precio_unitario * cantidad
            total += subtotal
            snapshot.append({
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "precio_unitario": int(precio_unitario),
                "cantidad": cantidad,
                "subtotal": int(subtotal),
            })

        data["productos_snapshot"] = snapshot
        data["total"] = total
        data["whatsapp_destino"] = whatsapp_destino
        return data

    def create(self, validated_data):
        productos_snapshot = validated_data.pop("productos_snapshot")
        total = validated_data.pop("total")
        whatsapp_destino = validated_data.pop("whatsapp_destino")
        validated_data.pop("productos", None)
        restaurante = self.context["restaurante"]

        with transaction.atomic():
            Restaurante.objects.select_for_update().get(id=restaurante.id)
            ultimo_numero = PedidoWhatsApp.objects.filter(
                restaurante=restaurante
            ).aggregate(maximo=Max("numero_pedido"))["maximo"] or 0
            numero_pedido = ultimo_numero + 1

            pedido = PedidoWhatsApp.objects.create(
                restaurante=restaurante,
                numero_pedido=numero_pedido,
                productos_snapshot=productos_snapshot,
                total=total,
                whatsapp_destino=whatsapp_destino,
                mensaje_whatsapp_generado="",
                **validated_data
            )
            mensaje = self.generar_mensaje(pedido)
            pedido.mensaje_whatsapp_generado = mensaje
            pedido.save(update_fields=["mensaje_whatsapp_generado"])

            try:
                crear_notificacion_pedido_whatsapp(pedido)
            except Exception:
                logger.exception(
                    "Error creando notificacion persistente de pedido WhatsApp",
                    extra={"pedido_whatsapp_id": pedido.id, "restaurante_id": restaurante.id},
                )

        pedido.whatsapp_url = self.generar_whatsapp_url(pedido.whatsapp_destino, mensaje)
        return pedido

    def generar_mensaje(self, pedido):
        return self.generar_mensaje_con_tracking(pedido)

    def get_tracking_url(self, pedido):
        request = self.context.get("request")
        base_url = ""
        if request:
            base_url = request.META.get("HTTP_ORIGIN") or request.build_absolute_uri("/")
        base_url = (base_url or "https://menly.cl").rstrip("/")
        return f"{base_url}/seguimiento/pedido/{pedido.tracking_token}"

    def generar_mensaje_con_tracking(self, pedido):
        tipo_entrega = pedido.get_tipo_entrega_display()
        direccion = ""
        if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
            direccion = f"Direccion: {pedido.direccion_entrega}\n"

        productos = "\n".join(
            f"{item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
            for item in pedido.productos_snapshot
        )

        return (
            "Hola, quiero hacer este pedido:\n\n"
            f"Pedido #{pedido.numero_pedido}\n"
            f"{productos}\n\n"
            f"Total: ${int(pedido.total)}\n"
            f"Tipo entrega: {tipo_entrega}\n"
            f"{direccion}"
            f"Cliente: {pedido.nombre_cliente}\n"
            f"Telefono: {pedido.telefono_cliente}\n\n"
            "Puedes ver el estado de tu pedido aqui:\n"
            f"{self.get_tracking_url(pedido)}"
        )

    def generar_mensaje_legacy(self, pedido):
        tipo_entrega = pedido.get_tipo_entrega_display()
        direccion = ""
        if pedido.tipo_entrega == PedidoWhatsApp.TIPO_DELIVERY and pedido.direccion_entrega:
            direccion = f"Direccion:\n{pedido.direccion_entrega}\n\n"

        productos = "\n".join(
            f"* {item['cantidad']} x {item['nombre']} - ${item['subtotal']}"
            for item in pedido.productos_snapshot
        )

        return (
            "Hola, quiero hacer un pedido desde Menly.\n\n"
            f"Cliente: {pedido.nombre_cliente}\n"
            f"Teléfono: {pedido.telefono_cliente}\n"
            f"Tipo de entrega: {tipo_entrega}\n\n"
            f"{direccion}"
            "Productos:\n\n"
            f"{productos}\n\n"
            f"Total: ${int(pedido.total)}\n\n"
            f"Pedido N°: {pedido.numero_pedido}"
        )

    def generar_whatsapp_url(self, telefono, mensaje):
        numero = "".join(ch for ch in str(telefono) if ch.isdigit())
        return f"https://wa.me/{numero}?text={quote(mensaje)}"

    def to_representation(self, pedido):
        return {
            "pedido_id": pedido.id,
            "numero_pedido": pedido.numero_pedido,
            "tracking_token": pedido.tracking_token,
            "tracking_url": self.get_tracking_url(pedido),
            "total": int(pedido.total),
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
            "productos_snapshot",
            "productos",
            "total",
            "estado",
            "estado_display",
            "fecha_creacion",
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
            "productos_snapshot",
            "total",
            "estado_display",
            "fecha_creacion",
            "mensaje_whatsapp_generado",
            "whatsapp_destino",
        ]

    def validate_estado(self, value):
        if value not in dict(PedidoWhatsApp.ESTADOS):
            raise serializers.ValidationError("Estado inválido.")
        return value


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

        cantidades_por_producto = {}
        for item in productos_solicitados:
            producto_id = item["producto_id"]
            cantidades_por_producto[producto_id] = (
                cantidades_por_producto.get(producto_id, 0) + item["cantidad"]
            )

        if not cantidades_por_producto:
            raise serializers.ValidationError({"productos": "Agrega al menos un producto."})

        productos = Producto.objects.filter(
            restaurante=restaurante,
            disponible=True,
            id__in=cantidades_por_producto.keys()
        ).in_bulk()

        if len(productos) != len(cantidades_por_producto):
            raise serializers.ValidationError({
                "productos": "Uno o mas productos no pertenecen a este restaurante o no estan disponibles."
            })

        snapshot = []
        total = 0
        for producto_id, cantidad in cantidades_por_producto.items():
            producto = productos[producto_id]
            precio_unitario = producto.precio
            subtotal = precio_unitario * cantidad
            total += subtotal
            snapshot.append({
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "precio_unitario": int(precio_unitario),
                "cantidad": cantidad,
                "subtotal": int(subtotal),
            })

        data["productos_snapshot"] = snapshot
        data["total"] = total
        return data

    def update(self, instance, validated_data):
        productos_editados = "productos_snapshot" in validated_data

        for attr in ["estado", "direccion_entrega", "productos_snapshot", "total"]:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])

        if productos_editados:
            instance.mensaje_whatsapp_generado = PedidoWhatsAppCreateSerializer().generar_mensaje(instance)

        instance.save()
        return instance


class PedidoWhatsAppEstadoUpdateSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=PedidoWhatsApp.ESTADOS)

    def update(self, instance, validated_data):
        estado_anterior = instance.estado
        estado_nuevo = validated_data["estado"]

        if estado_anterior == estado_nuevo:
            return instance

        instance.estado = estado_nuevo
        instance.save(update_fields=["estado"])
        HistorialEstadoPedidoWhatsApp.objects.create(
            pedido=instance,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            usuario=self.context.get("usuario"),
            observacion=self.context.get("observacion", ""),
        )
        return instance

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
                "cantidad": item.get("cantidad", 0),
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
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = [
            "id",
            "numero_pedido",
            "solicitud_especial",
            "total",
            "estado_display",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        extra_kwargs = {
            "nombre_cliente": {"required": False, "allow_blank": True},
            "telefono_cliente": {"required": False, "allow_blank": True},
            "email_cliente": {"required": False, "allow_blank": True},
            "descripcion_original": {"required": False, "allow_blank": True},
        }

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

    def _buscar_solicitud_relacionada(self, instance):
        if instance.solicitud_especial_id:
            return instance.solicitud_especial

        solicitud = SolicitudEspecial.objects.filter(
            restaurante=instance.restaurante,
            estado="aceptada",
            fecha_evento=instance.fecha_entrega,
            telefono_contacto=instance.telefono_cliente,
            email_contacto=instance.email_cliente,
            descripcion_solicitud=instance.descripcion_original,
        ).order_by("-fecha_creacion", "-id").first()

        if solicitud:
            instance.solicitud_especial = solicitud
            instance.save(update_fields=["solicitud_especial", "fecha_actualizacion"])
            logger.warning(
                "Pedido especial sin solicitud_especial_id fue vinculado por coincidencia",
                extra={
                    "pedido_especial_id": instance.id,
                    "pedido_especial_estado": instance.estado,
                    "pedido_especial_solicitud_id": instance.solicitud_especial_id,
                    "solicitud_estado_anterior": solicitud.estado,
                },
            )

        return solicitud

    def _completar_solicitud_si_entregado(self, instance):
        if str(instance.estado).lower() != PedidoEspecial.ESTADO_ENTREGADO:
            return

        solicitud = self._buscar_solicitud_relacionada(instance)
        logger.info(
            "Sincronizando pedido especial entregado con solicitud especial",
            extra={
                "pedido_especial_id": instance.id,
                "pedido_especial_estado": instance.estado,
                "pedido_especial_solicitud_id": instance.solicitud_especial_id,
                "solicitud_estado_anterior": solicitud.estado if solicitud else None,
            },
        )

        if not solicitud:
            logger.warning(
                "Pedido especial entregado sin solicitud especial relacionada",
                extra={
                    "pedido_especial_id": instance.id,
                    "pedido_especial_estado": instance.estado,
                    "pedido_especial_solicitud_id": instance.solicitud_especial_id,
                },
            )
            return

        if solicitud.estado != "completada":
            estado_anterior = solicitud.estado
            solicitud.estado = "completada"
            solicitud.save(update_fields=["estado", "fecha_actualizacion"])
            logger.info(
                "Solicitud especial completada por pedido especial entregado",
                extra={
                    "pedido_especial_id": instance.id,
                    "pedido_especial_estado": instance.estado,
                    "pedido_especial_solicitud_id": instance.solicitud_especial_id,
                    "solicitud_estado_anterior": estado_anterior,
                    "solicitud_estado_nuevo": solicitud.estado,
                },
            )
        else:
            logger.info(
                "Solicitud especial ya estaba completada",
                extra={
                    "pedido_especial_id": instance.id,
                    "pedido_especial_estado": instance.estado,
                    "pedido_especial_solicitud_id": instance.solicitud_especial_id,
                    "solicitud_estado_anterior": solicitud.estado,
                    "solicitud_estado_nuevo": solicitud.estado,
                },
            )

    def update(self, instance, validated_data):
        validated_data.pop("solicitud_especial", None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            self._completar_solicitud_si_entregado(instance)

        return instance


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


class ProductoCreateSerializer(serializers.ModelSerializer):
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
            "fecha_creacion"
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
