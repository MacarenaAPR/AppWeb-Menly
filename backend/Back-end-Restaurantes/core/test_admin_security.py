from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings


ADMIN_SECURITY_SETTINGS = {
    "ADMIN_URL_PATH": "admin",
    "ADMIN_ALLOWED_NETWORKS": ["127.0.0.1/32"],
    "ADMIN_CLIENT_IP_HEADER": "REMOTE_ADDR",
    "ADMIN_LOGIN_MAX_FAILURES": 3,
    "ADMIN_LOGIN_WINDOW_SECONDS": 60,
    "ADMIN_LOGIN_LOCKOUT_BASE_SECONDS": 120,
    "ADMIN_LOGIN_LOCKOUT_MAX_SECONDS": 600,
}


@override_settings(**ADMIN_SECURITY_SETTINGS)
class AdminSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_superuser(
            username="owner@example.com",
            email="owner@example.com",
            password="A-strong-admin-password-2026",
        )

    def tearDown(self):
        cache.clear()

    def _login(self, password, ip="127.0.0.1"):
        return self.client.post(
            "/admin/login/",
            {"username": self.user.username, "password": password, "next": "/admin/"},
            REMOTE_ADDR=ip,
        )

    def test_bloquea_al_llegar_al_maximo_y_entrega_retry_after(self):
        self.assertEqual(self._login("incorrecta-1").status_code, 200)
        self.assertEqual(self._login("incorrecta-2").status_code, 200)

        with self.assertLogs("core.admin_security", level="ERROR") as logs:
            response = self._login("incorrecta-3")

        self.assertEqual(response.status_code, 429)
        self.assertGreaterEqual(int(response["Retry-After"]), 1)
        self.assertIn("admin_login_lockout", " ".join(logs.output))
        self.assertEqual(
            self._login("A-strong-admin-password-2026").status_code,
            429,
        )

    def test_login_exitoso_limpia_intentos_fallidos(self):
        self.assertEqual(self._login("incorrecta").status_code, 200)
        response = self._login("A-strong-admin-password-2026")
        self.assertEqual(response.status_code, 302)

        self.client.logout()
        self.assertEqual(self._login("incorrecta-otra-vez").status_code, 200)

    @override_settings(ADMIN_ALLOWED_NETWORKS=["10.0.0.0/8"])
    def test_admin_devuelve_404_fuera_de_allowlist(self):
        with self.assertLogs("core.admin_security", level="WARNING") as logs:
            response = self.client.get("/admin/", REMOTE_ADDR="203.0.113.9")

        self.assertEqual(response.status_code, 404)
        self.assertIn("admin_access_denied", " ".join(logs.output))

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_puede_usar_ip_del_proxy_cuando_se_configura_explicitamente(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.0.0.4",
            HTTP_X_FORWARDED_FOR="203.0.113.8, 10.0.0.4",
        )
        self.assertEqual(response.status_code, 302)
