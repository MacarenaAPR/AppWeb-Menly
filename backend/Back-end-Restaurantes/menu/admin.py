from menu.models import Restaurante,Plan,Icono,ImagenRestaurante, Categoria, Producto, UsuarioRestaurante, BitacoraProducto,Reserva,HorarioAtencion,TurnoOperativo,MetodoPago,Mesa,SolicitudEspecial,Notificacion,PedidoWhatsApp,PedidoEspecial,PedidoManual,PedidoManualItem,PedidoPruebaImportado,RestaurantePedidoSecuencia,ActivacionCocina,SesionCocina,ReporteMetrica,EjecucionReportesMensuales,PushSubscription
from .forms import PedidoPruebaCSVImportForm, ProductoCSVImportForm
from .admin_csv_importers import (
    CSVImportError,
    importar_personalizacion_csv,
    importar_variantes_csv,
)

import csv
import json
import logging
from datetime import date
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.html import format_html
from menu.cache_utils import invalidate_menu_cache
from menu.services.estados_pedidos import (
    CANCELADO,
    EN_PREPARACION,
    ENTREGADO,
    RESULTADO_CANCELADO_OMITIDO,
    RESULTADO_ENTREGADO,
    RESULTADO_YA_ENTREGADO,
    TransicionEstadoInvalida,
    cambiar_estado_pedido,
    marcar_entregado_desde_admin,
    normalizar_estado_actual,
)
from menu.services.reportes_mensuales import (
    generar_reportes_pendientes,
    guardar_reporte_mensual,
)
from menu.services.exportacion_productos import respuesta_csv_productos
from menu.services.importacion_pedidos_prueba import (
    ImportacionPedidosPruebaError,
    importar_pedidos_prueba,
    plantilla_csv_pedidos_prueba,
    validar_csv_pedidos_prueba,
)

logger = logging.getLogger(__name__)


class TenantAdminMixin:
    """Impide que personal no superusuario consulte objetos de otro tenant."""

    tenant_lookup = "restaurante"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        perfil = getattr(request.user, "perfil_restaurante", None)
        if not perfil or not perfil.activo:
            return queryset.none()
        return queryset.filter(**{self.tenant_lookup: perfil.restaurante})


class MarcarProductosListosAdminMixin(TenantAdminMixin):
    actions = ("marcar_productos_listos",)

    def _cantidad_productos(self, pedido):
        if isinstance(pedido, PedidoWhatsApp):
            items = pedido.productos_snapshot or []
        elif isinstance(pedido, PedidoEspecial):
            items = pedido.items or []
        else:
            return sum(max(item.cantidad, 0) for item in pedido.items.all())
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                total += max(int(item.get("cantidad") or 0), 0)
            except (TypeError, ValueError):
                continue
        return total

    @admin.action(description="Marcar todos los productos como listos")
    def marcar_productos_listos(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "No tienes permiso para cambiar pedidos.", messages.ERROR)
            return None

        queryset = queryset.select_related("restaurante")
        if self.model is PedidoManual:
            queryset = queryset.prefetch_related("items")

        if request.POST.get("confirmar_marcar_listos") != "1":
            return TemplateResponse(
                request,
                "admin/pedidos_marcar_listos_confirmacion.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Marcar todos los productos como listos",
                    "pedidos": list(queryset),
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                    "opts": self.model._meta,
                },
            )

        procesados = productos = omitidos = errores = 0
        for pedido in queryset:
            cantidad = self._cantidad_productos(pedido)
            if cantidad == 0 or normalizar_estado_actual(pedido) != EN_PREPARACION:
                omitidos += 1
                continue
            try:
                cambiar_estado_pedido(
                    pedido,
                    "listo",
                    actor=request.user,
                    origen="panel",
                )
                procesados += 1
                productos += cantidad
            except TransicionEstadoInvalida:
                omitidos += 1
            except Exception:
                logger.exception(
                    "Error al marcar productos listos desde Admin",
                    extra={"pedido_modelo": self.model.__name__, "pedido_id": pedido.pk},
                )
                errores += 1

        nivel = messages.WARNING if errores else messages.SUCCESS
        self.message_user(
            request,
            (
                f"Pedidos procesados: {procesados}; productos/unidades marcados: {productos}; "
                f"pedidos omitidos: {omitidos}; errores: {errores}."
            ),
            nivel,
        )
        return None

    @admin.action(description="Marcar pedidos seleccionados como entregados")
    def marcar_pedidos_entregados(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, "No tienes permiso para cambiar pedidos.", messages.ERROR)
            return None

        queryset = queryset.select_related("restaurante")
        estados = [normalizar_estado_actual(pedido) for pedido in queryset]
        cancelados = estados.count(CANCELADO)
        ya_entregados = estados.count(ENTREGADO)
        actualizables = len(estados) - cancelados - ya_entregados

        if request.POST.get("confirmar_marcar_entregados") != "1":
            return TemplateResponse(
                request,
                "admin/pedidos_marcar_entregados_confirmacion.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Marcar pedidos seleccionados como entregados",
                    "pedidos": list(queryset),
                    "actualizables": actualizables,
                    "cancelados": cancelados,
                    "ya_entregados": ya_entregados,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                    "opts": self.model._meta,
                },
            )

        entregados = cancelados = ya_entregados = errores = 0
        for pedido in queryset:
            try:
                _pedido, resultado = marcar_entregado_desde_admin(
                    pedido,
                    actor=request.user,
                )
                if resultado == RESULTADO_ENTREGADO:
                    entregados += 1
                elif resultado == RESULTADO_CANCELADO_OMITIDO:
                    cancelados += 1
                elif resultado == RESULTADO_YA_ENTREGADO:
                    ya_entregados += 1
            except Exception:
                logger.exception(
                    "Error al marcar pedido entregado desde Admin",
                    extra={"pedido_modelo": self.model.__name__, "pedido_id": pedido.pk},
                )
                errores += 1

        mensaje = (
            f"{entregados} pedidos marcados como entregados. "
            f"{cancelados} pedidos cancelados omitidos. "
            f"{ya_entregados} pedidos ya entregados sin cambios."
        )
        if errores:
            mensaje += f" {errores} pedidos con errores."
        self.message_user(
            request,
            mensaje,
            messages.WARNING if errores else messages.SUCCESS,
        )
        return None


class ReporteAnioFilter(admin.SimpleListFilter):
    title = "año del período"
    parameter_name = "periodo_anio_filtro"

    def lookups(self, request, model_admin):
        valores = (
            model_admin.get_queryset(request)
            .exclude(periodo_anio__isnull=True)
            .exclude(periodo_anio="")
            .values_list("periodo_anio", flat=True)
            .distinct()
            .order_by("-periodo_anio")
        )
        return [(valor, valor) for valor in valores]

    def queryset(self, request, queryset):
        return queryset.filter(periodo_anio=self.value()) if self.value() else queryset


class ReporteMesFilter(admin.SimpleListFilter):
    title = "mes del período"
    parameter_name = "periodo_mes_filtro"

    def lookups(self, request, model_admin):
        return [(f"{mes:02d}", f"{mes:02d}") for mes in range(1, 13)]

    def queryset(self, request, queryset):
        return queryset.filter(periodo_mes__endswith=f"-{self.value()}") if self.value() else queryset


class GenerarReporteMensualForm(forms.Form):
    restaurante = forms.ModelChoiceField(queryset=Restaurante.objects.none())
    anio = forms.IntegerField(min_value=2000, max_value=9999, label="Año")
    mes = forms.TypedChoiceField(
        choices=[(mes, f"{mes:02d}") for mes in range(1, 13)],
        coerce=int,
        label="Mes",
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        restaurantes = Restaurante.objects.order_by("nombre_empresa")
        if request and not request.user.is_superuser:
            perfil = getattr(request.user, "perfil_restaurante", None)
            restaurantes = (
                restaurantes.filter(pk=perfil.restaurante_id)
                if perfil and perfil.activo
                else restaurantes.none()
            )
        self.fields["restaurante"].queryset = restaurantes

    def clean(self):
        cleaned = super().clean()
        anio = cleaned.get("anio")
        mes = cleaned.get("mes")
        if anio and mes:
            periodo = date(anio, mes, 1)
            hoy = timezone.localdate()
            if periodo >= date(hoy.year, hoy.month, 1):
                raise forms.ValidationError(
                    "Sólo se pueden guardar reportes de meses calendario cerrados."
                )
        return cleaned



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
class ProductoAdmin(TenantAdminMixin, admin.ModelAdmin):
    actions = ("exportar_productos_seleccionados_csv",)
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
                "exportar-todos-csv/",
                self.admin_site.admin_view(self.exportar_todos_csv),
                name="exportar_todos_productos_csv",
            ),
            path(
                "importar-csv/",
                self.admin_site.admin_view(self.importar_csv),
                name="importar_productos_csv",
            ),
            path(
                "importar-variantes-csv/",
                self.admin_site.admin_view(self.importar_variantes_csv),
                name="importar_variantes_csv",
            ),
            path(
                "importar-personalizacion-csv/",
                self.admin_site.admin_view(self.importar_personalizacion_csv),
                name="importar_personalizacion_csv",
            ),
        ]

        return custom_urls + urls

    @admin.action(description="Exportar productos seleccionados a CSV")
    def exportar_productos_seleccionados_csv(self, request, queryset):
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return respuesta_csv_productos(
            queryset,
            nombre_archivo="productos-seleccionados-menly.csv",
        )

    def exportar_todos_csv(self, request):
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return respuesta_csv_productos(
            self.get_queryset(request),
            nombre_archivo="todos-los-productos-menly.csv",
        )
    
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

    def _importar_catalogo_csv(self, request, *, importador, titulo, mensaje_resultado):
        form = ProductoCSVImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                resultado = importador(request.FILES["archivo_csv"].read())
            except CSVImportError as exc:
                for error in exc.errores[:20]:
                    messages.error(request, error)
                if len(exc.errores) > 20:
                    messages.error(request, f"Hay {len(exc.errores) - 20} errores más.")
            except Exception as exc:
                messages.error(
                    request,
                    f"No se importó ningún registro debido a un error: {exc}",
                )
            else:
                messages.success(request, mensaje_resultado(resultado))
                return redirect("..")

        return render(
            request,
            "admin/importar_catalogo_csv.html",
            {
                "form": form,
                "title": titulo,
            },
        )

    def importar_variantes_csv(self, request):
        return self._importar_catalogo_csv(
            request,
            importador=importar_variantes_csv,
            titulo="Importar variantes desde CSV",
            mensaje_resultado=lambda resultado: (
                "Importación terminada. "
                f"Variantes creadas: {resultado['creados']}. "
                f"Variantes actualizadas: {resultado['actualizados']}."
            ),
        )

    def importar_personalizacion_csv(self, request):
        return self._importar_catalogo_csv(
            request,
            importador=importar_personalizacion_csv,
            titulo="Importar personalización desde CSV",
            mensaje_resultado=lambda resultado: (
                "Importación terminada. "
                f"Grupos creados: {resultado['grupos_creados']}. "
                f"Grupos actualizados: {resultado['grupos_actualizados']}. "
                f"Opciones creadas: {resultado['opciones_creadas']}. "
                f"Opciones actualizadas: {resultado['opciones_actualizadas']}."
            ),
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
class PedidoWhatsAppAdmin(MarcarProductosListosAdminMixin, admin.ModelAdmin):
    actions = (
        "marcar_productos_listos",
        "marcar_pedidos_entregados",
    )
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


    list_filter = (
        "estado", "tipo_entrega",
        ("restaurante", admin.RelatedOnlyFieldListFilter), "fecha_creacion",
    )
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


@admin.register(RestaurantePedidoSecuencia)
class RestaurantePedidoSecuenciaAdmin(admin.ModelAdmin):
    list_display = ("restaurante", "ultimo_numero", "fecha_actualizacion")
    search_fields = ("restaurante__nombre_empresa", "restaurante__slug")
    readonly_fields = ("restaurante", "ultimo_numero", "fecha_actualizacion")


@admin.register(TurnoOperativo)
class TurnoOperativoAdmin(admin.ModelAdmin):
    list_display = (
        "restaurante",
        "inicio",
        "fin_programado",
        "origen_inicio",
        "cerrado",
    )
    list_filter = ("cerrado", "origen_inicio", "restaurante")
    search_fields = ("restaurante__nombre_empresa", "restaurante__slug")
    readonly_fields = (
        "restaurante",
        "inicio",
        "fin_programado",
        "fecha_operativa",
        "origen_inicio",
        "cerrado",
        "fecha_cierre_real",
        "creado_en",
        "actualizado_en",
    )


@admin.register(PedidoEspecial)
class PedidoEspecialAdmin(MarcarProductosListosAdminMixin, admin.ModelAdmin):
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
    list_filter = (
        "estado", "fecha_entrega",
        ("restaurante", admin.RelatedOnlyFieldListFilter), "fecha_creacion",
    )
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
class PedidoManualAdmin(MarcarProductosListosAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/pedidomanual_changelist.html"
    actions = (
        "marcar_productos_listos",
        "marcar_pedidos_entregados",
    )
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
    list_filter = (
        "estado", "tipo_entrega", "origen",
        ("restaurante", admin.RelatedOnlyFieldListFilter), "fecha_creacion",
    )
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

    def get_urls(self):
        urls = super().get_urls()
        propios = [
            path(
                "importar-pruebas-csv/",
                self.admin_site.admin_view(self.importar_pedidos_prueba_csv),
                name="importar_pedidos_prueba_csv",
            ),
            path(
                "plantilla-pruebas-csv/",
                self.admin_site.admin_view(self.descargar_plantilla_pedidos_prueba),
                name="plantilla_pedidos_prueba_csv",
            ),
        ]
        return propios + urls

    def _verificar_superusuario_importacion(self, request):
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

    def descargar_plantilla_pedidos_prueba(self, request):
        self._verificar_superusuario_importacion(request)
        response = HttpResponse(
            plantilla_csv_pedidos_prueba(),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="plantilla-pedidos-prueba-menly.csv"'
        )
        return response

    def importar_pedidos_prueba_csv(self, request):
        self._verificar_superusuario_importacion(request)
        session_key = "menly_preview_pedidos_prueba_csv"

        if request.method == "POST" and request.POST.get("confirmar") == "1":
            pendiente = request.session.get(session_key)
            if not pendiente:
                messages.error(request, "La vista previa expiró. Vuelve a cargar el CSV.")
                return redirect(".")
            try:
                resultado = importar_pedidos_prueba(
                    pendiente["contenido"],
                    actor=request.user,
                    archivo_origen=pendiente["archivo"],
                )
            except ImportacionPedidosPruebaError as exc:
                for error in exc.errores[:30]:
                    messages.error(request, error)
            except Exception as exc:
                messages.error(request, f"No se importó ningún pedido: {exc}")
            else:
                request.session.pop(session_key, None)
                messages.success(
                    request,
                    (
                        f"Pedidos de prueba creados: {resultado['pedidos_creados']}; "
                        f"ítems creados: {resultado['items_creados']}."
                    ),
                )
                return redirect("../")

        form = PedidoPruebaCSVImportForm(request.POST or None, request.FILES or None)
        validacion = None
        resumen_pedidos = []
        preparar = False
        if request.method == "POST" and "confirmar" not in request.POST and form.is_valid():
            archivo = form.cleaned_data["archivo_csv"]
            try:
                contenido = archivo.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                form.add_error("archivo_csv", "El archivo debe estar codificado en UTF-8.")
            else:
                validacion = validar_csv_pedidos_prueba(contenido)
                resumen_pedidos = [
                    {
                        "identificador_externo": pedido["identificador_externo"],
                        "restaurante": pedido["restaurante"].nombre_empresa,
                        "fecha": timezone.localtime(pedido["fecha_creacion"]),
                        "estado": pedido["estado"],
                        "items": len(pedido["items"]),
                        "total": int(pedido["total"]),
                    }
                    for pedido in validacion["pedidos"]
                ]
                preparar = (
                    form.cleaned_data["modo"] == PedidoPruebaCSVImportForm.MODO_PREPARAR
                    and not validacion["errores"]
                )
                if preparar:
                    request.session[session_key] = {
                        "contenido": contenido,
                        "archivo": archivo.name,
                    }
                else:
                    request.session.pop(session_key, None)

        return TemplateResponse(
            request,
            "admin/importar_pedidos_prueba_csv.html",
            {
                **self.admin_site.each_context(request),
                "title": "Importar pedidos de prueba CSV",
                "form": form,
                "validacion": validacion,
                "resumen_pedidos": resumen_pedidos,
                "preparar": preparar,
                "importacion_habilitada": settings.TEST_ORDER_IMPORT_ENABLED,
                "opts": self.model._meta,
            },
        )


@admin.register(PedidoPruebaImportado)
class PedidoPruebaImportadoAdmin(admin.ModelAdmin):
    list_display = (
        "identificador_externo",
        "restaurante",
        "pedido_manual",
        "archivo_origen",
        "fila_inicio",
        "creado_por",
        "fecha_importacion",
    )
    list_filter = ("restaurante", "fecha_importacion")
    search_fields = (
        "identificador_externo",
        "restaurante__nombre_empresa",
        "restaurante__slug",
    )
    readonly_fields = (
        "restaurante",
        "identificador_externo",
        "pedido_manual",
        "archivo_origen",
        "fila_inicio",
        "datos_origen",
        "creado_por",
        "fecha_importacion",
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
class ReporteMetricaAdmin(TenantAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/reportemetrica_changelist.html"
    actions = ("regenerar_reportes_mensuales",)
    list_display = (
        "id",
        "restaurante",
        "anio_reporte",
        "mes_reporte",
        "total_pedidos_reporte",
        "monto_total_reporte",
        "fecha_generacion",
        "estado_reporte",
        "descargar_csv",
    )
    list_filter = (
        "tipo", "activo", ("restaurante", admin.RelatedOnlyFieldListFilter), ReporteAnioFilter,
        ReporteMesFilter, "fecha_generacion",
    )
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

    def get_urls(self):
        urls = super().get_urls()
        propios = [
            path(
                "generar-mensual/",
                self.admin_site.admin_view(self.generar_reporte_mensual),
                name="menu_reportemetrica_generar_mensual",
            ),
            path(
                "generar-pendientes/",
                self.admin_site.admin_view(self.generar_reportes_pendientes_view),
                name="menu_reportemetrica_generar_pendientes",
            ),
            path(
                "<int:reporte_id>/descargar-csv/",
                self.admin_site.admin_view(self.descargar_reporte_csv),
                name="menu_reportemetrica_descargar_csv",
            )
        ]
        return propios + urls

    def changelist_view(self, request, extra_context=None):
        ultima_ejecucion = (
            EjecucionReportesMensuales.objects.first()
            if request.user.is_superuser
            else None
        )
        return super().changelist_view(
            request,
            extra_context={
                **(extra_context or {}),
                "title": "Reportes mensuales",
                "ultima_ejecucion": ultima_ejecucion,
                "mostrar_ultima_ejecucion": request.user.is_superuser,
            },
        )

    @admin.display(description="Año", ordering="periodo_anio")
    def anio_reporte(self, reporte):
        return reporte.periodo_anio or (reporte.periodo_mes or "")[:4]

    @admin.display(description="Mes", ordering="periodo_mes")
    def mes_reporte(self, reporte):
        return (reporte.periodo_mes or "-").split("-")[-1]

    @admin.display(description="Total de pedidos")
    def total_pedidos_reporte(self, reporte):
        resumen = reporte.resumen or {}
        return resumen.get("total_pedidos", resumen.get("pedidos_creados", 0))

    @admin.display(description="Monto total registrado")
    def monto_total_reporte(self, reporte):
        resumen = reporte.resumen or {}
        monto = resumen.get(
            "monto_pedidos_no_cancelados",
            resumen.get("venta_real", 0),
        )
        return f"${int(monto or 0):,}".replace(",", ".")

    @admin.display(description="Estado", boolean=False)
    def estado_reporte(self, reporte):
        return "Vigente" if reporte.activo else "Inactivo"

    @admin.display(description="Descarga")
    def descargar_csv(self, reporte):
        url = reverse("admin:menu_reportemetrica_descargar_csv", args=[reporte.pk])
        return format_html('<a href="{}">CSV</a>', url)

    def descargar_reporte_csv(self, request, reporte_id):
        reporte = self.get_queryset(request).filter(pk=reporte_id).first()
        if not reporte or not self.has_view_permission(request, reporte):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="reporte-{reporte.restaurante.slug}-'
            f'{reporte.periodo_mes or reporte.periodo_anio}.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["seccion", "indicador", "valor"])
        writer.writerow(["reporte", "restaurante", reporte.restaurante.nombre_empresa])
        writer.writerow(["reporte", "periodo", reporte.periodo_mes or reporte.periodo_anio])
        writer.writerow(["reporte", "fecha_generacion", reporte.fecha_generacion.isoformat()])
        for clave, valor in (reporte.resumen or {}).items():
            writer.writerow(["resumen", clave, valor])
        for seccion, contenido in (reporte.datos or {}).items():
            if seccion in {"resumen", "restaurante"}:
                continue
            if isinstance(contenido, dict):
                for clave, valor in contenido.items():
                    writer.writerow([seccion, clave, valor])
            elif isinstance(contenido, list):
                for indice, valor in enumerate(contenido, start=1):
                    writer.writerow([seccion, indice, json.dumps(valor, ensure_ascii=False)])
            else:
                writer.writerow(["reporte", seccion, contenido])
        return response

    def _verificar_permiso_gestion(self, request):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

    def generar_reporte_mensual(self, request):
        self._verificar_permiso_gestion(request)
        hoy = timezone.localdate()
        mes = 12 if hoy.month == 1 else hoy.month - 1
        anio = hoy.year - 1 if hoy.month == 1 else hoy.year
        form = GenerarReporteMensualForm(
            request.POST or None,
            request=request,
            initial={"anio": anio, "mes": mes},
        )
        if request.method == "POST" and form.is_valid():
            restaurante = form.cleaned_data["restaurante"]
            reporte, creado = guardar_reporte_mensual(
                restaurante,
                form.cleaned_data["anio"],
                form.cleaned_data["mes"],
            )
            self.message_user(
                request,
                (
                    f"Reporte {reporte.periodo_mes} generado correctamente."
                    if creado
                    else f"El reporte {reporte.periodo_mes} ya existía y no fue sobrescrito."
                ),
                messages.SUCCESS if creado else messages.WARNING,
            )
            return redirect("admin:menu_reportemetrica_changelist")
        return TemplateResponse(
            request,
            "admin/reporte_mensual_generar.html",
            {
                **self.admin_site.each_context(request),
                "title": "Generar reporte mensual",
                "form": form,
                "opts": self.model._meta,
            },
        )

    def generar_reportes_pendientes_view(self, request):
        self._verificar_permiso_gestion(request)
        restaurantes = Restaurante.objects.order_by("id")
        if not request.user.is_superuser:
            perfil = getattr(request.user, "perfil_restaurante", None)
            restaurantes = (
                restaurantes.filter(pk=perfil.restaurante_id)
                if perfil and perfil.activo
                else restaurantes.none()
            )
        if request.method == "POST" and request.POST.get("confirmar") == "1":
            resultado = generar_reportes_pendientes(restaurantes=restaurantes)
            nivel = messages.WARNING if resultado["errores"] else messages.SUCCESS
            self.message_user(
                request,
                (
                    f"Reportes generados: {resultado['generados']}; "
                    f"ya existentes: {resultado['existentes']}; "
                    f"errores: {len(resultado['errores'])}."
                ),
                nivel,
            )
            for error in resultado["errores"]:
                logger.error("Error generando reporte histórico", extra=error)
            return redirect("admin:menu_reportemetrica_changelist")
        return TemplateResponse(
            request,
            "admin/reportes_pendientes_confirmacion.html",
            {
                **self.admin_site.each_context(request),
                "title": "Generar reportes pendientes",
                "restaurantes": restaurantes.count(),
                "opts": self.model._meta,
            },
        )

    @admin.action(description="Regenerar reporte mensual seleccionado")
    def regenerar_reportes_mensuales(self, request, queryset):
        self._verificar_permiso_gestion(request)
        mensuales = queryset.filter(tipo=ReporteMetrica.TIPO_MENSUAL)
        omitidos = queryset.count() - mensuales.count()
        if request.POST.get("confirmar_regeneracion") != "1":
            return TemplateResponse(
                request,
                "admin/reportes_regenerar_confirmacion.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Regenerar reportes mensuales",
                    "reportes": list(queryset),
                    "mensuales": mensuales.count(),
                    "omitidos": omitidos,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                    "opts": self.model._meta,
                },
            )

        regenerados = errores = 0
        for reporte in mensuales.select_related("restaurante"):
            try:
                anio, mes = map(int, reporte.periodo_mes.split("-"))
                hoy = timezone.localdate()
                if date(anio, mes, 1) >= date(hoy.year, hoy.month, 1):
                    omitidos += 1
                    continue
                guardar_reporte_mensual(
                    reporte.restaurante,
                    anio,
                    mes,
                    regenerar=True,
                )
                regenerados += 1
            except Exception:
                errores += 1
                logger.exception(
                    "Error regenerando reporte mensual desde Admin",
                    extra={"reporte_id": reporte.pk},
                )
        self.message_user(
            request,
            (
                f"Reportes regenerados: {regenerados}; "
                f"omitidos: {omitidos}; errores: {errores}."
            ),
            messages.WARNING if errores else messages.SUCCESS,
        )


@admin.register(EjecucionReportesMensuales)
class EjecucionReportesMensualesAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_inicio",
        "fecha_fin",
        "modo",
        "periodo",
        "estado",
        "restaurantes_procesados",
        "reportes_generados",
        "reportes_existentes",
        "cantidad_errores",
    )
    list_filter = ("modo", "estado", "incluye_inactivos", "fecha_inicio")
    readonly_fields = (
        "modo",
        "periodo",
        "incluye_inactivos",
        "estado",
        "fecha_inicio",
        "fecha_fin",
        "restaurantes_procesados",
        "reportes_generados",
        "reportes_existentes",
        "cantidad_errores",
        "detalle",
    )
    ordering = ("-fecha_inicio",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
