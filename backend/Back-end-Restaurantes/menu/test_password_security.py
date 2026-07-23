from importlib import import_module

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import get_default_password_validators
from django.contrib.sessions.models import Session
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Restaurante, UsuarioRestaurante


class PasswordPolicySecurityTests(TestCase):
    users_url = "/api/mi-restaurante/usuarios/"
    valid_password = "River!Stone42"

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="security-owner@example.com",
            email="security-owner@example.com",
            password="legacy-password",
        )
        self.restaurant = Restaurante.objects.create(
            nombre_empresa="Password Security Restaurant",
            slug="password-security-restaurant",
            rut="33333333-3",
            telefono="999999991",
            email_contacto="security-restaurant@example.com",
            direccion="Security Street 1",
            ciudad="Santiago",
            activo=True,
        )
        self.owner_profile = UsuarioRestaurante.objects.create(
            user=self.owner,
            restaurante=self.restaurant,
            rol="dueno",
            activo=True,
        )
        self.client.force_authenticate(user=self.owner)

    def create_payload(self, password, **overrides):
        payload = {
            "username": "new-secure-user",
            "email": "new-secure-user@example.com",
            "password": password,
            "rol": "empleado",
        }
        payload.update(overrides)
        return payload

    def create_target(self, username="password-target"):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Old!Credential42",
        )
        profile = UsuarioRestaurante.objects.create(
            user=user,
            restaurante=self.restaurant,
            rol="empleado",
            activo=True,
            creado_por=self.owner_profile,
        )
        return user, profile

    def test_valid_password_is_accepted_by_direct_http_request(self):
        with self.assertLogs("menu.security", level="INFO") as logs:
            response = self.client.post(
                self.users_url,
                self.create_payload(self.valid_password),
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(username="new-secure-user")
        self.assertTrue(created.check_password(self.valid_password))
        audit_line = " ".join(logs.output)
        self.assertIn("operation=user_created", audit_line)
        self.assertIn(f"actor_user_id={self.owner.id}", audit_line)
        self.assertNotIn(self.valid_password, audit_line)

    def test_configured_password_validators_include_required_policy(self):
        validators = get_default_password_validators()
        validator_names = {validator.__class__.__name__ for validator in validators}

        self.assertEqual(
            validator_names,
            {
                "UserAttributeSimilarityValidator",
                "MinimumLengthValidator",
                "CommonPasswordValidator",
                "NumericPasswordValidator",
            },
        )
        minimum_length = next(
            validator
            for validator in validators
            if validator.__class__.__name__ == "MinimumLengthValidator"
        )
        self.assertEqual(minimum_length.min_length, 10)

    def test_password_shorter_than_ten_characters_is_rejected(self):
        response = self.client.post(
            self.users_url,
            self.create_payload("Ab3!short"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("10", response.data["error"])

    def test_common_password_is_rejected(self):
        response = self.client.post(
            self.users_url,
            self.create_payload("password"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="new-secure-user").exists())

    def test_numeric_password_is_rejected(self):
        response = self.client.post(
            self.users_url,
            self.create_payload("12345678901"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="new-secure-user").exists())

    def test_password_similar_to_username_or_email_is_rejected(self):
        cases = (
            {
                "username": "distinctiveaccount",
                "email": "unrelated-address@example.com",
                "password": "distinctiveaccount2026!",
            },
            {
                "username": "unrelated-user",
                "email": "personidentity@example.com",
                "password": "personidentity",
            },
        )
        for case in cases:
            with self.subTest(case=case):
                response = self.client.post(
                    self.users_url,
                    self.create_payload(**case),
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_null_empty_and_whitespace_passwords_are_rejected(self):
        password_cases = ("missing", None, "", "   ")
        for password in password_cases:
            with self.subTest(password=password):
                payload = self.create_payload(self.valid_password)
                if password == "missing":
                    payload.pop("password")
                else:
                    payload["password"] = password
                response = self.client.post(self.users_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("error", response.data)

    def test_update_without_password_preserves_current_hash(self):
        user, profile = self.create_target()
        original_hash = user.password

        response = self.client.patch(
            f"{self.users_url}{profile.id}/",
            {"username": "password-target-renamed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)

    def test_direct_password_update_rejects_weak_password_and_preserves_hash(self):
        user, profile = self.create_target()
        original_hash = user.password

        response = self.client.patch(
            f"{self.users_url}{profile.id}/",
            {"password": "short"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)

    def test_valid_password_change_stores_hash_and_audits_without_secret(self):
        user, profile = self.create_target()
        new_password = "Changed!Credential42"

        with self.assertLogs("menu.security", level="INFO") as logs:
            response = self.client.patch(
                f"{self.users_url}{profile.id}/",
                {"password": new_password},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertNotEqual(user.password, new_password)
        self.assertTrue(user.check_password(new_password))
        audit_line = " ".join(logs.output)
        self.assertIn("operation=password_changed", audit_line)
        self.assertIn(f"affected_user_id={user.id}", audit_line)
        self.assertNotIn(new_password, audit_line)

    def test_password_change_revokes_all_refresh_tokens_and_django_sessions(self):
        user, profile = self.create_target()
        refresh_token = str(RefreshToken.for_user(user))

        session_engine = import_module(settings.SESSION_ENGINE)
        session = session_engine.SessionStore()
        session["_auth_user_id"] = str(user.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["_auth_user_hash"] = user.get_session_auth_hash()
        session.save()
        session_key = session.session_key

        response = self.client.patch(
            f"{self.users_url}{profile.id}/",
            {"password": "Revoked!Credential42"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        refresh_response = APIClient().post(
            "/api/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_cannot_change_password_of_another_restaurant_user(self):
        other_restaurant = Restaurante.objects.create(
            nombre_empresa="Other Password Restaurant",
            slug="other-password-restaurant",
            rut="44444444-4",
            telefono="999999992",
            email_contacto="other-password@example.com",
            direccion="Security Street 2",
            ciudad="Santiago",
            activo=True,
        )
        other_user = User.objects.create_user(
            username="other-restaurant-user",
            email="other-restaurant-user@example.com",
            password="Original!Credential42",
        )
        other_profile = UsuarioRestaurante.objects.create(
            user=other_user,
            restaurante=other_restaurant,
            rol="empleado",
            activo=True,
        )
        original_hash = other_user.password

        response = self.client.patch(
            f"{self.users_url}{other_profile.id}/",
            {"password": "Intruder!Credential42"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        other_user.refresh_from_db()
        self.assertEqual(other_user.password, original_hash)
