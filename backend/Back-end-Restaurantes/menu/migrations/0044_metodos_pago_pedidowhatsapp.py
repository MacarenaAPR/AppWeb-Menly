from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def poblar_codigos_metodos_pago(apps, schema_editor):
    MetodoPago = apps.get_model("menu", "MetodoPago")

    for metodo in MetodoPago.objects.order_by("restaurante_id", "id"):
        base = slugify(metodo.nombre)[:40] or "metodo-pago"
        codigo = base
        sufijo = 2
        while MetodoPago.objects.filter(
            restaurante_id=metodo.restaurante_id,
            codigo=codigo,
        ).exclude(id=metodo.id).exists():
            codigo = f"{base[:45]}-{sufijo}"
            sufijo += 1

        metodo.codigo = codigo
        metodo.save(update_fields=["codigo"])


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0043_pedidomanualitem_variante"),
    ]

    operations = [
        migrations.AddField(
            model_name="metodopago",
            name="codigo",
            field=models.SlugField(default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="metodopago",
            name="orden",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(
            poblar_codigos_metodos_pago,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="metodopago",
            constraint=models.UniqueConstraint(
                fields=("restaurante", "codigo"),
                name="unique_codigo_metodo_pago_por_restaurante",
            ),
        ),
        migrations.AlterModelOptions(
            name="metodopago",
            options={"ordering": ["orden", "id"]},
        ),
        migrations.AddField(
            model_name="pedidowhatsapp",
            name="metodo_pago",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pedidos_whatsapp",
                to="menu.metodopago",
            ),
        ),
        migrations.AddField(
            model_name="pedidowhatsapp",
            name="metodo_pago_nombre",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
