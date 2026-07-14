from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0047_historiales_estados_pedidos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pedidomanual",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("preparando", "Preparando"),
                    ("listo", "Listo"),
                    ("en_reparto", "En reparto"),
                    ("entregado", "Entregado"),
                    ("cancelado", "Cancelado"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
    ]
