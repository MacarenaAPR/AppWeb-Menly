import csv
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .admin_csv_importers import (
    CSVImportError,
    PERSONALIZACION_COLUMNAS,
    VARIANTES_COLUMNAS,
    importar_personalizacion_csv,
    importar_variantes_csv,
)
from .models import (
    Categoria,
    GrupoOpcionesProducto,
    OpcionProducto,
    Producto,
    ProductoVariante,
    Restaurante,
)


def crear_csv(columnas, filas):
    salida = StringIO(newline="")
    writer = csv.DictWriter(salida, fieldnames=columnas, lineterminator="\n")
    writer.writeheader()
    writer.writerows(filas)
    return salida.getvalue().encode("utf-8-sig")


class AdminCSVImportBaseTests(TestCase):
    def setUp(self):
        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Sushi Costanera",
            slug="sushicostanera-fernando",
            telefono="999999999",
            email_contacto="sushi@example.com",
            direccion="Costanera 100",
            ciudad="Antofagasta",
        )
        self.otro_restaurante = Restaurante.objects.create(
            nombre_empresa="Otro restaurante",
            slug="otro-restaurante",
            telefono="988888888",
            email_contacto="otro@example.com",
            direccion="Otra 200",
            ciudad="Santiago",
        )
        self.categoria = Categoria.objects.create(
            restaurante=self.restaurante, nombre="Sushi", orden=0
        )
        self.otra_categoria = Categoria.objects.create(
            restaurante=self.otro_restaurante, nombre="Sushi", orden=0
        )
        self.producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Elección del Cliente",
            precio=10000,
            orden=0,
        )
        self.segundo_producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Roll Especial",
            precio=9000,
            orden=1,
        )
        self.producto_otro_tenant = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.otra_categoria,
            nombre="Producto exclusivo",
            precio=8000,
            orden=0,
        )

    def fila_variante(self, **cambios):
        fila = {
            "restaurante_slug": self.restaurante.slug,
            "producto_nombre": self.producto.nombre,
            "nombre": "20 piezas",
            "descripcion": "Selección clásica",
            "precio": "12000",
            "activo": "TRUE",
            "orden": "0",
        }
        fila.update(cambios)
        return fila

    def fila_personalizacion(self, **cambios):
        fila = {
            "restaurante_slug": self.restaurante.slug,
            "producto_nombre": self.producto.nombre,
            "grupo_nombre": "Proteína",
            "grupo_obligatorio": "TRUE",
            "grupo_minimo": "1",
            "grupo_maximo": "1",
            "grupo_orden": "0",
            "opcion_nombre": "Camarón",
            "opcion_precio_adicional": "0",
            "opcion_disponible": "TRUE",
            "opcion_orden": "0",
        }
        fila.update(cambios)
        return fila


class VariantesCSVImportTests(AdminCSVImportBaseTests):
    def test_importa_multiples_variantes_campos_y_utf8_bom(self):
        contenido = crear_csv(VARIANTES_COLUMNAS, [
            self.fila_variante(),
            self.fila_variante(
                nombre="30 piezas",
                descripcion="Selección fría",
                precio="15000",
                activo="0",
                orden="1",
            ),
        ])

        resultado = importar_variantes_csv(contenido)

        self.assertEqual(resultado, {"creados": 2, "actualizados": 0})
        variantes = list(self.producto.variantes.order_by("orden"))
        self.assertEqual([variante.nombre for variante in variantes], ["20 piezas", "30 piezas"])
        self.assertEqual(variantes[0].descripcion, "Selección clásica")
        self.assertEqual(variantes[0].precio, 12000)
        self.assertTrue(variantes[0].activo)
        self.assertFalse(variantes[1].activo)
        self.assertEqual(variantes[1].orden, 1)

    def test_reimporta_sin_duplicar_y_actualiza(self):
        importar_variantes_csv(crear_csv(VARIANTES_COLUMNAS, [self.fila_variante()]))

        resultado = importar_variantes_csv(crear_csv(VARIANTES_COLUMNAS, [
            self.fila_variante(precio="13500", activo="false", orden="4")
        ]))

        self.assertEqual(resultado, {"creados": 0, "actualizados": 1})
        self.assertEqual(ProductoVariante.objects.count(), 1)
        variante = ProductoVariante.objects.get()
        self.assertEqual(variante.precio, 13500)
        self.assertFalse(variante.activo)
        self.assertEqual(variante.orden, 4)

    def test_rechaza_restaurante_producto_inexistentes_y_aisla_tenant(self):
        contenido = crear_csv(VARIANTES_COLUMNAS, [
            self.fila_variante(restaurante_slug="no-existe"),
            self.fila_variante(producto_nombre="No existe", nombre="Otra"),
            self.fila_variante(producto_nombre="Producto exclusivo", nombre="Ajena"),
        ])

        with self.assertRaises(CSVImportError) as contexto:
            importar_variantes_csv(contenido)

        mensaje = str(contexto.exception)
        self.assertIn('No existe el restaurante "no-existe"', mensaje)
        self.assertIn('No existe el producto "No existe"', mensaje)
        self.assertIn('No existe el producto "Producto exclusivo"', mensaje)
        self.assertFalse(ProductoVariante.objects.exists())

    def test_error_critico_revierte_toda_la_importacion(self):
        contenido = crear_csv(VARIANTES_COLUMNAS, [
            self.fila_variante(),
            self.fila_variante(nombre="30 piezas", precio="15000", orden="1"),
        ])
        original = ProductoVariante.objects.update_or_create
        llamadas = 0

        def fallar_en_segunda(*args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("fallo simulado")
            return original(*args, **kwargs)

        with patch(
            "menu.admin_csv_importers.ProductoVariante.objects.update_or_create",
            side_effect=fallar_en_segunda,
        ):
            with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
                importar_variantes_csv(contenido)

        self.assertFalse(ProductoVariante.objects.exists())


class PersonalizacionCSVImportTests(AdminCSVImportBaseTests):
    def test_importa_grupos_opciones_campos_multiples_productos_y_utf8_bom(self):
        contenido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(),
            self.fila_personalizacion(opcion_nombre="Pollo crispy", opcion_orden="1"),
            self.fila_personalizacion(
                grupo_nombre="Extra",
                grupo_obligatorio="FALSE",
                grupo_minimo="0",
                grupo_maximo="",
                grupo_orden="1",
                opcion_nombre="Palta adicional",
                opcion_precio_adicional="1000",
            ),
            self.fila_personalizacion(
                producto_nombre=self.segundo_producto.nombre,
                grupo_nombre="Salsa fría",
                grupo_obligatorio="false",
                grupo_minimo="0",
                grupo_maximo="1",
                grupo_orden="0",
                opcion_nombre="Teriyaki",
                opcion_disponible="0",
            ),
        ])

        resultado = importar_personalizacion_csv(contenido)

        self.assertEqual(resultado["grupos_creados"], 3)
        self.assertEqual(resultado["opciones_creadas"], 4)
        proteina = GrupoOpcionesProducto.objects.get(producto=self.producto, nombre="Proteína")
        self.assertTrue(proteina.obligatorio)
        self.assertEqual(proteina.minimo_selecciones, 1)
        self.assertEqual(proteina.maximo_selecciones, 1)
        self.assertEqual(proteina.orden, 0)
        self.assertCountEqual(
            proteina.opciones.values_list("nombre", flat=True),
            ["Camarón", "Pollo crispy"],
        )
        extra = GrupoOpcionesProducto.objects.get(producto=self.producto, nombre="Extra")
        self.assertIsNone(extra.maximo_selecciones)
        palta = extra.opciones.get(nombre="Palta adicional")
        self.assertEqual(palta.precio_adicional, 1000)
        self.assertTrue(palta.disponible)
        salsa = GrupoOpcionesProducto.objects.get(producto=self.segundo_producto)
        self.assertFalse(salsa.opciones.get().disponible)

    def test_reimporta_sin_duplicar_y_actualiza_grupo_y_opcion(self):
        importar_personalizacion_csv(
            crear_csv(PERSONALIZACION_COLUMNAS, [self.fila_personalizacion()])
        )

        resultado = importar_personalizacion_csv(crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(
                grupo_orden="3",
                opcion_precio_adicional="1500",
                opcion_orden="2",
            )
        ]))

        self.assertEqual(resultado["grupos_actualizados"], 1)
        self.assertEqual(resultado["opciones_actualizadas"], 1)
        self.assertEqual(GrupoOpcionesProducto.objects.count(), 1)
        self.assertEqual(OpcionProducto.objects.count(), 1)
        grupo = GrupoOpcionesProducto.objects.get()
        opcion = OpcionProducto.objects.get()
        self.assertEqual(grupo.orden, 3)
        self.assertEqual(opcion.precio_adicional, 1500)
        self.assertEqual(opcion.orden, 2)

    def test_rechaza_relaciones_inexistentes_y_aisla_tenant(self):
        contenido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(restaurante_slug="no-existe"),
            self.fila_personalizacion(producto_nombre="Producto inexistente"),
            self.fila_personalizacion(producto_nombre="Producto exclusivo"),
        ])

        with self.assertRaises(CSVImportError) as contexto:
            importar_personalizacion_csv(contenido)

        mensaje = str(contexto.exception)
        self.assertIn('No existe el restaurante "no-existe"', mensaje)
        self.assertIn('No existe el producto "Producto inexistente"', mensaje)
        self.assertIn('No existe el producto "Producto exclusivo"', mensaje)
        self.assertFalse(GrupoOpcionesProducto.objects.exists())

    def test_valida_booleanos_minimo_maximo_precio_y_orden(self):
        contenido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(
                grupo_obligatorio="quizás",
                grupo_minimo="-1",
                grupo_maximo="-2",
                grupo_orden="abc",
                opcion_precio_adicional="-100",
                opcion_disponible="sí",
                opcion_orden="-1",
            )
        ])

        with self.assertRaises(CSVImportError) as contexto:
            importar_personalizacion_csv(contenido)

        mensaje = str(contexto.exception)
        self.assertIn("grupo_obligatorio debe ser TRUE", mensaje)
        self.assertIn("grupo_minimo no puede ser negativo", mensaje)
        self.assertIn("grupo_maximo no puede ser negativo", mensaje)
        self.assertIn("opcion_precio_adicional no puede ser negativo", mensaje)
        self.assertIn("opcion_disponible debe ser TRUE", mensaje)
        self.assertFalse(GrupoOpcionesProducto.objects.exists())

    def test_valida_estado_final_sin_fallar_durante_creacion_progresiva(self):
        valido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(grupo_minimo="2", grupo_maximo="2"),
            self.fila_personalizacion(
                grupo_minimo="2",
                grupo_maximo="2",
                opcion_nombre="Pollo",
                opcion_orden="1",
            ),
        ])
        importar_personalizacion_csv(valido)
        self.assertEqual(OpcionProducto.objects.count(), 2)

        invalido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(
                grupo_nombre="Otro grupo",
                grupo_minimo="2",
                grupo_maximo="2",
            )
        ])
        with self.assertRaisesRegex(CSVImportError, "requiere al menos 2 opciones disponibles"):
            importar_personalizacion_csv(invalido)
        self.assertFalse(GrupoOpcionesProducto.objects.filter(nombre="Otro grupo").exists())

    def test_error_critico_revierte_grupo_y_todas_sus_opciones(self):
        contenido = crear_csv(PERSONALIZACION_COLUMNAS, [
            self.fila_personalizacion(),
            self.fila_personalizacion(opcion_nombre="Pollo", opcion_orden="1"),
        ])
        original = OpcionProducto.objects.update_or_create
        llamadas = 0

        def fallar_en_segunda(*args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("fallo simulado")
            return original(*args, **kwargs)

        with patch(
            "menu.admin_csv_importers.OpcionProducto.objects.update_or_create",
            side_effect=fallar_en_segunda,
        ):
            with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
                importar_personalizacion_csv(contenido)

        self.assertFalse(GrupoOpcionesProducto.objects.exists())
        self.assertFalse(OpcionProducto.objects.exists())


class AdminCSVImportInterfaceTests(AdminCSVImportBaseTests):
    def setUp(self):
        super().setUp()
        self.superusuario = User.objects.create_superuser(
            username="admin-csv", email="admin@example.com", password="segura123"
        )
        self.client.force_login(self.superusuario)

    def test_listado_productos_expone_ambos_importadores(self):
        response = self.client.get(reverse("admin:menu_producto_changelist"))

        self.assertContains(response, "Importar variantes CSV")
        self.assertContains(response, "Importar personalización CSV")

    def test_error_normal_del_csv_se_muestra_sin_traceback(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        archivo = SimpleUploadedFile(
            "variantes.csv",
            crear_csv(VARIANTES_COLUMNAS, [self.fila_variante(restaurante_slug="no-existe")]),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("admin:importar_variantes_csv"),
            {"archivo_csv": archivo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No existe el restaurante &quot;no-existe&quot;')
        self.assertFalse(ProductoVariante.objects.exists())
