# CSV de productos y pedidos de prueba

## Exportación de productos

En Django Admin, `Productos` permite exportar la selección desde el menú de
acciones o descargar todos los productos desde el botón superior. El archivo
usa UTF-8 con BOM y una fila por producto.

Las columnas simples contienen los datos comerciales de uso frecuente. Las
columnas `producto_campos_json`, `categoria_json`, `variantes_json` y
`grupos_opciones_json` conservan todos los campos persistidos, IDs, timestamps,
variantes, grupos y opciones. `grupos_opciones_json` anida las opciones dentro
de su grupo. No existe un modelo de imágenes adicionales de producto.

Sólo se incluyen ID, nombre y slug del restaurante. No se exportan usuarios,
correos administrativos, credenciales, configuración de notificaciones ni
otros datos internos del tenant.

## Formato de pedidos de prueba

La plantilla se descarga desde `Pedidos manuales > Descargar plantilla CSV`.
Cada fila representa un ítem. Varias filas con el mismo
`restaurante_slug` e `identificador_externo` forman un solo pedido y deben
repetir exactamente sus datos generales.

| Columna | Descripción |
|---|---|
| `identificador_externo` | Clave estable del pedido simulado. Es única por restaurante. |
| `restaurante_slug` | Tenant receptor. |
| `fecha_creacion` | ISO 8601, idealmente con offset: `2026-10-15T20:30:00-03:00`. |
| `estado` | `pendiente`, `preparando`, `listo`, `en_reparto`, `entregado` o `cancelado`. |
| `tipo_entrega` | `mesa`, `retiro`, `delivery` o `para_llevar`. |
| `nombre_cliente`, `telefono_cliente` | Datos simulados. |
| `direccion`, `numero_mesa` | Según el tipo de entrega. |
| `observaciones_pedido` | Texto libre del pedido. |
| `producto_id` | ID real exportado; debe pertenecer al restaurante. |
| `variante_id` | Opcional; debe pertenecer al producto. |
| `cantidad` | Entero positivo. |
| `precio_unitario` | Precio histórico final por unidad, entero no negativo. |
| `precio_original` | Precio histórico anterior al descuento; opcional. |
| `porcentaje_descuento` | Opcional, entre 1 y 99. |
| `monto_descuento` | Descuento histórico por unidad; opcional. |
| `subtotal_item` | Debe ser `precio_unitario × cantidad`. |
| `observaciones_item` | Texto libre del ítem. |
| `opciones_json` | Lista JSON; los IDs deben pertenecer al producto. Use `[]` si no hay opciones. |
| `total_pedido` | Debe repetirse y coincidir con la suma de todos sus ítems. |

## Flujo seguro

1. Cargar el CSV como **Sólo validar** para ejecutar un dry-run.
2. Corregir cualquier error de tenant, IDs, estados, precios o totales.
3. Seleccionar **Validar y preparar confirmación**.
4. Revisar la vista previa.
5. Confirmar explícitamente sólo en development o staging.

La escritura requiere superusuario y `TEST_ORDER_IMPORT_ENABLED=true`. En
producción la opción está deshabilitada por defecto. El importador crea pedidos
manuales e ítems directamente dentro de una transacción; no invoca WhatsApp,
Web Push ni integraciones externas. Cada pedido queda asociado a
`PedidoPruebaImportado`, por lo que puede identificarse y no puede repetirse.

No se deben ejecutar importaciones de prueba en la base comercial de
producción. Las métricas de staging incluirán estos pedidos para validar días,
semanas y meses históricos.
