from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from .models import UsuarioRestaurante,ImagenRestaurante, HorarioAtencion, MetodoPago, Mesa, RespaldoRestaurante
from rest_framework import serializers
from .models import Producto, Categoria, Reserva, Restaurante, Icono, SolicitudEspecial
from django.contrib.auth.models import User

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

class RestauranteConfigSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

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
        ]

    def get_logo_url(self, obj):
        if not obj.logo:
            return None

        try:
            return obj.logo.url
        except Exception:
            return None


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
