# Generated by Django 5.1.1 on 2024-11-26 01:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listado_publicaciones', '0003_anunciomunicipal_categoria_anunciomunicipal_estado_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='anunciomunicipal',
            name='subtitulo',
            field=models.CharField(max_length=500),
        ),
    ]
