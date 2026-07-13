from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0044_metodos_pago_pedidowhatsapp"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurante",
            name="apertura_excepcional_hasta",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
