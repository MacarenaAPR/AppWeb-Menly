import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0054_alter_pedidowhatsapp_tipo_entrega"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PedidoPruebaImportado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador_externo", models.CharField(max_length=120)),
                ("archivo_origen", models.CharField(blank=True, max_length=255)),
                ("fila_inicio", models.PositiveIntegerField()),
                ("datos_origen", models.JSONField(blank=True, default=dict)),
                ("fecha_importacion", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pedidos_prueba_importados", to=settings.AUTH_USER_MODEL)),
                ("pedido_manual", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marca_importacion_prueba", to="menu.pedidomanual")),
                ("restaurante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pedidos_prueba_importados", to="menu.restaurante")),
            ],
            options={
                "ordering": ["-fecha_importacion"],
                "indexes": [models.Index(fields=["restaurante", "-fecha_importacion"], name="pedprueba_rest_fecha_idx")],
                "constraints": [models.UniqueConstraint(fields=("restaurante", "identificador_externo"), name="unique_pedido_prueba_ext_por_rest")],
            },
        ),
    ]
