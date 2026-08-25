from django import forms

from .models import AreaSolicitante, Categoria, Ticket


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
