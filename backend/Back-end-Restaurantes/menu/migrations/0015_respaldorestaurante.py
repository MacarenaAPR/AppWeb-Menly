from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0014_restaurante_facebook_restaurante_google_maps_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RespaldoRestaurante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_respaldo", models.DateTimeField(auto_now_add=True)),
                ("nombre_responsable", models.CharField(max_length=150)),
                ("nombre_restaurante", models.CharField(max_length=150)),
                ("datos_json", models.JSONField()),
                (
                    "responsable",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="respaldos_creados",
                        to="menu.usuariorestaurante",
                    ),
                ),
                (
                    "restaurante",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="respaldos",
                        to="menu.restaurante",
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha_respaldo"],
            },
        ),
    ]
