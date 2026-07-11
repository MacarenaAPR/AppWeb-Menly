import secrets

from django.db import migrations, models


def generar_token_unico(PedidoManual, PedidoWhatsApp):
    for _ in range(8):
        token = secrets.token_urlsafe(12)
        if (
            not PedidoManual.objects.filter(tracking_token=token).exists()
            and not PedidoWhatsApp.objects.filter(tracking_token=token).exists()
        ):
            return token
    raise RuntimeError("No se pudo generar un tracking_token unico.")


def poblar_tracking_tokens(apps, schema_editor):
    PedidoManual = apps.get_model("menu", "PedidoManual")
    PedidoWhatsApp = apps.get_model("menu", "PedidoWhatsApp")
    for pedido in PedidoManual.objects.filter(tracking_token__isnull=True).order_by("id"):
        pedido.tracking_token = generar_token_unico(PedidoManual, PedidoWhatsApp)
        pedido.save(update_fields=["tracking_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0039_pedidomanual_pedidomanualitem_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedidomanual",
            name="tracking_token",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=32, null=True, unique=True),
        ),
        migrations.RunPython(poblar_tracking_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pedidomanual",
            name="tracking_token",
            field=models.CharField(db_index=True, editable=False, max_length=32, unique=True),
        ),
    ]
