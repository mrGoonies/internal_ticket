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
