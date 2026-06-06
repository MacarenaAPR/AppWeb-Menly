from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0025_restaurante_feature_flags"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolicitudEspecial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=120)),
                ("apellido", models.CharField(max_length=120)),
                ("fecha_evento", models.DateField()),
                ("telefono_contacto", models.CharField(max_length=30)),
                ("email_contacto", models.EmailField(max_length=254)),
                ("descripcion_solicitud", models.TextField()),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("contactada", "Contactada"),
                            ("rechazada", "Rechazada"),
                            ("cerrada", "Cerrada"),
                        ],
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                (
                    "restaurante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="solicitudes_especiales",
                        to="menu.restaurante",
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha_creacion"],
                "indexes": [
                    models.Index(fields=["restaurante", "-fecha_creacion"], name="solesp_rest_creacion_idx"),
                    models.Index(fields=["restaurante", "estado"], name="solesp_rest_estado_idx"),
                ],
            },
        ),
    ]
