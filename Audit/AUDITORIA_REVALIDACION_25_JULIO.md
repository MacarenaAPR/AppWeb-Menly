# Revalidación de seguridad de Menly

**Entregable solicitado:** `AUDITORIA_REVALIDACION_25_JULIO.md`  
**Ejecución:** 24 de julio de 2026, zona `America/Santiago`  
**Línea base:** `Audit/Auditoria_15_julio`, fecha de corte indicada en el documento: 16 de julio de 2026  
**Commit auditado:** `7922beb84ac2307ddae8e76970925b2f4846d920` (`main`)  
**Working tree al inicio:** limpio  
**Modalidad:** revisión estática, historial Git y pruebas activas exclusivamente locales/de testing  

No se modificó código, no se alteraron datos reales, no se realizó commit, push ni despliegue, y no se enviaron ataques a producción ni a servicios externos.

## 1. Resumen ejecutivo

Las remediaciones posteriores al informe base son reales, pero el conjunto todavía no satisface el estándar exigido para declarar a Menly seguro para producción:

- **H-01 (SSRF Web Push): CORREGIDO.** La API limita los destinos a proveedores Push conocidos, exige HTTPS/443, valida todas las respuestas DNS IPv4/IPv6, revalida antes de enviar, desactiva registros antiguos inseguros y no sigue redirecciones. Sus pruebas positivas, negativas y de regresión aprobaron.
- **H-02 (contraseñas): CORREGIDO PARCIALMENTE.** Creación y edición directa ahora aplican los validadores Django y revocan refresh tokens/sesiones. No existe cambio/restablecimiento autoservicio seguro, el cambio de contraseña del propio dueño no exige contraseña actual o reautenticación reciente y los access tokens ya emitidos conservan hasta diez minutos de vigencia. La remediación además agregó nombres de usuario a logs persistentes.
- **H-03 (fuerza bruta en Django Admin): CORREGIDO PARCIALMENTE.** La protección local por IP+cuenta, cuenta e IP, la normalización, `429`, `Retry-After`, allowlist y ruta configurable funcionan. No fue posible verificar Redis real, caída de Redis, ni la topología efectiva de proxies/`X-Forwarded-For` en Render. MFA sigue sin estar implementado.
- **H-04 (dependencias): CORREGIDO PARCIALMENTE.** Se actualizaron las versiones originalmente señaladas y ambos frontends construyen, pero la ejecución actual de `npm audit` continúa en rojo: 7 avisos en el panel y 3 en la landing. Parte de los avisos React Router no es aplicable al modo declarativo usado por Menly, pero el gate de supply chain no está limpio. `pip-audit` backend quedó `NO VERIFICABLE`.
- **H-05 (métricas/reportes): CORREGIDO PARCIALMENTE.** El backend ignora cifras y tenant controlados por el cliente, recalcula desde la base, incorpora los tres canales, restringe a dueño/admin y aísla reportes por tenant. Sin embargo, la suite completa aún presenta tres fallas en métricas/listados, por lo que la semántica de turnos, módulos y estados no está consolidada.

Resultado de pruebas:

| Grupo | Resultado |
|---|---:|
| Pruebas enfocadas H-01/H-02/H-03/H-05 | **51/51 aprobadas** |
| Suite Django completa | **297/302 aprobadas; 5 fallidas** |
| Tests Node del panel | **18/18 aprobados** |
| Build panel | **aprobado** |
| Build landing | **aprobado** |
| Lint panel | **aprobado** |
| Lint landing | **fallido: 13 errores** |
| `npm audit` panel | **fallido: 7 avisos** |
| `npm audit` landing | **fallido: 3 avisos** |
| `pip-audit` backend | **NO VERIFICABLE** |

**Veredicto: `NO APTO PARA DESPLIEGUE`.**

Los bloqueadores son el gate de dependencias aún fallido, las regresiones funcionales/integridad de métricas y pedidos, la falta de verificación del control Admin en Redis/Render y riesgos medios previos todavía presentes (uploads, CSP, tracking/PII, logging y controles de abuso).

## 2. Alcance y limitaciones

### Incluido

- Backend Django/DRF, modelos, serializers, permisos, servicios, middleware, settings, rutas y pruebas.
- Panel React/Vite y landing React/Vite, locks, dependencias instaladas, build, lint y tests disponibles.
- Configuración versionada: `.env.example`, `vercel.json`, settings y documentación de Render.
- Historial desde el 15 de julio de 2026 y diff lógico de los commits de remediación.
- Revisión enfocada en OWASP Top 10, OWASP API Security Top 10, CWE y prácticas de Django/DRF/React/Vite.

### Limitaciones

- No se accedió a producción ni a variables reales de Render/Vercel.
- No se comprobaron TLS, firewall, cabeceras reales, dominios, proxy inmediato, allowlist real, Redis real, PostgreSQL productivo, Cloudinary, SMTP, backups, observabilidad ni rotación externa.
- No se realizó DNS rebinding real ni conexiones de prueba contra proveedores Push.
- No se ejecutó una prueba concurrente real del guardado de reportes.
- `pip-audit` no pudo iniciarse por una restricción del intérprete base del entorno virtual; la elevación fue rechazada por política de egreso. No se sustituyó por otra consulta externa.
- La revisión de secretos cubrió nombres sensibles versionados, patrones comunes en el árbol actual y 173 commits; no sustituye una herramienta dedicada con reglas completas y acceso a todos los objetos/remotos.

## 3. Entorno y herramientas

- Windows/PowerShell.
- Python del `venv`, Django test runner y base de testing existente.
- Node test runner, Vite, ESLint y npm audit.
- Git (`status`, `log`, `show`, búsqueda de historial).
- `rg` para inventario y búsqueda estática.
- GitHub Advisory Database para verificar alcance y aplicabilidad de avisos npm publicados entre el 22 y 24 de julio.

No se muestran secretos ni variables completas.

## 4. Cambios posteriores a la línea base

| Commit | Fecha | Propósito |
|---|---|---|
| `5c791e6` | 22-jul | H-01 SSRF Web Push |
| `9380a0b` | 22-jul | H-04 dependencias |
| `b0eaba1` | 22-jul | H-02 política de contraseñas |
| `6c9f1c2`, `1d28ac6`, `92f660a`, `e6070af` | 23-jul | H-03 Admin/Redis/proxy/regresión |
| `7922beb` | 23-jul | H-05 métricas y reportes |

El commit de H-04 agregó además siete archivos vacíos con nombres anómalos en `Frontend/restaurante-front`; se documentan como N-02.

## 5. Comparación de hallazgos originales

| ID | Hallazgo | Estado anterior | Estado actual | Evidencia | Riesgo residual |
| -- | -------- | --------------- | ------------- | --------- | --------------- |
| H-01 | SSRF mediante Web Push | Confirmado, Alto | **CORREGIDO** | `webpush_endpoints.py:17-139`, `webpush.py:20-109`; 15 pruebas Web Push dentro del bloque enfocado aprobadas | Resolución DNS y conexión no están fijadas a la misma IP; riesgo bajo por allowlist de proveedores |
| H-02 | Política backend de contraseñas | Confirmado, Alto | **CORREGIDO PARCIALMENTE** | `serializers.py:136-297`, `auth_sessions.py:27-48`; 12 pruebas enfocadas aprobadas | Sin contraseña actual/reautenticación; access JWT vigente; reset autoservicio inexistente; PII nueva en logs |
| H-03 | Fuerza bruta en Django Admin | Confirmado, Alto | **CORREGIDO PARCIALMENTE** | `admin_security.py:107-335`, `settings.py:206-240`; 19 pruebas enfocadas aprobadas | Redis/Render no verificables; caída de cache no probada; sin MFA |
| H-04 | Dependencias vulnerables | Confirmado, Alto | **CORREGIDO PARCIALMENTE** | Versiones originales actualizadas; builds OK; `npm audit` actual no limpio | 7 avisos panel, 3 landing; backend `pip-audit` no verificable |
| H-05 | Métricas/reportes manipulables | Confirmado, Alto | **CORREGIDO PARCIALMENTE** | `views.py:2370-2559`, `reportes.py`, `productos.py`; 5 pruebas H-05 aprobadas | 3 fallas relacionadas en suite completa; concurrencia no probada activamente |

## 6. Análisis detallado H-01 a H-05

### H-01 — SSRF mediante Web Push

**Estado: CORREGIDO**

#### Flujo HTTP

- `POST /api/push/subscriptions/`
- Autenticación: JWT obligatoria.
- Roles: perfil activo de cualquier rol del tenant.
- Entrada: body `endpoint`, `keys`, `tipo_dispositivo`.
- Serializer: `PushSubscriptionSerializer`.
- Persistencia: `PushSubscription`, con endpoint único y restaurante derivado del perfil autenticado.
- Salida de red: `programar_push_nuevo_pedido` → executor → `enviar_push_nuevo_pedido` → `pywebpush`.

#### Evidencia

- Endpoint máximo 1000 caracteres y claves máximas de 255: `menu/serializers.py:36-60`.
- Solo HTTPS y puerto 443; rechaza credenciales, fragmento, caracteres de control, IP literal y hostname inválido: `menu/services/webpush_endpoints.py:96-136`.
- Allowlist exacta de FCM, Mozilla y Apple; sufijo controlado para WNS: líneas 17-23 y 56-62.
- `getaddrinfo(AF_UNSPEC, SOCK_STREAM)` y validación de **todas** las IP mediante `ipaddress.is_global`: líneas 65-93 y 138.
- Revalidación inmediatamente antes de `pywebpush`: `menu/services/webpush.py:57-74`.
- Suscripciones antiguas inseguras se desactivan y no llegan a la red: líneas 60-71.
- Sesión Requests fuerza `allow_redirects=False`: líneas 20-25 y 57-88.
- Timeout de cinco segundos y TTL 60: líneas 74-88.
- Errores 404/410 desactivan suscripción; logs omiten endpoint/keys: líneas 89-109.
- El tenant se deriva del usuario y no de `restaurante_id`: `menu/views.py:1992-2028`.

#### Pruebas

Se probaron HTTP/localhost/loopback/privadas/link-local/metadata/IPv6/formatos alternativos, credenciales, puerto, confusión de sufijo, DNS privado, DNS mixto, registros antiguos, redirecciones, aislamiento tenant, registro/renovación/baja y continuidad de pedidos. Todas aprobaron.

#### Riesgo residual

La validación resuelve DNS y la librería vuelve a resolver al conectar; no existe pinning de la IP validada. La allowlist impide que un usuario controle el DNS normalmente, por lo que no se confirmó una evasión explotable. Una defensa adicional sería usar un adaptador que conecte a una IP validada preservando SNI/Host, o delegar el envío a una red con egress allowlist.

### H-02 — Política backend de contraseñas

**Estado: CORREGIDO PARCIALMENTE**

#### Flujo HTTP

- `POST /api/mi-restaurante/usuarios/`: solo dueño; crea usuario.
- `PATCH /api/mi-restaurante/usuarios/<user_id>/`: solo dueño; edita usuario del mismo restaurante.
- Serializer de creación/edición valida antes de `create_user()`/`set_password()`.
- Al cambiar contraseña se revocan outstanding refresh tokens y sesiones Django.

#### Evidencia positiva

- `validate_password(password, user=candidate)`: `menu/serializers.py:188-217` y `260-276`.
- `MinimumLengthValidator(min_length=10)`, similitud, contraseña común y numérica: `core/settings.py:401-417`.
- El hash solo se modifica tras serializer válido: `menu/serializers.py:278-297`.
- Tenant del objetivo fijado en `get_object_or_404(... restaurante=perfil.restaurante)`: `menu/views.py:815-849`.
- Revocación de refresh tokens y sesiones Django: `menu/services/auth_sessions.py:27-48`.
- Django Admin usa los formularios estándar para `auth.User`; no se encontró otra llamada productiva a `set_password()` o `create_user()`.
- La recuperación pública actual solo solicita contacto administrativo; no recibe ni cambia contraseña.

#### Pruebas

Las pruebas HTTP aceptan una contraseña válida y rechazan corta, común, numérica, similar, ausente, nula, vacía y solo espacios. También validan preservación del hash en fallos, auditoría sin contraseña, revocación de refresh/sesión y rechazo cross-tenant. Todas aprobaron.

#### Cobertura incompleta

- El dueño puede cambiar su propia contraseña sin enviar la contraseña actual ni demostrar reautenticación reciente.
- Los access JWT ya emitidos no se revocan inmediatamente; duran hasta diez minutos (`SIMPLE_JWT.ACCESS_TOKEN_LIFETIME`).
- No existe un reset autoservicio con token de un solo uso; el proceso sigue siendo manual por administrador.
- No existe una prueba HTTP específica del formulario Django Admin, aunque este usa los validadores estándar.
- La nueva auditoría escribe usernames (frecuentemente correos) al log: N-01.

### H-03 — Fuerza bruta en Django Admin

**Estado: CORREGIDO PARCIALMENTE**

#### Flujo HTTP

- `POST /<ADMIN_URL_PATH>/login/`.
- Middleware anterior a la vista Admin: `AdminSecurityMiddleware`.
- Primero determina IP y aplica allowlist; luego consulta bloqueos y llama al login Django.
- Tras fallo incrementa buckets; tras éxito limpia cuenta/par IP, pero conserva el contador global de IP.

#### Evidencia positiva

- Buckets independientes y con TTL:
  - IP+usuario: 5/15 min, lock 15 min.
  - Cuenta global: 15/15 min, lock 30 min.
  - IP global: 50/15 min, lock 30 min.
- Usuario normalizado con NFKC, `strip()` y `casefold()`: `core/admin_security.py:173-195`.
- Identificadores hasheados; IP en logs enmascarada: líneas 56-64 y 169-189.
- `429`, `Retry-After` decreciente y `Cache-Control: no-store`: líneas 279-288.
- Ruta configurable y allowlist CIDR; fuera de allowlist responde 404: líneas 25-26, 153-166 y 297-309.
- `X-Forwarded-For` solo se confía cuando `REMOTE_ADDR` pertenece a `ADMIN_TRUSTED_PROXY_NETWORKS`; cadenas vacías/malformadas se rechazan: líneas 107-150.
- Producción exige Redis, allowlist y proxies confiables cuando se usa XFF: `core/settings.py:464-565`.
- Los thresholds evitan que cinco fallos contra A bloqueen a B desde la misma IP; las pruebas de cuenta e IP global aprobaron.

#### Cobertura incompleta

- Las pruebas usan el backend de caché local, no Redis.
- Las operaciones de cache no capturan errores del backend. Una caída de Redis probablemente produce 500 y bloquea el login Admin (fail-closed para confidencialidad, pero no resiliente).
- No se verificó que los rangos configurados correspondan realmente a los proxies inmediatos de Render.
- No se verificó la allowlist real.
- No hay MFA.

### H-04 — Dependencias vulnerables

**Estado: CORREGIDO PARCIALMENTE**

#### Backend

Las versiones originalmente señaladas fueron elevadas:

- Django `6.0.4` → `6.0.7`.
- Pillow `12.2.0` → `12.3.0`.
- idna `3.11` → `3.15`.
- También se elevaron PyJWT y urllib3.

`pip-audit` no pudo ejecutarse. Por tanto, el backend es **NO VERIFICABLE** respecto de vulnerabilidades conocidas actuales; no se infiere seguridad solo desde las versiones.

#### Panel

- Instalado: React Router/DOM `7.17.0`, Vite `8.1.4`, ESLint `9.39.4`.
- `npm audit`: 7 avisos (6 altos, 1 moderado).
- `npm audit --omit=dev`: 2 avisos de producción (1 alto, 1 moderado), concentrados en React Router.
- Build y lint: aprobados.

El aviso de DoS de React Router `<7.18.0` solo afecta Framework Mode; Menly usa `BrowserRouter/Routes` declarativo, por lo que ese vector concreto no es aplicable. Los avisos de RSC tampoco son aplicables porque no se usan APIs RSC inestables. El aviso de open redirect requiere que una ruta no confiable llegue a `<Link>`/`navigate`; no se encontró ese flujo en las llamadas actuales, pero la versión sigue dentro del rango reportado.

Referencias verificadas: [DoS de React Router en Framework Mode](https://github.com/advisories/GHSA-chx6-hx7r-mcp5) y [open redirect de React Router](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6).

#### Landing

- Instalado: React Router/DOM `7.18.1`, Vite `8.1.5`, ESLint `10.2.1`.
- `npm audit`: 3 altos.
- `npm audit --omit=dev`: 2 altos de producción.
- El aviso RSC de React Router afecta `>=7.12.0 <8.3.0`, pero solo si se usan APIs RSC inestables; Menly usa modo declarativo y no se encontró RSC.
- `brace-expansion` aparece en tooling de desarrollo.
- Build aprobado; lint falló con 13 errores.

Referencias verificadas: [CSRF en APIs RSC inestables](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) y [DoS de brace-expansion](https://github.com/advisories/GHSA-mh99-v99m-4gvg).

#### Locks e instalación

Los locks existen y la instalación corresponde a versiones resueltas en ellos. Sin embargo, los `package.json` usan rangos `^`, por lo que una reinstalación sin lock o una regeneración no controlada puede cambiar versiones. Los siete archivos vacíos agregados durante la actualización indican un proceso de actualización no limpio.

#### Conclusión H-04

Los CVE originales fueron atendidos, pero la política “auditoría limpia antes de desplegar” no se cumple y el backend no pudo reauditarse. No corresponde marcarlo `CORREGIDO`.

### H-05 — Manipulación de métricas y reportes

**Estado: CORREGIDO PARCIALMENTE**

#### Flujos HTTP

| Ruta | Método | Acceso |
|---|---|---|
| `/api/mi-restaurante/pedidos/metricas/` | GET | dueño/admin |
| `/api/mi-restaurante/metricas/resumen/` | GET | dueño/admin |
| `/api/metricas/reporte-mensual/` | GET | dueño/admin |
| `/api/metricas/reporte-anual/` | GET | dueño/admin |
| `/api/metricas/reportes/` | GET | dueño/admin |
| `/api/metricas/reportes/<id>/` | GET | dueño/admin y tenant |
| `/api/metricas/reportes/guardar/` | POST | dueño/admin |

#### Evidencia positiva

- Todos usan `IsAuthenticated, IsDuenoOrAdmin`: `menu/views.py:2370-2471`.
- El restaurante siempre proviene de `get_perfil_activo(request)`.
- El detalle filtra simultáneamente `id`, `restaurante` y `activo`: líneas 2455-2467.
- Guardado acepta tipo/periodo/título, pero ignora `restaurante_id`, `resumen`, `datos` y totales del cliente: líneas 2473-2549.
- Periodos mensuales exigen `YYYY-MM`; el constructor `date()` rechaza meses inválidos. Anual exige cuatro dígitos.
- Mensual/anual recalculan WhatsApp, especiales y manuales desde querysets tenant-scoped.
- Solo pedidos en estados finalizados suman venta; cancelados se separan.
- Los reportes incluyen los tres canales y manejan cero pedidos sin división por cero.
- Constraints condicionales impiden más de un reporte activo por tenant/tipo/periodo: `menu/models.py:1070-1081`.
- Las pruebas H-05 manipulan payload/tenant, verifican roles, IDOR y los tres canales; 5/5 aprobaron.

#### Evidencia que impide cierre completo

La suite completa falló en tres contratos relacionados:

1. `test_metricas_pedidos_resumen_diario_y_mensual`: `pedidos_activos` fue 0, esperado 1.
2. `test_metricas_resumen_venta_real_excluye_pendientes_y_cancelados`: `venta_real_mes` fue 10000, esperado 30000.
3. `test_pedido_especial_entregado_completa_solicitud_y_sale_del_listado_activo`: el pedido entregado siguió en el listado por defecto.

La causa está asociada a semánticas no alineadas:

- métricas del turno actual excluyen pedidos cuando no existe/encaja un turno;
- especiales se omiten en ciertos resúmenes cuando el módulo está inactivo, aunque existan datos históricos;
- los listados por defecto filtran `scope=turno_actual`, no “estados activos”, por lo que un entregado del turno permanece.

No se confirmó acceso cruzado ni manipulación de cifras, pero sí una integridad funcional incompleta. Además, aunque el constraint evita duplicados, no se probó el tratamiento de `IntegrityError` ante dos `update_or_create` simultáneos.

## 7. Hallazgos nuevos

### N-01 — Eventos de seguridad agregan PII a logs persistentes sin rotación

- **ID:** N-01
- **Título:** Usernames/correos en eventos de creación y cambio de contraseña.
- **Severidad:** Bajo.
- **Estado:** Confirmado; regresión introducida por H-02.
- **CWE:** CWE-532, inserción de información sensible en log.
- **OWASP:** A02:2025 Security Misconfiguration / A09 Security Logging and Alerting Failures.
- **CVSS aproximado:** 3.3 (`CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N`). Requiere acceso local o al sistema de logs y afecta principalmente confidencialidad de identificadores.
- **Archivos y líneas:** `menu/services/auth_sessions.py:14-24`; `core/settings.py:361-384`.
- **Flujo vulnerable:** creación/cambio de contraseña → `record_user_security_event()` → logger raíz → consola y `django.log` sin rotación.
- **Evidencia:** la ejecución de tests emitió `affected_username` y `actor_username`; en Menly esos usernames suelen ser correos. No se registró la contraseña.
- **Reproducción local segura:**
  1. Ejecutar `manage.py test menu.test_password_security`.
  2. Observar el evento `user_security_event`.
  3. Confirmar que incluye ambos usernames y que el handler `FileHandler` no rota.
- **Impacto real:** aumenta la copia y retención de PII en archivos de log, backups del host y agregadores.
- **Recomendación:** registrar IDs internos y resultado, no username/email; usar redacción, `RotatingFileHandler` o logging gestionado con retención/acceso definidos.
- **Prueba de regresión propuesta:** capturar el logger y afirmar que el evento contiene IDs/operación pero no username, email ni contraseña.

### N-02 — Archivos vacíos anómalos versionados durante actualización de dependencias

- **ID:** N-02
- **Título:** Artefactos huérfanos con nombres no portables en raíz del frontend.
- **Severidad:** Informativo.
- **Estado:** Confirmado.
- **CWE:** CWE-1104 como referencia de higiene de supply chain; no existe explotación confirmada.
- **OWASP:** A03:2025 Software Supply Chain Failures.
- **CVSS aproximado:** 0.0; no hay impacto directo demostrado.
- **Archivos y líneas:** siete archivos de cero bytes bajo `Frontend/restaurante-front`, agregados por `9380a0b`.
- **Flujo vulnerable:** proceso manual/comando de actualización → argumentos o salida interpretados como nombres de archivo → commit.
- **Evidencia:** `git show --stat 9380a0b` lista los siete archivos junto con locks/requirements.
- **Reproducción local segura:** ejecutar `git show --stat --oneline 9380a0b` y listar los archivos de tamaño cero de la raíz.
- **Impacto real:** ruido de repositorio, problemas de portabilidad/checkout y señal de un proceso de actualización no determinista.
- **Recomendación:** revisar su origen y eliminarlos en un cambio separado autorizado; automatizar `npm ci`, audit y revisión de diff.
- **Prueba de regresión propuesta:** CI que falle ante archivos raíz no permitidos, caracteres de control o artefactos vacíos inesperados.

### Conteo de hallazgos nuevos

| Severidad | Cantidad |
|---|---:|
| Crítico | 0 |
| Alto | 0 |
| Medio | 0 |
| Bajo | 1 |
| Informativo | 1 |

Los avisos de dependencias publicados después de la línea base se contabilizan dentro de H-04 para no duplicar el mismo riesgo.

## 8. Revisión sistemática adicional

### Autenticación y sesiones

- Access JWT de 10 minutos; refresh de 7 días, rotación y blacklist.
- Refresh en cookie `HttpOnly`, `SameSite=Lax`, `Secure` en producción; path `/api/`.
- Logout y cambio de contraseña revocan refresh. Access ya emitido no se invalida.
- Refresh aún acepta token en body para migración legacy: superficie residual hasta retirar compatibilidad.
- Refresh sigue sin validar explícitamente perfil/restaurante activo antes de emitir un access nuevo; permisos posteriores reducen impacto, pero es deuda previa M-07.
- Recuperación evita enumeración en respuesta, pero sigue siendo manual (M-08).

### Autorización y multi-tenant

- En las rutas revisadas, el tenant se deriva del perfil autenticado o sesión KDS.
- IDs de objetos se vuelven a filtrar por restaurante.
- Las pruebas de tenant/IDOR incluidas en la suite no evidenciaron acceso horizontal.
- Empleados ya no acceden a métricas/reportes.
- Los endpoints operativos de pedidos/reservas siguen permitiendo empleados conforme a la política existente.

### Entradas y vulnerabilidades web

- No se encontró SQL manual, `raw()`, `extra()`, `eval`, ejecución de comandos con input o deserialización insegura.
- No se encontró `dangerouslySetInnerHTML`; React escapa texto.
- No se confirmó SQLi, XSS, path traversal, header injection u open redirect explotable.
- Uploads siguen sin controles completos de MIME real, tamaño, dimensiones, re-encode o cuota: riesgo previo M-01.
- `buildApiUrl` acepta URL absoluta, pero todas las llamadas `authFetch` revisadas construyen rutas internas; no se confirmó exfiltración de JWT.

### Funciones Menly

- Tracking tokens usan `secrets.token_urlsafe(12)` y unicidad; no se observó enumeración práctica.
- Tracking sigue sin expiración y expone datos de entrega según el contrato previo M-02.
- Idempotencia y transiciones usan constraints/transacciones/locks.
- KDS conserva activación de un uso y cookie firmada, pero sesiones de 30 días sin gestión por dispositivo (M-06).
- El motor de transición rechaza saltos de estado; dos tests antiguos esperan saltos que ahora reciben 409.
- Persisten inconsistencias entre “turno actual”, “estado activo” e históricos.

### Configuración y despliegue

- Producción exige `DEBUG=False` de forma indirecta y falla si faltan variables críticas.
- `ALLOWED_HOSTS` restringido y `*` rechazado en producción.
- HTTPS redirect, cookies seguras y HSTS se activan cuando no hay DEBUG.
- Cabeceras básicas están configuradas.
- CSP continúa construida pero no se envía; Vercel tampoco declara CSP (M-04).
- CORS con credenciales sigue aceptando cualquier subdominio `*.menly.cl` (M-03).
- No se encontraron claves privadas/tokens comunes en el árbol actual ni nombres sensibles versionados.
- No hay IaC/Render config versionada para demostrar el entorno real.
- El endpoint público `/api/debug/time/` sigue registrado (L-01).

### Disponibilidad, abuso y privacidad

- Throttling global: anónimo 120/min, usuario 600/min; scopes específicos para login, reset, reservas, solicitudes, clics y contacto.
- La creación pública de pedidos no tiene scope específico y depende del throttle anónimo/global y LocMem/Redis: riesgo previo M-05.
- `page_size` se limita a 50 en listados que usan el helper común.
- Executor Web Push tiene cuatro workers pero cola no acotada; abuso de pedidos puede acumular tareas (riesgo residual previo).
- Logs siguen en archivo sin rotación y existen mensajes con PII (M-11 y N-01).

## 9. Pruebas ejecutadas, comandos y resultados

### Backend

```text
venv\Scripts\python.exe manage.py test \
  menu.test_webpush menu.test_password_security \
  core.test_admin_security menu.test_h05_metricas_financieras --keepdb
```

Resultado: **51 tests, OK**, 124.040 s.

```text
venv\Scripts\python.exe manage.py test --keepdb
```

Resultado: **302 tests; 297 OK; 5 fallos**, 801.209 s.

Fallos:

1. `ConfiguracionRestauranteOperacionTests.test_delivery_activado_permite_estado_en_reparto`: esperado 200, recibido 409.
2. `ConfiguracionRestauranteOperacionTests.test_delivery_desactivado_rechaza_estado_en_reparto`: esperado 400, recibido 409.
3. `SeguridadCriticaTests.test_metricas_pedidos_resumen_diario_y_mensual`: activos 0, esperado 1.
4. `SeguridadCriticaTests.test_metricas_resumen_venta_real_excluye_pendientes_y_cancelados`: 10000, esperado 30000.
5. `SeguridadCriticaTests.test_pedido_especial_entregado_completa_solicitud_y_sale_del_listado_activo`: entregado presente en listado.

Los dos primeros son expectativas antiguas frente al motor que ahora impide saltar directamente de confirmado a reparto; los tres últimos son inconsistencias funcionales reales pendientes de decisión/ajuste.

```text
venv\Scripts\python.exe manage.py check --deploy
```

Resultado: no llegó al check porque el guard de producción detectó variables locales ausentes (`ADMIN_ALLOWED_NETWORKS`, `DATABASE_URL`, `REDIS_URL`). Esto demuestra fail-fast, pero no valida el deployment real.

### Frontend panel

```text
npm.cmd run build
```

Resultado: aprobado; warning por chunks superiores a 500 kB.

```text
npm.cmd run lint
```

Resultado: aprobado.

```text
node --test tests/*.test.mjs
```

Resultado: **18/18 aprobados**.

```text
npm.cmd audit --json
npm.cmd audit --omit=dev --json
```

Resultado: exit 1; 7 avisos totales y 2 sin dev.

### Frontend landing

```text
npm.cmd run build
```

Resultado: aprobado.

```text
npm.cmd run lint
```

Resultado: exit 1; **13 errores** en `home.jsx` y `vite.config.js`.

```text
npm.cmd audit --json
npm.cmd audit --omit=dev --json
```

Resultado: exit 1; 3 avisos totales y 2 sin dev.

### Historial, secretos y repositorio

- Working tree inicial y previo al informe: limpio.
- 173 commits inspeccionables.
- Sin nombres `.env`, claves privadas o credenciales versionados según las búsquedas realizadas.
- Sin coincidencias de patrones comunes de private keys/tokens en árbol actual ni patches Git revisados.
- `git diff --check`: aprobado.

## 10. Pruebas no ejecutadas o no verificables

| Comprobación | Estado | Motivo |
|---|---|---|
| `pip-audit -r requirements.txt` | NO VERIFICABLE | intérprete base bloqueado; elevación rechazada por política de egreso |
| Redis real/distribuido | NO VERIFICABLE | no hay Redis de testing disponible |
| Caída/latencia/mala configuración Redis | NO VERIFICABLE | mismo motivo |
| Proxy XFF/REMOTE_ADDR real de Render | NO VERIFICABLE | sin acceso a infraestructura |
| Allowlist Admin real | NO VERIFICABLE | variable de producción no accesible |
| TLS/cookies/cabeceras/CORS reales | NO VERIFICABLE | no se atacó ni consultó producción |
| DNS rebinding y pinning de conexión Push | NO VERIFICABLE | no se realizaron ataques/red a proveedores externos |
| Carrera simultánea de reportes | NO VERIFICABLE | no se creó prueba concurrente temporal |
| Backups, RPO/RTO y restauración | NO VERIFICABLE | no hay infraestructura/configuración disponible |
| Cloudinary/SMTP productivos | NO VERIFICABLE | sin credenciales ni llamadas externas |

## 11. Riesgos residuales

### Bloqueadores

1. H-04 no tiene auditoría limpia y el backend no fue revalidado con `pip-audit`.
2. H-05 conserva tres fallas de integridad/contrato en métricas y pedidos.
3. H-03 no está probado con Redis/Render reales.

### Altos/medios heredados aún abiertos

- Uploads inseguros (M-01).
- Tracking sin expiración/PII (M-02).
- CORS amplio a subdominios (M-03).
- CSP ausente (M-04).
- Throttling/colas/payloads no completamente acotados (M-05).
- KDS 30 días sin gestión de dispositivos (M-06).
- Refresh de perfiles desactivados (M-07).
- Reset manual (M-08).
- Contratos de turnos/listados/métricas (M-09).
- Logs con PII y sin rotación (M-11/N-01).
- Carrera de reservas tipo check-then-save (M-12).

## 12. Recomendaciones priorizadas

### P0 — Antes de desplegar

1. Resolver explícitamente los cinco fallos Django: actualizar implementación o contrato, sin simplemente cambiar asserts.
2. Definir una sola semántica para:
   - ventas históricas cuando un módulo se desactiva;
   - pedido “activo” versus “pertenece al turno”;
   - transición de delivery desde confirmado.
3. Dejar `npm audit` en un estado aceptado/documentado:
   - actualizar panel a React Router `>=7.18.0` por avisos aplicables a versiones anteriores;
   - evaluar versión/parche para el aviso RSC, documentando formalmente su no aplicabilidad mientras se use modo declarativo;
   - corregir `brace-expansion`/ESLint cuando exista ruta compatible.
4. Ejecutar `pip-audit` en CI o un entorno autorizado y remediar cualquier aviso.
5. Probar Admin con Redis y topología Render reales en staging, incluyendo outage, spoofing XFF, allowlist y varias cuentas/IP.

### P1 — Antes de producción con datos reales

1. Exigir contraseña actual o reautenticación reciente al dueño para cambiar su propia contraseña.
2. Invalidar access tokens mediante versión de sesión/contraseña o reducir la ventana residual.
3. Implementar reset con token de un uso y expiración.
4. Eliminar PII de logs y definir rotación/retención.
5. Activar CSP en report-only y luego enforcement.
6. Validar/re-encode uploads y aplicar cuotas.
7. Expirar tracking y minimizar PII.
8. Añadir throttle específico a pedidos públicos y cola Web Push acotada.

### P2 — Proceso

1. CI obligatorio: Django completo, Node tests, ambos lints, ambos builds, `pip-audit`, `npm audit` y `check --deploy` con settings de staging.
2. Pruebas de concurrencia PostgreSQL para reportes, reservas, secuencias y estados.
3. Eliminar los siete artefactos vacíos solo tras revisión/autorización.
4. Versionar IaC o, como mínimo, un checklist verificable de Render/Vercel/Redis.
5. Añadir secret scanning dedicado y política de dependencias/locks.

## 13. Veredicto final

# NO APTO PARA DESPLIEGUE

La corrección de SSRF es sólida y los controles de contraseñas, Admin y reportes representan avances importantes. Sin embargo, el criterio solicitado exige evidencia completa, no solo presencia de funciones o tests enfocados. La suite global conserva cinco fallos, H-04 sigue con auditorías Node no limpias y backend no verificable, H-03 depende de infraestructura no probada y H-05 mantiene contratos de integridad inconsistentes.

Uso permitido con la evidencia actual:

- Desarrollo local: **sí**.
- Demo interna con datos ficticios: **sí, aceptando las fallas conocidas**.
- Staging controlado para completar verificaciones: **sí**.
- Piloto con datos/operación real: **no**.
- Producción multi-restaurante: **no**.
