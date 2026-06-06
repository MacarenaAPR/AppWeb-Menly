from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0024_production_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurante",
            name="carrito_whatsapp_activo",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="restaurante",
            name="metricas_activas",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="restaurante",
            name="reservas_activas",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="restaurante",
            name="solicitudes_especiales_activas",
            field=models.BooleanField(default=False),
        ),
    ]
