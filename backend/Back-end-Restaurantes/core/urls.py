"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path
from django.http import JsonResponse, HttpResponse
from core.debug_views import debug_time
from menu.views import ProductosMasClickeadosView, menu_api
#from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView
from menu.views import menu_api,CustomLoginView, CookieTokenRefreshView, PasswordResetRequestView, ContactoView, ContactoPlanesAPIView, MiRestauranteView,ProductoListView,ProductoUpdateView, ProductoVariantesView, ProductoVarianteDetalleView, LogoutView,ProductoCreateView, ActualizarDisponibilidadProductoView, EliminarProductoView, HistorialBitacoraView, HistorialPedidosView
from menu.views import CrearReservaPublicaView, ReservasDashboardView,UsuariosView, CrearReservaManualView, ActualizarReservaView, ConfiguracionRestauranteView, RestauranteEstadoAperturaView, UploadLogoView, RestaurantePublicoDetalleView, CrearSolicitudEspecialPublicaView, CrearPedidoWhatsAppPublicoView, SeguimientoPedidoWhatsAppPublicoView, SolicitudesEspecialesDashboardView, SolicitudEspecialDetalleDashboardView
from menu.views import NotificacionesDashboardView, NotificacionesContadorView, NotificacionDetalleView, NotificacionMarcarLeidaView
from menu.views import PedidosWhatsAppDashboardView, PedidoWhatsAppDetalleDashboardView, PedidoWhatsAppEstadoDashboardView, PedidosEspecialesDashboardView, PedidoEspecialDetalleDashboardView, PedidoEspecialEstadoDashboardView, PedidosManualesDashboardView, PedidoManualDetalleDashboardView, PedidoManualEstadoDashboardView, CocinaActivacionDashboardView, CocinaActivarView, CocinaComandasView, CocinaEstadoView, CocinaComandaEstadoView, CocinaCerrarView, PedidosMetricasDashboardView, MetricasResumenView, ReporteMensualMetricasView, ReporteAnualMetricasView, ReportesMetricasView, ReporteMetricaDetalleView, ReporteMetricaGuardarView, DashboardUltimosPedidosView
from menu.views import CategoriasView, CategoriaDetalleView
from menu.views import MesasView, MesaDetalleView,IconosView
from menu.views import HorariosView, HorarioDetalleView
from menu.views import MetodosPagoView, MetodoPagoDetalleView, MetodosPagoPublicosView, ProductoClickView
from menu.views import RespaldosRestauranteView, UltimoRespaldoRestauranteView
from menu.views import PushConfigView, PushSubscriptionStatusView, PushSubscriptionView

urlpatterns = [


    path(f'{settings.ADMIN_URL_PATH}/', admin.site.urls),
    path("healthz/", lambda request: JsonResponse({"status": "ok"}), name="healthz"),
    path("api/debug/time/", debug_time, name="debug-time"),
    path(
        "robots.txt",
        lambda request: HttpResponse(
            "User-agent: *\nAllow: /\nSitemap: https://menly.cl/sitemap.xml\n",
            content_type="text/plain",
        ),
        name="robots",
    ),

    # 🔐 login custom
    path("api/login/", CustomLoginView.as_view(), name="login"),
    path("api/password-reset-request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("api/contacto/", ContactoView.as_view(), name="contacto"),
    path("api/contacto/planes/", ContactoPlanesAPIView.as_view(), name="contacto-planes"),

    # 🔄 refresh token
    path("api/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),

    # 🏪 dashboard privado
    path("api/mi-restaurante/", MiRestauranteView.as_view(), name="mi-restaurante"),
    path("api/push/config/", PushConfigView.as_view(), name="push-config"),
    path("api/push/subscriptions/", PushSubscriptionView.as_view(), name="push-subscriptions"),
    path("api/push/subscriptions/status/", PushSubscriptionStatusView.as_view(), name="push-subscription-status"),
    path("api/dashboard/ultimos-pedidos/", DashboardUltimosPedidosView.as_view(), name="dashboard-ultimos-pedidos"),
    path("api/metricas/reporte-mensual/", ReporteMensualMetricasView.as_view(), name="metricas-reporte-mensual"),
    path("api/metricas/reporte-anual/", ReporteAnualMetricasView.as_view(), name="metricas-reporte-anual"),
    path("api/metricas/reportes/", ReportesMetricasView.as_view(), name="metricas-reportes"),
    path("api/metricas/reportes/guardar/", ReporteMetricaGuardarView.as_view(), name="metricas-reportes-guardar"),
    path("api/metricas/reportes/<int:reporte_id>/", ReporteMetricaDetalleView.as_view(), name="metricas-reporte-detalle"),

    # 🌐 menu público
    path("api/menu/<slug:slug>/", menu_api),
    # 🌐 Restaurante público
    path("api/restaurantes/<slug:slug>/", RestaurantePublicoDetalleView.as_view(), name="restaurante-publico-detalle"),
    # 🌐 reserva público
    path("api/reservas/<slug:slug>/", CrearReservaPublicaView.as_view(), name="crear-reserva-publica"),
    path("api/solicitudes-especiales/<slug:slug>/", CrearSolicitudEspecialPublicaView.as_view(), name="crear-solicitud-especial-publica"),
    path("api/public/pedidos/seguimiento/<str:tracking_token>/", SeguimientoPedidoWhatsAppPublicoView.as_view(), name="seguimiento-pedido-whatsapp-publico"),
    path("api/pedidos-whatsapp/<slug:slug>/", CrearPedidoWhatsAppPublicoView.as_view(), name="crear-pedido-whatsapp-publico"),
    #logoyt
     path("api/logout/", LogoutView.as_view(), name="logout"),
    
    #Productos
    path(
    "api/mi-restaurante/productos/",
    ProductoListView.as_view(),
    name="listar-productos"
    ),

    path(
    "api/mi-restaurante/productos/<int:id>/",
    ActualizarDisponibilidadProductoView.as_view(),
    name="actualizar-disponibilidad-producto"
    ),

    #PRODUCTOS ELMINADOS
    path(
    "api/mi-restaurante/productos/<int:id>/eliminar/",
    EliminarProductoView.as_view(),
    name="eliminar-producto"
    ),

    # AGREGAR PRODUCTO
    path(
        "api/mi-restaurante/productos/agregar/",
        ProductoCreateView.as_view(),
        name="agregar-producto"
    ),
    
    # EDITAR PRODUCTO
    path(
        "api/mi-restaurante/productos/<int:id>/actualizar/",
        ProductoUpdateView.as_view(),
        name="actualizar-producto"
    ),

    path(
        "api/mi-restaurante/productos/<int:producto_id>/variantes/",
        ProductoVariantesView.as_view(),
        name="producto-variantes",
    ),
    path(
        "api/mi-restaurante/productos/<int:producto_id>/variantes/<int:variante_id>/",
        ProductoVarianteDetalleView.as_view(),
        name="producto-variante-detalle",
    ),

    #CLICKS PRODUCTOS
    path("api/productos/<int:pk>/click/", ProductoClickView.as_view(), name="producto-click"),

    path("api/mi-restaurante/productos-mas-clickeados/", ProductosMasClickeadosView.as_view(), name="productos-mas-clickeados"),
    
    #BITACORA 
    path("api/historial/", HistorialBitacoraView.as_view()),
    path("api/historial/pedidos/", HistorialPedidosView.as_view()),


    #RESERVAS

    path(
        "api/reservas/<slug:slug>/",
        CrearReservaPublicaView.as_view(),
        name="crear-reserva-publica"
    ),

    path(
        "api/mi-restaurante/reservas/",
        ReservasDashboardView.as_view(),
        name="reservas-dashboard"
    ),

    path(
        "api/mi-restaurante/reservas/crear/",
        CrearReservaManualView.as_view(),
        name="crear-reserva-manual"
    ),

    path(
        "api/mi-restaurante/reservas/<int:reserva_id>/",
        ActualizarReservaView.as_view(),
        name="actualizar-reserva"
    ),

    path(
        "api/mi-restaurante/solicitudes-especiales/",
        SolicitudesEspecialesDashboardView.as_view(),
        name="solicitudes-especiales-dashboard"
    ),

    path(
        "api/mi-restaurante/solicitudes-especiales/<int:solicitud_id>/",
        SolicitudEspecialDetalleDashboardView.as_view(),
        name="solicitud-especial-dashboard-detalle"
    ),

    path(
        "api/mi-restaurante/notificaciones/",
        NotificacionesDashboardView.as_view(),
        name="notificaciones-dashboard"
    ),

    path(
        "api/mi-restaurante/notificaciones/contador/",
        NotificacionesContadorView.as_view(),
        name="notificaciones-contador"
    ),

    path(
        "api/mi-restaurante/notificaciones/<int:notificacion_id>/",
        NotificacionDetalleView.as_view(),
        name="notificacion-detalle"
    ),

    path(
        "api/mi-restaurante/notificaciones/<int:notificacion_id>/marcar-leida/",
        NotificacionMarcarLeidaView.as_view(),
        name="notificacion-marcar-leida"
    ),

    path(
        "api/mi-restaurante/pedidos/whatsapp/",
        PedidosWhatsAppDashboardView.as_view(),
        name="pedidos-whatsapp-dashboard"
    ),

    path(
        "api/mi-restaurante/pedidos/whatsapp/<int:pedido_id>/",
        PedidoWhatsAppDetalleDashboardView.as_view(),
        name="pedido-whatsapp-dashboard-detalle"
    ),

    path(
        "api/mi-restaurante/pedidos/whatsapp/<int:pedido_id>/estado/",
        PedidoWhatsAppEstadoDashboardView.as_view(),
        name="pedido-whatsapp-dashboard-estado"
    ),

    path(
        "api/pedidos-whatsapp/<int:pedido_id>/estado/",
        PedidoWhatsAppEstadoDashboardView.as_view(),
        name="pedido-whatsapp-estado"
    ),

    path(
        "api/mi-restaurante/pedidos/especiales/",
        PedidosEspecialesDashboardView.as_view(),
        name="pedidos-especiales-dashboard"
    ),

    path(
        "api/mi-restaurante/pedidos/especiales/<int:pedido_id>/",
        PedidoEspecialDetalleDashboardView.as_view(),
        name="pedido-especial-dashboard-detalle"
    ),
    path(
        "api/mi-restaurante/pedidos/especiales/<int:pedido_id>/estado/",
        PedidoEspecialEstadoDashboardView.as_view(),
        name="pedido-especial-dashboard-estado"
    ),

    path(
        "api/mi-restaurante/pedidos/manuales/",
        PedidosManualesDashboardView.as_view(),
        name="pedidos-manuales-dashboard"
    ),

    path(
        "api/pedidos/manuales/",
        PedidosManualesDashboardView.as_view(),
        name="pedidos-manuales"
    ),

    path(
        "api/mi-restaurante/pedidos/manuales/<int:pedido_id>/",
        PedidoManualDetalleDashboardView.as_view(),
        name="pedido-manual-dashboard-detalle"
    ),
    path(
        "api/mi-restaurante/pedidos/manuales/<int:pedido_id>/estado/",
        PedidoManualEstadoDashboardView.as_view(),
        name="pedido-manual-dashboard-estado"
    ),

    path(
        "api/pedidos/manuales/<int:pedido_id>/",
        PedidoManualDetalleDashboardView.as_view(),
        name="pedido-manual-detalle"
    ),

    path(
        "api/mi-restaurante/cocina/activacion/",
        CocinaActivacionDashboardView.as_view(),
        name="cocina-activacion-dashboard"
    ),

    path(
        "api/cocina/activar/<str:token>/",
        CocinaActivarView.as_view(),
        name="cocina-activar"
    ),

    path(
        "api/cocina/comandas/",
        CocinaComandasView.as_view(),
        name="cocina-comandas"
    ),

    path(
        "api/cocina/estado/",
        CocinaEstadoView.as_view(),
        name="cocina-estado"
    ),

    path(
        "api/cocina/comandas/<str:pedido_id>/estado/",
        CocinaComandaEstadoView.as_view(),
        name="cocina-comanda-estado"
    ),

    path(
        "api/cocina/cerrar/",
        CocinaCerrarView.as_view(),
        name="cocina-cerrar"
    ),

    path(
        "api/mi-restaurante/pedidos/metricas/",
        PedidosMetricasDashboardView.as_view(),
        name="pedidos-metricas-dashboard"
    ),
    path(
        "api/mi-restaurante/metricas/resumen/",
        MetricasResumenView.as_view(),
        name="metricas-resumen"
    ),

    #SUBIR FOTO
    path("api/mi-restaurante/upload-logo/", UploadLogoView.as_view()),

    #CONFIGURACION DEL RESTAURANTE 
    path("api/mi-restaurante/configuracion/", ConfiguracionRestauranteView.as_view()),
    path("api/mi-restaurante/estado-apertura/", RestauranteEstadoAperturaView.as_view()),


    #USUARIOS CONFIGURACION SEGUN PERMISOS
    path("api/mi-restaurante/usuarios/<int:user_id>/", UsuariosView.as_view()),
    path("api/mi-restaurante/usuarios/", UsuariosView.as_view()),

    #CATEGORIAS CONFIGURACION
    path("api/mi-restaurante/categorias/", CategoriasView.as_view()),
    path("api/mi-restaurante/categorias/<int:categoria_id>/", CategoriaDetalleView.as_view()),

    #MESAS CONFIGURACION
    path("api/mi-restaurante/mesas/", MesasView.as_view()),
    path("api/mi-restaurante/mesas/<int:mesa_id>/", MesaDetalleView.as_view()),

    #HORARIOS CONFIGURACION
    path("api/mi-restaurante/horarios/", HorariosView.as_view()),
    path("api/mi-restaurante/horarios/<int:horario_id>/", HorarioDetalleView.as_view()),

    #MEOTODOS DE PAGO
    path("api/mi-restaurante/metodos-pago/",MetodosPagoView.as_view(),name="metodos-pago"),
    path("api/mi-restaurante/metodos-pago/<int:pk>/",MetodoPagoDetalleView.as_view(),name="metodo-pago-detalle"),
    path("api/public/restaurantes/<slug:slug>/metodos-pago/", MetodosPagoPublicosView.as_view(), name="metodos-pago-publicos"),

    #RESPALDOS
    path("api/mi-restaurante/respaldos/", RespaldosRestauranteView.as_view(), name="respaldos-restaurante"),
    path("api/mi-restaurante/respaldos/ultimo/", UltimoRespaldoRestauranteView.as_view(), name="ultimo-respaldo-restaurante"),

    #ICONOS
    path("api/iconos/", IconosView.as_view(), name="iconos"),


] #+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
