from django.shortcuts import get_object_or_404, redirect, render

from .forms import TicketPublicoForm
from .models import Adjunto, HistorialEstado, Ticket
from .services import inferir_prioridad

SESSION_KEY_ULTIMO_TICKET = 'ultimo_ticket_id'


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
