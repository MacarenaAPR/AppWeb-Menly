import csv
import io
import json
from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from cloudinary import CloudinaryResource
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings

from menu.admin import ProductoAdmin
from menu.models import (
    Categoria,
    GrupoOpcionesProducto,
    Icono,
    OpcionProducto,
    PedidoManual,
    PedidoPruebaImportado,
    Producto,
    ProductoVariante,
    Restaurante,
    UsuarioRestaurante,
)
from menu.services.exportacion_productos import (
    ENCABEZADOS_PRODUCTOS,
    respuesta_csv_productos,
)
from menu.services.importacion_pedidos_prueba import (
    PEDIDOS_PRUEBA_COLUMNAS,
    ImportacionPedidosPruebaError,
    importar_pedidos_prueba,
    plantilla_csv_pedidos_prueba,
    validar_csv_pedidos_prueba,
)


def csv_pedidos(filas):
    salida = io.StringIO(newline="")
    writer = csv.DictWriter(salida, fieldnames=PEDIDOS_PRUEBA_COLUMNAS)
    writer.writeheader()
    writer.writerows(filas)
    return "\ufeff" + salida.getvalue()


class CSVProductosPedidosPruebaBase(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username="root-csv", email="root@example.com", password="secret"
        )
        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Menly Centro",
            slug="menly-centro",
            telefono="999999999",
            email_contacto="centro@example.com",
            direccion="Centro 123",
            ciudad="Santiago",
        )
        self.otro_restaurante = Restaurante.objects.create(
            nombre_empresa="Menly Norte",
            slug="menly-norte",
            telefono="988888888",
            email_contacto="norte@example.com",
            direccion="Norte 456",
            ciudad="Antofagasta",
        )
        self.icono = Icono.objects.create(
            nombre="Hamburguesa", clase_css="bi-burger-csv", orden=3
        )
        self.categoria = Categoria.objects.create(
            restaurante=self.restaurante,
            nombre="Promociones",
            orden=2,
            icono=self.icono,
        )
        self.otra_categoria = Categoria.objects.create(
            restaurante=self.otro_restaurante, nombre="Carta", orden=0
        )
        self.producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre='Combo "Especial", familiar',
            descripcion="Primera línea, con coma\nSegunda línea",
            condiciones="Solo de lunes a viernes",
            precio=12000,
            porcentaje_descuento=25,
            disponible=True,
            destacado=True,
            orden=4,
            clicks=17,
        )
        self.producto_ajeno = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.otra_categoria,
            nombre="Producto ajeno",
            precio=9000,
            orden=0,
        )
        self.variante = ProductoVariante.objects.create(
            producto=self.producto,
            nombre="Grande",
            descripcion="Tamaño grande",
            precio=15000,
            activo=True,
            orden=1,
        )
        self.grupo = GrupoOpcionesProducto.objects.create(
            producto=self.producto,
            nombre="Salsas",
            obligatorio=True,
            minimo_selecciones=1,
            maximo_selecciones=2,
            orden=1,
        )
        self.opcion = OpcionProducto.objects.create(
            grupo=self.grupo,
            nombre="Picante",
            precio_adicional=500,
            disponible=True,
            orden=2,
        )
        self.otra_opcion = OpcionProducto.objects.create(
            grupo=self.grupo,
            nombre="Ajo",
            precio_adicional=250,
            disponible=False,
            orden=3,
        )

    def fila_pedido(self, **cambios):
        fila = {
            "identificador_externo": "historico-2026-001",
            "restaurante_slug": self.restaurante.slug,
            "fecha_creacion": "2026-10-15T20:30:00-03:00",
            "estado": PedidoManual.ESTADO_ENTREGADO,
            "tipo_entrega": PedidoManual.TIPO_RETIRO,
            "nombre_cliente": "Cliente simulado",
            "telefono_cliente": "+56900000000",
            "direccion": "",
            "numero_mesa": "",
            "observaciones_pedido": "Prueba histórica",
            "producto_id": str(self.producto.id),
            "variante_id": str(self.variante.id),
            "cantidad": "2",
            "precio_unitario": "7500",
            "precio_original": "8000",
            "porcentaje_descuento": "6",
            "monto_descuento": "500",
            "subtotal_item": "15000",
            "observaciones_item": "Sin cebolla",
            "opciones_json": json.dumps([
                {
                    "grupo_id": self.grupo.id,
                    "opciones": [{"opcion_id": self.opcion.id, "nombre": "Picante"}],
                }
            ]),
            "total_pedido": "15000",
        }
        fila.update(cambios)
        return fila


class ExportacionProductosCSVTests(CSVProductosPedidosPruebaBase):
    def test_exporta_campos_relaciones_utf8_y_no_modifica_datos(self):
        antes = list(
            Producto.objects.order_by("id").values_list(
                "id", "nombre", "precio", "porcentaje_descuento", "clicks"
            )
        )

        response = respuesta_csv_productos(Producto.objects.filter(pk=self.producto.pk))
        contenido = response.content.decode("utf-8-sig")
        filas = list(csv.DictReader(io.StringIO(contenido, newline="")))

        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(list(filas[0]), ENCABEZADOS_PRODUCTOS)
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila["nombre"], self.producto.nombre)
        self.assertEqual(fila["descripcion"], self.producto.descripcion)
        self.assertEqual(fila["precio_normal"], "12000")
        self.assertEqual(fila["precio_efectivo"], "9000")
        self.assertEqual(fila["monto_descuento"], "3000")
        self.assertEqual(fila["restaurante_slug"], self.restaurante.slug)

        campos = json.loads(fila["producto_campos_json"])
        categoria = json.loads(fila["categoria_json"])
        variantes = json.loads(fila["variantes_json"])
        grupos = json.loads(fila["grupos_opciones_json"])
        self.assertEqual(campos["id"], self.producto.id)
        self.assertEqual(categoria["icono"]["id"], self.icono.id)
        self.assertEqual(variantes[0]["id"], self.variante.id)
        self.assertEqual(grupos[0]["id"], self.grupo.id)
        self.assertEqual(grupos[0]["opciones"][0]["id"], self.opcion.id)
        self.assertEqual(len(grupos[0]["opciones"]), 2)
        self.assertEqual(
            antes,
            list(
                Producto.objects.order_by("id").values_list(
                    "id", "nombre", "precio", "porcentaje_descuento", "clicks"
                )
            ),
        )

    def test_queryset_admin_respeta_tenant_y_superusuario_ve_todos(self):
        staff = User.objects.create_user(
            username="staff-csv", password="secret", is_staff=True
        )
        UsuarioRestaurante.objects.create(
            user=staff, restaurante=self.restaurante, rol="admin", activo=True
        )
        model_admin = ProductoAdmin(Producto, admin.site)
        request = RequestFactory().get("/admin/menu/producto/")

        request.user = staff
        self.assertQuerySetEqual(
            model_admin.get_queryset(request),
            Producto.objects.filter(restaurante=self.restaurante),
            ordered=False,
        )
        request.user = self.superusuario
        self.assertEqual(model_admin.get_queryset(request).count(), 2)

    def test_exporta_cloudinary_y_productos_sin_imagen_en_ambas_acciones(self):
        self.producto.imagen = CloudinaryResource(
            public_id="productos/combo-especial",
            format="jpg",
            version="123456",
            type="upload",
            resource_type="image",
        )
        self.producto.save(update_fields=["imagen"])
        self.producto.refresh_from_db()
        model_admin = ProductoAdmin(Producto, admin.site)
        request = RequestFactory().get("/admin/menu/producto/")
        request.user = self.superusuario

        seleccionados = model_admin.exportar_productos_seleccionados_csv(
            request,
            Producto.objects.filter(pk__in=[self.producto.pk, self.producto_ajeno.pk]),
        )
        todos = model_admin.exportar_todos_csv(request)

        for response in (seleccionados, todos):
            filas = list(csv.DictReader(io.StringIO(
                response.content.decode("utf-8-sig"), newline=""
            )))
            self.assertEqual(len(filas), 2)
            por_id = {int(fila["producto_id"]): fila for fila in filas}
            fila_imagen = por_id[self.producto.id]
            imagen_json = json.loads(fila_imagen["producto_campos_json"])["imagen"]
            self.assertEqual(imagen_json["public_id"], "productos/combo-especial")
            self.assertEqual(
                imagen_json["valor"],
                "image/upload/v123456/productos/combo-especial.jpg",
            )
            self.assertEqual(imagen_json["url"], fila_imagen["imagen_url"])
            self.assertIn("productos/combo-especial", imagen_json["url"])
            self.assertEqual(imagen_json["format"], "jpg")
            self.assertEqual(
                json.loads(
                    por_id[self.producto_ajeno.id]["producto_campos_json"]
                )["imagen"],
                None,
            )
            self.assertEqual(por_id[self.producto_ajeno.id]["imagen_valor"], "")
            self.assertEqual(por_id[self.producto_ajeno.id]["imagen_url"], "")


class ImportacionPedidosPruebaCSVTests(CSVProductosPedidosPruebaBase):
    def test_plantilla_es_csv_utf8_con_todas_las_columnas(self):
        contenido = plantilla_csv_pedidos_prueba()
        self.assertTrue(contenido.startswith("\ufeff"))
        reader = csv.DictReader(io.StringIO(contenido.lstrip("\ufeff")))
        self.assertEqual(reader.fieldnames, PEDIDOS_PRUEBA_COLUMNAS)
        self.assertEqual(len(list(reader)), 1)

    def test_dry_run_valida_multiples_items_y_no_escribe(self):
        contenido = csv_pedidos([
            self.fila_pedido(cantidad="1", subtotal_item="7500", total_pedido="15000"),
            self.fila_pedido(
                variante_id="",
                cantidad="1",
                subtotal_item="7500",
                observaciones_item="Segundo item",
                total_pedido="15000",
            ),
        ])

        resultado = validar_csv_pedidos_prueba(contenido)

        self.assertEqual(resultado["errores"], [])
        self.assertEqual(resultado["filas"], 2)
        self.assertEqual(resultado["pedidos_validos"], 1)
        self.assertEqual(resultado["pedidos_rechazados"], 0)
        self.assertEqual(len(resultado["pedidos"]), 1)
        self.assertEqual(len(resultado["pedidos"][0]["items"]), 2)
        self.assertFalse(PedidoManual.objects.exists())
        self.assertFalse(PedidoPruebaImportado.objects.exists())

    def test_rechaza_producto_de_otro_tenant(self):
        resultado = validar_csv_pedidos_prueba(csv_pedidos([
            self.fila_pedido(producto_id=str(self.producto_ajeno.id), variante_id="")
        ]))

        self.assertTrue(resultado["errores"])
        self.assertEqual(resultado["pedidos_validos"], 0)
        self.assertEqual(resultado["pedidos_rechazados"], 1)
        self.assertIn("no pertenece al restaurante", resultado["errores"][0])
        self.assertFalse(PedidoManual.objects.exists())

    def test_rechaza_archivo_vacio_y_montos_no_finitos(self):
        vacio = csv_pedidos([])
        self.assertIn(
            "El CSV no contiene filas de pedidos.",
            validar_csv_pedidos_prueba(vacio)["errores"],
        )

        resultado = validar_csv_pedidos_prueba(csv_pedidos([
            self.fila_pedido(precio_unitario="NaN")
        ]))
        self.assertTrue(resultado["errores"])
        self.assertFalse(PedidoManual.objects.exists())

    @override_settings(TEST_ORDER_IMPORT_ENABLED=True)
    def test_importa_transaccional_con_fecha_estado_marca_y_sin_notificaciones(self):
        fecha_esperada = datetime(2026, 10, 15, 23, 30, tzinfo=datetime_timezone.utc)
        contenido = csv_pedidos([self.fila_pedido()])

        with patch("menu.utils.crear_notificacion_pedido_whatsapp") as notificacion, patch(
            "menu.services.webpush.programar_push_nuevo_pedido"
        ) as push:
            resultado = importar_pedidos_prueba(
                contenido,
                actor=self.superusuario,
                archivo_origen="historicos-octubre.csv",
            )

        self.assertEqual(resultado, {"pedidos_creados": 1, "items_creados": 1})
        pedido = PedidoManual.objects.get()
        self.assertEqual(pedido.restaurante, self.restaurante)
        self.assertEqual(pedido.estado, PedidoManual.ESTADO_ENTREGADO)
        self.assertEqual(pedido.total, 15000)
        self.assertEqual(pedido.fecha_creacion, fecha_esperada)
        self.assertEqual(pedido.items.get().producto, self.producto)
        marca = PedidoPruebaImportado.objects.get()
        self.assertEqual(marca.identificador_externo, "historico-2026-001")
        self.assertEqual(marca.pedido_manual, pedido)
        notificacion.assert_not_called()
        push.assert_not_called()

        with self.assertRaises(ImportacionPedidosPruebaError):
            importar_pedidos_prueba(contenido, actor=self.superusuario)
        self.assertEqual(PedidoManual.objects.count(), 1)

    @override_settings(TEST_ORDER_IMPORT_ENABLED=False)
    def test_importacion_bloqueada_por_entorno(self):
        with self.assertRaises(PermissionDenied):
            importar_pedidos_prueba(
                csv_pedidos([self.fila_pedido()]), actor=self.superusuario
            )
        self.assertFalse(PedidoManual.objects.exists())

    @override_settings(TEST_ORDER_IMPORT_ENABLED=True)
    def test_importacion_requiere_superusuario(self):
        staff = User.objects.create_user(
            username="staff-import", password="secret", is_staff=True
        )
        with self.assertRaises(PermissionDenied):
            importar_pedidos_prueba(csv_pedidos([self.fila_pedido()]), actor=staff)
        self.assertFalse(PedidoManual.objects.exists())

    @override_settings(TEST_ORDER_IMPORT_ENABLED=True)
    def test_error_en_un_pedido_revierte_el_lote_completo(self):
        segundo = self.fila_pedido(
            identificador_externo="historico-2026-002",
            total_pedido="15000",
        )
        contenido = csv_pedidos([self.fila_pedido(), segundo])

        with patch(
            "menu.services.importacion_pedidos_prueba.PedidoManualItem.objects.bulk_create",
            side_effect=[None, RuntimeError("fallo simulado")],
        ):
            with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
                importar_pedidos_prueba(contenido, actor=self.superusuario)

        self.assertFalse(PedidoManual.objects.exists())
        self.assertFalse(PedidoPruebaImportado.objects.exists())
