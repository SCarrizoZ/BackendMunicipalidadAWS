# Generated by Django 5.1.1 on 2024-12-17 03:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listado_publicaciones', '0007_alter_publicacion_situacion'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='publicacion',
            name='nombre_calle',
        ),
        migrations.RemoveField(
            model_name='publicacion',
            name='numero_calle',
        ),
        migrations.AddField(
            model_name='publicacion',
            name='ubicacion',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
        migrations.AlterField(
            model_name='publicacion',
            name='descripcion',
            field=models.TextField(blank=True, default='N/A', null=True),
        ),
    ]