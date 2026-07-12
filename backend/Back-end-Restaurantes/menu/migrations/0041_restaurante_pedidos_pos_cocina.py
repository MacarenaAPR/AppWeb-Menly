import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0040_pedidomanual_tracking_token"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurante",
            name="pedidos_pos",
            field=models.BooleanField(default=False, verbose_name="Pedidos POS activos"),
        ),
        migrations.CreateModel(
            name="ActivacionCocina",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=128, unique=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("expira_en", models.DateTimeField()),
                ("consumido_en", models.DateTimeField(blank=True, null=True)),
                ("activa", models.BooleanField(default=True)),
                ("creado_por", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activaciones_cocina_creadas", to=settings.AUTH_USER_MODEL)),
                ("restaurante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activaciones_cocina", to="menu.restaurante")),
            ],
            options={
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="SesionCocina",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=128, unique=True)),
                ("fecha_operativa", models.DateField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("expira_en", models.DateTimeField()),
                ("cerrada_en", models.DateTimeField(blank=True, null=True)),
                ("activa", models.BooleanField(default=True)),
                ("restaurante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sesiones_cocina", to="menu.restaurante")),
            ],
            options={
                "ordering": ["-creado_en"],
            },
        ),
        migrations.AddIndex(
            model_name="activacioncocina",
            index=models.Index(fields=["restaurante", "-creado_en"], name="actcoc_rest_creado_idx"),
        ),
        migrations.AddIndex(
            model_name="activacioncocina",
            index=models.Index(fields=["token_hash"], name="actcoc_token_hash_idx"),
        ),
        migrations.AddIndex(
            model_name="sesioncocina",
            index=models.Index(fields=["restaurante", "fecha_operativa", "activa"], name="sescoc_rest_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="sesioncocina",
            index=models.Index(fields=["token_hash"], name="sescoc_token_hash_idx"),
        ),
    ]
