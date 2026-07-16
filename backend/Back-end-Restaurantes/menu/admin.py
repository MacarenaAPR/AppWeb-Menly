from menu.models import Restaurante,Plan,Icono,ImagenRestaurante, Categoria, Producto, UsuarioRestaurante, BitacoraProducto,Reserva,HorarioAtencion,MetodoPago,Mesa,SolicitudEspecial,Notificacion,PedidoWhatsApp,PedidoEspecial,PedidoManual,PedidoManualItem,ActivacionCocina,SesionCocina,ReporteMetrica,PushSubscription
from .forms import ProductoCSVImportForm

import csv
from decimal import Decimal

from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from menu.cache_utils import invalidate_menu_cache



@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "slug", "activo", "fecha_creacion", "fecha_actualizacion")
    list_filter = ("activo",)
    search_fields = ("nombre", "slug", "descripcion")
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ("id",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(Restaurante)
class RestauranteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre_empresa",
        "slug",
        "plan",
        "telefono",
        "ciudad",
        "activo",
        "abierto",
        "delivery_activo",
        "reservas_activas",
        "solicitudes_especiales_activas",
        "carrito_whatsapp_activo",
        "pedidos_pos",
        "metricas_activas",
        "fecha_creacion",
        "imgen_principal",
        "imgen_form",
    )
    list_filter = (
        "activo",
        "abierto",
        "delivery_activo",
        "reservas_activas",
        "solicitudes_especiales_activas",
        "carrito_whatsapp_activo",
        "pedidos_pos",
        "metricas_activas",
        "plan",
        "ciudad",
    )
    search_fields = ("nombre_empresa", "rut", "telefono", "email_contacto", "slug")
    prepopulated_fields = {"slug": ("nombre_empresa",)}
    ordering = ("nombre_empresa",)
    fieldsets = (
        (None, {
            "fields": (
                "nombre_empresa",
                "rut",
                "slug",
                "plan",
                "activo",
                "abierto",
                "fecha_creacion",
            )
        }),
        ("Contacto y presencia", {
            "fields": (
                "telefono",
                "email_contacto",
                "direccion",
                "ciudad",
                "whatsapp",
                "instagram",
                "facebook",
                "google_maps",
                "sitio_web",
                "link_delivery",
            )
        }),
        ("Contenido", {
            "fields": (
                "descripcion",
                "slogan",
                "mensaje_bienvenida",
                "theme_color",
                "imgen_principal",
                "imgen_form",
                "logo",
            )
        }),
        ("Notificaciones", {
            "fields": (
                "notificar_reservas",
                "email_notificacion",
            )
        }),
        ("Modulos SaaS", {
            "fields": (
                "reservas_activas",
                "solicitudes_especiales_activas",
                "carrito_whatsapp_activo",
                "pedidos_pos",
                "delivery_activo",
                "metricas_activas",
            )
        }),
    )
    readonly_fields = ("fecha_creacion",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if any(
            field in form.changed_data
            for field in [
                "reservas_activas",
                "solicitudes_especiales_activas",
                "carrito_whatsapp_activo",
                "pedidos_pos",
                "delivery_activo",
                "abierto",
                "metricas_activas",
            ]
        ):
            invalidate_menu_cache(obj)

@admin.register(ImagenRestaurante)
class ImagenRestauranteAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "label", "activa", "orden", "fecha_creacion")
    list_filter = ("restaurante", "activa", "label")
    search_fields = ("restaurante__nombre_empresa", "label")
    ordering = ("restaurante", "orden")

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "restaurante", "orden", "activa")
    list_filter = ("activa", "restaurante")
    search_fields = ("nombre", "restaurante__nombre_empresa")
    ordering = ("restaurante", "orden")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "restaurante",
        "categoria",
        "precio",
        "disponible",
        "destacado",
        "orden",
        "fecha_creacion",
    )
    list_filter = ("disponible", "destacado", "restaurante", "categoria")
    search_fields = ("nombre", "descripcion", "restaurante__nombre_empresa", "categoria__nombre")
    ordering = ("restaurante", "categoria", "orden")
    readonly_fields = ("fecha_creacion",)

    
    change_list_template = "admin/productos_changelist.html"

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "importar-csv/",
                self.admin_site.admin_view(self.importar_csv),
                name="importar_productos_csv",
            ),
        ]

        return custom_urls + urls
    
    def importar_csv(self, request):
        if request.method == "POST":
            form = ProductoCSVImportForm(request.POST, request.FILES)

            if form.is_valid():
                archivo = request.FILES["archivo_csv"]

                decoded_file = archivo.read().decode("utf-8-sig").splitlines()
                reader = csv.DictReader(decoded_file)

                creados = 0
                actualizados = 0
                errores = []

                for index, row in enumerate(reader, start=2):
                    try:
                        restaurante_slug = row["restaurante_slug"].strip()
                        categoria_nombre = row["categoria"].strip()
                        nombre = row["nombre"].strip()

                        if not restaurante_slug or not categoria_nombre or not nombre:
                            errores.append(f"Fila {index}: restaurante, categoría o nombre vacío.")
                            continue

                        restaurante = Restaurante.objects.get(slug=restaurante_slug)

                        categoria, _ = Categoria.objects.get_or_create(
                            restaurante=restaurante,
                            nombre=categoria_nombre,
                            defaults={
                                "orden": 0,
                                "activa": True,
                            },
                        )

                        precio = Decimal(row["precio"].strip() or "0")

                        disponible = str(row.get("disponible", "True")).lower() in [
                            "true", "1", "sí", "si", "yes"
                        ]

                        destacado = str(row.get("destacado", "False")).lower() in [
                            "true", "1", "sí", "si", "yes"
                        ]

                        orden = int(row.get("orden", 0) or 0)

                        producto, created = Producto.objects.update_or_create(
                            restaurante=restaurante,
                            nombre=nombre,
                            defaults={
                                "categoria": categoria,
                                "descripcion": row.get("descripcion", "").strip(),
                                "condiciones": row.get("condiciones", "").strip(),
                                "precio": precio,
                                "disponible": disponible,
                                "destacado": destacado,
                                "orden": orden,
                            },
                        )

                        if created:
                            creados += 1
                        else:
                            actualizados += 1

                    except Restaurante.DoesNotExist:
                        errores.append(
                            f"Fila {index}: restaurante con slug '{restaurante_slug}' no existe."
                        )

                    except Exception as e:
                        errores.append(f"Fila {index}: {str(e)}")

                if errores:
                    for error in errores[:10]:
                        messages.error(request, error)

                    if len(errores) > 10:
                        messages.error(
                            request,
                            f"Hay {len(errores) - 10} errores más."
                        )

                messages.success(
                    request,
                    f"Importación terminada. Creados: {creados}. Actualizados: {actualizados}."
                )

                return redirect("..")

        else:
            form = ProductoCSVImportForm()

        return render(
            request,
            "admin/importar_productos_csv.html",
            {"form": form},
        )


@admin.register(UsuarioRestaurante)
class UsuarioRestauranteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "restaurante", "rol", "activo", "creado_por", "fecha_creacion")
    list_filter = ("rol", "activo", "restaurante")
    search_fields = ("user__username", "user__email", "restaurante__nombre_empresa")
    ordering = ("restaurante", "rol")
    readonly_fields = ("fecha_creacion",)


@admin.register(BitacoraProducto)
class BitacoraProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "producto_nombre", "accion", "usuario", "fecha")
    list_filter = ("accion", "restaurante", "fecha")
    search_fields = ("producto_nombre", "descripcion", "usuario__username", "usuario__email")
    ordering = ("-fecha",)
    readonly_fields = ("fecha",)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "nombre_cliente",
        "telefono",
        "fecha",
        "hora",
        "cantidad_personas",
        "estado",
        "mesa_asignada",
        "creada_por",
        "gestionada_por",
        "fecha_creacion",
    )
    list_filter = ("estado", "fecha", "restaurante")
    search_fields = (
        "nombre_cliente",
        "telefono",
        "email",
        "mesa_asignada",
        "restaurante__nombre_empresa",
    )
    ordering = ("fecha", "hora")
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(SolicitudEspecial)
class SolicitudEspecialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "nombre",
        "apellido",
        "telefono_contacto",
        "email_contacto",
        "fecha_evento",
        "estado",
        "fecha_creacion",
    )
    list_filter = ("estado", "fecha_evento", "restaurante")
    search_fields = (
        "nombre",
        "apellido",
        "telefono_contacto",
        "email_contacto",
        "descripcion_solicitud",
        "restaurante__nombre_empresa",
        "restaurante__slug",
    )
    ordering = ("-fecha_creacion",)
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "tipo",
        "titulo",
        "leida",
        "fecha_creacion",
        "fecha_lectura",
        "referencia_modelo",
        "referencia_id",
    )
    list_filter = ("tipo", "leida", "restaurante", "fecha_creacion")
    search_fields = (
        "titulo",
        "mensaje",
        "restaurante__nombre_empresa",
        "restaurante__slug",
        "referencia_modelo",
    )
    ordering = ("-fecha_creacion",)
    readonly_fields = ("fecha_creacion", "fecha_lectura")


@admin.register(PedidoWhatsApp)
class PedidoWhatsAppAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero_pedido",
        "restaurante",
        "nombre_cliente",
        "telefono_cliente",
        "tipo_entrega",
        "total",
        "estado",
        "fecha_creacion",
    )
    list_filter = ("estado", "tipo_entrega", "restaurante", "fecha_creacion")
    search_fields = (
        "nombre_cliente",
        "telefono_cliente",
        "restaurante__nombre_empresa",
        "restaurante__slug",
        "whatsapp_destino",
    )
    ordering = ("-fecha_creacion",)
    readonly_fields = (
        "numero_pedido",
        "estado",
        "fecha_creacion",
        "productos_snapshot",
        "mensaje_whatsapp_generado",
        "whatsapp_destino",
        "total",
    )


@admin.register(PedidoEspecial)
class PedidoEspecialAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero_pedido",
        "restaurante",
        "nombre_cliente",
        "telefono_cliente",
        "fecha_entrega",
        "total",
        "estado",
        "fecha_creacion",
    )
    list_filter = ("estado", "fecha_entrega", "restaurante", "fecha_creacion")
    search_fields = (
        "nombre_cliente",
        "telefono_cliente",
        "email_cliente",
        "descripcion_original",
        "restaurante__nombre_empresa",
        "restaurante__slug",
    )
    ordering = ("-fecha_creacion",)
    readonly_fields = (
        "numero_pedido",
        "estado",
        "fecha_creacion",
        "fecha_actualizacion",
        "total",
    )


class PedidoManualItemInline(admin.TabularInline):
    model = PedidoManualItem
    extra = 0
    readonly_fields = (
        "producto", "variante", "nombre_producto", "variante_nombre",
        "precio_unitario", "cantidad", "subtotal", "observaciones",
    )
    can_delete = False


@admin.register(PedidoManual)
class PedidoManualAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero_pedido",
        "restaurante",
        "origen",
        "nombre_cliente",
        "tipo_entrega",
        "total",
        "estado",
        "creado_por",
        "fecha_creacion",
    )
    list_filter = ("estado", "tipo_entrega", "origen", "restaurante", "fecha_creacion")
    search_fields = (
        "nombre_cliente",
        "telefono_cliente",
        "numero_mesa",
        "direccion",
        "restaurante__nombre_empresa",
        "restaurante__slug",
    )
    ordering = ("-fecha_creacion",)
    readonly_fields = (
        "numero_pedido",
        "estado",
        "origen",
        "subtotal",
        "total",
        "creado_por",
        "fecha_creacion",
        "fecha_actualizacion",
    )
    inlines = [PedidoManualItemInline]


@admin.register(ActivacionCocina)
class ActivacionCocinaAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "creado_por", "creado_en", "expira_en", "consumido_en", "activa")
    list_filter = ("activa", "restaurante")
    search_fields = ("restaurante__nombre_empresa", "creado_por__username")
    readonly_fields = ("token_hash", "creado_en", "consumido_en")
    ordering = ("-creado_en",)


@admin.register(SesionCocina)
class SesionCocinaAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "fecha_operativa", "creado_en", "expira_en", "cerrada_en", "activa")
    list_filter = ("activa", "fecha_operativa", "restaurante")
    search_fields = ("restaurante__nombre_empresa",)
    readonly_fields = ("token_hash", "creado_en", "cerrada_en")
    ordering = ("-creado_en",)


@admin.register(ReporteMetrica)
class ReporteMetricaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "tipo",
        "periodo_mes",
        "periodo_anio",
        "titulo",
        "fecha_generacion",
        "generado_por",
        "activo",
    )
    list_filter = ("tipo", "activo", "restaurante", "fecha_generacion")
    search_fields = (
        "titulo",
        "periodo_mes",
        "periodo_anio",
        "restaurante__nombre_empresa",
        "restaurante__slug",
        "generado_por__username",
        "generado_por__email",
    )
    ordering = ("-fecha_generacion",)
    readonly_fields = (
        "fecha_generacion",
        "resumen",
        "datos",
    )


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurante",
        "dia",
        "hora_apertura",
        "hora_cierre",
        "cerrado",
        "activo",
    )
    list_filter = ("restaurante", "dia", "cerrado", "activo")
    search_fields = ("restaurante__nombre_empresa",)
    ordering = ("restaurante", "dia")


@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "nombre", "activo")
    list_filter = ("restaurante", "activo")
    search_fields = ("nombre", "restaurante__nombre_empresa")
    ordering = ("restaurante", "nombre")


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "numero", "nombre", "activa")
    list_filter = ("restaurante", "activa")
    search_fields = ("nombre", "restaurante__nombre_empresa")
    ordering = ("restaurante", "numero")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurante", "usuario", "tipo_dispositivo", "activo", "fecha_actualizacion")
    list_filter = ("tipo_dispositivo", "activo", "restaurante")
    search_fields = ("restaurante__nombre_empresa", "usuario__username")
    readonly_fields = ("endpoint", "p256dh", "auth", "fecha_creacion", "fecha_actualizacion")

@admin.register(Icono)
class IconoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "clase_css")
    search_fields = ("nombre",)
    ordering = ("nombre",)
