import django
from django.db import models
from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone


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
    #creado por chatgpt luego esto lo verificas codex
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

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADO = "confirmado"
    ESTADO_EN_PREPARACION = "en_preparacion"
    ESTADO_LISTO = "listo"
    ESTADO_ENTREGADO = "entregado"
    ESTADO_CANCELADO = "cancelado"
    ESTADO_COMPLETADO = "completado"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADO, "Confirmado"),
        (ESTADO_EN_PREPARACION, "En preparación"),
        (ESTADO_LISTO, "Listo"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_CANCELADO, "Cancelado"),
        (ESTADO_COMPLETADO, "Completado"),
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
    productos_snapshot = models.JSONField()
    total = models.DecimalField(max_digits=10, decimal_places=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
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


class Notificacion(models.Model):
    TIPO_RESERVA = "reserva"
    TIPO_SOLICITUD_ESPECIAL = "solicitud_especial"

    TIPOS = [
        (TIPO_RESERVA, "Reserva"),
        (TIPO_SOLICITUD_ESPECIAL, "Solicitud especial"),
    ]

    MODELO_RESERVA = "Reserva"
    MODELO_SOLICITUD_ESPECIAL = "SolicitudEspecial"

    MODELOS_REFERENCIA = [
        (MODELO_RESERVA, "Reserva"),
        (MODELO_SOLICITUD_ESPECIAL, "Solicitud especial"),
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
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurante", "nombre"],
                name="unique_metodo_pago_por_restaurante"
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.restaurante.nombre_empresa}"

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


