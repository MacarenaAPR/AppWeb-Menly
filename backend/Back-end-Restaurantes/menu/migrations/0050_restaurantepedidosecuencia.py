from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
from django.db.models import Max
import django.db.models.deletion


def inicializar_secuencias(apps, schema_editor):
    Restaurante = apps.get_model("menu", "Restaurante")
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")
    PedidoEspecial = apps.get_model("menu", "PedidoEspecial")
    PedidoManual = apps.get_model("menu", "PedidoManual")
    RestaurantePedidoSecuencia = apps.get_model("menu", "RestaurantePedidoSecuencia")

    for restaurante_id in Restaurante.objects.values_list("id", flat=True).iterator():
        maximos = [
            PedidoWhatsApp.objects.filter(restaurante_id=restaurante_id).aggregate(
                maximo=Max("numero_pedido")
            )["maximo"] or 0,
            PedidoEspecial.objects.filter(restaurante_id=restaurante_id).aggregate(
                maximo=Max("numero_pedido")
            )["maximo"] or 0,
            PedidoManual.objects.filter(restaurante_id=restaurante_id).aggregate(
                maximo=Max("numero_pedido")
            )["maximo"] or 0,
        ]
        RestaurantePedidoSecuencia.objects.create(
            restaurante_id=restaurante_id,
            ultimo_numero=min(max(maximos), 9999),
        )


def eliminar_secuencias(apps, schema_editor):
    RestaurantePedidoSecuencia = apps.get_model("menu", "RestaurantePedidoSecuencia")
    RestaurantePedidoSecuencia.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0049_pushsubscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="RestaurantePedidoSecuencia",
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
                    "ultimo_numero",
                    models.PositiveIntegerField(
                        default=0,
                        validators=[MinValueValidator(0), MaxValueValidator(9999)],
                    ),
                ),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                (
                    "restaurante",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="secuencia_pedidos",
                        to="menu.restaurante",
                    ),
                ),
            ],
            options={
                "verbose_name": "secuencia de pedidos del restaurante",
                "verbose_name_plural": "secuencias de pedidos de restaurantes",
            },
        ),
        migrations.RunPython(inicializar_secuencias, eliminar_secuencias),
        migrations.RemoveConstraint(
            model_name="pedidowhatsapp",
            name="unique_pedido_whatsapp_numero_por_rest",
        ),
        migrations.RemoveConstraint(
            model_name="pedidoespecial",
            name="unique_pedido_especial_numero_por_rest",
        ),
        migrations.RemoveConstraint(
            model_name="pedidomanual",
            name="unique_pedido_manual_numero_por_rest",
        ),
    ]
