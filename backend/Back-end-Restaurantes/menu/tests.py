
from django.test import TestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from .models import Restaurante, UsuarioRestaurante, Categoria, Producto, Reserva, Mesa, RespaldoRestaurante, HorarioAtencion, MetodoPago, BitacoraProducto
from .views import CrearReservaPublicaView, PublicReservaRateThrottle, ProductoClickRateThrottle, ProductoClickView, PasswordResetRequestView, PasswordResetRateThrottle
from .cache_utils import menu_cache_key
from django.core.cache import cache


class BaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.dueno = User.objects.create_user(
            username="dueno@test.com",
            email="dueno@test.com",
            password="123456"
        )

        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="123456"
        )

        self.empleado = User.objects.create_user(
            username="empleado@test.com",
            email="empleado@test.com",
            password="123456"
        )

        self.restaurante = Restaurante.objects.create(
            nombre_empresa="Restaurante Test",
            slug="restaurante-test",
            rut="11111111-1",
            telefono="999999999",
            email_contacto="test@test.com",
            direccion="Calle Test 123",
            ciudad="Antofagasta",
            activo=True,
        )

        self.otro_restaurante = Restaurante.objects.create(
            nombre_empresa="Otro Restaurante",
            slug="otro-restaurante",
            rut="22222222-2",
            telefono="888888888",
            email_contacto="otro@test.com",
            direccion="Otra Calle 123",
            ciudad="Santiago",
            activo=True,
        )

        self.perfil_dueno = UsuarioRestaurante.objects.create(
            user=self.dueno,
            restaurante=self.restaurante,
            rol="dueno",
            activo=True,
        )

        self.perfil_admin = UsuarioRestaurante.objects.create(
            user=self.admin,
            restaurante=self.restaurante,
            rol="admin",
            activo=True,
        )

        self.perfil_empleado = UsuarioRestaurante.objects.create(
            user=self.empleado,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        self.categoria = Categoria.objects.create(
            restaurante=self.restaurante,
            nombre="Bebidas",
            orden=1,
            activa=True,
        )

        self.categoria_otro_restaurante = Categoria.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Comida",
            orden=1,
            activa=True,
        )

        self.producto = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Coca Cola",
            descripcion="Bebida",
            precio=1500,
            disponible=True,
            destacado=False,
            orden=1,
        )


class SuscripcionDashboardTests(BaseTestCase):

    def set_fecha_creacion_restaurante(self, fecha):
        Restaurante.objects.filter(id=self.restaurante.id).update(
            fecha_creacion=timezone.make_aware(datetime.combine(fecha, time(9, 0)))
        )

    def get_suscripcion(self, hoy):
        self.client.force_authenticate(user=self.dueno)
        with patch("menu.views.now") as now_mock:
            now_mock.return_value = timezone.make_aware(
                datetime.combine(hoy, time(12, 0))
            )
            response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["suscripcion"]

    def test_suscripcion_sin_alerta_si_faltan_mas_de_tres_dias(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 1))

        suscripcion = self.get_suscripcion(date(2026, 1, 15))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-01")
        self.assertEqual(suscripcion["dias_restantes"], 17)
        self.assertFalse(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_por_vencer_si_faltan_exactamente_tres_dias(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 7))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-10")
        self.assertEqual(suscripcion["dias_restantes"], 3)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_por_vencer_si_falta_un_dia(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 9))

        self.assertEqual(suscripcion["dias_restantes"], 1)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_dia_de_vencimiento_avisa_sin_marcar_vencida(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 10))

        self.assertEqual(suscripcion["dias_restantes"], 0)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])

    def test_suscripcion_vencida_despues_del_vencimiento(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 10))

        suscripcion = self.get_suscripcion(date(2026, 2, 11))

        self.assertEqual(suscripcion["dias_restantes"], -1)
        self.assertFalse(suscripcion["por_vencer"])
        self.assertTrue(suscripcion["vencida"])

    def test_suscripcion_calcula_fin_de_mes_correctamente(self):
        self.set_fecha_creacion_restaurante(date(2026, 1, 31))

        suscripcion = self.get_suscripcion(date(2026, 2, 25))

        self.assertEqual(suscripcion["fecha_vencimiento"], "2026-02-28")
        self.assertEqual(suscripcion["dias_restantes"], 3)
        self.assertTrue(suscripcion["por_vencer"])
        self.assertFalse(suscripcion["vencida"])


class RestauranteInactivoTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.mensaje_inactivo = (
            "La cuenta del restaurante está inactiva. Contacta al soporte de Menly para reactivar tu cuenta."
        )
        self.reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Inactivo",
            telefono="900000000",
            email="cliente-inactivo@test.com",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        self.dueno_b = User.objects.create_user(
            username="dueno-activo-b@test.com",
            email="dueno-activo-b@test.com",
            password="123456"
        )
        self.perfil_dueno_b = UsuarioRestaurante.objects.create(
            user=self.dueno_b,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

    def desactivar_restaurante(self):
        self.restaurante.activo = False
        self.restaurante.save(update_fields=["activo"])

    def assert_bloqueo_inactivo(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("inactiva", str(response.data))

    def test_landing_restaurante_activo_devuelve_menu_normal(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_landing_restaurante_inactivo_devuelve_403_controlado(self):
        self.desactivar_restaurante()

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["estado"], "inactivo")

    def test_landing_slug_inexistente_devuelve_404(self):
        response = self.client.get("/api/menu/slug-inexistente/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_usuario_de_restaurante_inactivo_puede_hacer_login(self):
        self.desactivar_restaurante()

        response = self.client.post(
            "/api/login/",
            {
                "email": "dueno@test.com",
                "password": "123456",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["activo"])

    @patch("menu.views.send_mail")
    def test_password_reset_request_responde_generico_y_notifica_admin(self, send_mail_mock):
        response = self.client.post(
            "/api/password-reset-request/",
            {"email": "DUENO@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Si el correo está registrado, el administrador será notificado.",
        )
        send_mail_mock.assert_called_once()
        self.assertIn("Usuario encontrado:\nSí", send_mail_mock.call_args.kwargs["message"])
        self.assertIn("dueno@test.com", send_mail_mock.call_args.kwargs["message"])

    @patch("menu.views.send_mail")
    def test_password_reset_request_no_revela_email_inexistente(self, send_mail_mock):
        response = self.client.post(
            "/api/password-reset-request/",
            {"email": "noexiste@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Si el correo está registrado, el administrador será notificado.",
        )
        send_mail_mock.assert_called_once()
        self.assertIn("Usuario encontrado:\nNo", send_mail_mock.call_args.kwargs["message"])

    def test_restaurante_inactivo_puede_ver_mi_restaurante(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["activo"])
        self.assertTrue(response.data["cuenta_inactiva"])
        self.assertIn("Cuenta inactiva", response.data["mensaje_cuenta"])

    def test_dueno_inactivo_no_puede_crear_producto(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto bloqueado",
                "descripcion": "No debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.assertFalse(Producto.objects.filter(nombre="Producto bloqueado").exists())

    def test_admin_inactivo_no_puede_editar_producto(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto editado",
                "precio": self.producto.precio,
                "orden": self.producto.orden,
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Coca Cola")

    def test_admin_inactivo_no_puede_editar_reserva(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva.id}/",
            {"estado": "confirmada"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, "pendiente")

    def test_empleado_inactivo_no_puede_gestionar_reserva(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.empleado)

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva.id}/",
            {"estado": "rechazada"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, "pendiente")

    def test_dueno_inactivo_no_puede_editar_configuracion(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {"nombre_empresa": "Nombre bloqueado"},
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.restaurante.refresh_from_db()
        self.assertEqual(self.restaurante.nombre_empresa, "Restaurante Test")

    def test_dueno_inactivo_no_puede_crear_usuario(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/usuarios/",
            {
                "username": "nuevo-inactivo@test.com",
                "email": "nuevo-inactivo@test.com",
                "password": "123456",
                "rol": "empleado",
            },
            format="json"
        )

        self.assert_bloqueo_inactivo(response)
        self.assertFalse(User.objects.filter(username="nuevo-inactivo@test.com").exists())

    def test_restaurante_activo_mantiene_comportamiento_normal(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Producto activo",
                "descripcion": "Debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_restaurante_inactivo_no_afecta_otro_restaurante_activo(self):
        self.desactivar_restaurante()
        self.client.force_authenticate(user=self.dueno_b)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria_otro_restaurante.id,
                "nombre": "Producto restaurante B",
                "descripcion": "B sigue activo",
                "precio": 4000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Producto.objects.filter(
                restaurante=self.otro_restaurante,
                nombre="Producto restaurante B",
            ).exists()
        )


class CategoriaTests(BaseTestCase):

    def test_dueno_puede_crear_categoria(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Promociones",
                "orden": 2,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Categoria.objects.filter(
                restaurante=self.restaurante,
                nombre="Promociones"
            ).exists()
        )

    def test_admin_no_puede_crear_categoria(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Postres",
                "orden": 3,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_permite_categoria_duplicada(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/categorias/",
            {
                "nombre": "Bebidas",
                "orden": 2,
                "activa": True,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lista_solo_categorias_del_restaurante_actual(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.get("/api/mi-restaurante/categorias/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        nombres = [cat["nombre"] for cat in response.data]

        self.assertIn("Bebidas", nombres)
        self.assertNotIn("Comida", nombres)


class ProductoTests(BaseTestCase):

    def test_no_permite_cambiar_producto_a_categoria_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/",
            {
                "categoria": self.categoria_otro_restaurante.id,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.categoria, self.categoria)

    def test_crear_producto_en_orden_ocupado_reordena(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria.id,
                "nombre": "Jugo Natural",
                "descripcion": "Jugo",
                "precio": 2500,
                "disponible": True,
                "destacado": False,
                "orden": 1,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        producto_nuevo = Producto.objects.get(nombre="Jugo Natural")
        self.producto.refresh_from_db()

        self.assertEqual(producto_nuevo.orden, 1)
        self.assertEqual(self.producto.orden, 2)

    def test_editar_producto_cambiando_orden_reordena(self):
        self.client.force_authenticate(user=self.dueno)

        segundo = Producto.objects.create(
            restaurante=self.restaurante,
            categoria=self.categoria,
            nombre="Sprite",
            descripcion="Bebida",
            precio=1500,
            disponible=True,
            destacado=False,
            orden=2,
        )

        response = self.client.patch(
            f"/api/mi-restaurante/productos/{segundo.id}/actualizar/",
            {
                "categoria": self.categoria.id,
                "nombre": segundo.nombre,
                "precio": segundo.precio,
                "descripcion": segundo.descripcion,
                "condiciones": segundo.condiciones,
                "disponible": segundo.disponible,
                "destacado": segundo.destacado,
                "orden": 1,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        segundo.refresh_from_db()
        self.producto.refresh_from_db()

        self.assertEqual(segundo.orden, 1)
        self.assertEqual(self.producto.orden, 2)


class UsuariosTests(BaseTestCase):

    def test_crear_usuario_con_email_global_existente_falla_claro(self):
        self.client.force_authenticate(user=self.dueno)
        User.objects.create_superuser(
            username="superuser@test.com",
            email="correoexistente@test.com",
            password="123456"
        )

        response = self.client.post(
            "/api/mi-restaurante/usuarios/",
            {
                "username": "empleado-nuevo",
                "email": "correoexistente@test.com",
                "password": "12345678",
                "rol": "empleado",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("superuser", response.data["error"])

    def test_editar_usuario_funciona(self):
        self.client.force_authenticate(user=self.dueno)
        empleado_user = User.objects.create_user(
            username="empleado-original",
            email="empleado-original@test.com",
            password="12345678"
        )
        empleado = UsuarioRestaurante.objects.create(
            user=empleado_user,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        response = self.client.patch(
            f"/api/mi-restaurante/usuarios/{empleado.id}/",
            {
                "username": "empleado-editado",
                "email": "empleado-editado@test.com",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        empleado_user.refresh_from_db()
        self.assertEqual(empleado_user.username, "empleado-editado")
        self.assertEqual(empleado_user.email, "empleado-editado@test.com")

    def test_desactivar_usuario_bloquea_login(self):
        self.client.force_authenticate(user=self.dueno)
        empleado_user = User.objects.create_user(
            username="empleado-login",
            email="empleado-login@test.com",
            password="12345678"
        )
        empleado = UsuarioRestaurante.objects.create(
            user=empleado_user,
            restaurante=self.restaurante,
            rol="empleado",
            activo=True,
        )

        response = self.client.patch(f"/api/mi-restaurante/usuarios/{empleado.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        empleado.refresh_from_db()
        empleado_user.refresh_from_db()
        self.assertFalse(empleado.activo)
        self.assertFalse(empleado_user.is_active)

        self.client.force_authenticate(user=None)
        login_response = self.client.post(
            "/api/login/",
            {
                "email": "empleado-login@test.com",
                "password": "12345678",
            },
            format="json"
        )

        self.assertNotEqual(login_response.status_code, status.HTTP_200_OK)


class RespaldosTests(BaseTestCase):

    def test_dueno_puede_crear_listar_y_ver_ultimo_respaldo(self):
        self.client.force_authenticate(user=self.dueno)

        crear_response = self.client.post("/api/mi-restaurante/respaldos/")

        self.assertEqual(crear_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RespaldoRestaurante.objects.count(), 1)
        self.assertEqual(crear_response.data["nombre_restaurante"], self.restaurante.nombre_empresa)
        self.assertIn("productos", crear_response.data["datos_json"])
        self.assertIn("reservas", crear_response.data["datos_json"])

        listar_response = self.client.get("/api/mi-restaurante/respaldos/")

        self.assertEqual(listar_response.status_code, status.HTTP_200_OK)
        self.assertEqual(listar_response.data["count"], 1)
        self.assertEqual(len(listar_response.data["results"]), 1)

        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")

        self.assertEqual(ultimo_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(ultimo_response.data["ultimo_respaldo"])

    def test_admin_puede_crear_respaldo(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post("/api/mi-restaurante/respaldos/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_empleado_no_puede_acceder_respaldos(self):
        self.client.force_authenticate(user=self.empleado)

        crear_response = self.client.post("/api/mi-restaurante/respaldos/")
        listar_response = self.client.get("/api/mi-restaurante/respaldos/")
        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")

        self.assertEqual(crear_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(listar_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ultimo_response.status_code, status.HTTP_403_FORBIDDEN)


class ReservaManualMesaTests(BaseTestCase):

    def reserva_manual_payload(self, mesa):
        return {
            "nombre_cliente": "Cliente Manual",
            "telefono": "999999999",
            "email": "cliente.manual@test.com",
            "fecha": (date.today() + timedelta(days=2)).isoformat(),
            "hora": "12:00",
            "cantidad_personas": 2,
            "mensaje": "Reserva creada desde dashboard",
            "mesa_asignada": mesa.id,
            "observacion_admin": "Mesa elegida manualmente",
        }

    def test_restaurante_puede_asignar_su_propia_mesa_activa(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=1,
            nombre="Mesa terraza",
            activa=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_restaurante_no_puede_asignar_mesa_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)
        mesa_externa = Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=1,
            nombre="Mesa externa",
            activa=True,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa_externa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_restaurante_no_puede_asignar_mesa_inactiva(self):
        self.client.force_authenticate(user=self.dueno)
        mesa_inactiva = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=2,
            nombre="Mesa inactiva",
            activa=False,
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa_inactiva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                nombre_cliente="Cliente Manual",
            ).exists()
        )

    def test_rechaza_mesa_ocupada_misma_fecha_y_hora(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=3,
            nombre="Mesa ocupada",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="pendiente",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "La mesa ya tiene una reserva para esa fecha y hora."
        )

    def test_permite_mesa_si_reserva_anterior_esta_cancelada(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=4,
            nombre="Mesa liberada",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="cancelada",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_mesa_si_reserva_anterior_esta_rechazada(self):
        self.client.force_authenticate(user=self.dueno)
        mesa = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=5,
            nombre="Mesa disponible",
            activa=True,
        )
        fecha_reserva = date.today() + timedelta(days=2)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="original@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            mesa_asignada=str(mesa.id),
            estado="rechazada",
        )

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            self.reserva_manual_payload(mesa),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PaginacionTests(BaseTestCase):

    def test_configuracion_global_paginacion_drf(self):
        self.assertNotIn("PAGE_SIZE", settings.REST_FRAMEWORK)
        self.assertNotIn("DEFAULT_PAGINATION_CLASS", settings.REST_FRAMEWORK)

    def test_reservas_dashboard_paginadas_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(25):
            Reserva.objects.create(
                restaurante=self.restaurante,
                nombre_cliente=f"Cliente {i}",
                telefono="999999999",
                fecha=date.today() + timedelta(days=2),
                hora=time(12, 0),
                cantidad_personas=2,
                estado="pendiente",
            )

        Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente externo",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.get("/api/mi-restaurante/reservas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])
        nombres = [reserva["nombre_cliente"] for reserva in response.data["results"]]
        self.assertNotIn("Cliente externo", nombres)

    def test_historial_paginado_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(25):
            BitacoraProducto.objects.create(
                restaurante=self.restaurante,
                producto_id=self.producto.id,
                producto_nombre=f"Producto {i}",
                usuario=self.dueno,
                accion="CREADO",
                descripcion="Producto creado",
            )

        BitacoraProducto.objects.create(
            restaurante=self.otro_restaurante,
            producto_id=999,
            producto_nombre="Producto externo",
            usuario=self.dueno,
            accion="CREADO",
            descripcion="No debe verse",
        )

        response = self.client.get("/api/historial/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        productos = [item["producto"] for item in response.data["results"]]
        self.assertNotIn("Producto externo", productos)

    def test_productos_paginados_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(2, 14):
            Producto.objects.create(
                restaurante=self.restaurante,
                categoria=self.categoria,
                nombre=f"Producto {i}",
                descripcion="Producto paginado",
                precio=1000 + i,
                disponible=True,
                destacado=False,
                orden=i,
            )

        Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto externo",
            descripcion="No debe verse",
            precio=9999,
            disponible=True,
            destacado=False,
            orden=1,
        )

        response = self.client.get("/api/mi-restaurante/productos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 13)
        self.assertEqual(len(response.data["results"]), 8)
        nombres = [producto["nombre"] for producto in response.data["results"]]
        self.assertIn("Coca Cola", nombres)
        self.assertNotIn("Producto externo", nombres)

    def test_respaldos_paginados_y_multi_tenant(self):
        self.client.force_authenticate(user=self.dueno)

        for i in range(12):
            RespaldoRestaurante.objects.create(
                restaurante=self.restaurante,
                responsable=self.perfil_dueno,
                nombre_responsable=f"Responsable {i}",
                nombre_restaurante=self.restaurante.nombre_empresa,
                datos_json={"indice": i},
            )

        RespaldoRestaurante.objects.create(
            restaurante=self.otro_restaurante,
            responsable=None,
            nombre_responsable="Externo",
            nombre_restaurante=self.otro_restaurante.nombre_empresa,
            datos_json={"externo": True},
        )

        response = self.client.get("/api/mi-restaurante/respaldos/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        restaurantes = [item["nombre_restaurante"] for item in response.data["results"]]
        self.assertNotIn(self.otro_restaurante.nombre_empresa, restaurantes)

    def test_usuarios_paginados_y_filtrados_por_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        otro_user = User.objects.create_user(
            username="otro-user@test.com",
            email="otro-user@test.com",
            password="12345678"
        )
        UsuarioRestaurante.objects.create(
            user=otro_user,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )

        response = self.client.get("/api/mi-restaurante/usuarios/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        usernames = [usuario["username"] for usuario in response.data["results"]]
        self.assertIn(self.dueno.username, usernames)
        self.assertNotIn("otro-user@test.com", usernames)


class ProductoClickTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_click_valido_incrementa_contador(self):
        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"mensaje": "Click registrado"})

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)

    def test_producto_inexistente_devuelve_404(self):
        response = self.client.post("/api/productos/999999/click/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_producto_no_disponible_no_incrementa_clicks(self):
        self.producto.disponible = False
        self.producto.clicks = 5
        self.producto.save(update_fields=["disponible", "clicks"])

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 5)

    def test_click_solo_incrementa_clicks_y_no_expone_datos_sensibles(self):
        nombre = self.producto.nombre
        precio = self.producto.precio
        categoria_id = self.producto.categoria_id
        restaurante_id = self.producto.restaurante_id

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data.keys()), ["mensaje"])

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)
        self.assertEqual(self.producto.nombre, nombre)
        self.assertEqual(self.producto.precio, precio)
        self.assertEqual(self.producto.categoria_id, categoria_id)
        self.assertEqual(self.producto.restaurante_id, restaurante_id)

    def test_throttle_bloquea_exceso_de_clicks(self):
        for _ in range(30):
            response = self.client.post(f"/api/productos/{self.producto.id}/click/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rate_producto_click_existe_y_no_afecta_otros_rates(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        self.assertEqual(rates["producto_click"], "30/min")
        self.assertEqual(rates["login"], "5/min")
        self.assertEqual(rates["password_reset"], "3/hour")
        self.assertEqual(rates["public_reservas"], "20/hour")
        self.assertIn(ProductoClickRateThrottle, ProductoClickView.throttle_classes)
        self.assertIn(PublicReservaRateThrottle, CrearReservaPublicaView.throttle_classes)
        self.assertIn(PasswordResetRateThrottle, PasswordResetRequestView.throttle_classes)


class MultiTenantIsolationTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.dueno_b = User.objects.create_user(
            username="dueno-b@test.com",
            email="dueno-b@test.com",
            password="123456"
        )
        self.admin_b = User.objects.create_user(
            username="admin-b@test.com",
            email="admin-b@test.com",
            password="123456"
        )
        self.empleado_b = User.objects.create_user(
            username="empleado-b@test.com",
            email="empleado-b@test.com",
            password="123456"
        )
        self.perfil_dueno_b = UsuarioRestaurante.objects.create(
            user=self.dueno_b,
            restaurante=self.otro_restaurante,
            rol="dueno",
            activo=True,
        )
        self.perfil_admin_b = UsuarioRestaurante.objects.create(
            user=self.admin_b,
            restaurante=self.otro_restaurante,
            rol="admin",
            activo=True,
        )
        self.perfil_empleado_b = UsuarioRestaurante.objects.create(
            user=self.empleado_b,
            restaurante=self.otro_restaurante,
            rol="empleado",
            activo=True,
        )
        self.producto_b = Producto.objects.create(
            restaurante=self.otro_restaurante,
            categoria=self.categoria_otro_restaurante,
            nombre="Producto B",
            descripcion="Producto de otro restaurante",
            precio=2500,
            disponible=True,
            destacado=False,
            orden=1,
        )
        self.mesa_a = Mesa.objects.create(
            restaurante=self.restaurante,
            numero=1,
            nombre="Mesa A",
            activa=True,
        )
        self.mesa_b = Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=1,
            nombre="Mesa B",
            activa=True,
        )
        self.reserva_b = Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente B",
            telefono="911111111",
            email="cliente-b@test.com",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )
        self.horario_b = HorarioAtencion.objects.create(
            restaurante=self.otro_restaurante,
            dia=1,
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.metodo_b = MetodoPago.objects.create(
            restaurante=self.otro_restaurante,
            nombre="Pago B",
            activo=True,
        )
        self.bitacora_b = BitacoraProducto.objects.create(
            restaurante=self.otro_restaurante,
            producto_id=self.producto_b.id,
            producto_nombre=self.producto_b.nombre,
            usuario=self.dueno_b,
            accion="CREADO",
            descripcion="Accion de B",
        )
        self.respaldo_b = RespaldoRestaurante.objects.create(
            restaurante=self.otro_restaurante,
            responsable=self.perfil_dueno_b,
            nombre_responsable="Dueno B",
            nombre_restaurante=self.otro_restaurante.nombre_empresa,
            datos_json={"restaurante": "B"},
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def assert_forbidden_or_not_found(self, response):
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )

    def test_usuarios_de_a_no_ven_usuarios_de_b(self):
        for user in [self.dueno, self.admin]:
            self.client.force_authenticate(user=user)
            response = self.client.get("/api/mi-restaurante/usuarios/")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            emails = [item["email"] for item in response.data["results"]]
            self.assertIn(self.dueno.email, emails)
            self.assertNotIn(self.dueno_b.email, emails)

        self.client.force_authenticate(user=self.empleado)
        response = self.client.get("/api/mi-restaurante/usuarios/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dueno_a_no_modifica_ni_elimina_usuario_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/usuarios/{self.perfil_admin_b.id}/",
            {"username": "admin-b-editado@test.com"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/usuarios/{self.perfil_admin_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.admin_b.refresh_from_db()
        self.perfil_admin_b.refresh_from_db()
        self.assertEqual(self.admin_b.username, "admin-b@test.com")
        self.assertTrue(self.perfil_admin_b.activo)

    def test_productos_de_a_no_ven_ni_modifican_productos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/productos/")
        nombres = [item["nombre"] for item in listar_response.data["results"]]
        self.assertIn(self.producto.nombre, nombres)
        self.assertNotIn(self.producto_b.nombre, nombres)

        editar_response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/actualizar/",
            {
                "nombre": "Producto B editado",
                "categoria": self.categoria_otro_restaurante.id,
                "orden": 2,
                "precio": 9999,
            },
            format="json"
        )
        disponibilidad_response = self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/",
            {"disponible": False},
            format="json"
        )
        eliminar_response = self.client.delete(
            f"/api/mi-restaurante/productos/{self.producto_b.id}/eliminar/"
        )

        self.assert_forbidden_or_not_found(editar_response)
        self.assert_forbidden_or_not_found(disponibilidad_response)
        self.assert_forbidden_or_not_found(eliminar_response)
        self.producto_b.refresh_from_db()
        self.assertEqual(self.producto_b.nombre, "Producto B")
        self.assertTrue(self.producto_b.disponible)
        self.assertEqual(self.producto_b.orden, 1)

    def test_producto_de_a_no_puede_usar_categoria_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/productos/agregar/",
            {
                "categoria": self.categoria_otro_restaurante.id,
                "nombre": "Producto cruzado",
                "descripcion": "No debe crearse",
                "precio": 3000,
                "orden": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Producto.objects.filter(
                restaurante=self.restaurante,
                nombre="Producto cruzado",
            ).exists()
        )

    def test_categorias_de_a_no_ven_ni_modifican_categorias_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/categorias/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertIn(self.categoria.nombre, nombres)
        self.assertNotIn(self.categoria_otro_restaurante.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/categorias/{self.categoria_otro_restaurante.id}/",
            {"nombre": "Categoria B editada"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/categorias/{self.categoria_otro_restaurante.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.categoria_otro_restaurante.refresh_from_db()
        self.assertEqual(self.categoria_otro_restaurante.nombre, "Comida")

    def test_reservas_de_a_no_ven_ni_gestionan_reservas_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/reservas/")
        ids = [item["id"] for item in listar_response.data["results"]]
        self.assertNotIn(self.reserva_b.id, ids)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/reservas/{self.reserva_b.id}/",
            {"estado": "confirmada"},
            format="json"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.reserva_b.refresh_from_db()
        self.assertEqual(self.reserva_b.estado, "pendiente")

    def test_reserva_manual_de_a_no_usa_mesa_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        response = self.client.post(
            "/api/mi-restaurante/reservas/crear/",
            {
                "nombre_cliente": "Cliente A",
                "telefono": "922222222",
                "email": "cliente-a@test.com",
                "fecha": (date.today() + timedelta(days=2)).isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mesa_asignada": self.mesa_b.id,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mesa_asignada", response.data)

    def test_reserva_publica_slug_a_crea_en_a_y_no_en_b(self):
        fecha_reserva = date.today() + timedelta(days=3)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Publico A",
                "telefono": "933333333",
                "email": "publico-a@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Reserva.objects.filter(
                restaurante=self.restaurante,
                email="publico-a@test.com",
            ).exists()
        )
        self.assertFalse(
            Reserva.objects.filter(
                restaurante=self.otro_restaurante,
                email="publico-a@test.com",
            ).exists()
        )

    def test_mesas_de_a_no_ven_ni_modifican_mesas_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/mesas/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertIn(self.mesa_a.nombre, nombres)
        self.assertNotIn(self.mesa_b.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/mesas/{self.mesa_b.id}/",
            {"nombre": "Mesa B editada", "numero": 9},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/mesas/{self.mesa_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.mesa_b.refresh_from_db()
        self.assertEqual(self.mesa_b.nombre, "Mesa B")

    def test_horarios_de_a_no_ven_ni_modifican_horarios_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/horarios/")
        ids = [item["id"] for item in listar_response.data]
        self.assertNotIn(self.horario_b.id, ids)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/horarios/{self.horario_b.id}/",
            {"cerrado": True},
            format="json"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.horario_b.refresh_from_db()
        self.assertFalse(self.horario_b.cerrado)

    def test_metodos_pago_de_a_no_ven_ni_modifican_metodos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/metodos-pago/")
        nombres = [item["nombre"] for item in listar_response.data]
        self.assertNotIn(self.metodo_b.nombre, nombres)

        patch_response = self.client.patch(
            f"/api/mi-restaurante/metodos-pago/{self.metodo_b.id}/",
            {"nombre": "Pago B editado"},
            format="json"
        )
        delete_response = self.client.delete(
            f"/api/mi-restaurante/metodos-pago/{self.metodo_b.id}/"
        )

        self.assert_forbidden_or_not_found(patch_response)
        self.assert_forbidden_or_not_found(delete_response)
        self.metodo_b.refresh_from_db()
        self.assertEqual(self.metodo_b.nombre, "Pago B")

    def test_historial_de_a_no_incluye_acciones_de_b_y_escribe_en_a(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/historial/")
        productos = [item["producto"] for item in listar_response.data["results"]]
        self.assertNotIn(self.producto_b.nombre, productos)

        self.client.patch(
            f"/api/mi-restaurante/productos/{self.producto.id}/actualizar/",
            {
                "nombre": "Coca Cola Zero",
                "categoria": self.categoria.id,
                "orden": self.producto.orden,
                "precio": self.producto.precio,
            },
            format="json"
        )

        self.assertTrue(
            BitacoraProducto.objects.filter(
                restaurante=self.restaurante,
                producto_id=self.producto.id,
                accion="EDITADO",
            ).exists()
        )
        self.assertFalse(
            BitacoraProducto.objects.filter(
                restaurante=self.otro_restaurante,
                producto_id=self.producto.id,
            ).exists()
        )

    def test_respaldos_de_a_no_ven_respaldos_de_b(self):
        self.client.force_authenticate(user=self.dueno)

        listar_response = self.client.get("/api/mi-restaurante/respaldos/")
        ids = [item["id"] for item in listar_response.data["results"]]
        self.assertNotIn(self.respaldo_b.id, ids)

        ultimo_response = self.client.get("/api/mi-restaurante/respaldos/ultimo/")
        ultimo = ultimo_response.data["ultimo_respaldo"]
        if ultimo:
            self.assertNotEqual(ultimo["id"], self.respaldo_b.id)

    def test_menu_publico_por_slug_no_mezcla_productos(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        categorias = response.json()["categorias"]
        productos = [
            producto["nombre"]
            for categoria in categorias
            for producto in categoria["productos"]
        ]
        self.assertIn(self.producto.nombre, productos)
        self.assertNotIn(self.producto_b.nombre, productos)

    def test_detalle_publico_por_slug_no_expone_otro_restaurante(self):
        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "restaurante-test")
        self.assertEqual(response.data["nombre_empresa"], self.restaurante.nombre_empresa)
        self.assertNotEqual(response.data["slug"], "otro-restaurante")

    def test_click_producto_solo_afecta_producto_indicado(self):
        response = self.client.post(f"/api/productos/{self.producto.id}/click/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.producto.refresh_from_db()
        self.producto_b.refresh_from_db()
        self.assertEqual(self.producto.clicks, 1)
        self.assertEqual(self.producto_b.clicks, 0)

    def test_slugs_publicos_inexistentes_devuelven_404(self):
        menu_response = self.client.get("/api/menu/no-existe/")
        detalle_response = self.client.get("/api/restaurantes/no-existe/")

        self.assertEqual(menu_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(detalle_response.status_code, status.HTTP_404_NOT_FOUND)


class MenuPublicoTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_menu_publico_responde_por_slug(self):
        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_menu_publico_no_requiere_login(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_menu_publico_no_muestra_restaurante_inactivo(self):
        self.restaurante.activo = False
        self.restaurante.save()

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["estado"], "inactivo")

    def test_menu_publico_usa_cache_por_slug(self):
        cache.set(
            menu_cache_key("restaurante-test"),
            {
                "restaurante": {"reservas_activas": True},
                "categorias": [{"id": 999, "nombre": "Cacheado", "icono": None, "productos": []}],
            },
            timeout=300,
        )

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["categorias"][0]["nombre"], "Cacheado")

    def test_cambio_producto_invalida_cache_menu_publico(self):
        cache.set(
            menu_cache_key("restaurante-test"),
            {
                "restaurante": {"reservas_activas": True},
                "categorias": [{"id": 999, "nombre": "Cache viejo", "icono": None, "productos": []}],
            },
            timeout=300,
        )

        self.producto.nombre = "Producto cache actualizado"
        self.producto.save(update_fields=["nombre"])

        response = self.client.get("/api/menu/restaurante-test/")
        nombres = [
            producto["nombre"]
            for categoria in response.json()["categorias"]
            for producto in categoria["productos"]
        ]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Producto cache actualizado", nombres)
        self.assertNotEqual(response.json()["categorias"][0]["nombre"], "Cache viejo")

    def test_menu_publico_devuelve_flags_del_restaurante(self):
        self.restaurante.reservas_activas = False
        self.restaurante.solicitudes_especiales_activas = True
        self.restaurante.carrito_whatsapp_activo = True
        self.restaurante.metricas_activas = False
        self.restaurante.save(update_fields=[
            "reservas_activas",
            "solicitudes_especiales_activas",
            "carrito_whatsapp_activo",
            "metricas_activas",
        ])

        response = self.client.get("/api/menu/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["restaurante"]["reservas_activas"])
        self.assertTrue(response.json()["restaurante"]["solicitudes_especiales_activas"])
        self.assertTrue(response.json()["restaurante"]["carrito_whatsapp_activo"])
        self.assertFalse(response.json()["restaurante"]["metricas_activas"])


class RestaurantePublicoDetalleTests(BaseTestCase):

    def test_detalle_publico_responde_por_slug(self):
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=1,
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        MetodoPago.objects.create(
            restaurante=self.restaurante,
            nombre="Transferencia",
            activo=True,
        )
        MetodoPago.objects.create(
            restaurante=self.restaurante,
            nombre="Cheque",
            activo=False,
        )

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "restaurante-test")
        self.assertEqual(response.data["nombre_empresa"], "Restaurante Test")
        self.assertEqual(len(response.data["horarios"]), 1)
        self.assertEqual(
            [metodo["nombre"] for metodo in response.data["metodos_pago"]],
            ["Transferencia"]
        )
        self.assertNotIn("notificar_reservas", response.data)
        self.assertNotIn("email_notificacion", response.data)
        self.assertIn("reservas_activas", response.data)
        self.assertIn("solicitudes_especiales_activas", response.data)
        self.assertIn("carrito_whatsapp_activo", response.data)
        self.assertIn("metricas_activas", response.data)

    def test_detalle_publico_no_requiere_login(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_detalle_publico_no_muestra_restaurante_inactivo(self):
        self.restaurante.activo = False
        self.restaurante.save()

        response = self.client.get("/api/restaurantes/restaurante-test/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["estado"], "inactivo")


class RestauranteFeatureFlagsTests(BaseTestCase):

    def test_restaurante_feature_flags_tienen_defaults_correctos(self):
        restaurante = Restaurante.objects.get(id=self.restaurante.id)

        self.assertTrue(restaurante.reservas_activas)
        self.assertFalse(restaurante.solicitudes_especiales_activas)
        self.assertFalse(restaurante.carrito_whatsapp_activo)
        self.assertTrue(restaurante.metricas_activas)

    def test_mi_restaurante_devuelve_flags_para_lectura(self):
        self.client.force_authenticate(user=self.dueno)
        self.restaurante.reservas_activas = False
        self.restaurante.save(update_fields=["reservas_activas"])

        response = self.client.get("/api/mi-restaurante/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["restaurante"]["reservas_activas"])
        self.assertIn("metricas_activas", response.data["restaurante"])

    def test_configuracion_devuelve_flags_pero_patch_no_los_modifica(self):
        self.client.force_authenticate(user=self.dueno)

        get_response = self.client.get("/api/mi-restaurante/configuracion/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertIn("reservas_activas", get_response.data["restaurante"])

        patch_response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {
                "nombre_empresa": "Nombre editado",
                "reservas_activas": False,
                "solicitudes_especiales_activas": True,
                "carrito_whatsapp_activo": True,
                "metricas_activas": False,
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.restaurante.refresh_from_db()
        self.assertEqual(self.restaurante.nombre_empresa, "Nombre editado")
        self.assertTrue(self.restaurante.reservas_activas)
        self.assertFalse(self.restaurante.solicitudes_especiales_activas)
        self.assertFalse(self.restaurante.carrito_whatsapp_activo)
        self.assertTrue(self.restaurante.metricas_activas)

    def test_admin_puede_ver_configuracion_pero_no_modificar_flags_por_api(self):
        self.client.force_authenticate(user=self.admin)

        get_response = self.client.get("/api/mi-restaurante/configuracion/")
        patch_response = self.client.patch(
            "/api/mi-restaurante/configuracion/",
            {"reservas_activas": False},
            format="json",
        )

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertIn("reservas_activas", get_response.data["restaurante"])
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)


class SeguridadCriticaTests(BaseTestCase):

    def crear_horario_para_reserva(self, restaurante, fecha_reserva):
        return HorarioAtencion.objects.create(
            restaurante=restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )

    def payload_reserva_publica(self, fecha_reserva, **overrides):
        data = {
            "nombre_cliente": "Cliente Reserva",
            "telefono": "999999999",
            "email": "cliente@test.com",
            "fecha": fecha_reserva.isoformat(),
            "hora": "12:00",
            "cantidad_personas": 2,
            "mensaje": "",
        }
        data.update(overrides)
        return data

    def test_login_usuario_sin_perfil_falla(self):
        User.objects.create_user(
            username="sinperfil@test.com",
            email="sinperfil@test.com",
            password="123456"
        )

        response = self.client.post(
            "/api/login/",
            {
                "email": "sinperfil@test.com",
                "password": "123456",
            },
            format="json"
        )

        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_reserva_publica_tiene_throttle_configurado(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        self.assertIn("public_reservas", rates)
        self.assertEqual(rates["public_reservas"], "20/hour")
        self.assertIn(PublicReservaRateThrottle, CrearReservaPublicaView.throttle_classes)

    def test_no_permite_duplicar_reserva_publica_por_email_misma_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(
                fecha_reserva,
                telefono="222222222",
                hora="15:00",
            ),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Ya existe una reserva registrada para este cliente en esa fecha."
        )

    def test_no_permite_duplicar_reserva_publica_por_telefono_misma_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="otro@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="confirmada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(
                fecha_reserva,
                email="cliente-nuevo@test.com",
                hora="16:00",
            ),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Ya existe una reserva registrada para este cliente en esa fecha."
        )

    def test_permite_mismo_email_en_otra_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        nueva_fecha = fecha_reserva + timedelta(days=1)
        self.crear_horario_para_reserva(self.restaurante, nueva_fecha)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="111111111",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(nueva_fecha, telefono="222222222"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_mismo_telefono_en_otra_fecha(self):
        fecha_reserva = date.today() + timedelta(days=2)
        nueva_fecha = fecha_reserva + timedelta(days=1)
        self.crear_horario_para_reserva(self.restaurante, nueva_fecha)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="otro@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="confirmada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(nueva_fecha, email="cliente-nuevo@test.com"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_reserva_publica_si_anterior_esta_cancelada(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="cancelada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_permite_reserva_publica_si_anterior_esta_rechazada(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Original",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="rechazada",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicado_publico_no_se_mezcla_entre_restaurantes(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)
        Reserva.objects.create(
            restaurante=self.otro_restaurante,
            nombre_cliente="Cliente Otro Restaurante",
            telefono="999999999",
            email="cliente@test.com",
            fecha=fecha_reserva,
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reserva_publica_rechaza_dia_cerrado(self):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=True,
            activo=True,
        )

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_rechaza_antes_de_apertura(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="09:59"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_rechaza_despues_de_cierre(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="22:01"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_publica_permite_dentro_del_horario(self):
        fecha_reserva = date.today() + timedelta(days=2)
        self.crear_horario_para_reserva(self.restaurante, fecha_reserva)

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            self.payload_reserva_publica(fecha_reserva, hora="12:00"),
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("menu.utils.send_mail")
    def test_reserva_publica_envia_notificacion_si_esta_configurado(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = True
        self.restaurante.email_notificacion = " reservas@test.com "
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente Correo",
                "telefono": "999999999",
                "email": "cliente@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "Mesa tranquila",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_called_once()
        kwargs = send_mail_mock.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["reservas@test.com"])
        self.assertIn(fecha_reserva.strftime("%d-%m-%Y"), kwargs["message"])
        self.assertIn("Hora: 12:00", kwargs["message"])

    @patch("menu.utils.send_mail", side_effect=Exception("SMTP caido"))
    def test_fallo_email_no_bloquea_reserva_publica(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = True
        self.restaurante.email_notificacion = "reservas@test.com"
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente Sin Bloqueo",
                "telefono": "999999999",
                "email": "cliente@test.com",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_called_once()

    @patch("menu.utils.send_mail")
    def test_no_envia_email_si_notificaciones_desactivadas(self, send_mail_mock):
        fecha_reserva = date.today() + timedelta(days=2)
        HorarioAtencion.objects.create(
            restaurante=self.restaurante,
            dia=fecha_reserva.isoweekday(),
            hora_apertura=time(10, 0),
            hora_cierre=time(22, 0),
            cerrado=False,
            activo=True,
        )
        self.restaurante.notificar_reservas = False
        self.restaurante.email_notificacion = "reservas@test.com"
        self.restaurante.save(update_fields=["notificar_reservas", "email_notificacion"])

        response = self.client.post(
            "/api/reservas/restaurante-test/",
            {
                "nombre_cliente": "Cliente No Email",
                "telefono": "999999999",
                "fecha": fecha_reserva.isoformat(),
                "hora": "12:00",
                "cantidad_personas": 2,
                "mensaje": "",
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        send_mail_mock.assert_not_called()

    def test_estado_invalido_de_reserva_devuelve_400(self):
        self.client.force_authenticate(user=self.dueno)

        reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Test",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{reserva.id}/",
            {"estado": "estado_invalido"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_puede_asignar_mesa_de_otro_restaurante(self):
        self.client.force_authenticate(user=self.dueno)

        Mesa.objects.create(
            restaurante=self.otro_restaurante,
            numero=99,
            nombre="Mesa externa",
            activa=True,
        )
        reserva = Reserva.objects.create(
            restaurante=self.restaurante,
            nombre_cliente="Cliente Test",
            telefono="999999999",
            fecha=date.today() + timedelta(days=2),
            hora=time(12, 0),
            cantidad_personas=2,
            estado="pendiente",
        )

        response = self.client.patch(
            f"/api/mi-restaurante/reservas/{reserva.id}/",
            {"mesa_asignada": "99"},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
# Create your tests here.
