from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.crear_ticket, name='crear_ticket'),
    path('gracias/', views.ticket_creado, name='ticket_creado'),
    path(
        'panel/login/',
        auth_views.LoginView.as_view(template_name='tickets/login.html'),
        name='login',
    ),
    path('panel/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('panel/', views.lista_tickets, name='lista_tickets'),
    path('panel/<str:codigo>/', views.detalle_ticket, name='detalle_ticket'),
    path('encuesta/<uuid:token>/', views.responder_encuesta, name='responder_encuesta'),
]
