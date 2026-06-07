import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import HorarioAtencion, Notificacion


logger = logging.getLogger(__name__)


RESERVED_SUBDOMAINS = {"www", "api", "admin", "app"}
DEFAULT_TENANT_BASE_DOMAINS = (
    "menly.cl",
    "menly.localhost",
    "localhost",
    "lvh.me",
    "nip.io",
)


def get_slug_from_host(host, base_domains=None):
    hostname = str(host or "").split(":")[0].lower()

    if hostname in {"localhost", "127.0.0.1"}:
        return None

    tenant_base_domains = base_domains or getattr(
        settings,
        "TENANT_BASE_DOMAINS",
        DEFAULT_TENANT_BASE_DOMAINS,
    )

    if hostname in tenant_base_domains:
        return None

    for base_domain in tenant_base_domains:
        suffix = f".{base_domain}"

        if not hostname.endswith(suffix):
            continue

        slug = hostname[: -len(suffix)].split(".")[0]
        if slug and slug not in RESERVED_SUBDOMAINS:
            return slug

    return None


def validar_horario_reserva(restaurante, fecha, hora, permitir_sin_horario=False):
    dia_semana = fecha.isoweekday()

    horarios = HorarioAtencion.objects.filter(
        restaurante=restaurante,
        dia=dia_semana,
        activo=True
    )

    if not horarios.exists():
        return permitir_sin_horario

    for horario in horarios:
        if horario.cerrado:
            continue

        if not horario.hora_apertura or not horario.hora_cierre:
            continue

        apertura = horario.hora_apertura
        cierre = horario.hora_cierre

        if apertura <= cierre:
            if apertura <= hora <= cierre:
                return True
        else:
            if hora >= apertura or hora <= cierre:
                return True

    return False

def notificar_nueva_reserva(reserva):
    restaurante = reserva.restaurante

    if not restaurante.notificar_reservas:
        return None

    email_destino = (restaurante.email_notificacion or "").strip()

    if not email_destino:
        logger.info(
            "Reserva %s sin notificacion: restaurante %s no tiene email_notificacion.",
            reserva.id,
            restaurante.id,
        )
        return None

    asunto = f"Nueva reserva pendiente - {restaurante.nombre_empresa}"
    mensaje = (
        "Se recibio una nueva solicitud de reserva.\n\n"
        f"Cliente: {reserva.nombre_cliente}\n"
        f"Telefono: {reserva.telefono}\n"
        f"Email: {reserva.email or 'No informado'}\n"
        f"Fecha: {reserva.fecha.strftime('%d-%m-%Y')}\n"
        f"Hora: {reserva.hora.strftime('%H:%M')}\n"
        f"Personas: {reserva.cantidad_personas}\n"
        f"Mensaje: {reserva.mensaje or 'Sin mensaje'}\n\n"
        f"Estado: {reserva.estado}\n"
    )

    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False,
            # Si usas SMTP real y tu version de Django lo permite, configura timeout en el backend/email connection.
        )
    except Exception:
        logger.exception(
            "Error enviando notificacion de reserva %s al restaurante %s.",
            reserva.id,
            restaurante.id,
        )

    return None


def crear_notificacion_reserva(reserva):
    return Notificacion.objects.create(
        restaurante=reserva.restaurante,
        tipo=Notificacion.TIPO_RESERVA,
        titulo="Nueva reserva recibida",
        mensaje=(
            f"{reserva.nombre_cliente} solicito una reserva para "
            f"{reserva.cantidad_personas} persona(s) el "
            f"{reserva.fecha.strftime('%d-%m-%Y')} a las {reserva.hora.strftime('%H:%M')}."
        ),
        referencia_id=reserva.id,
        referencia_modelo=Notificacion.MODELO_RESERVA,
    )


def notificar_nueva_solicitud_especial(solicitud):
    restaurante = solicitud.restaurante

    if not restaurante.notificar_reservas:
        return None

    email_destino = (restaurante.email_notificacion or "").strip()

    if not email_destino:
        logger.info(
            "Solicitud especial %s sin notificacion: restaurante %s no tiene email_notificacion.",
            solicitud.id,
            restaurante.id,
        )
        return None

    asunto = f"Nueva solicitud especial - {restaurante.nombre_empresa}"
    mensaje = (
        "Se recibio una nueva solicitud especial.\n\n"
        f"Cliente: {solicitud.nombre} {solicitud.apellido}\n"
        f"Telefono: {solicitud.telefono_contacto}\n"
        f"Email: {solicitud.email_contacto}\n"
        f"Fecha del evento: {solicitud.fecha_evento.strftime('%d-%m-%Y')}\n"
        f"Descripcion: {solicitud.descripcion_solicitud}\n\n"
        f"Estado: {solicitud.estado}\n"
    )

    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Error enviando notificacion de solicitud especial %s al restaurante %s.",
            solicitud.id,
            restaurante.id,
        )

    return None


def crear_notificacion_solicitud_especial(solicitud):
    return Notificacion.objects.create(
        restaurante=solicitud.restaurante,
        tipo=Notificacion.TIPO_SOLICITUD_ESPECIAL,
        titulo="Nueva solicitud especial recibida",
        mensaje=(
            f"{solicitud.nombre} {solicitud.apellido} envio una solicitud especial "
            f"para el {solicitud.fecha_evento.strftime('%d-%m-%Y')}."
        ),
        referencia_id=solicitud.id,
        referencia_modelo=Notificacion.MODELO_SOLICITUD_ESPECIAL,
    )
