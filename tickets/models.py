import uuid

from django.conf import settings
from django.db import models


class Agente(models.Model):
    class Rol(models.TextChoices):
        L1 = 'L1', 'Soporte L1'
        L2 = 'L2', 'Soporte L2'
        GERENCIA = 'GERENCIA', 'Gerencia (solo lectura)'

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agente'
    )
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.L1)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.usuario.get_full_name() or self.usuario.username} ({self.get_rol_display()})'


class Prioridad(models.Model):
    nombre = models.CharField(max_length=20, unique=True)
    orden = models.PositiveSmallIntegerField(
        help_text='Menor numero = mayor prioridad. Se usa para ordenar listados.'
    )
    sla_primera_respuesta_horas = models.PositiveIntegerField()
    sla_resolucion_horas = models.PositiveIntegerField()

    class Meta:
        ordering = ['orden']
        verbose_name = 'Prioridad'
        verbose_name_plural = 'Prioridades'

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'

    def __str__(self):
        return self.nombre


class AreaSolicitante(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Area solicitante'
        verbose_name_plural = 'Areas solicitantes'

    def __str__(self):
        return self.nombre


class Ticket(models.Model):
    class TipoSolicitud(models.TextChoices):
        INCIDENCIA = 'INCIDENCIA', 'Incidencia'
        REQUERIMIENTO = 'REQUERIMIENTO', 'Requerimiento'

    class Estado(models.TextChoices):
        NUEVO = 'NUEVO', 'Nuevo'
        ASIGNADO = 'ASIGNADO', 'Asignado'
        EN_PROGRESO = 'EN_PROGRESO', 'En progreso'
        ESPERANDO_USUARIO = 'ESPERANDO_USUARIO', 'Esperando al usuario'
        RESUELTO = 'RESUELTO', 'Resuelto'
        CERRADO = 'CERRADO', 'Cerrado'

    codigo = models.CharField(max_length=12, unique=True, blank=True)

    tipo_solicitud = models.CharField(max_length=15, choices=TipoSolicitud.choices)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='tickets'
    )
    area_solicitante = models.ForeignKey(
        AreaSolicitante, on_delete=models.PROTECT, related_name='tickets'
    )
    prioridad = models.ForeignKey(
        Prioridad, on_delete=models.PROTECT, related_name='tickets'
    )

    solicitante_nombre = models.CharField(max_length=120)
    solicitante_email = models.EmailField()

    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.NUEVO, db_index=True
    )
    agente_asignado = models.ForeignKey(
        Agente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_asignados',
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_primera_respuesta = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    solucion_aplicada = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.codigo} - {self.titulo}'

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.codigo:
            self.codigo = f'TCK-{self.pk:06d}'
            super().save(update_fields=['codigo'])


class HistorialEstado(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='historial_estados'
    )
    estado_anterior = models.CharField(
        max_length=20, choices=Ticket.Estado.choices, null=True, blank=True
    )
    estado_nuevo = models.CharField(max_length=20, choices=Ticket.Estado.choices)
    agente = models.ForeignKey(
        Agente, on_delete=models.SET_NULL, null=True, blank=True
    )
    comentario = models.TextField(blank=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_cambio']
        verbose_name = 'Historial de estado'
        verbose_name_plural = 'Historial de estados'

    def __str__(self):
        return f'{self.ticket.codigo}: {self.estado_anterior} -> {self.estado_nuevo}'


class EncuestaCSAT(models.Model):
    class Calificacion(models.IntegerChoices):
        UNA_ESTRELLA = 1, '1 estrella'
        DOS_ESTRELLAS = 2, '2 estrellas'
        TRES_ESTRELLAS = 3, '3 estrellas'
        CUATRO_ESTRELLAS = 4, '4 estrellas'
        CINCO_ESTRELLAS = 5, '5 estrellas'

    ticket = models.OneToOneField(
        Ticket, on_delete=models.CASCADE, related_name='encuesta_csat'
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    calificacion = models.PositiveSmallIntegerField(
        choices=Calificacion.choices, null=True, blank=True
    )
    comentario = models.TextField(blank=True)
    enviado_at = models.DateTimeField(null=True, blank=True)
    respondido_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Encuesta CSAT'
        verbose_name_plural = 'Encuestas CSAT'

    def __str__(self):
        return f'Encuesta {self.ticket.codigo} - {self.calificacion or "sin responder"}'


class ArticuloKB(models.Model):
    titulo = models.CharField(max_length=150)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='articulos_kb'
    )
    sintoma = models.TextField(help_text='Como se manifiesta el problema')
    solucion = models.TextField()
    tags = models.CharField(
        max_length=255, blank=True, help_text='Palabras clave separadas por coma'
    )
    ticket_origen = models.ForeignKey(
        Ticket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_generados',
    )
    creado_por = models.ForeignKey(Agente, on_delete=models.SET_NULL, null=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizado_at']
        verbose_name = 'Articulo de base de conocimiento'
        verbose_name_plural = 'Articulos de base de conocimiento'

    def __str__(self):
        return self.titulo


class Adjunto(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='adjuntos'
    )
    archivo = models.FileField(upload_to='adjuntos/%Y/%m/')
    subido_por = models.ForeignKey(
        Agente, on_delete=models.SET_NULL, null=True, blank=True
    )
    subido_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.ticket.codigo} - {self.archivo.name}'
