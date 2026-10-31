from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0053_producto_ofertas_pedidomanualitem_descuento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="tipo_entrega",
            field=models.CharField(
                choices=[
                    ("delivery", "Delivery"),
                    ("retiro_local", "Retiro en local"),
                    ("para_llevar", "Para llevar"),
                    ("servir_en_local", "Servir en el local"),
                ],
                max_length=20,
            ),
        ),
    ]
