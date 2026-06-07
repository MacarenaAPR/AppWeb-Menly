# Generated manually to preserve existing PedidoWhatsApp rows.

import django.db.models.deletion
from django.db import migrations, models


def asignar_numeros_pedidos_whatsapp(apps, schema_editor):
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")
    Restaurante = apps.get_model("menu", "Restaurante")

    for restaurante in Restaurante.objects.all().order_by("id"):
        pedidos = PedidoWhatsApp.objects.filter(
            restaurante=restaurante
        ).order_by("fecha_creacion", "id")

        for numero, pedido in enumerate(pedidos, start=1):
            pedido.numero_pedido = numero
            pedido.save(update_fields=["numero_pedido"])


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0029_pedidowhatsapp"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedidowhatsapp",
            name="numero_pedido",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("confirmado", "Confirmado"),
                    ("en_preparacion", "En preparaci\u00f3n"),
                    ("listo", "Listo"),
                    ("entregado", "Entregado"),
                    ("cancelado", "Cancelado"),
                    ("completado", "Completado"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            asignar_numeros_pedidos_whatsapp,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="numero_pedido",
            field=models.PositiveIntegerField(),
        ),
        migrations.AddConstraint(
            model_name="pedidowhatsapp",
            constraint=models.UniqueConstraint(
                fields=("restaurante", "numero_pedido"),
                name="unique_pedido_whatsapp_numero_por_rest",
            ),
        ),
        migrations.CreateModel(
            name="PedidoEspecial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_pedido", models.PositiveIntegerField()),
                ("nombre_cliente", models.CharField(max_length=120)),
                ("telefono_cliente", models.CharField(max_length=30)),
                ("email_cliente", models.EmailField(blank=True, max_length=254)),
                ("descripcion_original", models.TextField(blank=True)),
                ("items", models.JSONField()),
                ("total", models.DecimalField(decimal_places=0, max_digits=10)),
                ("fecha_entrega", models.DateField()),
                ("estado", models.CharField(
                    choices=[
                        ("pendiente", "Pendiente"),
                        ("confirmado", "Confirmado"),
                        ("en_preparacion", "En preparaci\u00f3n"),
                        ("listo", "Listo"),
                        ("entregado", "Entregado"),
                        ("cancelado", "Cancelado"),
                    ],
                    default="pendiente",
                    max_length=20,
                )),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
                ("restaurante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pedidos_especiales", to="menu.restaurante")),
                ("solicitud_especial", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pedidos_especiales", to="menu.solicitudespecial")),
            ],
            options={
                "ordering": ["-fecha_creacion"],
                "indexes": [
                    models.Index(fields=["restaurante", "-fecha_creacion"], name="pedesp_rest_fecha_idx"),
                    models.Index(fields=["restaurante", "estado"], name="pedesp_rest_estado_idx"),
                    models.Index(fields=["restaurante", "fecha_entrega"], name="pedesp_rest_entrega_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("restaurante", "numero_pedido"), name="unique_pedido_especial_numero_por_rest"),
                ],
            },
        ),
    ]
