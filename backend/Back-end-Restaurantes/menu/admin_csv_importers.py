import csv
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .cache_utils import invalidate_menu_cache
from .models import (
    GrupoOpcionesProducto,
    OpcionProducto,
    Producto,
    ProductoVariante,
    Restaurante,
)


VARIANTES_COLUMNAS = (
    "restaurante_slug",
    "producto_nombre",
    "nombre",
    "descripcion",
    "precio",
    "activo",
    "orden",
)

PERSONALIZACION_COLUMNAS = (
    "restaurante_slug",
    "producto_nombre",
    "grupo_nombre",
    "grupo_obligatorio",
    "grupo_minimo",
    "grupo_maximo",
    "grupo_orden",
    "opcion_nombre",
    "opcion_precio_adicional",
    "opcion_disponible",
    "opcion_orden",
)

BOOLEANOS = {
    "true": True,
    "1": True,
    "false": False,
    "0": False,
}


class CSVImportError(Exception):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("\n".join(errores))


def _leer_csv(contenido, columnas):
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError([
            "El archivo debe estar codificado en UTF-8 (se acepta UTF-8 con BOM)."
        ]) from exc

    reader = csv.DictReader(texto.splitlines())
    encabezados = tuple(reader.fieldnames or ())
    if encabezados != columnas:
        raise CSVImportError([
            "Encabezados inválidos. Deben ser exactamente: " + ",".join(columnas) + "."
        ])

    filas = list(reader)
    if not filas:
        raise CSVImportError(["El archivo CSV no contiene filas para importar."])
    return filas


def _texto_requerido(row, campo, fila, errores, max_length=None):
    valor = (row.get(campo) or "").strip()
    if not valor:
        errores.append(f"Fila {fila}: {campo} es obligatorio.")
    elif max_length is not None and len(valor) > max_length:
        errores.append(f"Fila {fila}: {campo} no puede superar {max_length} caracteres.")
    return valor


def _booleano(row, campo, fila, errores):
    valor = (row.get(campo) or "").strip().lower()
    if valor not in BOOLEANOS:
        errores.append(
            f"Fila {fila}: {campo} debe ser TRUE, FALSE, true, false, 1 o 0."
        )
        return None
    return BOOLEANOS[valor]


def _entero_no_negativo(row, campo, fila, errores, permite_vacio=False):
    valor = (row.get(campo) or "").strip()
    if permite_vacio and valor == "":
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        errores.append(f"Fila {fila}: {campo} debe ser un entero válido.")
        return None
    if numero < 0:
        errores.append(f"Fila {fila}: {campo} no puede ser negativo.")
        return None
    return numero


def _precio_no_negativo(row, campo, fila, errores):
    valor = (row.get(campo) or "").strip()
    try:
        precio = Decimal(valor)
    except (InvalidOperation, TypeError):
        errores.append(f"Fila {fila}: {campo} debe ser un precio válido.")
        return None
    if not precio.is_finite() or precio < 0:
        errores.append(f"Fila {fila}: {campo} no puede ser negativo.")
        return None
    if precio != precio.to_integral_value() or precio >= Decimal("100000000"):
        errores.append(
            f"Fila {fila}: {campo} debe ser un entero entre 0 y 99999999."
        )
        return None
    return precio


def _resolver_producto(row, fila, errores):
    slug = _texto_requerido(row, "restaurante_slug", fila, errores)
    nombre = _texto_requerido(row, "producto_nombre", fila, errores, max_length=150)
    if not slug or not nombre:
        return None, None

    try:
        restaurante = Restaurante.objects.get(slug=slug)
    except Restaurante.DoesNotExist:
        errores.append(f'Fila {fila}: No existe el restaurante "{slug}".')
        return None, None

    try:
        producto = Producto.objects.get(restaurante=restaurante, nombre=nombre)
    except Producto.DoesNotExist:
        errores.append(
            f'Fila {fila}: No existe el producto "{nombre}" para el restaurante "{slug}".'
        )
        return restaurante, None
    return restaurante, producto


def importar_variantes_csv(contenido):
    filas = _leer_csv(contenido, VARIANTES_COLUMNAS)
    errores = []
    registros = []
    identidades = set()

    for numero_fila, row in enumerate(filas, start=2):
        restaurante, producto = _resolver_producto(row, numero_fila, errores)
        nombre = _texto_requerido(row, "nombre", numero_fila, errores, max_length=100)
        descripcion = (row.get("descripcion") or "").strip()
        precio = _precio_no_negativo(row, "precio", numero_fila, errores)
        activo = _booleano(row, "activo", numero_fila, errores)
        orden = _entero_no_negativo(row, "orden", numero_fila, errores)

        identidad = (producto.pk, nombre) if producto and nombre else None
        if identidad in identidades:
            errores.append(
                f'Fila {numero_fila}: La variante "{nombre}" está repetida para este producto.'
            )
        elif identidad:
            identidades.add(identidad)

        if all(valor is not None for valor in [restaurante, producto, precio, activo, orden]) and nombre:
            registros.append({
                "restaurante": restaurante,
                "producto": producto,
                "nombre": nombre,
                "descripcion": descripcion,
                "precio": precio,
                "activo": activo,
                "orden": orden,
            })

    if errores:
        raise CSVImportError(errores)

    creados = 0
    actualizados = 0
    restaurantes = {}
    with transaction.atomic():
        for registro in registros:
            _variante, creada = ProductoVariante.objects.update_or_create(
                producto=registro["producto"],
                nombre=registro["nombre"],
                defaults={
                    "descripcion": registro["descripcion"],
                    "precio": registro["precio"],
                    "activo": registro["activo"],
                    "orden": registro["orden"],
                },
            )
            creados += int(creada)
            actualizados += int(not creada)
            restaurantes[registro["restaurante"].pk] = registro["restaurante"]

    for restaurante in restaurantes.values():
        invalidate_menu_cache(restaurante)
    return {"creados": creados, "actualizados": actualizados}


def importar_personalizacion_csv(contenido):
    filas = _leer_csv(contenido, PERSONALIZACION_COLUMNAS)
    errores = []
    grupos = OrderedDict()
    opciones_identidades = set()

    for numero_fila, row in enumerate(filas, start=2):
        restaurante, producto = _resolver_producto(row, numero_fila, errores)
        grupo_nombre = _texto_requerido(
            row, "grupo_nombre", numero_fila, errores, max_length=100
        )
        obligatorio = _booleano(row, "grupo_obligatorio", numero_fila, errores)
        minimo = _entero_no_negativo(row, "grupo_minimo", numero_fila, errores)
        maximo = _entero_no_negativo(
            row, "grupo_maximo", numero_fila, errores, permite_vacio=True
        )
        grupo_orden = _entero_no_negativo(row, "grupo_orden", numero_fila, errores)
        opcion_nombre = _texto_requerido(
            row, "opcion_nombre", numero_fila, errores, max_length=100
        )
        precio = _precio_no_negativo(
            row, "opcion_precio_adicional", numero_fila, errores
        )
        disponible = _booleano(row, "opcion_disponible", numero_fila, errores)
        opcion_orden = _entero_no_negativo(row, "opcion_orden", numero_fila, errores)

        if obligatorio is True and minimo is not None and minimo < 1:
            errores.append(
                f"Fila {numero_fila}: Un grupo obligatorio debe tener grupo_minimo mayor o igual a 1."
            )
        if maximo is not None and minimo is not None and maximo < minimo:
            errores.append(
                f"Fila {numero_fila}: grupo_maximo no puede ser menor que grupo_minimo."
            )

        if not producto or not grupo_nombre:
            continue

        grupo_clave = (producto.pk, grupo_nombre)
        configuracion = (obligatorio, minimo, maximo, grupo_orden)
        grupo = grupos.get(grupo_clave)
        if grupo and grupo["configuracion"] != configuracion:
            errores.append(
                f'Fila {numero_fila}: La configuración del grupo "{grupo_nombre}" '
                "no coincide con sus filas anteriores."
            )
        elif not grupo:
            grupo = {
                "restaurante": restaurante,
                "producto": producto,
                "nombre": grupo_nombre,
                "obligatorio": obligatorio,
                "minimo": minimo,
                "maximo": maximo,
                "orden": grupo_orden,
                "configuracion": configuracion,
                "opciones": [],
            }
            grupos[grupo_clave] = grupo

        opcion_clave = (producto.pk, grupo_nombre, opcion_nombre)
        if opcion_nombre and opcion_clave in opciones_identidades:
            errores.append(
                f'Fila {numero_fila}: La opción "{opcion_nombre}" está repetida en el grupo "{grupo_nombre}".'
            )
        elif opcion_nombre:
            opciones_identidades.add(opcion_clave)

        if (
            opcion_nombre
            and precio is not None
            and disponible is not None
            and opcion_orden is not None
        ):
            grupo["opciones"].append({
                "nombre": opcion_nombre,
                "precio": precio,
                "disponible": disponible,
                "orden": opcion_orden,
            })

    for grupo in grupos.values():
        if None in (grupo["obligatorio"], grupo["minimo"], grupo["orden"]):
            continue
        nombres_importados = [opcion["nombre"] for opcion in grupo["opciones"]]
        existente = GrupoOpcionesProducto.objects.filter(
            producto=grupo["producto"], nombre=grupo["nombre"]
        ).first()
        disponibles_existentes = 0
        if existente:
            disponibles_existentes = existente.opciones.filter(disponible=True).exclude(
                nombre__in=nombres_importados
            ).count()
        disponibles_finales = disponibles_existentes + sum(
            opcion["disponible"] for opcion in grupo["opciones"]
        )
        minimo_efectivo = max(grupo["minimo"], 1 if grupo["obligatorio"] else 0)
        if disponibles_finales < minimo_efectivo:
            errores.append(
                f'Grupo "{grupo["nombre"]}" del producto "{grupo["producto"].nombre}": '
                f"requiere al menos {minimo_efectivo} opciones disponibles y quedaría con "
                f"{disponibles_finales}."
            )

    if errores:
        raise CSVImportError(errores)

    grupos_creados = 0
    grupos_actualizados = 0
    opciones_creadas = 0
    opciones_actualizadas = 0
    restaurantes = {}
    with transaction.atomic():
        for registro in grupos.values():
            grupo, creado = GrupoOpcionesProducto.objects.update_or_create(
                producto=registro["producto"],
                nombre=registro["nombre"],
                defaults={
                    "obligatorio": registro["obligatorio"],
                    "minimo_selecciones": registro["minimo"],
                    "maximo_selecciones": registro["maximo"],
                    "orden": registro["orden"],
                },
            )
            grupos_creados += int(creado)
            grupos_actualizados += int(not creado)

            for opcion in registro["opciones"]:
                _opcion, creada = OpcionProducto.objects.update_or_create(
                    grupo=grupo,
                    nombre=opcion["nombre"],
                    defaults={
                        "precio_adicional": opcion["precio"],
                        "disponible": opcion["disponible"],
                        "orden": opcion["orden"],
                    },
                )
                opciones_creadas += int(creada)
                opciones_actualizadas += int(not creada)
            restaurantes[registro["restaurante"].pk] = registro["restaurante"]

    for restaurante in restaurantes.values():
        invalidate_menu_cache(restaurante)
    return {
        "grupos_creados": grupos_creados,
        "grupos_actualizados": grupos_actualizados,
        "opciones_creadas": opciones_creadas,
        "opciones_actualizadas": opciones_actualizadas,
    }
