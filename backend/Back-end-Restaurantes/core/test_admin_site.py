from copy import deepcopy

from django.contrib import admin
from django.test import SimpleTestCase

from core.admin_site import MenlyAdminSite


class MenlyAdminSiteTests(SimpleTestCase):
    def setUp(self):
        self.site = MenlyAdminSite()
        self.menu_app = {
            "name": "Menu",
            "app_label": "menu",
            "app_url": "/admin/menu/",
            "has_module_perms": True,
            "models": [
                {
                    "name": "Productos",
                    "object_name": "Producto",
                    "admin_url": "/admin/menu/producto/",
                    "add_url": "/admin/menu/producto/add/",
                },
                {
                    "name": "Categorías",
                    "object_name": "Categoria",
                    "admin_url": "/admin/menu/categoria/",
                    "add_url": "/admin/menu/categoria/add/",
                },
                {
                    "name": "Modelo futuro",
                    "object_name": "ModeloFuturo",
                    "admin_url": "/admin/menu/modelofuturo/",
                    "add_url": "/admin/menu/modelofuturo/add/",
                },
            ],
        }

    def test_default_admin_site_uses_menly_subclass(self):
        self.assertIsInstance(admin.site, MenlyAdminSite)

    def test_groups_models_without_duplicates_and_preserves_links(self):
        original_models = deepcopy(self.menu_app["models"])

        groups = self.site._group_menu_models(self.menu_app)
        grouped_models = [
            model
            for group in groups
            for model in group["models"]
        ]

        self.assertCountEqual(grouped_models, original_models)
        self.assertEqual(len(grouped_models), len(original_models))
        self.assertEqual(
            {model["object_name"]: model["admin_url"] for model in grouped_models},
            {model["object_name"]: model["admin_url"] for model in original_models},
        )

    def test_unknown_models_are_placed_in_otros(self):
        groups = self.site._group_menu_models(self.menu_app)

        otros = next(group for group in groups if group["name"] == "Otros")

        self.assertEqual(
            [model["object_name"] for model in otros["models"]],
            ["ModeloFuturo"],
        )

    def test_models_are_sorted_alphabetically_inside_each_group(self):
        groups = self.site._group_menu_models(self.menu_app)
        carta = next(
            group for group in groups if group["name"] == "Carta y Productos"
        )

        self.assertEqual(
            [model["name"] for model in carta["models"]],
            ["Categorías", "Productos"],
        )
