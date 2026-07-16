from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0050_restaurantepedidosecuencia"),
    ]

    operations = [
        migrations.CreateModel(
            name="TurnoOperativo",
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
                ("inicio", models.DateTimeField()),
                ("fin_programado", models.DateTimeField()),
                ("fecha_operativa", models.DateField()),
                (
                    "origen_inicio",
                    models.CharField(
                        choices=[
                            ("horario", "Horario programado"),
                            ("apertura_excepcional", "Apertura excepcional"),
                        ],
                        max_length=30,
                    ),
                ),
                ("cerrado", models.BooleanField(default=False)),
                ("fecha_cierre_real", models.DateTimeField(blank=True, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "restaurante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turnos_operativos",
                        to="menu.restaurante",
                    ),
                ),
            ],
            options={
                "ordering": ["-inicio"],
                "indexes": [
                    models.Index(
                        fields=["restaurante", "-inicio"],
                        name="turno_rest_inicio_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("cerrado", False)),
                        fields=("restaurante",),
                        name="unique_turno_operativo_activo_por_rest",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("fin_programado__gt", models.F("inicio"))
                        ),
                        name="turno_fin_posterior_inicio",
                    ),
                ],
            },
        ),
    ]
