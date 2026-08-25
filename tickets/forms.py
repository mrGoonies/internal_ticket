from django import forms

from .models import Agente, AreaSolicitante, Categoria, EncuestaCSAT, Ticket


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class TicketPublicoForm(forms.ModelForm):
    adjuntos = forms.FileField(
        widget=MultiFileInput(attrs={'multiple': True}),
        required=False,
        label='Adjuntos',
    )

    class Meta:
        model = Ticket
        fields = [
            'tipo_solicitud',
            'categoria',
            'area_solicitante',
            'titulo',
            'descripcion',
            'solicitante_nombre',
            'solicitante_email',
        ]
        widgets = {
            'tipo_solicitud': forms.RadioSelect,
            'titulo': forms.TextInput(
                attrs={'placeholder': 'Ej: No puedo acceder al correo corporativo'}
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Cuenta que pasa, desde cuando y que has intentado.',
                }
            ),
            'solicitante_nombre': forms.TextInput(attrs={'placeholder': 'Nombre y apellido'}),
            'solicitante_email': forms.EmailInput(
                attrs={'placeholder': 'nombre@empresa.com'}
            ),
        }
        labels = {
            'tipo_solicitud': 'Que necesitas',
            'categoria': 'Categoria',
            'area_solicitante': 'Area',
            'titulo': 'Titulo',
            'descripcion': 'Descripcion',
            'solicitante_nombre': 'Tu nombre',
            'solicitante_email': 'Tu correo',
        }
        error_messages = {
            'titulo': {'required': 'Escribe un titulo breve para tu solicitud.'},
            'descripcion': {
                'required': 'Cuentanos que pasa para poder ayudarte mas rapido.'
            },
            'solicitante_nombre': {'required': 'Necesitamos tu nombre para contactarte.'},
            'solicitante_email': {
                'required': 'Necesitamos tu correo para avisarte del avance.',
                'invalid': 'Ese correo no parece valido, revisalo.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El modelo no define un default para tipo_solicitud, asi que Django
        # agrega una opcion en blanco automaticamente; la quitamos porque con
        # RadioSelect queda marcada por defecto en vez de forzar una eleccion.
        self.fields['tipo_solicitud'].choices = Ticket.TipoSolicitud.choices
        self.fields['categoria'].queryset = Categoria.objects.order_by('nombre')
        self.fields['categoria'].empty_label = 'Selecciona una categoria'
        self.fields['area_solicitante'].queryset = AreaSolicitante.objects.order_by('nombre')
        self.fields['area_solicitante'].empty_label = 'Selecciona tu area'


class TicketGestionForm(forms.ModelForm):
    comentario = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        label='Comentario del cambio (opcional)',
        help_text='Se guarda en el historial junto con el cambio de estado.',
    )

    class Meta:
        model = Ticket
        fields = ['estado', 'agente_asignado', 'solucion_aplicada']
        widgets = {
            'solucion_aplicada': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Describe la solucion aplicada (queda disponible para la base de conocimiento).',
                }
            ),
        }
        labels = {
            'estado': 'Estado',
            'agente_asignado': 'Asignado a',
            'solucion_aplicada': 'Solucion aplicada',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agente_asignado'].queryset = Agente.objects.filter(activo=True)
        self.fields['agente_asignado'].empty_label = 'Sin asignar'


class EncuestaCSATForm(forms.ModelForm):
    class Meta:
        model = EncuestaCSAT
        fields = ['calificacion', 'comentario']
        widgets = {
            'calificacion': forms.RadioSelect,
            'comentario': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Cuentanos mas (opcional).'}
            ),
        }
        labels = {'calificacion': 'Tu calificacion', 'comentario': 'Comentario'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Igual que con tipo_solicitud: el campo es nullable en el modelo
        # (hasta que se responde), asi que Django agregaria una opcion en
        # blanco. La sacamos y forzamos a elegir una estrella.
        self.fields['calificacion'].choices = list(reversed(EncuestaCSAT.Calificacion.choices))
        self.fields['calificacion'].required = True
