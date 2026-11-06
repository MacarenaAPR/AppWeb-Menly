import csv
import io
import json
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from menu.models import (
    GrupoOpcionesProducto,
    OpcionProducto,
    PedidoManual,
    PedidoManualItem,
    PedidoPruebaImportado,
    Producto,
    ProductoVariante,
    Restaurante,
)
from menu.services.secuencia_pedidos import obtener_siguiente_numero_pedido


PEDIDOS_PRUEBA_COLUMNAS = [
    "identificador_externo",
    "restaurante_slug",
    "fecha_creacion",
    "estado",
    "tipo_entrega",
    "nombre_cliente",
    "telefono_cliente",
    "direccion",
    "numero_mesa",
    "observaciones_pedido",
    "producto_id",
    "variante_id",
    "cantidad",
    "precio_unitario",
    "precio_original",
    "porcentaje_descuento",
    "monto_descuento",
    "subtotal_item",
    "observaciones_item",
    "opciones_json",
    "total_pedido",
]

EJEMPLO_PEDIDO_PRUEBA = {
    "identificador_externo": "oct-2026-001",
    "restaurante_slug": "mi-restaurante",
    "fecha_creacion": "2026-10-15T20:30:00-03:00",
    "estado": PedidoManual.ESTADO_ENTREGADO,
    "tipo_entrega": PedidoManual.TIPO_RETIRO,
    "nombre_cliente": "Cliente de prueba",
    "telefono_cliente": "+56900000000",
    "direccion": "",
    "numero_mesa": "",
    "observaciones_pedido": "Dato simulado para staging",
    "producto_id": "1",
    "variante_id": "",
    "cantidad": "2",
    "precio_unitario": "5000",
    "precio_original": "6000",
    "porcentaje_descuento": "17",
    "monto_descuento": "1000",
    "subtotal_item": "10000",
    "observaciones_item": "",
    "opciones_json": "[]",
    "total_pedido": "10000",
}


class ImportacionPedidosPruebaError(Exception):
    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("El CSV contiene errores de validación.")


def plantilla_csv_pedidos_prueba():
    salida = io.StringIO(newline="")
    writer = csv.DictWriter(salida, fieldnames=PEDIDOS_PRUEBA_COLUMNAS)
    writer.writeheader()
    writer.writerow(EJEMPLO_PEDIDO_PRUEBA)
    return "\ufeff" + salida.getvalue()


def _texto(valor):
    return str(valor or "").strip()


def _entero(valor, etiqueta, fila, minimo=0):
    try:
        numero = int(_texto(valor))
    except (TypeError, ValueError):
        raise ValueError(f"Fila {fila}: {etiqueta} debe ser un entero.")
    if numero < minimo:
        raise ValueError(f"Fila {fila}: {etiqueta} debe ser mayor o igual a {minimo}.")
    return numero


def _monto(valor, etiqueta, fila, obligatorio=True):
    texto = _texto(valor)
    if not texto and not obligatorio:
        return None
    try:
        monto = Decimal(texto)
        es_entero_no_negativo = (
            monto.is_finite()
            and monto >= 0
            and monto == monto.quantize(Decimal("1"))
        )
    except InvalidOperation:
        raise ValueError(f"Fila {fila}: {etiqueta} no es un monto válido.")
    if not es_entero_no_negativo:
        raise ValueError(f"Fila {fila}: {etiqueta} debe ser un entero no negativo.")
    return monto


def _fecha(valor, fila):
    try:
        fecha = datetime.fromisoformat(_texto(valor).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(
            f"Fila {fila}: fecha_creacion debe usar ISO 8601, por ejemplo 2026-10-15T20:30:00-03:00."
        )
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.get_current_timezone())
    return fecha


def _opciones(valor, producto, fila):
    try:
        grupos = json.loads(_texto(valor) or "[]")
    except json.JSONDecodeError:
        raise ValueError(f"Fila {fila}: opciones_json no contiene JSON válido.")
    if not isinstance(grupos, list):
        raise ValueError(f"Fila {fila}: opciones_json debe ser una lista JSON.")

    for grupo in grupos:
        if not isinstance(grupo, dict):
            raise ValueError(f"Fila {fila}: cada grupo de opciones debe ser un objeto JSON.")
        grupo_id = grupo.get("grupo_id")
        if grupo_id and not GrupoOpcionesProducto.objects.filter(
            pk=grupo_id, producto=producto
        ).exists():
            raise ValueError(f"Fila {fila}: el grupo {grupo_id} no pertenece al producto.")
        for opcion in grupo.get("opciones") or []:
            opcion_id = opcion.get("opcion_id") if isinstance(opcion, dict) else None
            if not opcion_id or not OpcionProducto.objects.filter(
                pk=opcion_id, grupo__producto=producto
            ).exists():
                raise ValueError(f"Fila {fila}: una opción no pertenece al producto.")
    return grupos


def validar_csv_pedidos_prueba(contenido):
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8-sig")
    else:
        contenido = str(contenido).lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(contenido, newline=""))
    faltantes = [columna for columna in PEDIDOS_PRUEBA_COLUMNAS if columna not in (reader.fieldnames or [])]
    if faltantes:
        return {
            "pedidos": [],
            "pedidos_validos": 0,
            "pedidos_rechazados": 0,
            "errores": ["Faltan columnas obligatorias: " + ", ".join(faltantes)],
            "filas": 0,
        }

    errores = []
    pedidos = OrderedDict()
    claves_invalidas = set()
    estados = dict(PedidoManual.ESTADOS)
    tipos_entrega = dict(PedidoManual.TIPOS_ENTREGA)
    filas = 0

    for numero_fila, row in enumerate(reader, start=2):
        filas += 1
        clave_csv = ("__fila__", numero_fila)
        try:
            externo = _texto(row["identificador_externo"])
            slug = _texto(row["restaurante_slug"])
            if not externo or not slug:
                raise ValueError(f"Fila {numero_fila}: identificador_externo y restaurante_slug son obligatorios.")
            clave_csv = (slug, externo)
            restaurante = Restaurante.objects.filter(slug=slug).first()
            if not restaurante:
                raise ValueError(f"Fila {numero_fila}: el restaurante {slug} no existe.")
            if PedidoPruebaImportado.objects.filter(
                restaurante=restaurante,
                identificador_externo=externo,
            ).exists():
                raise ValueError(f"Fila {numero_fila}: el identificador externo ya fue importado.")

            estado = _texto(row["estado"])
            tipo_entrega = _texto(row["tipo_entrega"])
            if estado not in estados:
                raise ValueError(f"Fila {numero_fila}: estado no válido: {estado}.")
            if tipo_entrega not in tipos_entrega:
                raise ValueError(f"Fila {numero_fila}: tipo_entrega no válido: {tipo_entrega}.")

            producto_id = _entero(row["producto_id"], "producto_id", numero_fila, 1)
            producto = Producto.objects.filter(pk=producto_id, restaurante=restaurante).first()
            if not producto:
                raise ValueError(
                    f"Fila {numero_fila}: el producto {producto_id} no pertenece al restaurante {slug}."
                )
            variante = None
            if _texto(row["variante_id"]):
                variante_id = _entero(row["variante_id"], "variante_id", numero_fila, 1)
                variante = ProductoVariante.objects.filter(
                    pk=variante_id,
                    producto=producto,
                ).first()
                if not variante:
                    raise ValueError(f"Fila {numero_fila}: la variante no pertenece al producto.")

            cantidad = _entero(row["cantidad"], "cantidad", numero_fila, 1)
            precio_unitario = _monto(row["precio_unitario"], "precio_unitario", numero_fila)
            precio_original = _monto(row["precio_original"], "precio_original", numero_fila, obligatorio=False)
            porcentaje = (
                _entero(row["porcentaje_descuento"], "porcentaje_descuento", numero_fila, 1)
                if _texto(row["porcentaje_descuento"])
                else None
            )
            if porcentaje is not None and porcentaje > 99:
                raise ValueError(f"Fila {numero_fila}: porcentaje_descuento debe estar entre 1 y 99.")
            monto_descuento = _monto(row["monto_descuento"], "monto_descuento", numero_fila, obligatorio=False)
            subtotal = _monto(row["subtotal_item"], "subtotal_item", numero_fila)
            total_pedido = _monto(row["total_pedido"], "total_pedido", numero_fila)
            if subtotal != precio_unitario * cantidad:
                raise ValueError(
                    f"Fila {numero_fila}: subtotal_item debe ser precio_unitario × cantidad."
                )
            if precio_original is not None and monto_descuento is not None:
                if monto_descuento > precio_original:
                    raise ValueError(f"Fila {numero_fila}: monto_descuento supera precio_original.")
            opciones = _opciones(row["opciones_json"], producto, numero_fila)

            metadata = {
                "restaurante": restaurante,
                "identificador_externo": externo,
                "fecha_creacion": _fecha(row["fecha_creacion"], numero_fila),
                "estado": estado,
                "tipo_entrega": tipo_entrega,
                "nombre_cliente": _texto(row["nombre_cliente"]),
                "telefono_cliente": _texto(row["telefono_cliente"]),
                "direccion": _texto(row["direccion"]),
                "numero_mesa": _texto(row["numero_mesa"]),
                "observaciones": _texto(row["observaciones_pedido"]),
                "total": total_pedido,
            }
            if clave_csv not in pedidos:
                pedidos[clave_csv] = {
                    **metadata,
                    "fila_inicio": numero_fila,
                    "items": [],
                }
            else:
                existente = pedidos[clave_csv]
                for campo, valor in metadata.items():
                    existente_valor = existente.get(campo)
                    if campo == "restaurante":
                        existente_valor = existente["restaurante"]
                    if existente_valor != valor:
                        raise ValueError(
                            f"Fila {numero_fila}: {campo} no coincide con las otras filas del pedido {externo}."
                        )

            pedidos[clave_csv]["items"].append({
                "producto": producto,
                "variante": variante,
                "nombre_producto": producto.nombre,
                "variante_nombre": variante.nombre if variante else "",
                "precio_unitario": precio_unitario,
                "precio_original": precio_original,
                "porcentaje_descuento_aplicado": porcentaje,
                "monto_descuento": monto_descuento,
                "cantidad": cantidad,
                "subtotal": subtotal,
                "observaciones": _texto(row["observaciones_item"]),
                "opciones_snapshot": opciones,
            })
        except (ValueError, UnicodeDecodeError) as exc:
            errores.append(str(exc))
            claves_invalidas.add(clave_csv)

    for clave_csv, pedido in pedidos.items():
        suma = sum(item["subtotal"] for item in pedido["items"])
        if suma != pedido["total"]:
            errores.append(
                f"Pedido {pedido['identificador_externo']}: total_pedido={pedido['total']} "
                f"no coincide con la suma de ítems={suma}."
            )
            claves_invalidas.add(clave_csv)

    if not filas:
        errores.append("El CSV no contiene filas de pedidos.")

    pedidos_validos = [
        pedido for clave_csv, pedido in pedidos.items()
        if clave_csv not in claves_invalidas
    ]
    return {
        "pedidos": pedidos_validos,
        "pedidos_validos": len(pedidos_validos),
        "pedidos_rechazados": len(claves_invalidas),
        "errores": errores,
        "filas": filas,
    }


def importar_pedidos_prueba(contenido, *, actor, archivo_origen=""):
    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("Sólo un superadministrador puede importar pedidos de prueba.")
    if not settings.TEST_ORDER_IMPORT_ENABLED:
        raise PermissionDenied(
            "La importación de pedidos de prueba está deshabilitada en este entorno."
        )
    resultado = validar_csv_pedidos_prueba(contenido)
    if resultado["errores"]:
        raise ImportacionPedidosPruebaError(resultado["errores"])

    creados = []
    with transaction.atomic():
        for datos in resultado["pedidos"]:
            marca = PedidoPruebaImportado.objects.create(
                restaurante=datos["restaurante"],
                identificador_externo=datos["identificador_externo"],
                archivo_origen=archivo_origen[:255],
                fila_inicio=datos["fila_inicio"],
                creado_por=actor,
                datos_origen={
                    "fecha_creacion": datos["fecha_creacion"].isoformat(),
                    "estado": datos["estado"],
                    "tipo_entrega": datos["tipo_entrega"],
                    "total": int(datos["total"]),
                },
            )
            pedido = PedidoManual.objects.create(
                restaurante=datos["restaurante"],
                numero_pedido=obtener_siguiente_numero_pedido(datos["restaurante"]),
                origen=PedidoManual.ORIGEN_MENLY,
                estado=datos["estado"],
                nombre_cliente=datos["nombre_cliente"],
                telefono_cliente=datos["telefono_cliente"],
                tipo_entrega=datos["tipo_entrega"],
                direccion=datos["direccion"],
                numero_mesa=datos["numero_mesa"],
                observaciones=datos["observaciones"],
                subtotal=datos["total"],
                total=datos["total"],
                creado_por=actor,
            )
            PedidoManualItem.objects.bulk_create([
                PedidoManualItem(pedido=pedido, **item)
                for item in datos["items"]
            ])
            PedidoManual.objects.filter(pk=pedido.pk).update(
                fecha_creacion=datos["fecha_creacion"],
                fecha_actualizacion=datos["fecha_creacion"],
            )
            marca.pedido_manual = pedido
            marca.save(update_fields=["pedido_manual"])
            creados.append(pedido)
    return {"pedidos_creados": len(creados), "items_creados": sum(len(p["items"]) for p in resultado["pedidos"])}
