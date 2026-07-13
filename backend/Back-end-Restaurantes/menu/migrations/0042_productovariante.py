import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0041_restaurante_pedidos_pos_cocina"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductoVariante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100)),
                ("descripcion", models.TextField(blank=True)),
                ("precio", models.DecimalField(decimal_places=0, max_digits=8)),
                ("activo", models.BooleanField(default=True)),
                ("orden", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("producto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variantes", to="menu.producto")),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.AddIndex(
            model_name="productovariante",
            index=models.Index(fields=["producto", "activo", "orden"], name="prodvar_prod_act_orden_idx"),
        ),
        migrations.AddConstraint(
            model_name="productovariante",
            constraint=models.CheckConstraint(condition=models.Q(("precio__gte", 0)), name="producto_variante_precio_no_negativo"),
        ),
        migrations.AddConstraint(
            model_name="productovariante",
            constraint=models.UniqueConstraint(fields=("producto", "nombre"), name="unique_variante_nombre_por_producto"),
        ),
    ]
