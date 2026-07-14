# Auditoría técnica, funcional, de seguridad y arquitectura de Menly

**Fecha de corte:** 13 de julio de 2026  
**Alcance:** `backend/Back-end-Restaurantes`, `Frontend/restaurante-front`, `Frontend/restaurante-landings`, configuración, migraciones, tests y scripts de carga existentes.  
**Método:** análisis estático completo de las 261 rutas inventariadas, trazado frontend → API → serializer/servicio → modelo, búsquedas de accesos ORM, revisión de permisos y ejecución local segura. No se modificó código, dependencias ni esquema. El único archivo creado es este informe.

## 1. Resumen ejecutivo

Menly ya es más que un menú QR: tiene una base SaaS funcional con menú y landing por slug, administración por restaurante, tres familias de pedidos, seguimiento público, KDS con sesión independiente, reservas, solicitudes especiales, métricas, horarios, métodos de pago, respaldos y roles. El aislamiento multi-tenant de los CRUD principales está implementado en backend y fue confirmado tanto por lectura como por 25 pruebas de KDS/tenant que pasaron.

La conclusión importante es matizada: **no se encontró una consulta activa que permita a un usuario del restaurante A leer o modificar por ID los pedidos, productos, reservas, horarios, usuarios, reportes o comandas del restaurante B**. El KDS tampoco acepta un `restaurante_id` del cliente: obtiene el tenant desde una sesión de cocina validada en backend y vuelve a filtrar cada consulta y cambio de estado por ese restaurante.

Sin embargo, Menly todavía no está listo para operar con restaurantes reales sin una fase de endurecimiento. Los principales bloqueadores no son una fuga multi-tenant confirmada, sino integridad operacional y control comercial: el backend permite crear pedidos públicos aunque la tienda esté cerrada; no hay idempotencia; los estados de pedidos WhatsApp/especiales admiten saltos y retrocesos; panel y KDS pueden sobrescribirse sin control de concurrencia; una cookie KDS única por host puede cambiar silenciosamente todas las pestañas a otra cocina; los reportes guardados confían en JSON financiero enviado por el navegador; los reportes omiten pedidos manuales; los empleados pueden consultar métricas en backend aunque la UI las oculte; los planes casi no se hacen cumplir; y existen dependencias fijadas con avisos vigentes.

**Veredicto:** **APTO PARA PRUEBA CONTROLADA**. No apto aún para piloto con operación real ni para producción multi-restaurante.

### Conteo de hallazgos

| Severidad | Cantidad |
|---|---:|
| Crítica | 0 |
| Alta | 11 |
| Media | 19 |
| Baja | 7 |
| **Total** | **37** |

La ausencia de hallazgos críticos significa que no se confirmó mezcla directa de tenants ni toma de control inmediata. No significa ausencia de bloqueadores: varios hallazgos altos pueden perder, duplicar, aceptar o contabilizar mal pedidos reales.

## 2. Nivel general de madurez

| Área | Madurez | Evaluación basada en código |
|---|---|---|
| Arquitectura base | Media | Separación clara entre API, panel y landing, pero una sola app Django y archivos monolíticos concentran demasiado dominio. |
| Multi-tenant | Media-alta | El tenant se deriva del perfil/sesión y se filtra en backend. Hay helpers, índices y tests específicos. Falta convertir esta disciplina en una abstracción obligatoria para reducir regresiones. |
| KDS | Media | Sesión independiente, tokens fuertes, cookie HttpOnly y filtros backend correctos. Falta manejo multi-pantalla, concurrencia y revocación operativa. |
| Pedidos | Media-baja | Precios públicos se recalculan y hay snapshots/transacciones, pero no hay idempotencia ni una máquina de estados común y estricta. |
| Autenticación | Media | Access en memoria, refresh HttpOnly rotado y blacklist. La inactividad es controlada solo por React y el modelo de revocación es limitado. |
| Planes/suscripción | Baja | `Plan` es descriptivo; las capacidades se gobiernan principalmente con flags manuales. Solo reportes tienen una barrera de plan explícita. |
| Métricas/reportes | Media-baja | Buen aislamiento tenant y criterios explícitos, pero reportes incompletos, costosos y guardados desde payload cliente. |
| Calidad/pruebas | Media | 4.662 líneas de tests backend con casos críticos; no hay tests frontend y ambos linters fallan. |
| Preparación productiva | Baja-media | Builds correctos y settings con controles productivos, pero dependencias vulnerables, carga de archivos, observabilidad y operación requieren trabajo. |

## 3. Arquitectura actual

### 3.1 Estructura

```text
Proyecto Menly/
├─ backend/Back-end-Restaurantes/
│  ├─ core/                 settings, URLs, middleware, ASGI/WSGI
│  ├─ menu/                 única app de dominio
│  │  ├─ models.py          1.099 líneas, 19 modelos de dominio
│  │  ├─ serializers.py     1.672 líneas
│  │  ├─ views.py           3.704 líneas, casi toda la API
│  │  ├─ permissions.py     roles y helpers tenant
│  │  ├─ services/          cocina, pedidos WhatsApp, horarios, métricas
│  │  ├─ signals.py         invalidación de caché de menú
│  │  ├─ admin.py           administración e importación CSV
│  │  └─ tests.py           4.662 líneas
│  └─ templates/admin/      UI de importación CSV
├─ Frontend/restaurante-front/
│  └─ src/                  panel, KDS y páginas comerciales públicas
├─ Frontend/restaurante-landings/
│  └─ src/                  landing/menu/tracking por slug o subdominio
└─ load-tests/              dos scripts k6 solo para menú público
```

No hay Celery, colas, tareas asíncronas, Channels ni WebSockets. La actualización es por polling. Redis es opcional y se usa solo como caché; sin `REDIS_URL`, cada proceso usa `LocMemCache` (`core/settings.py:235-256`).

### 3.2 Modelos y relaciones principales

| Modelo | Relación tenant/dominio | Evidencia |
|---|---|---|
| `Restaurante` | Tenant raíz; slug único, plan, flags y estado de apertura | `menu/models.py:46-96` |
| `UsuarioRestaurante` | `OneToOne(User)` + FK a un restaurante + rol | `models.py:253-292` |
| `Categoria` | FK obligatoria a restaurante; nombre único por tenant | `models.py:134-156` |
| `Producto` | FK a restaurante y categoría; valida coherencia de tenant | `models.py:161-213` |
| `ProductoVariante` | FK al producto; precio y unicidad por producto | `models.py:220-248` |
| `Reserva` | FK a restaurante; autores/gestores vía perfil | `models.py:328-386` |
| `SolicitudEspecial` | FK a restaurante | `models.py:392-426` |
| `PedidoWhatsApp` | FK a restaurante, snapshot JSON, token público, número único por tenant | `models.py:432-503` |
| `PedidoEspecial` | FK a restaurante, items JSON y solicitud opcional | `models.py:570-623` |
| `PedidoManual`/`Item` | FK a restaurante; items relacionales con snapshots de nombre/precio | `models.py:629-758` |
| `ActivacionCocina`/`SesionCocina` | Tokens hasheados y FK a restaurante | `models.py:763-860` |
| `Notificacion` | FK a restaurante + referencia lógica | `models.py:863-906` |
| `ReporteMetrica` | FK a restaurante y unicidad por periodo | `models.py:913-962` |
| `HorarioAtencion`, `MetodoPago`, `Mesa`, `RespaldoRestaurante` | Todos dependen del restaurante | `models.py:969-1097` |

La relación `UsuarioRestaurante.user` es `OneToOne`, por lo que un usuario API pertenece a un solo restaurante. No existe hoy un usuario con membresías en varios tenants.

### 3.3 Superficies frontend activas

- `restaurante-front`: login, dashboard, pedidos, productos, reservas, solicitudes, métricas, configuración, historial, activación/KDS y páginas comerciales `/saber-mas`/`/planes`. `App.jsx:42-85` es el router efectivo; `src/router/AppRouter.jsx` está vacío.
- `restaurante-landings`: landing pública por subdominio o `/:slug`, menú, carrito WhatsApp, reservas, solicitudes y `/seguimiento/pedido/:trackingToken`. `src/App.jsx` y `pages/home.jsx:109-197`.
- La landing resuelve primero subdominio y luego slug de ruta; si ninguno existe usa `demo-menly` (`home.jsx:109-113`). Backend y frontend comparten reglas similares de dominios base (`menu/utils.py:16-51`, `getSlugFromHostname.js:1-45`).
- No hay React Context propio. El estado se concentra por página, el único hook compartido de negocio es `useAdminInactivity`, y la sesión/rol se comparte mediante módulo en memoria + `localStorage`/`sessionStorage`.

### 3.4 Inventario de API activa

| Grupo | Endpoints principales | Autenticación/tenant |
|---|---|---|
| Auth/contacto | `/api/login/`, `/token/refresh/`, `/logout/`, `/password-reset-request/`, `/contacto/`, `/contacto/planes/` | Login/contacto públicos; refresh cookie/body legacy |
| Landing | `/menu/<slug>/`, `/restaurantes/<slug>/`, `/public/restaurantes/<slug>/metodos-pago/` | Público, tenant por slug |
| Entrada pública | `/reservas/<slug>/`, `/solicitudes-especiales/<slug>/`, `/pedidos-whatsapp/<slug>/` | Público, tenant por slug |
| Tracking/click | `/public/pedidos/seguimiento/<token>/`, `/productos/<pk>/click/` | Público, token o ID |
| Restaurante/dashboard | `/mi-restaurante/`, `/dashboard/ultimos-pedidos/`, `/mi-restaurante/configuracion/`, `/estado-apertura/`, `/upload-logo/` | JWT, tenant por perfil |
| Catálogo | `/mi-restaurante/productos/`, `/productos/agregar/`, `/<id>/actualizar/`, `/eliminar/`, `/variantes/`, `/categorias/` | JWT + permisos de producto/categoría |
| Operación | `/usuarios/`, `/mesas/`, `/horarios/`, `/metodos-pago/`, `/respaldos/` | JWT + permisos específicos |
| Reservas/solicitudes | `/mi-restaurante/reservas/`, `/reservas/crear/`, `/reservas/<id>/`, `/solicitudes-especiales/` | JWT + `CanManageReservas` |
| Pedidos | `/mi-restaurante/pedidos/whatsapp/`, `/especiales/`, `/manuales/` y detalles/estado | JWT + `CanManageReservas`; aliases antiguos `/api/pedidos/...` siguen activos |
| KDS | `/mi-restaurante/cocina/activacion/`, `/cocina/activar/<token>/`, `/cocina/comandas/`, `/cocina/cerrar/` | Activación JWT; operación por cookie cocina |
| Métricas | `/mi-restaurante/metricas/resumen/`, `/pedidos/metricas/`, `/metricas/reporte-*`, `/metricas/reportes/` | JWT; reutiliza `CanManageReservas` |
| Historial/notificaciones | `/historial/`, `/historial/pedidos/`, `/mi-restaurante/notificaciones/` | JWT; historial dueño, notificaciones todos los roles operativos |

No se encontró router DRF ni ViewSet registrado; `core/urls.py` declara las rutas una a una y `menu/views.py` implementa APIViews/generics.

## 4. Mapa de módulos

| Módulo | Estado real | Backend | Frontend | Observación |
|---|---|---|---|---|
| Login/JWT/logout | Implementado | Cookies refresh + JWT | Login y renovación centralizada | Parcialmente endurecido; ver sesión/inactividad. |
| Usuarios/roles | Implementado | Dueño/admin/empleado | UI condicionada por rol | No existe rol de cocina como usuario. |
| Restaurantes/landing | Implementado | Slug único y endpoints públicos | Landing temática | Tenant identificado por slug, no por ID cliente. |
| Productos/categorías | Implementado | CRUD, variantes, orden, bitácora | Gestión completa | Sin cuota por plan; uploads débiles. |
| Importación CSV | Parcial | Solo Django Admin | Sin UI tenant | Global para superadmin; no atómica. |
| Pedido WhatsApp/carrito | Implementado | Snapshot y precio backend | Landing + panel | No exige tienda abierta ni idempotencia. |
| Pedido manual/POS | Implementado | Modelo/ítems propios | Panel | Separado de WhatsApp y especial. |
| Pedido especial | Implementado | Modelo/serializer propio | Solicitud → pedido | Precio cotizado manualmente desde cliente admin. |
| Tracking público | Implementado | Token bearer | Polling cada 20 s | Sin expiración; expone dirección. |
| KDS | Implementado | Sesión propia + polling | Pantalla cocina | Aislamiento backend correcto, concurrencia incompleta. |
| Reservas | Implementado | Pública/manual/dashboard | Formularios y panel | Validación de horario; carreras posibles. |
| Solicitudes especiales | Implementado | Pública/dashboard | Landing y panel | Feature flag aplicado. |
| Notificaciones | Implementado | Persistentes + email síncrono | Burbuja dashboard | Sin worker/cola. |
| Horarios/apertura | Implementado | Horario nocturno + excepción 2 h | Confirmación dashboard | Un bloque por día; sin feriados. |
| Métricas | Implementado parcialmente | Servicios tenant | Dashboard/página | Inconsistencia con pedidos manuales. |
| Reportes | Implementado parcialmente | Mensual/anual/guardado | PDF cliente/guardados | No hay PDF backend; datos guardados confiados al cliente. |
| Planes | Parcial | Modelo mínimo + chequeo de reportes | Comparativa comercial | Sin motor de entitlements/cuotas/vencimiento. |
| Respaldos | Parcial | Snapshot JSON en DB | Crear/listar | No es exportación descargable ni backup fuera de la misma DB. |
| WebSockets/tareas | Inexistente | — | — | Todo es request síncrono/polling. |

## 5. Flujos principales

### 5.1 Landing → pedido → panel → KDS → seguimiento

| Paso | Archivo/endpoint | Modelo | Validaciones actuales | Riesgo |
|---|---|---|---|---|
| 1. Cliente entra | `landings/pages/home.jsx:109-197`; `GET /api/restaurantes/<slug>/` | `Restaurante` | slug, `activo` | Fallback `demo-menly` puede ocultar errores de configuración local. |
| 2. Consulta menú | `GET /api/menu/<slug>/`; `views.py:3535-3598` | Categoría/producto/variante | restaurante activo; categoría/producto disponible | Caché 5 min; flags pueden quedar temporalmente obsoletos. |
| 3. Arma carrito | `home.jsx:380-449` | Estado React | cantidad y campos básicos | Control de tienda cerrada solo en UI. |
| 4. Crea pedido | `POST /api/pedidos-whatsapp/<slug>/`; `views.py:1509-1535` | `PedidoWhatsApp` | producto/variante/método pertenecen al slug; precio recalculado | No verifica `abierto_ahora`; no idempotencia. |
| 5. Guarda/numeración | `services/pedidos_whatsapp.py:165-201` | Pedido + notificación | `atomic`, lock del restaurante, número único | Doble POST crea dos pedidos válidos distintos. |
| 6. Visible en panel | `GET /mi-restaurante/pedidos/whatsapp/`; `views.py:1754-1769` | Pedido WhatsApp | tenant desde perfil | Solo pedidos de hoy en este endpoint. |
| 7. Entra al KDS | Panel cambia a `en_preparacion`; KDS `GET /cocina/comandas/` | Tres pedidos | sesión cookie → restaurante → filtros backend | Sin control optimista entre panel/KDS. |
| 8. Cocina cambia estado | `PATCH /cocina/comandas/<tipo:id>/estado/`; `cocina.py:218-271` | Pedido/historial | tenant y transición KDS estricta | Carrera puede duplicar historial o pisar panel. |
| 9. Cliente sigue | `GET /public/pedidos/seguimiento/<token>/`; `views.py:1538-1555` | WhatsApp/manual | token global único | Sin expiración; dirección delivery pública al poseedor. |

### 5.2 Reserva pública

Landing `home.jsx:463-505` → `POST /reservas/<slug>/` → `CrearReservaPublicaView` (`views.py:1348-1435`) → valida módulo, fecha, horario y duplicado → `Reserva` + `Notificacion` + email síncrono → panel `ReservasDashboardView`. La asociación al tenant proviene exclusivamente del slug. La comprobación de duplicados no tiene restricción DB ni lock.

### 5.3 Solicitud especial → pedido especial

Landing `home.jsx:507-575` → endpoint por slug valida que cualquier `restaurante_id` opcional coincida (`views.py:1459-1468`) → solicitud tenant → empleado/dueño/admin la acepta → `PedidoEspecialSerializer` comprueba que la solicitud pertenezca al mismo restaurante (`serializers.py:880-897`) → crea número bajo lock del restaurante. Los items y precios son una cotización libre de usuario interno, no catálogo.

### 5.4 Pedido manual

Panel `Pedidos.jsx` → `POST /mi-restaurante/pedidos/manuales/` → flag `pedidos_pos` → `PedidoManualSerializer` → `normalizar_productos_pedido` verifica producto/variante tenant y recalcula precios → transacción, lock de restaurante y bulk create de items (`serializers.py:1184-1267`). Este es el flujo de integridad de precio más sólido.

## 6. Auditoría multi-tenant

### 6.1 Patrón efectivo

El tenant privado se obtiene de `UsuarioRestaurante` activo (`permissions.py:26-46`), nunca de un `restaurante_id` libre del frontend. Los helpers `TenantScopedQuerysetMixin` y `get_object_for_restaurante_or_404` agregan `restaurante=...` (`permissions.py:49-72`). Los endpoints públicos resuelven el tenant por slug; el KDS por `SesionCocina.restaurante`.

Se revisaron los usos de `.objects.all/get/filter` fuera de migraciones/tests. Los accesos por ID sensibles de usuarios, productos, categorías, variantes, reservas, solicitudes, pedidos, notificaciones, reportes, mesas, horarios, métodos y respaldos agregan tenant. Excepciones no sensibles/globales: planes, iconos, usuarios Django globales, tracking por token y click público de producto.

### 6.2 Respuestas a los escenarios IDOR

| Intento desde restaurante A | Resultado por código | Evidencia |
|---|---|---|
| Leer/cambiar `/pedidos/<id B>` | 404 | `views.py:1775-1780`, `1861-1863`, `1941-1949` |
| Editar/eliminar producto B | 404 | `views.py:2717-2719`, `2970-2976`, `3000-3006` |
| Usar categoría/variante B | 400/404 | `serializers.py:1581-1592`, `views.py:2874-2881` |
| Consultar reservas B | No aparecen/404 | `views.py:2373-2378`, `2464-2468` |
| Métricas/reportes B | No parametrizable; usa perfil | `views.py:2107-2117`, `2184-2191` |
| Horarios/mesas/métodos B | 404 | helpers de detalle en `views.py:1204-1209`, `1297-1302`, `659-663` |
| Usuarios B | 404 | `views.py:842-847`, `919-924` |
| KDS B con sesión A | No aparece/no cambia | `cocina.py:185-230` |
| Tracking por ID | No existe endpoint por ID público | Se usa token de alta entropía. |

**Resultado:** aislamiento confirmado para estas rutas. Los 25 tests de `CocinaComandasTests` + `MultiTenantIsolationTests` pasaron el 13-07-2026.

### 6.3 Riesgos residuales de arquitectura tenant

- El aislamiento depende de disciplina por endpoint; no existe un manager/queryset tenant obligatorio a nivel modelo.
- `get_restaurante_from_view` silencia cualquier excepción al intentar resolver objeto (`permissions.py:82-91`), lo que dificulta detectar fallos de programación aunque el fallback siga usando el perfil.
- El click público usa solo ID global (`views.py:3665-3679`); no expone datos, pero permite contaminar métricas de cualquier producto conocido.
- Django Admin es global por diseño. La importación CSV selecciona restaurante por slug en cada fila (`admin.py:182-241`); está protegida por `admin_view`, pero un error del superadmin puede afectar múltiples tenants en una sola importación.

## 7. Auditoría específica del KDS

### 7.1 Autenticación y tenant

1. Dueño/admin autenticado genera enlace de 5 minutos (`views.py:1984-1997`).
2. `ActivacionCocina` guarda SHA-256 de un token de 32 bytes URL-safe y se consume una vez bajo `select_for_update` (`services/cocina.py:41-64`).
3. Se crea `SesionCocina` de 30 días por defecto, también con token hasheado (`models.py:814-860`).
4. El token de sesión va en cookie Django firmada `HttpOnly`, `Secure` en producción, `SameSite=Lax`, path `/` (`cocina.py:67-77`).
5. Cada polling vuelve a obtener la sesión, verifica vigencia, restaurante activo y `pedidos_pos`, y consulta por `sesion.restaurante` (`cocina.py:89-104`, `views.py:2026-2044`).
6. Cada cambio de estado vuelve a filtrar el pedido por tipo, ID **y restaurante** (`cocina.py:218-230`).

### 7.2 Respuestas expresas

1. **¿Pueden aparecer pedidos de dos restaurantes en la misma respuesta KDS?**  
   **No se encontró un camino por código.** Las tres consultas tienen `restaurante=sesion.restaurante`; no hay unión global ni filtro frontend usado como barrera.

2. **¿En qué escenario puede verse la cocina equivocada?**  
   La cookie `menly_cocina_session` es única por host/dominio. Si en el mismo perfil de navegador se activa restaurante B después de A, la cookie de B reemplaza la de A. Al siguiente polling, todas las pestañas abiertas muestran B. No mezcla A+B en la misma respuesta, pero sí puede cambiar silenciosamente una pantalla física a la cocina incorrecta. En hosts distintos (`localhost` vs `127.0.0.1`) ocurre lo contrario: hay cookies separadas y una activación no autentica al otro host.

3. **¿Qué protección existe?**  
   Token de activación fuerte, un solo uso, expiración, hash en DB, cookie firmada/HttpOnly, sesión revocable, tenant tomado de sesión, filtros backend y transiciones KDS permitidas.

4. **¿Backend o frontend?**  
   La protección principal está en backend. El frontend no envía `restaurante_id` y solo representa `data.restaurante` devuelto por API.

5. **¿Qué falta para aislamiento total operacional?**  
   Identificador de pantalla/sesión visible y confirmación al reemplazar una cocina; opción de perfiles de navegador o subdominio/cookie particionada por restaurante; listado/revocación de sesiones desde panel; bloqueo/versionado transaccional al cambiar estado; auditoría de todos los orígenes; y alerta persistente con nombre/slug de cocina.

### 7.3 Otros comportamientos

- KDS no participa en el hook de inactividad administrativa porque solo se activa para rutas de panel (`adminSession.js:105-111`, `useAdminInactivity.js:23-25`). Cumple el requisito de persistir.
- Logout administrativo solo elimina refresh admin; no toca cookie KDS. Cumple la independencia esperada.
- El polling es cada 10 s y se pausa si `document.hidden` (`PedidosCocina.jsx:136-152`). No hay WebSocket ni caché de comandas.
- Solo muestra estados preparación/listo. Entregados/cancelados desaparecen por query; no reaparecen salvo que otro endpoint retroceda el estado, posibilidad actual en WhatsApp/especial.
- Dos cocinas pueden actuar simultáneamente. No hay `select_for_update`, columna de versión ni comparación de estado en una actualización SQL atómica (`cocina.py:234-271`).

## 8. Roles y permisos

### 8.1 Roles reales

- **Superusuario/staff Django:** administra globalmente desde `/admin/`; no es un rol API salvo que además tenga perfil.
- **Dueño (`dueno`)**, **administrador (`admin`)**, **empleado (`empleado`)**: únicos roles de `UsuarioRestaurante` (`models.py:267-276`).
- **Cocina:** no es usuario; es una sesión bearer separada ligada a restaurante.
- **Público:** landing, menú, reservas, solicitudes, creación WhatsApp, tracking, métodos y clicks.

### 8.2 Matriz efectiva de backend

| Acción | Superadmin Django | Dueño | Admin | Empleado | Cocina | Público |
|---|---:|---:|---:|---:|---:|---:|
| Ver productos | Sí global | Sí | Sí | Sí | No | Solo disponibles por slug |
| Crear/editar/eliminar productos | Sí | Sí | Sí | No | No | No |
| Cambiar disponibilidad | Sí | Sí | Sí | **No** | No | No |
| Ver pedidos | Sí | Sí | Sí | Sí | Solo activos de cocina | Tracking por token |
| Crear pedido manual/especial | Sí | Sí | Sí | Sí | No | WhatsApp únicamente |
| Cambiar estado | Sí | Sí | Sí | Sí | Solo listo/entregado | No |
| Ver KDS | — | vía sesión | vía sesión | No genera enlace | Sí | No sin cookie |
| Generar activación KDS | Sí | Sí | Sí | No | No | No |
| Ver métricas | Sí | Sí | Sí | **Sí en API** | No | No |
| Guardar/ver reportes | Sí | Sí | Sí | **Sí en API si plan permite** | No | No |
| Cambiar plan/flags premium | Sí, Admin Django | No | No | No | No | No |
| Modificar config general | Sí | Sí | Solo lectura | No | No | No |
| Mesas/horarios/métodos | Sí | Sí | PATCH operativo | Solo lectura | No | Métodos activos |
| Abrir/cerrar/forzar excepción | Sí | Sí | **No: endpoint usa `CanManageConfiguracion`** | No | No | No |
| Usuarios | Sí | CRUD | Solo lectura | No | No | No |
| Historial | Sí | Sí | No | No | No | No |
| Respaldos | Sí | Sí | Sí | No | No | No |

Hay divergencias de contrato: la UI declara que empleado puede cambiar disponibilidad (`utils/permisos.js:21`), pero backend lo niega; la UI oculta métricas a empleados (`permisos.js:17`), pero backend usa `CanManageReservas` y las permite. La seguridad backend prevalece, pero estas diferencias crean soporte confuso y acceso no intencionado.

## 9. Autenticación y sesiones

### 9.1 Administración

- Access JWT: 10 minutos; se mantiene en memoria en la versión actual (`adminSession.js:29-39`).
- Refresh: 7 días, rotación y blacklist; cookie `HttpOnly`, `Secure` en producción, `SameSite=Lax`, path `/api/` (`settings.py:278-283`, `auth_sessions.py:4-14`).
- Compatibilidad temporal aún acepta refresh en body (`auth_sessions.py:26-32`).
- Logout blacklistea refresh y elimina cookie (`views.py:3031-3048`).
- La actividad se registra con mouse, teclado, scroll, touch y click, sincronizada entre pestañas; cierra a los 10 minutos (`useAdminInactivity.js:12-113`). Navegar dentro de rutas admin monta el hook y registra actividad. KDS queda excluido.

**Cumplimiento esperado:** funcionalmente sí en el navegador, pero no existe sesión server-side de actividad. Un access JWT robado sigue válido hasta su expiración y el backend no sabe cuándo fue la última interacción. El refresh puede renovarse aunque el perfil haya sido desactivado, aunque las vistas principales después deniegan al no hallar perfil activo.

### 9.2 CSRF/CORS/cookies

Las APIs administrativas usan `Authorization: Bearer`; CSRF no es la barrera principal. Refresh/cocina dependen de cookies `SameSite=Lax` y CORS con credenciales. Producción debe mantener frontend y API en el mismo “site” (por ejemplo `menly.cl`/`api.menly.cl`); un API cross-site como `onrender.com` no recibirá una cookie Lax en fetch aunque `credentials: include` esté presente.

En local hay una divergencia confirmada: el panel apunta a `http://localhost:8000/api`, la landing a `http://127.0.0.1:8000/api`. Son hosts y depósitos de cookies distintos. No mezcla tenants, pero puede confundir pruebas de sesión.

### 9.3 Configuración

`SECRET_KEY`, DB, email y Cloudinary se cargan desde archivos ignorados/entorno. Los `.env` reales no están versionados; solo `.env.example` sí. El bloque productivo exige variables críticas y rechaza `ALLOWED_HOSTS=*` (`settings.py:411-446`). La verificación `manage.py check --deploy` sobre el entorno **local** reportó DEBUG, HSTS/SSL/cookies y una secret débil; esto describe la configuración local cargada, no demuestra que el despliegue productivo tenga esos valores.

## 10. Pedidos y estados

### 10.1 Tipos

| Tipo | Fuente | Precio | Items históricos | Tracking | KDS |
|---|---|---|---|---|---|
| WhatsApp | Público por slug | Recalculado desde producto/variante backend | JSON snapshot | Sí | Sí en preparación/listo |
| Manual/Menly POS | Usuario interno | Recalculado backend | Filas + nombre/precio snapshot | Sí | Sí |
| Especial | Usuario interno desde solicitud/cotización | Precio unitario enviado por panel | JSON snapshot | No | Sí |

La numeración de los tres tipos bloquea la fila de restaurante y calcula `MAX+1`, protegida además por unicidad `(restaurante, numero_pedido)`. Es segura frente a concurrencia normal, aunque serializa toda creación del mismo tenant.

### 10.2 Máquina de estados real

```text
WhatsApp (panel):
  cualquiera excepto cancelado ──> cualquier estado declarado
  cancelado ──> cancelado
  restricción extra: en_reparto solo si delivery activo y pedido delivery

WhatsApp (KDS): en_preparacion -> listo -> entregado

Manual (panel): pendiente -> preparando -> listo -> entregado
  se permiten saltos hacia adelante y cancelación desde cualquier estado,
  incluso entregado; no se permiten retrocesos ni salir de cancelado.

Manual (KDS): preparando -> listo -> entregado

Especial (panel): cualquiera excepto cancelado -> cualquier estado declarado
  cancelado -> cancelado

Especial (KDS): en_preparacion -> listo -> entregado
```

No existe una máquina de estados compartida. WhatsApp y especial pueden pasar de recibido/pendiente a entregado o retroceder de entregado a preparación desde panel. El frontend sí muestra un modal de confirmación antes de cancelar (`ConfirmarCancelacionPedido.jsx`, `Pedidos.jsx:405-418`), pero la API no exige motivo, versión ni transición previa.

### 10.3 Integridad de precios y productos

`normalizar_productos_pedido` filtra producto disponible por restaurante, variantes activas del mismo tenant y exige la variante correcta; luego toma el precio del backend (`services/pedidos_whatsapp.py:17-80`). Esto protege WhatsApp y manual contra precio/producto/variante manipulados. Los 17 tests de pedido manual, cancelación y cookies pasaron.

El endpoint genérico de detalle WhatsApp también acepta `estado` (`PedidoWhatsAppDashboardSerializer`) pero su `update()` no crea `HistorialEstadoPedidoWhatsApp`; solo el endpoint dedicado de estado lo hace (`serializers.py:697-708` frente a `730-745`). Un cliente autorizado puede, por tanto, cambiar estado por una ruta válida sin dejar el mismo rastro de auditoría.

Pedido especial es deliberadamente una cotización libre: `precio_unitario` llega desde el usuario interno y forma el total (`serializers.py:805-878`). Al permitir empleados, cualquier empleado puede alterar ventas reportadas de ese canal. Debe decidirse si es requisito comercial o requiere aprobación.

### 10.4 Históricos y eliminación

WhatsApp/especial conservan snapshots JSON. Manual conserva nombre, variante, precio y subtotal aunque producto/variante se eliminen (`SET_NULL`). La eliminación no rompe el detalle histórico. No obstante, los reportes de productos manuales ni siquiera consumen esos items actualmente.

## 11. Seguimiento público

- Token: `secrets.token_urlsafe(12)`, 12 bytes (~96 bits), unique e indexado (`models.py:485,508-521`); manual comprueba colisión contra ambos modelos.
- No es enumerable de forma práctica por fuerza bruta.
- No expira ni puede revocarse individualmente.
- Es solo lectura; no existe mutación por token.
- El payload omite nombre/teléfono del cliente, pero para delivery expone la dirección completa como `observaciones_cliente` (`serializers.py:792-795`; manual `1322-1327`).
- No hay throttle específico; aplica el global anónimo de 120/min.

Debería ser público: restaurante, número no global, estado, tiempos, tipo de entrega, items resumidos y total si el negocio lo desea. No debería mostrarse dirección completa; bastaría “Delivery” o dirección parcialmente enmascarada. Se recomienda expiración posterior a entrega y capacidad de rotar/revocar.

## 12. Productos, categorías y variantes

Fortalezas confirmadas: constraints tenant, validación de categoría, variantes activas, precios backend en pedidos, snapshots, reordenamiento transaccional y cache invalidation. La importación CSV se limita a Django Admin y asigna explícitamente por slug.

Debilidades: `ProductoUpdateView` asigna `precio` directamente desde `request.data` y guarda sin ejecutar el serializer ni `full_clean` (`views.py:2750-2784`), por lo que puede persistir valores negativos válidos para `DecimalField`; creación sí pasa por serializer pero no hay `CheckConstraint` de producto. La importación no es atómica y puede quedar parcialmente aplicada. Uploads no tienen límites explícitos de tamaño/tipo/dimensiones. El hard delete está permitido para productos/variantes, aunque snapshots preservan pedidos.

## 13. Horarios y apertura

Hay una única fila por restaurante/día, por tanto no se soportan dos bloques (almuerzo/cena) ni feriados. Sí se soportan horarios que cruzan medianoche (`estado_restaurante.py:15-53`) y existen tests de madrugada.

La prioridad real es: cierre manual → excepción vigente → dentro de horario → cerrado (`estado_restaurante.py:56-85`). Abrir fuera de horario requiere `forzar_fuera_de_horario=true`; backend devuelve 409 para pedir confirmación y crea excepción de dos horas (`views.py:1014-1033`). La landing y el dashboard usan el mismo servicio.

Problema crítico operacional: el endpoint público de pedido no llama `calcular_estado_restaurante`; un cliente que omita la UI puede crear pedidos con tienda cerrada. Reservas validan su horario, pero pedidos no.

Zona horaria está fijada a `America/Santiago`, `USE_TZ=True`, con middleware que activa esa zona (`settings.py:374-380`, `timezone_middleware.py`).

## 14. Planes y restricciones

`Plan` solo tiene nombre/slug/descripción/activo. No hay precios, límites, entitlement, fechas de suscripción ni estado de pago. `calcular_estado_suscripcion` supone vencimiento exactamente un mes desde creación del restaurante y solo lo muestra; no bloquea (`views.py:261-272`). Si falta plan, se presenta Básico por fallback (`serializers.py:247-269`).

| Función | Plan comercial declarado | Frontend | Backend | Riesgo |
|---|---|---|---|---|
| Productos máximos | Comparativa sugiere diferencias | No cuota real | No cuota | Uso fuera de plan |
| Métricas | Pro en UI comercial | Flag/rol oculta | Resumen sin chequeo de plan ni `metricas_activas` | Básico/empleado accede por API |
| Reporte mensual/anual | Pro/Full Pro | Visible según UI | Sí valida slug Pro/Full Pro | Única barrera explícita |
| Guardar reportes | Pro/Full Pro | Sí | Sí | Payload no recalculado |
| Reservas | Comparativa | Feature flag | Flag en endpoints públicos; privados parcialmente | Flag manual, no derivado de plan |
| Solicitudes especiales | Comparativa | Feature flag | Sí valida flag | Sin vínculo automático a plan |
| Pedidos WhatsApp | Comparativa | Feature flag | Sí valida `carrito_whatsapp_activo` | No valida tienda abierta |
| POS/KDS | Comparativa | Feature flag | `pedidos_pos` para manual/KDS | Activación manual por superadmin |
| Usuarios adicionales | Implícito | UI | Límite fijo 1 admin + 2 empleados para todos | No varía por plan |
| Personalización | Comparativa | Temas/flags | Sin entitlement | Cualquier configuración habilitada por admin global |
| Downgrade/vencido/sin plan | No implementado | Solo aviso de fecha | Sin bloqueo | Funciones continúan |

## 15. Dashboard, métricas y reportes

El aislamiento por restaurante está confirmado. Cancelados se excluyen de venta real y entregados cuentan como finalizados. Se usan fechas locales, pero filtros `fecha_creacion__date` pueden impedir aprovechar índices de timestamp.

Inconsistencias:

- El resumen canónico incluye manuales (`services/metricas/pedidos.py:263-333`), pero `reportes.py` solo consolida WhatsApp y especiales (`39-87`).
- Ranking de productos vendidos solo recorre snapshots WhatsApp/especiales (`productos.py:64-81`); omite manuales.
- `venta_diaria_menly` y `venta_diaria_whatsapp` incluyen no cancelados, aunque “venta real” solo entregados; nombres cercanos representan conceptos distintos.
- Reporte mensual ejecuta consultas por cada día y vuelve a recorrer snapshots varias veces; anual repite consolidación por 12 meses. No hay materialización/caché.
- `ReporteMetricaGuardarView` persiste `resumen` y `datos` entregados por React sin recalcularlos (`views.py:2207-2253`, `Metricas.jsx:1162-1224`). Un usuario autorizado puede guardar cifras arbitrarias.
- PDF se genera en navegador (`jspdf/html2canvas`); `archivo_pdf` del modelo no se llena por este flujo.

## 16. Seguridad general

### 16.1 Hallazgos consolidados

| ID | Severidad | Estado | Módulo | Hallazgo y evidencia | Impacto / escenario | Recomendación |
|---|---|---|---|---|---|---|
| AUD-001 | Alta | Confirmado | Pedidos públicos | No se valida tienda abierta en `CrearPedidoWhatsAppPublicoView`/serializer (`views.py:1509-1535`, `serializers.py:495-560`). | POST directo crea pedido fuera de horario/cierre manual. | Validar servicio canónico de apertura dentro de la transacción. |
| AUD-002 | Alta | Confirmado | Pedidos | No hay clave de idempotencia ni deduplicación (`pedidos_whatsapp.py:165-201`). | Doble click, timeout/reintento o automatización crea pedidos duplicados. | `Idempotency-Key` por tenant + constraint/registro de respuesta. |
| AUD-003 | Alta | Confirmado | Estados | WhatsApp/especial aceptan saltos y retrocesos; además el PATCH genérico WhatsApp cambia estado sin crear historial (`serializers.py:647-708,730-745,852-859`). | Pedido entregado reaparece en cocina, salta validaciones o cambia sin rastro homogéneo. | Máquina de estados/servicio único y bloquear estado en el serializer genérico. |
| AUD-004 | Alta | Confirmado | Concurrencia | Panel/KDS hacen read-modify-save sin lock/version (`cocina.py:234-271`, serializers de estado). | Dos cocinas o panel pisan estado; historial duplicado/inexacto. | Transacción + `select_for_update` o actualización condicional por versión/estado esperado. |
| AUD-005 | Alta | Confirmado | KDS | Cookie única `menly_cocina_session` por host (`cocina.py:17,67-77`). | Activar B reemplaza A; todas las pestañas cambian de cocina en el siguiente polling. | Sesión/pantalla identificada, aviso de reemplazo y revocación; estrategia por dispositivo/tenant. |
| AUD-006 | Alta | Confirmado | Reportes | Backend guarda JSON financiero provisto por cliente (`views.py:2207-2253`). | Usuario autorizado falsifica reportes históricos sin alterar pedidos. | Aceptar solo periodo/tipo y recalcular servidor. |
| AUD-007 | Alta | Confirmado | Métricas | Reportes/rankings omiten pedidos manuales (`reportes.py`, `productos.py:64-81`). | Ventas y productos subreportados; decisiones comerciales incorrectas. | Incorporar canal manual en consolidado y pruebas. |
| AUD-008 | Alta | Confirmado | Roles | Métricas/reportes usan `CanManageReservas`, que permite empleado (`views.py:2096-2199`, `permissions.py:303-324`). | Empleado consulta información comercial oculta por UI. | Permiso específico `CanViewMetricas/CanManageReportes`. |
| AUD-009 | Alta | Parcial | Planes | Solo reportes validan plan; no hay cuotas/entitlements/vencimiento (`models.py:31-43`, `views.py:1731-1743`). | Acceso fuera del plan y modelo comercial no exigible. | Servicio central de capacidades backend; flags derivados/auditables. |
| AUD-010 | Alta | Confirmado | Tracking/privacidad | Token no expira y serializa dirección delivery (`models.py:485`, `serializers.py:792-795`). | Link reenviado conserva PII indefinidamente. | Expirar/revocar y enmascarar dirección. |
| AUD-011 | Alta | Confirmado por inventario vigente | Dependencias | npm: axios/form-data altos y DOMPurify moderado; OSV marca Django 6.0.4, Pillow 12.2.0, PyJWT 2.12.1, urllib3 2.6.3 e idna 3.11 afectados. | DoS, fugas o gadgets según ruta aplicable; Pillow se cruza con uploads. | Actualizar a versiones corregidas, regenerar locks y ejecutar regresión. |
| AUD-012 | Media | Confirmado | Productos | Update evita validación serializer y no hay check de precio no negativo (`views.py:2750-2784`, `models.py:177`). | Precio negativo/inválido en menú y pedidos. | Serializer para todo update + DB `CheckConstraint`. |
| AUD-013 | Media | Confirmado | Pedido especial | Empleado define precios libres y total (`serializers.py:805-878`). | Manipulación interna de métricas/cotización. | Permiso/aprobación explícita o catálogo de cotización auditable. |
| AUD-014 | Media | Riesgo probable | Reservas | Duplicado/mesa se comprueba antes de guardar sin constraint/lock (`views.py:2422-2445`). | Dos requests simultáneos reservan la misma mesa/hora. | Constraint viable o lock/transaction con modelo de asignación estructurado. |
| AUD-015 | Media | Confirmado | KDS | Sesiones duran 30 días y no hay UI de listado/revocación por pantalla (`settings.py:196-198`, modelos de sesión). | Dispositivo perdido mantiene cocina hasta expirar o desactivar POS. | Panel de sesiones, nombre de dispositivo, revocación y último uso. |
| AUD-016 | Media | Confirmado | Cookies/despliegue | `SameSite=Lax` exige topología same-site; localhost y 127 tienen cookies distintas. | KDS/admin falla o parece cambiar de sesión según host. | Documentar dominio canónico y validar variables en CI/deploy. |
| AUD-017 | Media | Parcial | Inactividad | Timeout es solo frontend; no hay sesión de actividad server-side (`useAdminInactivity.js`). | Token robado sigue válido hasta 10 min; política no centralizada. | JTI/sesión revocable y `last_activity` si el requisito es de seguridad estricta. |
| AUD-018 | Media | Confirmado | Refresh/perfiles | Refresh valida JWT/User, no `UsuarioRestaurante.activo`; permisos lo frenan después. | Se siguen emitiendo access tokens inútiles a perfiles desactivados. | Regla de refresh que valide perfil/restaurante y revoque familia. |
| AUD-019 | Media | Confirmado | Uploads | Logo/producto sin límite MIME/tamaño/dimensiones (`views.py:937-953,2779-2781`). | Consumo de recursos, archivos no esperados, riesgo ampliado por Pillow. | Validadores, límites, re-encode seguro y cuotas. |
| AUD-020 | Media | Confirmado | Headers | CSP se construye en settings pero está comentada en middleware (`security_middleware.py:13`). | Menor defensa frente a XSS/recursos inyectados. | Emitir CSP validada, inicialmente report-only. |
| AUD-021 | Media | Confirmado | Abuso público | Pedido no tiene throttle específico/captcha; reserva/solicitud solo throttle por IP. | Spam de pedidos/notificaciones y costos operativos. | Throttle por slug/IP, CAPTCHA adaptativo y límites de payload. |
| AUD-022 | Media | Confirmado | Rendimiento reportes | Bucles diarios/mensuales y parsing JSON repetido (`reportes.py:90-208`, `productos.py`). | Latencia/DB/CPU crecen con histórico. | Agregados por rango, prefetch único o tablas/materialización. |
| AUD-023 | Media | Riesgo probable | Escalabilidad polling | KDS 10 s, dashboard 20 s, pedidos 30 s, tracking 20 s. | A 500 KDS: ~50 req/s permanentes antes de panel/tracking; cada KDS lanza varias queries. | Backoff/ETag; luego SSE/WebSocket solo si métricas lo justifican. |
| AUD-024 | Media | Confirmado | Caché | Menú cachea flags; señales solo producto/categoría. Cambios vía Django Admin a restaurante/variante pueden quedar 5 min (`signals.py`, `cache_utils.py`). | Landing muestra disponibilidad/config obsoleta. | Señales selectivas para restaurante/variante o versionar cache key. |
| AUD-025 | Media | Confirmado | Suscripción | “Vencimiento” se calcula desde fecha de alta y no se aplica (`views.py:261-272`). | Avisos falsos y cuentas vencidas siguen operando. | Modelo de suscripción explícito; no usar fecha de creación. |
| AUD-026 | Media | Confirmado | Logs/PII | FileHandler sin rotación; password reset registra email en excepción (`settings.py:315-338`, `views.py:3174-3177`). | Disco creciente y datos personales en logs. | Rotating handler/servicio, redacción y retención. |
| AUD-027 | Media | Confirmado local, no versionado | Datos | `backup.json` ignorado contiene datos personales reales. | Exposición en equipo/backups del desarrollador. | Cifrar/eliminar copias locales y usar datos sintéticos. |
| AUD-028 | Media | Confirmado | Calidad frontend | Lint falla: panel 11 errores/5 warnings; landing 14 errores. | Bugs reales como operador coma en iconos (`Dashboard.jsx:505-506`) y efectos frágiles. | Cero errores lint en CI; corregir por riesgo. |
| AUD-029 | Media | Funcionalidad inexistente | Pruebas frontend | No existen `.test/.spec`, Vitest, Jest, Cypress o Playwright. | Sesiones, rutas, carrito y polling regresan sin alarma. | Tests unitarios + E2E críticos. |
| AUD-030 | Baja | Confirmado | Métricas click | Endpoint público incrementa por ID sin slug (`views.py:3665-3679`). | Cualquiera infla “más clickeados” de otro tenant. | Firmar contexto/slug, deduplicar o tratar métrica como no confiable. |
| AUD-031 | Baja | Confirmado | Debug | `/api/debug/time/` público consulta primer restaurante (`core/urls.py:40`, `debug_views.py:9-27`). | Divulgación menor y superficie innecesaria. | Exponer solo con DEBUG o retirar de producción. |
| AUD-032 | Baja | Confirmado | Código/rutas | Alias duplicados de pedidos y componentes/servicios vacíos o redundantes (`core/urls.py:233-255`, `AppRouter.jsx`). | Contratos ambiguos y mantenimiento duplicado. | Deprecar rutas con inventario y telemetría. |
| AUD-033 | Baja | Confirmado | Rendimiento frontend | Build admin genera chunks ~812/702 kB y imágenes de 1,2–2,3 MB. | Carga lenta móvil y costo de datos. | Lazy routes, WebP/AVIF y assets responsivos. |
| AUD-034 | Baja | Confirmado | API | Listado de reportes no pagina y KDS devuelve todas las comandas activas (`views.py:2157-2178`, `cocina.py:185-215`). | Payload crece en tenants de volumen alto. | Límites/paginación o ventana operativa. |
| AUD-035 | Baja | Confirmado | Async | Emails se envían dentro del request y no hay cola (`utils.py:75-180`). | Latencia y dependencia SMTP en endpoints públicos. | Cola simple en fase 4; mantener persistencia antes de enviar. |
| AUD-036 | Baja | No verificable en producción | Infra | No hay IaC, configuración de proxy, backups PostgreSQL ni monitoreo de despliegue en repo. | No se puede certificar TLS, restore, RPO/RTO o límites reales. | Checklist/infra documentada y prueba de restauración. |
| AUD-037 | Media | Confirmado | Horarios | Sin filas de horario, `calcular_estado_horario` devuelve `True` (`estado_restaurante.py:35-43`), mientras reserva pública sin horario se rechaza (`utils.py:66-73`). | Una tienda sin configuración aparece siempre dentro de horario, pero no acepta reservas; contradice “cerrada por defecto fuera de horario”. | Definir estado inicial cerrado y exigir horario o excepción explícita; alinear reservas/pedidos/landing. |

No se encontró SQL construido manualmente, `raw()`, `extra()` ni ejecución de comandos con input; el riesgo de SQL injection es bajo por ORM. Tampoco se encontró `dangerouslySetInnerHTML`, `eval` o HTML cliente directo; React escapa texto. No se confirmó path traversal. CORS no está abierto globalmente (`CORS_ALLOW_ALL_ORIGINS=False`).

### 16.2 Detalle de dependencias vulnerables a la fecha de corte

| Superficie | Versión instalada/bloqueada | Aviso/resultado | Corrección indicada por auditoría |
|---|---|---|---|
| Panel | Axios 1.15.2 | `npm audit`: múltiples GHSA altas; uso directo en login | >= 1.16.0 |
| Panel transitivo | form-data 4.0.0–4.0.5 | CRLF injection, alta | >= 4.0.6 |
| Panel transitivo | DOMPurify <= 3.4.10 | contaminación de configuración, moderada | versión posterior corregida |
| Landing | React Router 7.15.0 | GHSA-84g9-w2xq-vcv6, baja | >= 7.15.1 |
| Backend | Django 6.0.4 | GHSA-5hrc, 7h2m, mm6v, w26r y aliases | >= 6.0.6 cubre los fixes consultados |
| Backend | Pillow 12.2.0 | cinco PYSEC, cuatro DoS remotos | >= 12.3.0 |
| Backend | idna 3.11 | GHSA-65pc-fj4g-8rjx | >= 3.15 |
| Backend | PyJWT 2.12.1 | cinco GHSA de PyJWK/JWS | >= 2.13.0; varias rutas no parecen aplicables a SimpleJWT con secret local, validar regresión |
| Backend | urllib3 2.6.3 | GHSA-mf9v y qccp | >= 2.7.0; aplicabilidad depende de llamadas salientes |

Estos datos provienen de `npm audit` y la API oficial OSV consultados el 13-07-2026. “Versión afectada” está confirmado; que cada advisory sea explotable en Menly es **riesgo probable/no verificado** hasta analizar la ruta específica y actualizar.

## 17. Integridad y concurrencia

| Operación | Protección | Falta |
|---|---|---|
| Numeración de pedidos | `transaction.atomic`, lock de restaurante, unique constraint | Idempotencia del request |
| Reordenar productos | Locks y orden temporal | Validación homogénea de campos |
| Consumir activación KDS | `select_for_update`, un solo uso | Límite/revocación de activaciones antiguas |
| Cambiar estado | Validación parcial | Lock, versión, estado esperado y máquina común |
| Reserva/mesa | Checks previos | Constraint/lock contra carreras |
| Guardar reporte | Unique condicional + `update_or_create` | Recalcular servidor y manejar carrera `IntegrityError` |
| Notificación de pedido | Excepción atrapada | Reintento/cola; puede faltar notificación aunque exista pedido |

## 18. Rendimiento y escalabilidad

| Escala | Evaluación razonada |
|---|---|
| 10 restaurantes | Adecuado para prueba controlada después de bloqueadores; carga pequeña. |
| 50 | Probablemente viable con PostgreSQL/Redis bien dimensionados, pero debe medirse KDS+dashboard, no solo menú. |
| 100 | Requiere observabilidad, optimizar métricas/reportes y medir polling concurrente. |
| 500 | No justificable con evidencia actual. Solo KDS a 10 s genera ~50 requests/s continuos; locmem no comparte caché y no hay estrategia push/backoff global. |
| Cientos de pedidos/tenant | CRUD listados tienen paginación en varias rutas, pero reportes parsean snapshots en Python y KDS no limita ventana. |

Los scripts k6 solo prueban `GET /api/menu/demo-menly/` con 100 VUs/stages y umbral p95, pero no hay resultados guardados ni prueba de autenticación, escritura, KDS o métricas. No permiten afirmar capacidad productiva.

## 19. Calidad del código

- `views.py`, `serializers.py`, `models.py`, `tests.py`, `Pedidos.jsx` y `Metricas.jsx` son hotspots reales. `views.py` combina contacto, auth, CRUD, KDS, métricas y configuración.
- Hay una capa de servicios útil para cocina, pedidos WhatsApp, apertura y métricas; es un buen punto de evolución, pero muchas reglas siguen en views/serializers.
- Tres modelos de pedido tienen estados, serialización y reportes duplicados/inconsistentes. No se recomienda reescribir a un modelo único ahora; sí extraer contratos compartidos.
- `CanManageReservas` se reutiliza como permiso genérico de pedidos, notificaciones y métricas, ocultando intención.
- Manejo de error frontend está centralizado en `authFetch/readJsonResponse`, pero aún existe un segundo cliente Axios solo para login.
- Hay código muerto comentado y helpers no usados en landing; lint lo confirma.
- Builds Vite pasan, pero el build no sustituye lint/tests.

## 20. Pruebas existentes y faltantes

### 20.1 Evidencia ejecutada

| Comando | Resultado |
|---|---|
| `manage.py test menu.tests.CocinaComandasTests menu.tests.MultiTenantIsolationTests --keepdb` | **25/25 OK** |
| Pedido manual + cancelación + cookies admin | **17/17 OK** |
| Suite completa `menu.tests` | No verificable: excedió timeout de 180 s antes de resultado final |
| `manage.py check --deploy` local | 6 warnings esperables de entorno local; ninguna excepción de sistema |
| Build `restaurante-front` | OK; warnings de chunks/assets |
| Build `restaurante-landings` | OK |
| Lint panel | Falla: 11 errores, 5 warnings |
| Lint landings | Falla: 14 errores |
| `npm audit --omit=dev` panel | 2 altas, 1 moderada |
| `npm audit --omit=dev` landing | 2 bajas |
| OSV requirements | Versiones afectadas confirmadas; aplicabilidad por flujo requiere actualización/regresión |

### 20.2 Pruebas mínimas a agregar

| Caso | Positivo | Negativo/concurrencia |
|---|---|---|
| Tienda cerrada | Pedido abierto crea | Cerrada/manual/fuera horario rechaza API directa |
| Idempotencia | Primera clave crea | Repetición devuelve mismo pedido; distinta clave crea otro |
| Estados | Cada transición permitida | Saltos, retrocesos, cancelado/entregado inválidos |
| KDS | Sesión A lista/cambia A | ID B, cookie reemplazada, dos PATCH simultáneos |
| Roles | Matriz por endpoint | Empleado no accede métricas/reportes si esa es política |
| Tracking | Token válido | expirado/revocado/aleatorio; dirección enmascarada |
| Reservas | Mesa libre | dos requests simultáneos misma mesa/hora |
| Planes | capacidad permitida | cuota, vencimiento, downgrade y sin plan |
| Métricas | tres canales conciliados | cancelados/pendientes y reportes manipulados |
| Sesión admin | actividad renueva UI | inactividad multi-tab revoca refresh y sesión backend |
| Frontend | carrito/variantes/error | doble click, 401 refresh, polling superpuesto |

## 21. Fortalezas reales y potencial comercial

| Fortaleza | Problema que resuelve / cliente | Madurez | Para hacerla ventaja sólida | Cómo vender/demostrar |
|---|---|---|---|---|
| Landing + menú por restaurante | Presencia digital para pequeños locales sin web | Media-alta | SEO/temas consistentes, assets ligeros y uptime | Cambiar menú/estado en panel y verlo en subdominio. |
| Precio seguro en carrito | Evita que el cliente altere precios | Alta en WhatsApp/manual | Idempotencia y cierre backend | Manipular payload en demo y mostrar que total se recalcula. |
| WhatsApp sin API oficial | Convierte carrito en mensaje y conserva pedido/tracking | Media | Garantizar confirmación operativa y anti-duplicado | Crear carrito, abrir WhatsApp y seguir pedido. |
| KDS independiente | Cocina no depende de sesión del dueño | Media | Concurrencia, dispositivos y revocación | Cerrar panel y mostrar KDS activo/aislado. |
| Seguimiento público | Reduce llamadas “¿dónde está?” | Media | Privacidad/expiración | Cambiar estado en cocina y ver polling del cliente. |
| Multi-tenant | Una plataforma sirve a varios restaurantes | Media-alta técnica | Guardrails obligatorios y pruebas CI | Dos tenants con IDs cruzados recibiendo 404. |
| Reservas + solicitudes | Centraliza demanda no estándar | Media | Concurrencia, agenda y notificación robusta | Reserva pública → burbuja → gestión. |
| Horarios nocturnos/excepción | Operación real de locales que cierran pasada medianoche | Media-alta | Feriados/múltiples bloques | Abrir fuera de horario con confirmación y vencimiento. |
| Snapshots históricos | Pedidos sobreviven a cambios de catálogo | Alta | Reportes completos | Eliminar producto y mostrar pedido histórico intacto. |
| Métricas multicanal | Da visibilidad de operación | Media-baja | Incluir manuales, datos server-side y performance | Solo después de conciliación automática con pedidos. |

## 22. Debilidades y oportunidades

- **Demasiados conceptos de pedido:** mantener tres flujos en MVP es razonable porque responden a orígenes distintos, pero compartir estados, auditoría e interfaces de reporte reducirá errores sin migrar todo a un “supermodelo”.
- **Planes prometen más que el backend:** oportunidad para convertir flags existentes en capacidades centralizadas y vendibles.
- **KDS es diferenciador pero operativamente silencioso:** mostrar siempre restaurante, dispositivo, conexión y última actualización reduce errores humanos.
- **Reportes parecen persistentes pero no son evidencia contable:** deben etiquetarse “operacionales” hasta recalcularse en servidor y conciliar tres canales.
- **Respaldos dentro de la misma DB:** útiles como snapshot lógico, no como disaster recovery. Debe comunicarse así.
- **Email síncrono:** simple para MVP, pero frágil para volumen; una cola puede esperar a fase 4.
- **Configuración distribuida:** backend, dashboard y landing comparten servicio de apertura (fortaleza); replicar este patrón para permisos, planes y estados es la mejor oportunidad arquitectónica.

## 23. Priorización

### Bloqueadores antes de producción/piloto real

1. AUD-001: impedir pedidos con tienda cerrada.
2. AUD-002: idempotencia de creación.
3. AUD-003/AUD-004: máquina de estados y concurrencia panel/KDS.
4. AUD-005: evitar cambio silencioso de cocina entre pestañas/dispositivos.
5. AUD-006/AUD-007: reportes server-side y canal manual completo.
6. AUD-008: cerrar matriz de permisos backend.
7. AUD-010: privacidad/expiración tracking.
8. AUD-011/AUD-019: actualizar dependencias y endurecer uploads.
9. AUD-014: evitar doble reserva de mesa.

### Importantes para MVP

- Entitlements mínimos de plan y suscripción real.
- Validación homogénea de producto/precio.
- Sesiones KDS revocables y visibles.
- CSP, throttles públicos y logs con rotación.
- Corregir lint y añadir E2E de flujos críticos.
- Conciliar métricas y aclarar “venta operativa” vs “venta real”.

### Mejoras posteriores

- Cola de email/notificaciones.
- SSE/WebSockets solo después de medir polling.
- Materialización avanzada de métricas.
- Dos bloques horarios/feriados.
- Refactor modular de views/serializers.
- Optimización agresiva de assets/marketing.

## 24. Recomendaciones y plan de corrección

### Fase 1: Aislamiento y seguridad

| Tarea | Prioridad/riesgo | Archivos | Complejidad | Dependencias | Criterio de aceptación | Pruebas |
|---|---|---|---|---|---|---|
| Formalizar permisos por dominio | P0/Alta | `permissions.py`, `views.py` | Media | Decisión matriz roles | Cada endpoint usa permiso nombrado; UI y API coinciden | Matriz positiva/negativa por rol |
| Endurecer KDS multi-pantalla | P0/Alta | `models.py`, `cocina.py`, KDS/panel | Alta | UX dispositivo/cookie | Activar B no cambia A sin confirmación; sesiones revocables | Dos restaurantes, pestañas y dispositivos |
| Tracking privado/expirable | P0/Alta | modelos/serializers/tracking | Media | Política de retención | Dirección enmascarada; token expira/revoca | válido, expirado, revocado, aleatorio |
| Dependencias/uploads | P0/Alta | requirements, locks, validadores | Media | Versiones compatibles | Auditorías sin altas; archivos limitados/re-encode | archivos grandes, MIME falso, regresión imágenes |
| CSP/debug/logs | P1/Media | middleware, URLs, settings | Baja-media | Inventario de orígenes | CSP report-only limpia; debug ausente prod; rotación | headers, DEBUG true/false |

### Fase 2: Integridad operacional

| Tarea | Prioridad/riesgo | Archivos | Complejidad | Dependencias | Criterio de aceptación | Pruebas |
|---|---|---|---|---|---|---|
| Validar tienda abierta backend | P0/Alta | view/serializer WhatsApp, estado service | Baja | Regla comercial | POST cerrado devuelve 409/403 y no crea | horario, cierre, excepción |
| Idempotencia | P0/Alta | modelo/servicio/view | Media | Retención de claves | Repetición devuelve mismo ID/response | doble click, timeout, paralelo |
| Máquina de estados común | P0/Alta | serializers, cocina, servicio nuevo | Media | Definir transiciones/cancelación | Ningún canal salta/retrocede fuera de tabla | todas las aristas y rechazos |
| Concurrencia de estado | P0/Alta | servicios de pedidos/KDS | Media | Máquina de estados | Un único cambio gana; conflicto 409 | dos PATCH simultáneos panel/KDS |
| Reserva de mesa atómica | P0/Media-alta | modelos/views/migración futura | Alta | Normalizar `mesa_asignada` FK | Imposible doble ocupación activa | carrera transaccional |
| Producto/precio consistente | P1/Media | view/serializer/model | Baja | Ninguna | precio >=0 en API y DB | update/create/import negativo |

### Fase 3: Mejoras del MVP

| Tarea | Prioridad/riesgo | Archivos | Complejidad | Dependencias | Criterio de aceptación | Pruebas |
|---|---|---|---|---|---|---|
| Reportes canónicos | P0/Alta | métricas/reportes/view/React | Media | Estados comunes | Backend recalcula y contiene tres canales | conciliación fixture completa |
| Plan/capacidades mínimo | P1/Alta comercial | Plan/Restaurante/permisos | Alta | Catálogo comercial final | Backend bloquea cada capacidad y cuota | básico/pro/vencido/downgrade |
| Sesión admin contractual | P1/Media | auth/session/hook | Media | Política revocación | 10 min reales en tabs/dispositivos | reloj simulado y refresh revocado |
| UX KDS/errores humanos | P1/Media | KDS/Pedidos | Baja-media | Sesiones KDS | nombre tenant fijo, offline/stale/conflicto visibles | E2E pantalla cocina |
| Calidad frontend | P1/Media | ambos frontends | Media | Config lint/test | lint 0; E2E críticos en CI | Vitest + Playwright/Cypress |

### Fase 4: Escalabilidad

| Tarea | Prioridad/riesgo | Archivos | Complejidad | Dependencias | Criterio de aceptación | Pruebas |
|---|---|---|---|---|---|---|
| Observabilidad | P1 | settings/infra | Media | Plataforma deploy | métricas latencia/error/query y alertas | fallo DB/SMTP/Redis simulado |
| Optimizar métricas | P1 | services/metricas | Alta | Reportes canónicos | número de queries acotado por reporte | `assertNumQueries`, dataset grande |
| Estrategia actualización | P2 | KDS/API/frontend | Alta | Métricas reales de polling | SLO con menor carga; SSE/WS si conviene | carga 10/50/100/500 |
| Índices/queries | P2 | modelos/migraciones futuras | Media | `EXPLAIN ANALYZE` prod-like | planes de consulta usan índices | benchmarks PostgreSQL |
| Cola de notificaciones | P2 | utils/worker | Alta | Redis/servicio | request no depende de SMTP y hay reintento | caída SMTP/idempotencia |
| Backups reales | P1 | infraestructura | Media | Proveedor PostgreSQL | RPO/RTO definidos y restore probado | simulacro restauración |

## 25. Diez riesgos más importantes

1. Pedidos públicos aceptados con tienda cerrada.
2. Pedidos duplicados por ausencia de idempotencia.
3. Estados inválidos y retrocesos entre panel y KDS.
4. Carreras de estado sin locks/versionado.
5. Una activación KDS puede reemplazar silenciosamente otra cocina en el mismo navegador.
6. Reportes guardados confían en datos financieros del cliente.
7. Reportes y ranking omiten pedidos manuales.
8. Empleados acceden a métricas/reportes por API pese a la UI.
9. Tracking permanente expone dirección delivery.
10. Dependencias vulnerables y uploads sin validación suficiente.

## 26. Veredicto final

**APTO PARA PRUEBA CONTROLADA**

La base multi-tenant y el KDS tienen protecciones backend reales y pruebas que pasaron, por lo que Menly es apto para demostraciones, QA y pruebas con datos sintéticos o pedidos no operacionales. No es todavía apto para un piloto con un restaurante real porque puede aceptar/duplicar pedidos, registrar transiciones inconsistentes, presentar conflictos panel-cocina y producir métricas/reportes incorrectos. Tampoco es apto para producción multi-restaurante hasta resolver sesiones KDS multi-pantalla, permisos, tracking, dependencias y observabilidad.

La recomendación no es reescribir Menly. La ruta más segura es conservar modelos y flujos existentes, centralizar cuatro contratos —tenant, permisos, estados y capacidades de plan— y cerrar primero los bloqueadores P0 con pruebas de regresión.
