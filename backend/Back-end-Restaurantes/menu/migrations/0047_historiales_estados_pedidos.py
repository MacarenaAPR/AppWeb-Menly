import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0046_pedidoidempotencia"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="historialestadopedidowhatsapp",
            name="origen",
            field=models.CharField(
                choices=[
                    ("panel", "Panel"),
                    ("kds", "KDS"),
                    ("sistema", "Sistema"),
                ],
                default="sistema",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="HistorialEstadoPedidoManual",
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
                ("estado_anterior", models.CharField(blank=True, max_length=30)),
                ("estado_nuevo", models.CharField(max_length=30)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                (
                    "origen",
                    models.CharField(
                        choices=[
                            ("panel", "Panel"),
                            ("kds", "KDS"),
                            ("sistema", "Sistema"),
                        ],
                        default="sistema",
                        max_length=20,
                    ),
                ),
                (
                    "pedido",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historial_estados",
                        to="menu.pedidomanual",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="historial_estados_pedidos_manuales",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha"],
                "indexes": [
                    models.Index(
                        fields=["pedido", "-fecha"],
                        name="histpedm_pedido_fecha_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="HistorialEstadoPedidoEspecial",
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
                ("estado_anterior", models.CharField(blank=True, max_length=30)),
                ("estado_nuevo", models.CharField(max_length=30)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                (
                    "origen",
                    models.CharField(
                        choices=[
                            ("panel", "Panel"),
                            ("kds", "KDS"),
                            ("sistema", "Sistema"),
                        ],
                        default="sistema",
                        max_length=20,
                    ),
                ),
                (
                    "pedido",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historial_estados",
                        to="menu.pedidoespecial",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="historial_estados_pedidos_especiales",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha"],
                "indexes": [
                    models.Index(
                        fields=["pedido", "-fecha"],
                        name="histpede_pedido_fecha_idx",
                    ),
                ],
            },
        ),
    ]
