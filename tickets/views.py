import calendar
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import emails
from .forms import EncuestaCSATForm, TicketGestionForm, TicketPublicoForm
from .models import Adjunto, AreaSolicitante, EncuestaCSAT, HistorialEstado, Prioridad, Ticket
from .services import cumple_sla, inferir_prioridad, tiempo_habil_resolucion

SESSION_KEY_ULTIMO_TICKET = 'ultimo_ticket_id'

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


def crear_ticket(request):
    if request.method == 'POST':
        form = TicketPublicoForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.canal_origen = Ticket.CanalOrigen.WEB
            ticket.prioridad = inferir_prioridad(ticket.tipo_solicitud, ticket.categoria)
            ticket.save()

            HistorialEstado.objects.create(
                ticket=ticket,
                estado_anterior=None,
                estado_nuevo=Ticket.Estado.NUEVO,
                comentario='Ticket creado por el solicitante via formulario web.',
            )

            for archivo in request.FILES.getlist('adjuntos'):
                Adjunto.objects.create(ticket=ticket, archivo=archivo)

            emails.notificar_ticket_creado(ticket)

            # Se guarda en la sesion (no en la URL) para que el codigo del ticket,
            # que es correlativo y adivinable, no sirva para ver tickets ajenos.
            request.session[SESSION_KEY_ULTIMO_TICKET] = ticket.pk
            return redirect('tickets:ticket_creado')
    else:
        form = TicketPublicoForm()

    return render(request, 'tickets/crear_ticket.html', {'form': form})


def ticket_creado(request):
    ticket_id = request.session.get(SESSION_KEY_ULTIMO_TICKET)
    if not ticket_id:
        return redirect('tickets:crear_ticket')
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    return render(request, 'tickets/ticket_creado.html', {'ticket': ticket})


@login_required
def lista_tickets(request):
    agente = getattr(request.user, 'agente', None)
    if agente is None:
        return render(request, 'tickets/sin_perfil_agente.html')

    tickets = Ticket.objects.select_related('categoria', 'area_solicitante', 'prioridad', 'agente_asignado')

    estado = request.GET.get('estado')
    tipo_solicitud = request.GET.get('tipo_solicitud')
    prioridad = request.GET.get('prioridad')
    q = request.GET.get('q')

    if estado:
        tickets = tickets.filter(estado=estado)
    if tipo_solicitud:
        tickets = tickets.filter(tipo_solicitud=tipo_solicitud)
    if prioridad:
        tickets = tickets.filter(prioridad_id=prioridad)
    if q:
        tickets = tickets.filter(models.Q(codigo__icontains=q) | models.Q(titulo__icontains=q))

    return render(
        request,
        'tickets/lista_tickets.html',
        {
            'agente': agente,
            'tickets': tickets,
            'estados': Ticket.Estado.choices,
            'tipos': Ticket.TipoSolicitud.choices,
            'prioridades': Prioridad.objects.order_by('orden'),
            'filtros': {
                'estado': estado or '',
                'tipo_solicitud': tipo_solicitud or '',
                'prioridad': prioridad or '',
                'q': q or '',
            },
        },
    )


@login_required
def detalle_ticket(request, codigo):
    agente = getattr(request.user, 'agente', None)
    if agente is None:
        return render(request, 'tickets/sin_perfil_agente.html')

    ticket = get_object_or_404(Ticket, codigo=codigo)

    if request.method == 'POST':
        # Se captura antes de instanciar el form: ModelForm.is_valid() ya
        # escribe los datos limpios sobre esta misma instancia (_post_clean),
        # asi que leer ticket.estado despues del is_valid() daria el nuevo
        # valor, no el anterior.
        estado_anterior = ticket.estado
        form = TicketGestionForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save(commit=False)
            estado_nuevo = ticket.estado
            ahora = timezone.now()

            if estado_nuevo != estado_anterior:
                HistorialEstado.objects.create(
                    ticket=ticket,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_nuevo,
                    agente=agente,
                    comentario=form.cleaned_data.get('comentario', ''),
                )
                if estado_anterior == Ticket.Estado.NUEVO and ticket.fecha_primera_respuesta is None:
                    ticket.fecha_primera_respuesta = ahora
                if estado_nuevo == Ticket.Estado.RESUELTO and ticket.fecha_resolucion is None:
                    ticket.fecha_resolucion = ahora
                if estado_nuevo == Ticket.Estado.CERRADO:
                    if ticket.fecha_cierre is None:
                        ticket.fecha_cierre = ahora
                    encuesta, _ = EncuestaCSAT.objects.get_or_create(ticket=ticket)

            ticket.save()

            if estado_nuevo != estado_anterior:
                emails.notificar_cambio_estado(ticket)
                if estado_nuevo == Ticket.Estado.CERRADO:
                    encuesta.enviado_at = ahora
                    encuesta.save(update_fields=['enviado_at'])
                    emails.notificar_encuesta_csat(encuesta)

            return redirect('tickets:detalle_ticket', codigo=ticket.codigo)
    else:
        form = TicketGestionForm(instance=ticket)

    return render(
        request,
        'tickets/detalle_ticket.html',
        {
            'agente': agente,
            'ticket': ticket,
            'form': form,
            'historial': ticket.historial_estados.select_related('agente__usuario'),
            'adjuntos': ticket.adjuntos.all(),
        },
    )


def responder_encuesta(request, token):
    encuesta = get_object_or_404(EncuestaCSAT, token=token)

    if encuesta.respondido_at:
        return render(request, 'tickets/encuesta_gracias.html', {'encuesta': encuesta})

    if request.method == 'POST':
        form = EncuestaCSATForm(request.POST, instance=encuesta)
        if form.is_valid():
            encuesta = form.save(commit=False)
            encuesta.respondido_at = timezone.now()
            encuesta.save()
            return redirect('tickets:responder_encuesta', token=token)
    else:
        form = EncuestaCSATForm(instance=encuesta)

    return render(
        request,
        'tickets/encuesta.html',
        {'form': form, 'encuesta': encuesta},
    )


@login_required
def panel_kpi(request):
    agente = getattr(request.user, 'agente', None)
    if agente is None:
        return render(request, 'tickets/sin_perfil_agente.html')

    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in request.GET.get('mes', '').split('-'))
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
    ).aggregate(promedio=models.Avg('calificacion'), total=models.Count('id'))

    por_area_qs = (
        resueltos.values('area_solicitante__nombre')
        .annotate(total=models.Count('id'))
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
        .annotate(total=models.Count('id'))
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

    return render(
        request,
        'tickets/panel_kpi.html',
        {
            'agente': agente,
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
        },
    )
