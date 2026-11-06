import csv
import json
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from cloudinary import CloudinaryResource
from django.db.models import Model
from django.http import HttpResponse


ENCABEZADOS_PRODUCTOS = [
    "producto_id",
    "restaurante_id",
    "restaurante_nombre",
    "restaurante_slug",
    "categoria_id",
    "categoria_nombre",
    "nombre",
    "descripcion",
    "condiciones",
    "precio_normal",
    "precio_efectivo",
    "porcentaje_descuento",
    "monto_descuento",
    "imagen_valor",
    "imagen_url",
    "disponible",
    "destacado",
    "orden",
    "fecha_creacion",
    "clicks",
    "producto_campos_json",
    "categoria_json",
    "variantes_json",
    "grupos_opciones_json",
]


def _url_cloudinary(recurso):
    try:
        return recurso.url or ""
    except (AttributeError, TypeError, ValueError):
        return ""


def _cloudinary_json(recurso):
    if not recurso or not recurso.public_id:
        return None
    try:
        valor_persistido = recurso.get_prep_value() or recurso.public_id
    except (AttributeError, TypeError, ValueError):
        valor_persistido = recurso.public_id
    return {
        "valor": valor_persistido,
        "public_id": recurso.public_id,
        "url": _url_cloudinary(recurso),
        "format": recurso.format,
        "version": recurso.version,
        "type": recurso.type,
        "resource_type": recurso.resource_type,
    }


def _valor_json(valor):
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, CloudinaryResource):
        return _cloudinary_json(valor)
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, Model):
        return {
            "modelo": valor._meta.label_lower,
            "pk": _valor_json(valor.pk),
        }
    if isinstance(valor, dict):
        return {str(clave): _valor_json(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_valor_json(item) for item in valor]
    if hasattr(valor, "name"):
        return str(valor.name or "")
    raise TypeError(
        f"El valor de tipo {type(valor).__name__} no tiene una serialización CSV definida."
    )


def serializar_campos_modelo(instancia):
    return {
        campo.attname: _valor_json(getattr(instancia, campo.attname))
        for campo in instancia._meta.concrete_fields
    }


def _json(valor):
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def fila_producto(producto):
    categoria = serializar_campos_modelo(producto.categoria)
    categoria["icono"] = (
        serializar_campos_modelo(producto.categoria.icono)
        if producto.categoria.icono_id
        else None
    )
    variantes = [
        serializar_campos_modelo(variante)
        for variante in producto.variantes.all()
    ]
    grupos = []
    for grupo in producto.grupos_opciones.all():
        datos_grupo = serializar_campos_modelo(grupo)
        datos_grupo["opciones"] = [
            serializar_campos_modelo(opcion)
            for opcion in grupo.opciones.all()
        ]
        grupos.append(datos_grupo)

    imagen = producto.imagen
    imagen_url = _url_cloudinary(imagen) if imagen else ""

    return {
        "producto_id": producto.id,
        "restaurante_id": producto.restaurante_id,
        "restaurante_nombre": producto.restaurante.nombre_empresa,
        "restaurante_slug": producto.restaurante.slug,
        "categoria_id": producto.categoria_id,
        "categoria_nombre": producto.categoria.nombre,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion,
        "condiciones": producto.condiciones,
        "precio_normal": str(producto.precio),
        "precio_efectivo": str(producto.precio_efectivo),
        "porcentaje_descuento": producto.porcentaje_descuento or "",
        "monto_descuento": str(producto.monto_descuento),
        "imagen_valor": str(imagen or ""),
        "imagen_url": imagen_url,
        "disponible": producto.disponible,
        "destacado": producto.destacado,
        "orden": producto.orden,
        "fecha_creacion": producto.fecha_creacion.isoformat(),
        "clicks": producto.clicks,
        "producto_campos_json": _json(serializar_campos_modelo(producto)),
        "categoria_json": _json(categoria),
        "variantes_json": _json(variantes),
        "grupos_opciones_json": _json(grupos),
    }


def respuesta_csv_productos(queryset, nombre_archivo="productos-menly.csv"):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    response.write("\ufeff")
    writer = csv.DictWriter(response, fieldnames=ENCABEZADOS_PRODUCTOS)
    writer.writeheader()
    queryset = (
        queryset.select_related("restaurante", "categoria", "categoria__icono")
        .prefetch_related("variantes", "grupos_opciones__opciones")
        .order_by("restaurante_id", "categoria_id", "orden", "id")
    )
    for producto in queryset:
        writer.writerow(fila_producto(producto))
    return response
