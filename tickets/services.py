import calendar
from datetime import datetime, timedelta

from django.db import models as dj_models
from django.utils import timezone

from .models import AreaSolicitante, EncuestaCSAT, Prioridad, Ticket

CATEGORIAS_CRITICAS = {'Red y conectividad', 'Accesos y contrasenas'}

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

# Paleta categorica validada (ver skill dataviz) contra la superficie de las
# tarjetas (#f2eee3). Se asigna por identidad del area (orden alfabetico fijo),
# no por su ranking del mes, para que un area no cambie de color solo porque
# subio o bajo en el conteo.
AREA_COLORES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']

# Prioridad es ordinal (severidad), no identidad: se colorea como escala de
# estado fija (mismos tonos que ya usan los badges del panel), no con la
# paleta categorica de arriba.
COLOR_PRIORIDAD = {
    'Critica': '#8f2d23',
    'Alta': '#b23a2e',
    'Media': '#c98500',
    'Baja': '#3f6b71',
}


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


def calcular_kpis_mes(mes_param):
    """Agrega los KPI de tickets resueltos en el mes dado (formato 'YYYY-MM').

    Mes invalido o ausente cae al mes actual. Devuelve un dict listo para
    pasar como contexto tanto al dashboard web como al reporte PDF.
    """
    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in (mes_param or '').split('-'))
        datetime(anio, mes, 1)
    except (ValueError, TypeError):
        anio, mes = hoy.year, hoy.month

    inicio = timezone.make_aware(datetime(anio, mes, 1))
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fin = timezone.make_aware(datetime(anio, mes, ultimo_dia, 23, 59, 59))

    anio_prev, mes_prev = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    anio_sig, mes_sig = (anio + 1, 1) if mes == 12 else (anio, mes + 1)

    resueltos = (
        Ticket.objects.filter(fecha_resolucion__gte=inicio, fecha_resolucion__lte=fin)
        .select_related('area_solicitante', 'prioridad', 'categoria')
        .order_by('fecha_resolucion')
    )

    detalle = []
    tiempos_horas = []
    dentro_sla = 0
    for ticket in resueltos:
        th = tiempo_habil_resolucion(ticket)
        ok_sla = cumple_sla(ticket, th)
        if th is not None:
            tiempos_horas.append(th.total_seconds() / 3600)
        if ok_sla:
            dentro_sla += 1
        detalle.append({'ticket': ticket, 'horas': th.total_seconds() / 3600 if th else None, 'cumple_sla': ok_sla})

    total_resueltos = len(detalle)
    promedio_horas = sum(tiempos_horas) / len(tiempos_horas) if tiempos_horas else None
    pct_sla = (dentro_sla / total_resueltos * 100) if total_resueltos else None

    csat = EncuestaCSAT.objects.filter(
        ticket__in=resueltos, calificacion__isnull=False
    ).aggregate(promedio=dj_models.Avg('calificacion'), total=dj_models.Count('id'))

    por_area_qs = (
        resueltos.values('area_solicitante__nombre')
        .annotate(total=dj_models.Count('id'))
        .order_by('-total')
    )
    max_area = max((r['total'] for r in por_area_qs), default=0)
    nombres_area = list(AreaSolicitante.objects.order_by('nombre').values_list('nombre', flat=True))
    color_por_area = {nombre: AREA_COLORES[i % len(AREA_COLORES)] for i, nombre in enumerate(nombres_area)}
    por_area = [
        {
            'nombre': r['area_solicitante__nombre'],
            'total': r['total'],
            'pct': round(r['total'] / max_area * 100),
            'color': color_por_area.get(r['area_solicitante__nombre'], '#8b8577'),
        }
        for r in por_area_qs
    ]

    por_prioridad_qs = (
        resueltos.values('prioridad__nombre', 'prioridad__orden')
        .annotate(total=dj_models.Count('id'))
        .order_by('prioridad__orden')
    )
    max_prioridad = max((r['total'] for r in por_prioridad_qs), default=0)
    por_prioridad = [
        {
            'nombre': r['prioridad__nombre'],
            'total': r['total'],
            'pct': round(r['total'] / max_prioridad * 100),
            'color': COLOR_PRIORIDAD.get(r['prioridad__nombre'], '#8b8577'),
        }
        for r in por_prioridad_qs
    ]

    return {
        'anio': anio,
        'mes': mes,
        'nombre_mes': MESES_ES[mes],
        'mes_anterior': f'{anio_prev}-{mes_prev:02d}',
        'mes_siguiente': f'{anio_sig}-{mes_sig:02d}',
        'es_mes_actual': (anio, mes) == (hoy.year, hoy.month),
        'total_resueltos': total_resueltos,
        'promedio_horas': promedio_horas,
        'pct_sla': pct_sla,
        'dentro_sla': dentro_sla,
        'csat_promedio': csat['promedio'],
        'csat_total': csat['total'],
        'por_area': por_area,
        'por_prioridad': por_prioridad,
        'total_incidencias': resueltos.filter(tipo_solicitud=Ticket.TipoSolicitud.INCIDENCIA).count(),
        'total_requerimientos': resueltos.filter(tipo_solicitud=Ticket.TipoSolicitud.REQUERIMIENTO).count(),
        'detalle': detalle,
    }
