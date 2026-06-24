# Generated manually for public WhatsApp order tracking.

import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def generar_token_unico(PedidoWhatsApp):
    for _ in range(12):
        token = secrets.token_urlsafe(12)
        if not PedidoWhatsApp.objects.filter(tracking_token=token).exists():
            return token
    raise RuntimeError("No se pudo generar un tracking_token unico.")


def poblar_tracking_y_estados(apps, schema_editor):
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")

    for pedido in PedidoWhatsApp.objects.all().order_by("id"):
        cambios = []
        if not pedido.tracking_token:
            pedido.tracking_token = generar_token_unico(PedidoWhatsApp)
            cambios.append("tracking_token")
        if not pedido.fecha_actualizacion_estado:
            pedido.fecha_actualizacion_estado = pedido.fecha_creacion or timezone.now()
            cambios.append("fecha_actualizacion_estado")
        if pedido.estado == "pendiente":
            pedido.estado = "pendiente_confirmacion"
            cambios.append("estado")
        if cambios:
            pedido.save(update_fields=cambios)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0033_reportemetrica"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pedidowhatsapp",
            name="tracking_token",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=32, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="pedidowhatsapp",
            name="fecha_actualizacion_estado",
            field=models.DateTimeField(default=timezone.now),
        ),
        migrations.RunPython(
            poblar_tracking_y_estados,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="tracking_token",
            field=models.CharField(db_index=True, editable=False, max_length=32, unique=True),
        ),
        migrations.AlterField(
            model_name="pedidowhatsapp",
            name="estado",
            field=models.CharField(
                choices=[
                    ("recibido", "Pedido recibido"),
                    ("pendiente_confirmacion", "Pendiente de confirmacion"),
                    ("confirmado", "Confirmado"),
                    ("en_preparacion", "En preparación"),
                    ("listo", "Listo"),
                    ("entregado", "Entregado"),
                    ("cancelado", "Cancelado"),
                ],
                default="recibido",
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="HistorialEstadoPedidoWhatsApp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado_anterior", models.CharField(blank=True, max_length=30)),
                ("estado_nuevo", models.CharField(max_length=30)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("observacion", models.TextField(blank=True)),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial_estados", to="menu.pedidowhatsapp")),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="historial_estados_pedidos_whatsapp", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-fecha"],
                "indexes": [
                    models.Index(fields=["pedido", "-fecha"], name="histpedw_pedido_fecha_idx"),
                ],
            },
        ),
    ]
