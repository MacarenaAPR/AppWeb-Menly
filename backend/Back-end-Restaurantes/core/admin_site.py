from django.contrib.admin import AdminSite


class MenlyAdminSite(AdminSite):
    """Admin de Menly con los modelos de MENU agrupados visualmente."""

    menu_groups = (
        (
            "Restaurantes y Configuración",
            {
                "Restaurante",
                "ImagenRestaurante",
                "HorarioAtencion",
                "MetodoPago",
                "Mesa",
                "Plan",
                "UsuarioRestaurante",
            },
        ),
        (
            "Carta y Productos",
            {
                "Categoria",
                "Producto",
                "ProductoVariante",
                "Icono",
                "BitacoraProducto",
            },
        ),
        (
            "Pedidos",
            {
                "PedidoWhatsApp",
                "PedidoManual",
                "PedidoEspecial",
                "RestaurantePedidoSecuencia",
            },
        ),
        (
            "Cocina",
            {
                "ActivacionCocina",
                "TurnoOperativo",
                "SesionCocina",
            },
        ),
        (
            "Clientes",
            {
                "Reserva",
                "SolicitudEspecial",
            },
        ),
        (
            "Notificaciones",
            {
                "Notificacion",
                "PushSubscription",
            },
        ),
        (
            "Reportes y Métricas",
            {
                "ReporteMetrica",
            },
        ),
    )

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)

        # La vista propia de una aplicación debe conservar su estructura original.
        if app_label is not None:
            return app_list

        grouped_app_list = []
        for app in app_list:
            if app["app_label"] != "menu":
                grouped_app_list.append(app)
                continue

            grouped_app_list.extend(self._group_menu_models(app))

        return grouped_app_list

    def _group_menu_models(self, menu_app):
        models_by_group = {
            group_name: []
            for group_name, _model_names in self.menu_groups
        }
        other_models = []

        group_for_model = {
            model_name: group_name
            for group_name, model_names in self.menu_groups
            for model_name in model_names
        }

        for model in menu_app["models"]:
            group_name = group_for_model.get(model["object_name"])
            if group_name is None:
                other_models.append(model)
            else:
                models_by_group[group_name].append(model)

        grouped_apps = []
        ordered_groups = [
            (group_name, models_by_group[group_name])
            for group_name, _model_names in self.menu_groups
        ]
        ordered_groups.append(("Otros", other_models))

        for position, (group_name, models) in enumerate(ordered_groups):
            if not models:
                continue

            grouped_apps.append(
                {
                    **menu_app,
                    "name": group_name,
                    "app_label": f"menu_group_{position}",
                    "models": sorted(
                        models,
                        key=lambda model: str(model["name"]).casefold(),
                    ),
                }
            )

        return grouped_apps
