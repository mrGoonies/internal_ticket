from datetime import timedelta

from .models import Prioridad, Ticket

CATEGORIAS_CRITICAS = {'Red y conectividad', 'Accesos y contrasenas'}


def inferir_prioridad(tipo_solicitud, categoria):
    """Prioridad por defecto segun tipo y categoria; el agente la reajusta al triar."""
    if tipo_solicitud == Ticket.TipoSolicitud.INCIDENCIA:
        nombre = 'Alta' if categoria.nombre in CATEGORIAS_CRITICAS else 'Media'
    else:
        nombre = 'Baja'

    return (
        Prioridad.objects.filter(nombre=nombre).first()
        or Prioridad.objects.order_by('orden').first()
    )


def tiempo_habil_resolucion(ticket):
    """Tiempo entre creacion y resolucion, descontando el tiempo en espera del usuario.

    Recorre el historial del ticket sumando la duracion de cada tramo excepto
    los que estuvieron en ESPERANDO_USUARIO, para que el tiempo de resolucion
    no penalice al agente por algo fuera de su control.
    """
    if ticket.fecha_resolucion is None:
        return None

    eventos = list(ticket.historial_estados.order_by('fecha_cambio'))
    if not eventos:
        return ticket.fecha_resolucion - ticket.fecha_creacion

    total = timedelta()
    cursor = ticket.fecha_creacion
    estado = eventos[0].estado_nuevo

    for evento in eventos[1:]:
        limite = min(evento.fecha_cambio, ticket.fecha_resolucion)
        if limite > cursor and estado != Ticket.Estado.ESPERANDO_USUARIO:
            total += limite - cursor
        cursor = evento.fecha_cambio
        estado = evento.estado_nuevo
        if cursor >= ticket.fecha_resolucion:
            break
    else:
        if cursor < ticket.fecha_resolucion and estado != Ticket.Estado.ESPERANDO_USUARIO:
            total += ticket.fecha_resolucion - cursor

    return total


def cumple_sla(ticket, tiempo_habil):
    if tiempo_habil is None:
        return None
    return tiempo_habil <= timedelta(hours=ticket.prioridad.sla_resolucion_horas)
