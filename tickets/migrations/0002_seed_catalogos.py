from django.db import migrations


def crear_catalogos(apps, schema_editor):
    Prioridad = apps.get_model('tickets', 'Prioridad')
    Categoria = apps.get_model('tickets', 'Categoria')
    AreaSolicitante = apps.get_model('tickets', 'AreaSolicitante')

    for nombre, orden, sla_respuesta, sla_resolucion in [
        ('Critica', 1, 1, 4),
        ('Alta', 2, 2, 8),
        ('Media', 3, 4, 24),
        ('Baja', 4, 8, 72),
    ]:
        Prioridad.objects.get_or_create(
            nombre=nombre,
            defaults={
                'orden': orden,
                'sla_primera_respuesta_horas': sla_respuesta,
                'sla_resolucion_horas': sla_resolucion,
            },
        )

    for nombre in [
        'Hardware',
        'Red y conectividad',
        'Software',
        'Accesos y contrasenas',
        'Correo electronico',
        'Otro',
    ]:
        Categoria.objects.get_or_create(nombre=nombre)

    # Placeholder generico: ajustar en /admin a la estructura real de la empresa.
    for nombre in [
        'Administracion y Finanzas',
        'Comercial y Ventas',
        'Operaciones',
        'Recursos Humanos',
        'Gerencia',
        'Otro',
    ]:
        AreaSolicitante.objects.get_or_create(nombre=nombre)


def eliminar_catalogos(apps, schema_editor):
    Prioridad = apps.get_model('tickets', 'Prioridad')
    Categoria = apps.get_model('tickets', 'Categoria')
    AreaSolicitante = apps.get_model('tickets', 'AreaSolicitante')
    Prioridad.objects.all().delete()
    Categoria.objects.all().delete()
    AreaSolicitante.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_catalogos, eliminar_catalogos),
    ]
