import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from core.admin_security import _digest, _scope_identifiers


ADMIN_SECURITY_SETTINGS = {
    "ADMIN_URL_PATH": "admin",
    "ADMIN_ALLOWED_NETWORKS": ["127.0.0.1/32"],
    "ADMIN_CLIENT_IP_HEADER": "REMOTE_ADDR",
    "ADMIN_TRUSTED_PROXY_NETWORKS": [],
    "ADMIN_IP_DIAGNOSTICS": False,
    "ADMIN_LOGIN_PAIR_MAX_FAILURES": 3,
    "ADMIN_LOGIN_PAIR_WINDOW_SECONDS": 60,
    "ADMIN_LOGIN_PAIR_LOCK_SECONDS": 120,
    "ADMIN_LOGIN_IP_MAX_FAILURES": 20,
    "ADMIN_LOGIN_IP_WINDOW_SECONDS": 60,
    "ADMIN_LOGIN_IP_LOCK_SECONDS": 240,
    "ADMIN_LOGIN_ACCOUNT_MAX_FAILURES": 6,
    "ADMIN_LOGIN_ACCOUNT_WINDOW_SECONDS": 60,
    "ADMIN_LOGIN_ACCOUNT_LOCK_SECONDS": 240,
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
        self.other_user = User.objects.create_superuser(
            username="other-owner@example.com",
            email="other-owner@example.com",
            password="Another-strong-admin-password-2026",
        )

    def tearDown(self):
        cache.clear()

    def _login(self, password, ip="127.0.0.1", username=None):
        return self.client.post(
            "/admin/login/",
            {
                "username": username or self.user.username,
                "password": password,
                "next": "/admin/",
            },
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
        self.assertEqual(self._login("incorrecta-1").status_code, 200)
        self.assertEqual(self._login("incorrecta-2").status_code, 200)
        response = self._login("A-strong-admin-password-2026")
        self.assertEqual(response.status_code, 302)

        self.client.logout()
        self.assertEqual(self._login("incorrecta-3").status_code, 200)
        self.assertEqual(self._login("incorrecta-4").status_code, 200)
        self.assertEqual(self._login("incorrecta-5").status_code, 429)

    @override_settings(
        ADMIN_LOGIN_PAIR_MAX_FAILURES=5,
        ADMIN_LOGIN_ACCOUNT_MAX_FAILURES=20,
        ADMIN_LOGIN_IP_MAX_FAILURES=20,
    )
    def test_cinco_fallos_de_a_no_bloquean_a_b_desde_la_misma_ip(self):
        for attempt in range(1, 5):
            self.assertEqual(self._login(f"incorrecta-{attempt}").status_code, 200)

        self.assertEqual(self._login("incorrecta-5").status_code, 429)
        response = self._login(
            "Another-strong-admin-password-2026",
            username=self.other_user.username,
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        ADMIN_LOGIN_PAIR_MAX_FAILURES=3,
        ADMIN_LOGIN_ACCOUNT_MAX_FAILURES=10,
        ADMIN_LOGIN_IP_MAX_FAILURES=6,
    )
    def test_muchos_usuarios_desde_una_ip_activan_bloqueo_por_ip(self):
        for attempt in range(1, 6):
            response = self._login(
                "incorrecta",
                username=f"target-{attempt}@example.com",
            )
            self.assertEqual(response.status_code, 200)

        response = self._login(
            "incorrecta",
            username="target-6@example.com",
        )
        self.assertEqual(response.status_code, 429)

    @override_settings(
        ADMIN_ALLOWED_NETWORKS=["127.0.0.0/8"],
        ADMIN_LOGIN_PAIR_MAX_FAILURES=3,
        ADMIN_LOGIN_ACCOUNT_MAX_FAILURES=4,
        ADMIN_LOGIN_IP_MAX_FAILURES=20,
    )
    def test_una_cuenta_atacada_desde_varias_ips_queda_bloqueada(self):
        for last_octet in range(2, 5):
            response = self._login(
                "incorrecta",
                ip=f"127.0.0.{last_octet}",
            )
            self.assertEqual(response.status_code, 200)

        response = self._login("incorrecta", ip="127.0.0.5")
        self.assertEqual(response.status_code, 429)

    @override_settings(
        ADMIN_LOGIN_PAIR_MAX_FAILURES=2,
        ADMIN_LOGIN_ACCOUNT_MAX_FAILURES=10,
        ADMIN_LOGIN_IP_MAX_FAILURES=4,
    )
    def test_login_exitoso_no_limpia_contador_global_de_ip(self):
        self.assertEqual(self._login("incorrecta").status_code, 200)
        self.assertEqual(
            self._login("A-strong-admin-password-2026").status_code,
            302,
        )
        self.client.logout()

        for attempt in range(1, 3):
            response = self._login(
                "incorrecta",
                username=f"other-target-{attempt}@example.com",
            )
            self.assertEqual(response.status_code, 200)

        response = self._login(
            "incorrecta",
            username="other-target-3@example.com",
        )
        self.assertEqual(response.status_code, 429)

    @override_settings(
        ADMIN_LOGIN_PAIR_MAX_FAILURES=2,
        ADMIN_LOGIN_PAIR_LOCK_SECONDS=120,
        ADMIN_LOGIN_ACCOUNT_MAX_FAILURES=20,
        ADMIN_LOGIN_IP_MAX_FAILURES=20,
    )
    @patch("core.admin_security.time.time")
    def test_bloqueo_no_se_prolonga_y_retry_after_disminuye(self, mocked_time):
        mocked_time.return_value = 1000
        self.assertEqual(self._login("incorrecta-1").status_code, 200)
        initial = self._login("incorrecta-2")
        self.assertEqual(initial.status_code, 429)
        self.assertEqual(initial["Retry-After"], "120")

        mocked_time.return_value = 1030
        after_thirty_seconds = self._login("A-strong-admin-password-2026")
        self.assertEqual(after_thirty_seconds.status_code, 429)
        self.assertEqual(after_thirty_seconds["Retry-After"], "90")

        mocked_time.return_value = 1060
        after_sixty_seconds = self._login("A-strong-admin-password-2026")
        self.assertEqual(after_sixty_seconds.status_code, 429)
        self.assertEqual(after_sixty_seconds["Retry-After"], "60")

    def test_identificadores_son_hashes_y_unknown_no_crea_bucket_ip(self):
        username = "owner@example.com"
        identifiers = _scope_identifiers("127.0.0.1", username)

        self.assertEqual(
            {kind for kind, _ in identifiers},
            {"ip", "pair", "account"},
        )
        for _, identifier in identifiers:
            self.assertEqual(len(identifier), 64)
            self.assertNotIn(username, identifier)
            self.assertNotIn("127.0.0.1", identifier)

        self.assertEqual(_scope_identifiers("unknown", ""), [])
        self.assertEqual(
            [kind for kind, _ in _scope_identifiers("unknown", username)],
            ["account"],
        )

    def test_bloqueo_global_legacy_no_contamina_namespace_v2(self):
        legacy_ip_identifier = _digest("ip:127.0.0.1")
        cache.set(
            f"admin-security:ip:{legacy_ip_identifier}:locked-until",
            time.time() + 600,
            timeout=600,
        )

        response = self._login(
            "Another-strong-admin-password-2026",
            username=self.other_user.username,
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(ADMIN_ALLOWED_NETWORKS=["10.0.0.0/8"])
    def test_admin_devuelve_404_fuera_de_allowlist(self):
        with self.assertLogs("core.admin_security", level="WARNING") as logs:
            response = self.client.get("/admin/", REMOTE_ADDR="203.0.113.9")

        self.assertEqual(response.status_code, 404)
        self.assertIn("admin_access_denied", " ".join(logs.output))

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_acceso_permitido_detras_de_proxy_confiable(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.197.4.2",
            HTTP_X_FORWARDED_FOR="203.0.113.8, 198.51.100.99",
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_rechaza_ip_publica_no_permitida_detras_de_proxy(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.24.1.9",
            HTTP_X_FORWARDED_FOR="198.51.100.20, 10.24.1.9",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_no_confia_en_header_desde_conexion_no_confiable(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="198.51.100.20",
            HTTP_X_FORWARDED_FOR="203.0.113.8",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_acepta_cadena_con_multiples_proxies_confiables(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.197.4.2",
            HTTP_X_FORWARDED_FOR="203.0.113.8, 10.24.1.9, 10.197.4.2",
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_un_elemento_agregado_no_puede_autorizar_al_cliente(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.197.4.2",
            HTTP_X_FORWARDED_FOR="198.51.100.99, 203.0.113.8",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
    )
    def test_rechaza_header_vacio_o_malformado(self):
        malformed_values = (
            "",
            "203.0.113.8,,10.0.0.4",
            "203.0.113.8:443, 10.0.0.4",
            "not-an-ip, 10.0.0.4",
        )
        for value in malformed_values:
            with self.subTest(value=value):
                response = self.client.get(
                    "/admin/",
                    REMOTE_ADDR="10.0.0.4",
                    HTTP_X_FORWARDED_FOR=value,
                )
                self.assertEqual(response.status_code, 404)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["2001:db8:1234::/48"],
    )
    def test_acepta_ipv6_valida_detras_de_proxy(self):
        response = self.client.get(
            "/admin/",
            REMOTE_ADDR="10.0.0.4",
            HTTP_X_FORWARDED_FOR="2001:db8:1234::25, 10.0.0.4",
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        ADMIN_CLIENT_IP_HEADER="HTTP_X_FORWARDED_FOR",
        ADMIN_TRUSTED_PROXY_NETWORKS=["10.0.0.0/8"],
        ADMIN_ALLOWED_NETWORKS=["203.0.113.0/24"],
        ADMIN_IP_DIAGNOSTICS=True,
    )
    def test_diagnostico_es_opcional_y_enmascara_la_ip(self):
        with self.assertLogs("core.admin_security", level="INFO") as logs:
            response = self.client.get(
                "/admin/",
                REMOTE_ADDR="10.0.0.4",
                HTTP_X_FORWARDED_FOR="203.0.113.8, 10.0.0.4",
                HTTP_TRUE_CLIENT_IP="203.0.113.8",
            )

        output = " ".join(logs.output)
        self.assertEqual(response.status_code, 302)
        self.assertIn("admin_ip_diagnostic", output)
        self.assertIn("HTTP_X_FORWARDED_FOR", output)
        self.assertIn("HTTP_TRUE_CLIENT_IP", output)
        self.assertIn("detected_ip=203.0.113.x", output)
        self.assertIn("chain_length=2", output)
        self.assertIn("method=trusted_forwarded_header", output)
        self.assertNotIn("203.0.113.8", output)

    @override_settings(
        ADMIN_ALLOWED_NETWORKS=[],
        IS_PRODUCTION=True,
    )
    def test_login_saas_no_es_interceptado_por_seguridad_del_admin(self):
        response = self.client.post(
            "/api/login/",
            {"email": "nobody@example.com", "password": "invalid-password"},
            content_type="application/json",
            REMOTE_ADDR="198.51.100.20",
        )
        self.assertNotEqual(response.status_code, 404)
