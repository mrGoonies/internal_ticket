from django.contrib import admin

from .models import (
    Adjunto,
    Agente,
    AreaSolicitante,
    ArticuloKB,
    Categoria,
    EncuestaCSAT,
    HistorialEstado,
    Prioridad,
    Ticket,
)


class HistorialEstadoInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    readonly_fields = ['estado_anterior', 'estado_nuevo', 'agente', 'comentario', 'fecha_cambio']
    can_delete = False
    ordering = ['fecha_cambio']


class AdjuntoInline(admin.TabularInline):
    model = Adjunto
    extra = 0
    readonly_fields = ['subido_at']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'codigo',
        'titulo',
        'tipo_solicitud',
        'estado',
        'prioridad',
        'area_solicitante',
        'agente_asignado',
        'fecha_creacion',
    ]
    list_filter = ['tipo_solicitud', 'estado', 'prioridad', 'categoria', 'area_solicitante', 'canal_origen']
    search_fields = ['codigo', 'titulo', 'descripcion', 'solicitante_nombre', 'solicitante_email']
    readonly_fields = ['codigo', 'fecha_creacion']
    inlines = [HistorialEstadoInline, AdjuntoInline]


@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'rol', 'activo']
    list_filter = ['rol', 'activo']


@admin.register(Prioridad)
class PrioridadAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'sla_primera_respuesta_horas', 'sla_resolucion_horas']
    ordering = ['orden']


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre']


@admin.register(AreaSolicitante)
class AreaSolicitanteAdmin(admin.ModelAdmin):
    list_display = ['nombre']


@admin.register(EncuestaCSAT)
class EncuestaCSATAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'calificacion', 'enviado_at', 'respondido_at']
    list_filter = ['calificacion']
    readonly_fields = ['token']


@admin.register(ArticuloKB)
class ArticuloKBAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'creado_por', 'actualizado_at']
    list_filter = ['categoria']
    search_fields = ['titulo', 'sintoma', 'solucion', 'tags']


@admin.register(HistorialEstado)
class HistorialEstadoAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'estado_anterior', 'estado_nuevo', 'agente', 'fecha_cambio']
    list_filter = ['estado_nuevo']
