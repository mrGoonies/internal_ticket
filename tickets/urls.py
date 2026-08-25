from django.urls import path

from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.crear_ticket, name='crear_ticket'),
    path('gracias/', views.ticket_creado, name='ticket_creado'),
]
