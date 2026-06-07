from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0027_alter_solicitudespecial_estado"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notificacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("reserva", "Reserva"),
                            ("solicitud_especial", "Solicitud especial"),
                        ],
                        max_length=30,
                    ),
                ),
                ("titulo", models.CharField(max_length=160)),
                ("mensaje", models.TextField()),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("leida", models.BooleanField(default=False)),
                ("fecha_lectura", models.DateTimeField(blank=True, null=True)),
                ("referencia_id", models.PositiveIntegerField()),
                (
                    "referencia_modelo",
                    models.CharField(
                        choices=[
                            ("Reserva", "Reserva"),
                            ("SolicitudEspecial", "Solicitud especial"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "restaurante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notificaciones",
                        to="menu.restaurante",
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha_creacion"],
                "indexes": [
                    models.Index(fields=["restaurante", "leida", "-fecha_creacion"], name="notif_rest_leida_fecha_idx"),
                    models.Index(fields=["restaurante", "tipo"], name="notif_rest_tipo_idx"),
                    models.Index(fields=["referencia_modelo", "referencia_id"], name="notif_referencia_idx"),
                ],
            },
        ),
    ]
