from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0023_alter_restaurante_fecha_creacion"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="restaurante",
            index=models.Index(fields=["slug", "activo"], name="rest_slug_activo_idx"),
        ),
        migrations.AddIndex(
            model_name="restaurante",
            index=models.Index(fields=["fecha_creacion"], name="rest_fecha_creacion_idx"),
        ),
        migrations.AddIndex(
            model_name="imagenrestaurante",
            index=models.Index(fields=["restaurante", "activa", "orden"], name="img_rest_activa_orden_idx"),
        ),
        migrations.AddIndex(
            model_name="categoria",
            index=models.Index(fields=["restaurante", "activa", "orden"], name="cat_rest_activa_orden_idx"),
        ),
        migrations.AddIndex(
            model_name="producto",
            index=models.Index(fields=["restaurante", "categoria", "disponible", "orden"], name="prod_menu_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="producto",
            index=models.Index(fields=["restaurante", "clicks"], name="prod_clicks_idx"),
        ),
        migrations.AddIndex(
            model_name="bitacoraproducto",
            index=models.Index(fields=["restaurante", "-fecha"], name="bit_rest_fecha_idx"),
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(fields=["restaurante", "-fecha_creacion"], name="res_rest_creacion_idx"),
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(fields=["restaurante", "fecha", "hora", "estado"], name="res_rest_fecha_hora_idx"),
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(fields=["restaurante", "estado"], name="res_rest_estado_idx"),
        ),
    ]
