# Cierre mensual automático en Render

El repositorio no contiene actualmente un Blueprint `render.yaml`; el servicio
web se administra desde Render. El cierre debe crearse como un **Cron Job**
separado, no como temporizador dentro de Gunicorn ni como tarea del frontend.

## Configuración recomendada

- **Name:** `menly-reportes-mensuales`
- **Repository / branch:** los mismos del backend.
- **Root directory:** `backend/Back-end-Restaurantes` si el repositorio completo
  es la raíz conectada en Render.
- **Build command:** el mismo del backend (como mínimo,
  `pip install -r requirements.txt`).
- **Command:**

  ```bash
  python manage.py generar_reportes_mensuales --scheduled --include-inactive
  ```

- **Schedule:** `10 4 * * *` (UTC, ejecución diaria).
- **Environment variables:** reutilizar el mismo `DATABASE_URL`, `SECRET_KEY`,
  `ENVIRONMENT=production` y demás variables necesarias del servicio web.

Render evalúa el cron en UTC. `04:10 UTC` ocurre después de las 00:05 tanto
cuando Chile está en UTC-4 (`00:10`) como cuando está en UTC-3 (`01:10`). El
comando calcula los meses cerrados con `TIME_ZONE=America/Santiago`, por lo que
no usa un desfase chileno fijo.

La frecuencia diaria es deliberada: el comando es idempotente, conserva los
reportes existentes y recupera todos los meses cerrados faltantes. Si un
restaurante falla, los demás continúan y el siguiente cron vuelve a intentar
el cierre pendiente. Un resultado parcial termina con código distinto de cero
para que Render marque la ejecución como fallida.

## Operación manual segura

Antes de generar octubre de 2026 en producción, obtener autorización y hacer
un respaldo. Luego ejecutar una única vez desde un Shell/One-off Job conectado
a la misma base:

```bash
python manage.py generar_reportes_mensuales --periodo 2026-10 --include-inactive
```

Para detectar y completar cualquier mes anterior faltante:

```bash
python manage.py generar_reportes_mensuales --backfill --include-inactive
```

No usar `--regenerate` en automatizaciones. Esa opción reemplaza deliberadamente
un snapshot y queda reservada a una operación manual autorizada.

## Comprobación

En Django Admin, abrir **Reportes y Métricas > Reportes mensuales** y filtrar
por restaurante, año y mes. El encabezado muestra el último procesamiento. El
detalle completo de cada corrida está en **Ejecuciones de reportes mensuales**,
visible sólo para superadministradores.
