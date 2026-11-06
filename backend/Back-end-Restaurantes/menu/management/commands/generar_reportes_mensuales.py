from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from menu.models import Restaurante
from menu.services.reportes_mensuales import guardar_reporte_mensual


def mes_anterior(fecha):
    return (fecha.year - 1, 12) if fecha.month == 1 else (fecha.year, fecha.month - 1)


class Command(BaseCommand):
    help = "Genera reportes mensuales persistentes e idempotentes por restaurante."

    def add_arguments(self, parser):
        parser.add_argument("--periodo", help="Mes cerrado en formato AAAA-MM; por defecto, el anterior.")
        parser.add_argument("--include-inactive", action="store_true", help="Incluye restaurantes inactivos.")
        parser.add_argument("--regenerate", action="store_true", help="Regenera snapshots existentes de forma explícita.")

    def handle(self, *args, **options):
        periodo = options.get("periodo")
        if periodo:
            try:
                anio, mes = map(int, periodo.split("-"))
                if periodo != f"{anio:04d}-{mes:02d}" or not 1 <= mes <= 12:
                    raise ValueError
            except (TypeError, ValueError):
                raise CommandError("--periodo debe usar el formato AAAA-MM.")
        else:
            anio, mes = mes_anterior(timezone.localdate())

        inicio_mes_actual = date(timezone.localdate().year, timezone.localdate().month, 1)
        if date(anio, mes, 1) >= inicio_mes_actual:
            raise CommandError("Solo se pueden generar reportes de meses ya cerrados.")

        restaurantes = Restaurante.objects.order_by("id")
        if not options["include_inactive"]:
            restaurantes = restaurantes.filter(activo=True)

        creados = omitidos = errores = 0
        for restaurante in restaurantes.iterator():
            try:
                _reporte, escrito = guardar_reporte_mensual(
                    restaurante, anio, mes, regenerar=options["regenerate"]
                )
                if escrito:
                    creados += 1
                else:
                    omitidos += 1
            except Exception as exc:
                errores += 1
                self.stderr.write(
                    self.style.ERROR(f"Restaurante {restaurante.id}: {exc}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Periodo {anio:04d}-{mes:02d}: generados/regenerados={creados}, "
                f"omitidos={omitidos}, errores={errores}."
            )
        )
        if errores:
            raise CommandError(
                f"La generación terminó con errores en {errores} restaurante(s)."
            )
