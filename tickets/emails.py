import logging

import mailchimp_transactional as MailchimpTransactional
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _enviar(destinatario, asunto, template, contexto):
    html = render_to_string(template, contexto)
    texto = strip_tags(html)

    if not settings.MANDRILL_API_KEY:
        logger.info(
            'MANDRILL_API_KEY no configurada; correo no enviado (asunto=%r, para=%r)',
            asunto,
            destinatario,
        )
        return

    client = MailchimpTransactional.Client(settings.MANDRILL_API_KEY)
    mensaje = {
        'from_email': settings.EMAIL_FROM_ADDRESS,
        'from_name': settings.EMAIL_FROM_NAME,
        'to': [{'email': destinatario, 'type': 'to'}],
        'subject': asunto,
        'html': html,
        'text': texto,
    }
    try:
        client.messages.send({'message': mensaje})
    except Exception:
        logger.exception('Error enviando correo a %s', destinatario)


def notificar_ticket_creado(ticket):
    _enviar(
        ticket.solicitante_email,
        f'Tu ticket {ticket.codigo} fue registrado',
        'emails/ticket_creado.html',
        {'ticket': ticket},
    )
    if settings.SOPORTE_TEAM_EMAIL:
        _enviar(
            settings.SOPORTE_TEAM_EMAIL,
            f'Nuevo ticket {ticket.codigo}: {ticket.titulo}',
            'emails/alerta_nuevo_ticket.html',
            {'ticket': ticket, 'url_panel': f'{settings.SITE_BASE_URL}/panel/{ticket.codigo}/'},
        )


def notificar_cambio_estado(ticket):
    _enviar(
        ticket.solicitante_email,
        f'Tu ticket {ticket.codigo} cambio a {ticket.get_estado_display()}',
        'emails/cambio_estado.html',
        {'ticket': ticket},
    )


def notificar_encuesta_csat(encuesta):
    url_encuesta = f'{settings.SITE_BASE_URL}/encuesta/{encuesta.token}/'
    _enviar(
        encuesta.ticket.solicitante_email,
        f'Como fue tu experiencia con el ticket {encuesta.ticket.codigo}?',
        'emails/encuesta_csat.html',
        {'ticket': encuesta.ticket, 'url_encuesta': url_encuesta},
    )
