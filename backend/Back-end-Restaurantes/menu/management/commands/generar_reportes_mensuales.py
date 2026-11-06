from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from menu.models import EjecucionReportesMensuales, Restaurante
from menu.services.reportes_mensuales import (
    generar_reportes_pendientes,
    guardar_reporte_mensual,
)


def mes_anterior(fecha):
    return (fecha.year - 1, 12) if fecha.month == 1 else (fecha.year, fecha.month - 1)


class Command(BaseCommand):
    help = "Genera reportes mensuales persistentes e idempotentes por restaurante."

    def add_arguments(self, parser):
        parser.add_argument("--periodo", help="Mes cerrado en formato AAAA-MM; por defecto, el anterior.")
        parser.add_argument("--include-inactive", action="store_true", help="Incluye restaurantes inactivos.")
        parser.add_argument("--regenerate", action="store_true", help="Regenera snapshots existentes de forma explícita.")
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Genera todos los meses cerrados faltantes desde el inicio de cada restaurante.",
        )
        parser.add_argument(
            "--scheduled",
            action="store_true",
            help=(
                "Modo para Cron: recupera todos los cierres faltantes según la fecha "
                "actual de America/Santiago y es seguro ante reintentos diarios."
            ),
        )

    def _cerrar_ejecucion(self, ejecucion, resultado, estado=None):
        errores = resultado.get("errores", [])
        ejecucion.fecha_fin = timezone.now()
        ejecucion.estado = estado or (
            EjecucionReportesMensuales.ESTADO_PARCIAL
            if errores
            else EjecucionReportesMensuales.ESTADO_EXITOSO
        )
        ejecucion.reportes_generados = resultado.get("generados", 0)
        ejecucion.reportes_existentes = resultado.get("existentes", 0)
        ejecucion.cantidad_errores = len(errores)
        ejecucion.detalle = {"errores": errores}
        ejecucion.save(update_fields=[
            "fecha_fin",
            "estado",
            "reportes_generados",
            "reportes_existentes",
            "cantidad_errores",
            "detalle",
        ])

    def handle(self, *args, **options):
        periodo = options.get("periodo")
        modos_especiales = int(options["backfill"]) + int(options["scheduled"])
        if modos_especiales > 1 or (periodo and modos_especiales):
            raise CommandError(
                "--periodo, --backfill y --scheduled son modos excluyentes."
            )
        if options["scheduled"] and options["regenerate"]:
            raise CommandError("--scheduled nunca permite --regenerate.")

        restaurantes = Restaurante.objects.order_by("id")
        if not options["include_inactive"]:
            restaurantes = restaurantes.filter(activo=True)

        if options["backfill"] or options["scheduled"]:
            hoy_chile = timezone.localdate()
            anio_cerrado, mes_cerrado = mes_anterior(hoy_chile)
            modo = (
                EjecucionReportesMensuales.MODO_PROGRAMADO
                if options["scheduled"]
                else EjecucionReportesMensuales.MODO_BACKFILL
            )
            ejecucion = EjecucionReportesMensuales.objects.create(
                modo=modo,
                periodo=f"{anio_cerrado:04d}-{mes_cerrado:02d}",
                incluye_inactivos=options["include_inactive"],
                restaurantes_procesados=restaurantes.count(),
            )
            try:
                resultado = generar_reportes_pendientes(restaurantes=restaurantes)
            except Exception as exc:
                resultado = {
                    "generados": 0,
                    "existentes": 0,
                    "errores": [{
                        "restaurante_id": None,
                        "periodo": ejecucion.periodo,
                        "error": str(exc),
                    }],
                }
                self._cerrar_ejecucion(
                    ejecucion,
                    resultado,
                    estado=EjecucionReportesMensuales.ESTADO_FALLIDO,
                )
                raise
            self._cerrar_ejecucion(ejecucion, resultado)
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Cierre programado y recuperación: "
                        if options["scheduled"]
                        else "Recuperación histórica: "
                    )
                    + f"generados={resultado['generados']}, "
                    f"existentes={resultado['existentes']}, "
                    f"errores={len(resultado['errores'])}."
                )
            )
            for error in resultado["errores"]:
                self.stderr.write(self.style.ERROR(
                    f"Restaurante {error['restaurante_id']} periodo "
                    f"{error['periodo']}: {error['error']}"
                ))
            if resultado["errores"]:
                raise CommandError("La recuperación histórica terminó con errores parciales.")
            return

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

        ejecucion = EjecucionReportesMensuales.objects.create(
            modo=EjecucionReportesMensuales.MODO_PERIODO,
            periodo=f"{anio:04d}-{mes:02d}",
            incluye_inactivos=options["include_inactive"],
            restaurantes_procesados=restaurantes.count(),
        )
        creados = omitidos = 0
        errores = []
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
                errores.append({
                    "restaurante_id": restaurante.id,
                    "periodo": f"{anio:04d}-{mes:02d}",
                    "error": str(exc),
                })
                self.stderr.write(
                    self.style.ERROR(f"Restaurante {restaurante.id}: {exc}")
                )

        resultado = {
            "generados": creados,
            "existentes": omitidos,
            "errores": errores,
        }
        self._cerrar_ejecucion(ejecucion, resultado)

        self.stdout.write(
            self.style.SUCCESS(
                f"Periodo {anio:04d}-{mes:02d}: generados/regenerados={creados}, "
                f"omitidos={omitidos}, errores={len(errores)}."
            )
        )
        if errores:
            raise CommandError(
                f"La generación terminó con errores en {len(errores)} restaurante(s)."
            )
