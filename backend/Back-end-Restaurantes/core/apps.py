from django.contrib.admin.apps import AdminConfig


class MenlyAdminConfig(AdminConfig):
    default_site = "core.admin_site.MenlyAdminSite"
