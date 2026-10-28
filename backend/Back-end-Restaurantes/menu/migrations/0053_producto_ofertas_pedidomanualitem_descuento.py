from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0052_grupoopcionesproducto_opcionproducto_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="producto",
            name="precio",
            field=models.DecimalField(
                decimal_places=0,
                max_digits=8,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="producto",
            name="porcentaje_descuento",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(99)],
            ),
        ),
        migrations.AddConstraint(
            model_name="producto",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(porcentaje_descuento__isnull=True)
                    | models.Q(
                        porcentaje_descuento__gte=1,
                        porcentaje_descuento__lte=99,
                    )
                ),
                name="producto_descuento_nulo_o_1_99",
            ),
        ),
        migrations.AddConstraint(
            model_name="producto",
            constraint=models.CheckConstraint(
                condition=models.Q(precio__gte=0),
                name="producto_precio_no_negativo",
            ),
        ),
        migrations.AddField(
            model_name="pedidomanualitem",
            name="precio_original",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="pedidomanualitem",
            name="porcentaje_descuento_aplicado",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pedidomanualitem",
            name="monto_descuento",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                max_digits=10,
                null=True,
            ),
        ),
    ]
