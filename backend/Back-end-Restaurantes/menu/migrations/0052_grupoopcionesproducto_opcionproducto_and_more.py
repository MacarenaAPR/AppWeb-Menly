import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0051_turnooperativo"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrupoOpcionesProducto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=100)),
                ("obligatorio", models.BooleanField(default=False)),
                ("minimo_selecciones", models.PositiveIntegerField(default=0)),
                (
                    "maximo_selecciones",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("orden", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "producto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grupos_opciones",
                        to="menu.producto",
                    ),
                ),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.CreateModel(
            name="OpcionProducto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=100)),
                (
                    "precio_adicional",
                    models.DecimalField(decimal_places=0, default=0, max_digits=8),
                ),
                ("disponible", models.BooleanField(default=True)),
                ("orden", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "grupo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="opciones",
                        to="menu.grupoopcionesproducto",
                    ),
                ),
            ],
            options={"ordering": ["orden", "id"]},
        ),
        migrations.AddField(
            model_name="pedidomanualitem",
            name="opciones_snapshot",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddIndex(
            model_name="grupoopcionesproducto",
            index=models.Index(
                fields=["producto", "orden"],
                name="grpopc_prod_orden_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoopcionesproducto",
            constraint=models.CheckConstraint(
                condition=models.Q(("minimo_selecciones__gte", 0)),
                name="grpopc_min_no_negativo",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoopcionesproducto",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("maximo_selecciones__isnull", True))
                    | models.Q(
                        ("maximo_selecciones__gte", models.F("minimo_selecciones"))
                    )
                ),
                name="grpopc_max_gte_min",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoopcionesproducto",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("obligatorio", False))
                    | models.Q(("minimo_selecciones__gte", 1))
                ),
                name="grpopc_oblig_min_uno",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoopcionesproducto",
            constraint=models.UniqueConstraint(
                fields=("producto", "nombre"),
                name="unique_grupo_opcion_por_producto",
            ),
        ),
        migrations.AddIndex(
            model_name="opcionproducto",
            index=models.Index(
                fields=["grupo", "disponible", "orden"],
                name="opprod_grup_disp_ord_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="opcionproducto",
            constraint=models.CheckConstraint(
                condition=models.Q(("precio_adicional__gte", 0)),
                name="opprod_precio_no_negativo",
            ),
        ),
        migrations.AddConstraint(
            model_name="opcionproducto",
            constraint=models.UniqueConstraint(
                fields=("grupo", "nombre"),
                name="unique_opcion_por_grupo",
            ),
        ),
    ]
