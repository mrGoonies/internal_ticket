from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from . import emails
from .forms import EncuestaCSATForm, TicketGestionForm, TicketPublicoForm
from .models import Adjunto, EncuestaCSAT, HistorialEstado, Prioridad, Ticket
from .services import calcular_kpis_mes, inferir_prioridad

SESSION_KEY_ULTIMO_TICKET = 'ultimo_ticket_id'

# Grupos mutuamente excluyentes (cubren todos los estados sin superposicion),
# para poder mostrarlos como una barra de distribucion proporcional.
GRUPOS_ESTADO = {
    'abiertos': [Ticket.Estado.NUEVO],
    'proceso': [
        Ticket.Estado.ASIGNADO,
        Ticket.Estado.EN_PROGRESO,
        Ticket.Estado.ESPERANDO_USUARIO,
    ],
    'cerrados': [Ticket.Estado.RESUELTO, Ticket.Estado.CERRADO],
}


def crear_ticket(request):
    if request.method == 'POST':
        form = TicketPublicoForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
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
    vista = request.GET.get('vista')
    tipo_solicitud = request.GET.get('tipo_solicitud')
    prioridad = request.GET.get('prioridad')
    q = request.GET.get('q')

    if tipo_solicitud:
        tickets = tickets.filter(tipo_solicitud=tipo_solicitud)
    if prioridad:
        tickets = tickets.filter(prioridad_id=prioridad)
    if q:
        tickets = tickets.filter(models.Q(codigo__icontains=q) | models.Q(titulo__icontains=q))

    conteos = {
        'todos': tickets.count(),
        'abiertos': tickets.filter(estado__in=GRUPOS_ESTADO['abiertos']).count(),
        'proceso': tickets.filter(estado__in=GRUPOS_ESTADO['proceso']).count(),
        'cerrados': tickets.filter(estado__in=GRUPOS_ESTADO['cerrados']).count(),
    }

    if estado:
        tickets = tickets.filter(estado=estado)
    elif vista in GRUPOS_ESTADO:
        tickets = tickets.filter(estado__in=GRUPOS_ESTADO[vista])

    return render(
        request,
        'tickets/lista_tickets.html',
        {
            'agente': agente,
            'tickets': tickets,
            'estados': Ticket.Estado.choices,
            'tipos': Ticket.TipoSolicitud.choices,
            'prioridades': Prioridad.objects.order_by('orden'),
            'conteos': conteos,
            'filtros': {
                'estado': estado or '',
                'vista': vista or '',
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

    contexto = calcular_kpis_mes(request.GET.get('mes'))
    contexto['agente'] = agente
    return render(request, 'tickets/panel_kpi.html', contexto)


@login_required
def panel_kpi_pdf(request):
    agente = getattr(request.user, 'agente', None)
    if agente is None:
        return render(request, 'tickets/sin_perfil_agente.html')

    contexto = calcular_kpis_mes(request.GET.get('mes'))
    contexto['agente'] = agente
    contexto['generado_at'] = timezone.now()

    html = render_to_string('tickets/panel_kpi_pdf.html', contexto)
    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"kpi-{contexto['anio']}-{contexto['mes']:02d}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    pisa.CreatePDF(html, dest=response, encoding='utf-8')
    return response
