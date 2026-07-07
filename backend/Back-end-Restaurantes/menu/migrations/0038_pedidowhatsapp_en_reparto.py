from django.db import migrations, models


def migrar_en_delivery_a_en_reparto(apps, schema_editor):
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")
    PedidoWhatsApp.objects.filter(estado="en_delivery").update(estado="en_reparto")


def revertir_en_reparto_a_en_delivery(apps, schema_editor):
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")
    PedidoWhatsApp.objects.filter(estado="en_reparto").update(estado="en_delivery")


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0037_alter_pedidowhatsapp_estado"),
    ]

    operations = [
        migrations.RunPython(
            migrar_en_delivery_a_en_reparto,
            revertir_en_reparto_a_en_delivery,
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="estado",
            field=models.CharField(
                choices=[
                    ("recibido", "Pedido recibido"),
                    ("pendiente_confirmacion", "Pendiente de confirmacion"),
                    ("confirmado", "Confirmado"),
                    ("en_preparacion", "En preparación"),
                    ("listo", "Listo"),
                    ("en_reparto", "En reparto"),
                    ("entregado", "Entregado"),
                    ("cancelado", "Cancelado"),
                ],
                default="recibido",
                max_length=30,
            ),
        ),
    ]
