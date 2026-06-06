from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0026_solicitudespecial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitudespecial",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("en_revision", "En revisión"),
                    ("aceptada", "Aceptada"),
                    ("rechazada", "Rechazada"),
                    ("completada", "Completada"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
    ]
