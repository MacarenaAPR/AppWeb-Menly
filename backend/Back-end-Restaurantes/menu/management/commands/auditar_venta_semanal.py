from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from menu.models import Restaurante
from menu.services.metricas.pedidos import (
    fecha_hoy,
    inicio_semana,
    pedidos_especiales_finalizados,
    pedidos_manuales_finalizados,
    pedidos_whatsapp_finalizados,
)


class Command(BaseCommand):
    help = "Desglosa, sin modificar datos, los pedidos que componen la venta semanal."

    def add_arguments(self, parser):
        parser.add_argument("--restaurante", required=True, help="Slug del restaurante.")
        parser.add_argument("--fecha", help="Fecha local AAAA-MM-DD; por defecto hoy.")

    def handle(self, *args, **options):
        try:
            hoy = (
                datetime.strptime(options["fecha"], "%Y-%m-%d").date()
                if options.get("fecha")
                else fecha_hoy()
            )
        except ValueError as exc:
            raise CommandError("--fecha debe usar el formato AAAA-MM-DD.") from exc

        restaurante = Restaurante.objects.filter(slug=options["restaurante"]).first()
        if not restaurante:
            raise CommandError("No existe un restaurante con ese slug.")

        rangos = (
            ("ventana_7_dias_anterior", hoy - timedelta(days=6), hoy),
            ("semana_calendario", inicio_semana(hoy), hoy),
        )
        for nombre_rango, desde, hasta in rangos:
            canales = [
                ("whatsapp", pedidos_whatsapp_finalizados(restaurante, desde, hasta)),
                ("manual", pedidos_manuales_finalizados(restaurante, desde, hasta)),
            ]
            if restaurante.solicitudes_especiales_activas:
                canales.append(
                    ("especial", pedidos_especiales_finalizados(restaurante, desde, hasta))
                )

            total = cantidad = 0
            self.stdout.write(f"RANGO,{nombre_rango},{desde},{hasta}")
            self.stdout.write("canal,id,numero,fecha_local,estado,total")
            for canal, queryset in canales:
                for pedido in queryset.order_by("fecha_creacion", "id"):
                    cantidad += 1
                    total += int(pedido.total)
                    fecha_local = timezone.localtime(pedido.fecha_creacion).isoformat()
                    self.stdout.write(
                        f"{canal},{pedido.id},{pedido.numero_pedido},"
                        f"{fecha_local},{pedido.estado},{int(pedido.total)}"
                    )
            self.stdout.write(f"TOTAL,{nombre_rango},pedidos={cantidad},monto={total}")
