import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0042_productovariante"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedidomanualitem",
            name="variante",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="items_pedidos_manuales",
                to="menu.productovariante",
            ),
        ),
        migrations.AddField(
            model_name="pedidomanualitem",
            name="variante_nombre",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
