from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0055_pedidopruebaimportado"),
    ]

    operations = [
        migrations.CreateModel(
            name="EjecucionReportesMensuales",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "modo",
                    models.CharField(
                        choices=[
                            ("programado", "Cierre programado"),
                            ("periodo", "Período específico"),
                            ("backfill", "Recuperación histórica"),
                        ],
                        max_length=20,
                    ),
                ),
                ("periodo", models.CharField(blank=True, max_length=7)),
                ("incluye_inactivos", models.BooleanField(default=False)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("ejecutando", "Ejecutando"),
                            ("exitoso", "Exitoso"),
                            ("parcial", "Con errores parciales"),
                            ("fallido", "Fallido"),
                        ],
                        default="ejecutando",
                        max_length=20,
                    ),
                ),
                ("fecha_inicio", models.DateTimeField(auto_now_add=True)),
                ("fecha_fin", models.DateTimeField(blank=True, null=True)),
                ("restaurantes_procesados", models.PositiveIntegerField(default=0)),
                ("reportes_generados", models.PositiveIntegerField(default=0)),
                ("reportes_existentes", models.PositiveIntegerField(default=0)),
                ("cantidad_errores", models.PositiveIntegerField(default=0)),
                ("detalle", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "ejecución de reportes mensuales",
                "verbose_name_plural": "ejecuciones de reportes mensuales",
                "ordering": ["-fecha_inicio"],
                "indexes": [
                    models.Index(fields=["-fecha_inicio"], name="ejrepmes_fecha_idx"),
                    models.Index(
                        fields=["estado", "-fecha_inicio"],
                        name="ejrepmes_estado_fecha_idx",
                    ),
                ],
            },
        ),
    ]
