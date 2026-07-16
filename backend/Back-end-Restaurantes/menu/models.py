import django
import hashlib
import secrets
from django.db import models
from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


class Icono(models.Model):
    nombre = models.CharField(max_length=100)  # Ej: "Hamburguesa"
    
    clase_css = models.CharField(
        max_length=50,
        unique=True,
        help_text="Clase de Font Awesome. Ej: bi-egg-fried"
    )

    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def __str__(self):
        return f"{self.nombre} ({self.clase_css})"


class Plan(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nombre


class Restaurante(models.Model):
    
    nombre_empresa = models.CharField(max_length=150)
    rut = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=20)
    email_contacto = models.EmailField()
    notificar_reservas = models.BooleanField(default=True)
    email_notificacion = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=255)
    ciudad = models.CharField(max_length=100)
    imgen_principal = CloudinaryField("imagen_principal", blank=True, null=True)
    imgen_form= CloudinaryField("imagen_form", blank=True, null=True)
    logo = CloudinaryField("logo", blank=True, null=True)
    descripcion = models.TextField(blank=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    google_maps = models.URLField(blank=True, null=True)
    sitio_web = models.URLField(blank=True, null=True)
    link_delivery = models.URLField(blank=True, null=True)
    
    slug = models.SlugField(unique=True)
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="restaurantes"
    )
    
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    slogan = models.CharField(max_length=255, blank=True)
    mensaje_bienvenida = models.TextField(blank=True)
    theme_color = models.CharField(max_length=7, blank=True, null=True)  

    reservas_activas = models.BooleanField(default=True)
    solicitudes_especiales_activas = models.BooleanField(default=False)
    carrito_whatsapp_activo = models.BooleanField(default=False)
    pedidos_pos = models.BooleanField(default=False, verbose_name="Pedidos POS activos")
    delivery_activo = models.BooleanField(default=False)
    abierto = models.BooleanField(default=True)
    apertura_excepcional_hasta = models.DateTimeField(null=True, blank=True)
    metricas_activas = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["slug", "activo"], name="rest_slug_activo_idx"),
            models.Index(fields=["fecha_creacion"], name="rest_fecha_creacion_idx"),
        ]

    def __str__(self):
        return self.nombre_empresa
    

class ImagenRestaurante(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="imagenes"
    )

    label = models.CharField(
        max_length=100,
        help_text="Ej: portada, galeria, interior, comida, etc"
    )

    imagen = CloudinaryField(
        "imagen",
        blank=True,
        null=True
    )

    orden = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden"]
        indexes = [
            models.Index(fields=["restaurante", "activa", "orden"], name="img_rest_activa_orden_idx"),
        ]

    def __str__(self):
        return f"{self.restaurante.nombre_empresa} - {self.label}"
    
class Categoria(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    orden = models.IntegerField(default=0)
    activa = models.BooleanField(default=True)
    icono = models.ForeignKey(
        Icono,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categorias"
    )
    class Meta:
        ordering = ["orden"]
        indexes = [
            models.Index(fields=["restaurante", "activa", "orden"], name="cat_rest_activa_orden_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "nombre"],
                name="unique_categoria_por_restaurante"
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.restaurante.nombre_empresa}"

class Producto(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="productos"
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name="productos"
    )

    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    condiciones = models.TextField(blank=True)

    precio = models.DecimalField(max_digits=8, decimal_places=0)

    imagen = CloudinaryField("imagen", blank=True, null=True)

    disponible = models.BooleanField(default=True)
    destacado = models.BooleanField(default=False)

    orden = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    clicks = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ["orden"]
        indexes = [
            models.Index(fields=["restaurante", "categoria", "disponible", "orden"], name="prod_menu_lookup_idx"),
            models.Index(fields=["restaurante", "clicks"], name="prod_clicks_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "nombre"],
                name="unique_producto_por_restaurante"
            ),
            models.UniqueConstraint(
                fields=["restaurante", "categoria", "orden"],
                name="unique_orden_por_categoria"
            )
        ]

    def clean(self):
        if self.categoria and self.restaurante:
            if self.categoria.restaurante_id != self.restaurante_id:
                raise ValidationError({
                    "categoria": "La categoría seleccionada no pertenece al restaurante elegido."
                })

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} - {self.restaurante.nombre_empresa}"


class ProductoVariante(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="variantes",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=8, decimal_places=0)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden", "id"]
        indexes = [
            models.Index(fields=["producto", "activo", "orden"], name="prodvar_prod_act_orden_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(precio__gte=0),
                name="producto_variante_precio_no_negativo",
            ),
            models.UniqueConstraint(
                fields=["producto", "nombre"],
                name="unique_variante_nombre_por_producto",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.nombre}"

class UsuarioRestaurante(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_restaurante"
    )

    restaurante = models.ForeignKey(
        "Restaurante",
        on_delete=models.CASCADE,
        related_name="usuarios"
    )

    ROL_CHOICES = [
        ("dueno", "Dueño"),
        ("admin", "Administrador"),
        ("empleado", "Empleado"),
    ]

    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default="empleado"
    )
    creado_por = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios_creados"
    )


    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurante")

    def __str__(self):
        return f"{self.user.email} - {self.restaurante.nombre_empresa} ({self.rol})"

class BitacoraProducto(models.Model):
    ACCIONES = [
        ("CREADO", "Creado"),
        ("EDITADO", "Editado"),
        ("ELIMINADO", "Eliminado"),
        ("DISPONIBLE", "Cambio de disponibilidad"),
        ("PRECIO", "Cambio de precio"),
        ("ORDEN", "Cambio de orden"),
    ]

    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE)
    producto_id = models.IntegerField(null=True, blank=True)
    producto_nombre = models.CharField(max_length=150)
    usuario = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)

    accion = models.CharField(max_length=20, choices=ACCIONES)
    descripcion = models.TextField()

    valor_anterior = models.TextField(blank=True, null=True)
    valor_nuevo = models.TextField(blank=True, null=True)

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha"], name="bit_rest_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.accion} - {self.producto_nombre}"

class Reserva(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("rechazada", "Rechazada"),
        ("cancelada", "Cancelada"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="reservas"
    )

    creada_por = models.ForeignKey(
        UsuarioRestaurante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_creadas"
    )

    gestionada_por = models.ForeignKey(
        UsuarioRestaurante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_gestionadas"
    )

    nombre_cliente = models.CharField(max_length=120)
    telefono = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)

    fecha = models.DateField()
    hora = models.TimeField()
    cantidad_personas = models.PositiveIntegerField()

    mensaje = models.TextField(blank=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )

    mesa_asignada = models.CharField(max_length=50, blank=True, null=True)
    observacion_admin = models.TextField(blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha_creacion"], name="res_rest_creacion_idx"),
            models.Index(fields=["restaurante", "fecha", "hora", "estado"], name="res_rest_fecha_hora_idx"),
            models.Index(fields=["restaurante", "estado"], name="res_rest_estado_idx"),
        ]

    def __str__(self):
        return f"{self.nombre_cliente} - {self.fecha} {self.hora}"


class SolicitudEspecial(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("en_revision", "En revisión"),
        ("aceptada", "Aceptada"),
        ("rechazada", "Rechazada"),
        ("completada", "Completada"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="solicitudes_especiales"
    )

    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120)
    fecha_evento = models.DateField()
    telefono_contacto = models.CharField(max_length=30)
    email_contacto = models.EmailField()
    descripcion_solicitud = models.TextField()
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha_creacion"], name="solesp_rest_creacion_idx"),
            models.Index(fields=["restaurante", "estado"], name="solesp_rest_estado_idx"),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.restaurante.nombre_empresa}"


class PedidoWhatsApp(models.Model):
    TIPO_DELIVERY = "delivery"
    TIPO_RETIRO_LOCAL = "retiro_local"
    TIPO_PARA_LLEVAR = "para_llevar"

    TIPOS_ENTREGA = [
        (TIPO_DELIVERY, "Delivery"),
        (TIPO_RETIRO_LOCAL, "Retiro en local"),
        (TIPO_PARA_LLEVAR, "Para llevar"),
    ]

    ESTADO_RECIBIDO = "recibido"
    ESTADO_PENDIENTE_CONFIRMACION = "pendiente_confirmacion"
    ESTADO_PENDIENTE = ESTADO_PENDIENTE_CONFIRMACION
    ESTADO_CONFIRMADO = "confirmado"
    ESTADO_EN_PREPARACION = "en_preparacion"
    ESTADO_LISTO = "listo"
    ESTADO_EN_REPARTO = "en_reparto"
    ESTADO_EN_DELIVERY = ESTADO_EN_REPARTO
    ESTADO_ENTREGADO = "entregado"
    ESTADO_CANCELADO = "cancelado"

    ESTADOS = [
        (ESTADO_RECIBIDO, "Pedido recibido"),
        (ESTADO_PENDIENTE_CONFIRMACION, "Pendiente de confirmacion"),
        (ESTADO_CONFIRMADO, "Confirmado"),
        (ESTADO_EN_PREPARACION, "En preparación"),
        (ESTADO_LISTO, "Listo"),
        (ESTADO_EN_REPARTO, "En reparto"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_CANCELADO, "Cancelado"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="pedidos_whatsapp"
    )
    numero_pedido = models.PositiveIntegerField()
    nombre_cliente = models.CharField(max_length=120)
    telefono_cliente = models.CharField(max_length=30)
    tipo_entrega = models.CharField(max_length=20, choices=TIPOS_ENTREGA)
    direccion_entrega = models.TextField(blank=True, null=True)
    metodo_pago = models.ForeignKey(
        "MetodoPago",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pedidos_whatsapp",
    )
    metodo_pago_nombre = models.CharField(max_length=100, blank=True, default="")
    productos_snapshot = models.JSONField()
    total = models.DecimalField(max_digits=10, decimal_places=0)
    tracking_token = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    estado = models.CharField(max_length=30, choices=ESTADOS, default=ESTADO_RECIBIDO)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion_estado = models.DateTimeField(default=timezone.now)
    mensaje_whatsapp_generado = models.TextField()
    whatsapp_destino = models.CharField(max_length=30)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha_creacion"], name="pedw_rest_fecha_idx"),
            models.Index(fields=["restaurante", "estado"], name="pedw_rest_estado_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "numero_pedido"],
                name="unique_pedido_whatsapp_numero_por_rest"
            )
        ]

    def __str__(self):
        return f"Pedido WhatsApp #{self.numero_pedido} - {self.restaurante.nombre_empresa}"

    @staticmethod
    def generar_tracking_token():
        return secrets.token_urlsafe(12)

    def save(self, *args, **kwargs):
        if not self.tracking_token:
            for _ in range(8):
                token = self.generar_tracking_token()
                if not PedidoWhatsApp.objects.filter(tracking_token=token).exists():
                    self.tracking_token = token
                    break

        if not self.tracking_token:
            raise ValidationError("No se pudo generar un token de seguimiento unico.")

        estado_cambio = self._state.adding
        if not self._state.adding and self.pk:
            estado_anterior = (
                PedidoWhatsApp.objects
                .filter(pk=self.pk)
                .values_list("estado", flat=True)
                .first()
            )
            estado_cambio = estado_anterior != self.estado

        if estado_cambio:
            self.fecha_actualizacion_estado = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"fecha_actualizacion_estado"}

        super().save(*args, **kwargs)


class PedidoIdempotencia(models.Model):
    ESTADO_PROCESANDO = "procesando"
    ESTADO_COMPLETADO = "completado"

    ESTADOS = [
        (ESTADO_PROCESANDO, "Procesando"),
        (ESTADO_COMPLETADO, "Completado"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="idempotencias_pedidos",
    )
    clave = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    pedido_whatsapp = models.OneToOneField(
        PedidoWhatsApp,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idempotencia",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PROCESANDO,
    )
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    respuesta = models.JSONField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "clave"],
                name="unique_idempotencia_pedido_por_rest",
            )
        ]

    def __str__(self):
        return f"{self.restaurante.slug}: {self.clave} ({self.estado})"


class HistorialEstadoPedidoWhatsApp(models.Model):
    ORIGEN_PANEL = "panel"
    ORIGEN_KDS = "kds"
    ORIGEN_SISTEMA = "sistema"
    ORIGENES = [
        (ORIGEN_PANEL, "Panel"),
        (ORIGEN_KDS, "KDS"),
        (ORIGEN_SISTEMA, "Sistema"),
    ]

    pedido = models.ForeignKey(
        PedidoWhatsApp,
        on_delete=models.CASCADE,
        related_name="historial_estados"
    )
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="historial_estados_pedidos_whatsapp"
    )
    observacion = models.TextField(blank=True)
    origen = models.CharField(max_length=20, choices=ORIGENES, default=ORIGEN_SISTEMA)

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["pedido", "-fecha"], name="histpedw_pedido_fecha_idx"),
        ]

    def __str__(self):
        return f"Pedido WhatsApp #{self.pedido.numero_pedido}: {self.estado_anterior} -> {self.estado_nuevo}"


class PedidoEspecial(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADO = "confirmado"
    ESTADO_EN_PREPARACION = "en_preparacion"
    ESTADO_LISTO = "listo"
    ESTADO_ENTREGADO = "entregado"
    ESTADO_CANCELADO = "cancelado"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADO, "Confirmado"),
        (ESTADO_EN_PREPARACION, "En preparación"),
        (ESTADO_LISTO, "Listo"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_CANCELADO, "Cancelado"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="pedidos_especiales"
    )
    solicitud_especial = models.ForeignKey(
        SolicitudEspecial,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="pedidos_especiales"
    )
    numero_pedido = models.PositiveIntegerField()
    nombre_cliente = models.CharField(max_length=120)
    telefono_cliente = models.CharField(max_length=30)
    email_cliente = models.EmailField(blank=True)
    descripcion_original = models.TextField(blank=True)
    items = models.JSONField()
    total = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_entrega = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha_creacion"], name="pedesp_rest_fecha_idx"),
            models.Index(fields=["restaurante", "estado"], name="pedesp_rest_estado_idx"),
            models.Index(fields=["restaurante", "fecha_entrega"], name="pedesp_rest_entrega_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "numero_pedido"],
                name="unique_pedido_especial_numero_por_rest"
            )
        ]

    def __str__(self):
        return f"Pedido especial #{self.numero_pedido} - {self.restaurante.nombre_empresa}"


class PedidoManual(models.Model):
    ORIGEN_MENLY = "menly"

    ORIGENES = [
        (ORIGEN_MENLY, "Menly"),
    ]

    TIPO_MESA = "mesa"
    TIPO_RETIRO = "retiro"
    TIPO_DELIVERY = "delivery"
    TIPO_PARA_LLEVAR = "para_llevar"

    TIPOS_ENTREGA = [
        (TIPO_MESA, "Mesa"),
        (TIPO_RETIRO, "Retiro"),
        (TIPO_DELIVERY, "Delivery"),
        (TIPO_PARA_LLEVAR, "Para llevar"),
    ]

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_PREPARANDO = "preparando"
    ESTADO_LISTO = "listo"
    ESTADO_EN_REPARTO = "en_reparto"
    ESTADO_ENTREGADO = "entregado"
    ESTADO_CANCELADO = "cancelado"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_PREPARANDO, "Preparando"),
        (ESTADO_LISTO, "Listo"),
        (ESTADO_EN_REPARTO, "En reparto"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_CANCELADO, "Cancelado"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="pedidos_manuales"
    )
    numero_pedido = models.PositiveIntegerField()
    origen = models.CharField(max_length=20, choices=ORIGENES, default=ORIGEN_MENLY)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
    nombre_cliente = models.CharField(max_length=120, blank=True)
    telefono_cliente = models.CharField(max_length=30, blank=True)
    tipo_entrega = models.CharField(max_length=20, choices=TIPOS_ENTREGA)
    direccion = models.TextField(blank=True)
    numero_mesa = models.CharField(max_length=30, blank=True)
    observaciones = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    tracking_token = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_manuales_creados"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "-fecha_creacion"], name="pedman_rest_fecha_idx"),
            models.Index(fields=["restaurante", "estado"], name="pedman_rest_estado_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "numero_pedido"],
                name="unique_pedido_manual_numero_por_rest"
            )
        ]

    def __str__(self):
        return f"Pedido Menly #{self.numero_pedido} - {self.restaurante.nombre_empresa}"

    @staticmethod
    def generar_tracking_token():
        return secrets.token_urlsafe(12)

    def save(self, *args, **kwargs):
        if not self.tracking_token:
            for _ in range(8):
                token = self.generar_tracking_token()
                if (
                    not PedidoManual.objects.filter(tracking_token=token).exists()
                    and not PedidoWhatsApp.objects.filter(tracking_token=token).exists()
                ):
                    self.tracking_token = token
                    break

        if not self.tracking_token:
            raise ValidationError("No se pudo generar un token de seguimiento unico.")

        super().save(*args, **kwargs)


class HistorialEstadoPedidoManual(models.Model):
    pedido = models.ForeignKey(
        PedidoManual,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="historial_estados_pedidos_manuales",
    )
    origen = models.CharField(
        max_length=20,
        choices=HistorialEstadoPedidoWhatsApp.ORIGENES,
        default=HistorialEstadoPedidoWhatsApp.ORIGEN_SISTEMA,
    )

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["pedido", "-fecha"], name="histpedm_pedido_fecha_idx"),
        ]


class HistorialEstadoPedidoEspecial(models.Model):
    pedido = models.ForeignKey(
        PedidoEspecial,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="historial_estados_pedidos_especiales",
    )
    origen = models.CharField(
        max_length=20,
        choices=HistorialEstadoPedidoWhatsApp.ORIGENES,
        default=HistorialEstadoPedidoWhatsApp.ORIGEN_SISTEMA,
    )

    class Meta:
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["pedido", "-fecha"], name="histpede_pedido_fecha_idx"),
        ]


class PedidoManualItem(models.Model):
    pedido = models.ForeignKey(
        PedidoManual,
        on_delete=models.CASCADE,
        related_name="items"
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_pedidos_manuales"
    )
    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_pedidos_manuales",
    )
    nombre_producto = models.CharField(max_length=150)
    variante_nombre = models.CharField(max_length=100, blank=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["pedido"], name="pedman_item_pedido_idx"),
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.nombre_producto}"


class ActivacionCocina(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="activaciones_cocina",
    )
    token_hash = models.CharField(max_length=128, unique=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="activaciones_cocina_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    consumido_en = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["restaurante", "-creado_en"], name="actcoc_rest_creado_idx"),
            models.Index(fields=["token_hash"], name="actcoc_token_hash_idx"),
        ]

    @staticmethod
    def generar_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hashear_token(token):
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @classmethod
    def crear(cls, restaurante, usuario, expira_en):
        token = cls.generar_token()
        activacion = cls.objects.create(
            restaurante=restaurante,
            creado_por=usuario,
            token_hash=cls.hashear_token(token),
            expira_en=expira_en,
        )
        return activacion, token

    @property
    def consumida(self):
        return self.consumido_en is not None

    def puede_consumirse(self):
        return self.activa and not self.consumida and timezone.now() <= self.expira_en


class SesionCocina(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="sesiones_cocina",
    )
    token_hash = models.CharField(max_length=128, unique=True)
    fecha_operativa = models.DateField()
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    cerrada_en = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["restaurante", "fecha_operativa", "activa"], name="sescoc_rest_fecha_idx"),
            models.Index(fields=["token_hash"], name="sescoc_token_hash_idx"),
        ]

    @staticmethod
    def generar_token():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hashear_token(token):
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @classmethod
    def crear(cls, restaurante, expira_en):
        token = cls.generar_token()
        sesion = cls.objects.create(
            restaurante=restaurante,
            token_hash=cls.hashear_token(token),
            fecha_operativa=timezone.localdate(),
            expira_en=expira_en,
        )
        return sesion, token

    def esta_vigente(self):
        return (
            self.activa
            and self.cerrada_en is None
            and timezone.now() <= self.expira_en
            and self.restaurante.activo
            and self.restaurante.pedidos_pos
        )


class Notificacion(models.Model):
    TIPO_RESERVA = "reserva"
    TIPO_SOLICITUD_ESPECIAL = "solicitud_especial"
    TIPO_PEDIDO = "pedido"

    TIPOS = [
        (TIPO_RESERVA, "Reserva"),
        (TIPO_SOLICITUD_ESPECIAL, "Solicitud especial"),
        (TIPO_PEDIDO, "Pedido"),
    ]

    MODELO_RESERVA = "Reserva"
    MODELO_SOLICITUD_ESPECIAL = "SolicitudEspecial"
    MODELO_PEDIDO_WHATSAPP = "PedidoWhatsApp"
    MODELO_PEDIDO_ESPECIAL = "PedidoEspecial"

    MODELOS_REFERENCIA = [
        (MODELO_RESERVA, "Reserva"),
        (MODELO_SOLICITUD_ESPECIAL, "Solicitud especial"),
        (MODELO_PEDIDO_WHATSAPP, "Pedido WhatsApp"),
        (MODELO_PEDIDO_ESPECIAL, "Pedido especial"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="notificaciones"
    )
    tipo = models.CharField(max_length=30, choices=TIPOS)
    titulo = models.CharField(max_length=160)
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    fecha_lectura = models.DateTimeField(blank=True, null=True)
    referencia_id = models.PositiveIntegerField()
    referencia_modelo = models.CharField(max_length=40, choices=MODELOS_REFERENCIA)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["restaurante", "leida", "-fecha_creacion"], name="notif_rest_leida_fecha_idx"),
            models.Index(fields=["restaurante", "tipo"], name="notif_rest_tipo_idx"),
            models.Index(fields=["referencia_modelo", "referencia_id"], name="notif_referencia_idx"),
        ]

    def __str__(self):
        estado = "leida" if self.leida else "pendiente"
        return f"{self.titulo} - {self.restaurante.nombre_empresa} ({estado})"


class ReporteMetrica(models.Model):
    TIPO_MENSUAL = "mensual"
    TIPO_ANUAL = "anual"

    TIPOS = [
        (TIPO_MENSUAL, "Mensual"),
        (TIPO_ANUAL, "Anual"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="reportes_metricas"
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    periodo_mes = models.CharField(max_length=7, blank=True, null=True)
    periodo_anio = models.CharField(max_length=4, blank=True, null=True)
    titulo = models.CharField(max_length=180)
    resumen = models.JSONField(default=dict)
    datos = models.JSONField(default=dict)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    generado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reportes_metricas_generados"
    )
    archivo_pdf = models.FileField(upload_to="reportes_metricas/", blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha_generacion"]
        indexes = [
            models.Index(fields=["restaurante", "tipo", "-fecha_generacion"], name="repmet_rest_tipo_fecha_idx"),
            models.Index(fields=["restaurante", "periodo_mes"], name="repmet_rest_mes_idx"),
            models.Index(fields=["restaurante", "periodo_anio"], name="repmet_rest_anio_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "tipo", "periodo_mes"],
                condition=models.Q(tipo="mensual", activo=True),
                name="unique_reporte_mensual_rest_periodo"
            ),
            models.UniqueConstraint(
                fields=["restaurante", "tipo", "periodo_anio"],
                condition=models.Q(tipo="anual", activo=True),
                name="unique_reporte_anual_rest_periodo"
            ),
        ]

    def __str__(self):
        periodo = self.periodo_mes if self.tipo == self.TIPO_MENSUAL else self.periodo_anio
        return f"{self.get_tipo_display()} {periodo} - {self.restaurante.nombre_empresa}"


class HorarioAtencion(models.Model):
    DIAS_SEMANA = [
        (1, "Lunes"),
        (2, "Martes"),
        (3, "Miércoles"),
        (4, "Jueves"),
        (5, "Viernes"),
        (6, "Sábado"),
        (7, "Domingo"),
    ]

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="horarios"
    )

    dia = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)

    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)

    cerrado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["dia"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "dia"],
                name="unique_horario_por_restaurante_dia"
            )
        ]

    def __str__(self):
        estado = "Cerrado" if self.cerrado else f"{self.hora_apertura} - {self.hora_cierre}"
        return f"{self.restaurante.nombre_empresa} | {self.get_dia_display()} | {estado}"

class MetodoPago(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="metodos_pago"
    )

    nombre = models.CharField(max_length=100)
    codigo = models.SlugField(max_length=50)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "nombre"],
                name="unique_metodo_pago_por_restaurante"
            ),
            models.UniqueConstraint(
                fields=["restaurante", "codigo"],
                name="unique_codigo_metodo_pago_por_restaurante",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.restaurante.nombre_empresa}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            base = slugify(self.nombre)[:40] or "metodo-pago"
            codigo = base
            sufijo = 2
            existentes = MetodoPago.objects.filter(restaurante_id=self.restaurante_id)
            if self.pk:
                existentes = existentes.exclude(pk=self.pk)
            while existentes.filter(codigo=codigo).exists():
                codigo = f"{base[:45]}-{sufijo}"
                sufijo += 1
            self.codigo = codigo
        super().save(*args, **kwargs)

class Mesa(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="mesas"
    )

    numero = models.PositiveIntegerField()
    nombre = models.CharField(max_length=50, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "numero"],
                name="unique_mesa_por_restaurante"
            )
        ]

    def __str__(self):
        return f"Mesa {self.numero} - {self.restaurante.nombre_empresa}"


class RespaldoRestaurante(models.Model):
    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="respaldos",
        db_index=True
    )
    fecha_respaldo = models.DateTimeField(auto_now_add=True)
    responsable = models.ForeignKey(
        UsuarioRestaurante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respaldos_creados"
    )
    nombre_responsable = models.CharField(max_length=150)
    nombre_restaurante = models.CharField(max_length=150)
    # Si el respaldo crece mucho, conviene paginar/exportar por seccion o moverlo a storage externo.
    datos_json = models.JSONField()

    class Meta:
        ordering = ["-fecha_respaldo"]

    def __str__(self):
        return f"Respaldo {self.nombre_restaurante} - {self.fecha_respaldo}"


class PushSubscription(models.Model):
    TIPO_PANEL = "panel"
    TIPO_KDS = "kds"
    TIPOS_DISPOSITIVO = (
        (TIPO_PANEL, "Panel"),
        (TIPO_KDS, "KDS"),
    )

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.CASCADE,
        related_name="suscripciones_push",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suscripciones_push",
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    tipo_dispositivo = models.CharField(
        max_length=10,
        choices=TIPOS_DISPOSITIVO,
        default=TIPO_PANEL,
    )
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha_actualizacion",)
        indexes = [
            models.Index(
                fields=("restaurante", "tipo_dispositivo", "activo"),
                name="push_rest_tipo_activo_idx",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_dispositivo_display()} - {self.restaurante.nombre_empresa}"


