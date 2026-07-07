from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0035_alter_notificacion_referencia_modelo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurante",
            name="abierto",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="restaurante",
            name="delivery_activo",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="estado",
            field=models.CharField(
                choices=[
                    ("recibido", "Pedido recibido"),
                    ("pendiente_confirmacion", "Pendiente de confirmacion"),
                    ("confirmado", "Confirmado"),
                    ("en_preparacion", "En preparaciÃ³n"),
                    ("en_delivery", "En camino"),
                    ("listo", "Listo"),
                    ("entregado", "Entregado"),
                    ("cancelado", "Cancelado"),
                ],
                default="recibido",
                max_length=30,
            ),
        ),
    ]
