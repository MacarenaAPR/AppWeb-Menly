from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("menu", "0048_alter_pedidomanual_estado_en_reparto"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("endpoint", models.URLField(max_length=1000, unique=True)),
                ("p256dh", models.CharField(max_length=255)),
                ("auth", models.CharField(max_length=255)),
                ("tipo_dispositivo", models.CharField(choices=[("panel", "Panel"), ("kds", "KDS")], default="panel", max_length=10)),
                ("activo", models.BooleanField(default=True)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("restaurante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="suscripciones_push", to="menu.restaurante")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="suscripciones_push", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-fecha_actualizacion",),
                "indexes": [models.Index(fields=["restaurante", "tipo_dispositivo", "activo"], name="push_rest_tipo_activo_idx")],
            },
        ),
    ]
