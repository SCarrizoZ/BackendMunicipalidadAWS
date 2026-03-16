from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField
import uuid
from datetime import datetime
from .usuarios import Usuario
from .organizaciones import DepartamentoMunicipal, JuntaVecinal

class Categoria(models.Model):
    departamento = models.ForeignKey(DepartamentoMunicipal, on_delete=models.RESTRICT)
    nombre = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=300, null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[
            ("habilitado", "Habilitado"),
            ("pendiente", "Pendiente"),
            ("deshabilitado", "Deshabilitado"),
        ],
        default="habilitado",
    )
    fecha_creacion = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.nombre

    def get_cantidad_publicaciones(self):
        """Retorna la cantidad de publicaciones asociadas a esta categoría"""
        return Publicacion.objects.filter(categoria=self).count()


class SituacionPublicacion(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self):
        return self.nombre


class Publicacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    junta_vecinal = models.ForeignKey(JuntaVecinal, on_delete=models.RESTRICT)
    categoria = models.ForeignKey(Categoria, on_delete=models.RESTRICT)
    situacion = models.ForeignKey(
        SituacionPublicacion,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        default=4,
    )
    departamento = models.ForeignKey(DepartamentoMunicipal, on_delete=models.RESTRICT)
    descripcion = models.TextField(default="N/A", null=True, blank=True)
    fecha_publicacion = models.DateTimeField(default=timezone.now)
    titulo = models.CharField(max_length=100)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    ubicacion = models.CharField(max_length=300, null=True, blank=True)
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)
    es_incognito = models.BooleanField(default=False)
    encargado = models.ForeignKey(
        Usuario,
        on_delete=models.RESTRICT,
        related_name="publicaciones_encargadas",
        null=True,
        blank=True,
    )
    prioridad = models.CharField(
        max_length=20,
        choices=[("alta", "Alta"), ("media", "Media"), ("baja", "Baja")],
        default="media",
    )

    def __str__(self):
        return (
            (self.codigo if self.codigo else "Sin código")
            + " - "
            + self.fecha_publicacion.strftime("%d/%m/%Y")
        )

    def save(self, *args, **kwargs):
        if not self.codigo:
            current_year = str(datetime.now().year)
            current_month = str(datetime.now().month)
            while True:
                codigo_generado = f"P-{current_year}-{current_month.zfill(2)}-{uuid.uuid4().hex[:8].upper()}"
                if not Publicacion.objects.filter(codigo=codigo_generado).exists():
                    self.codigo = codigo_generado
                    break
        super().save(*args, **kwargs)


class Evidencia(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    archivo = CloudinaryField("archivo")
    nombre = models.CharField(max_length=200, null=True, blank=True)
    peso = models.IntegerField(null=True, blank=True)  # en bytes
    fecha = models.DateTimeField(default=timezone.now)
    extension = models.CharField(max_length=30)

    def __str__(self):
        return f"Evidencia para: {self.publicacion.titulo}"


class AnuncioMunicipal(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    titulo = models.CharField(max_length=100)
    subtitulo = models.CharField(max_length=500)
    estado = models.CharField(max_length=100, default="Pendiente")
    descripcion = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.RESTRICT)
    fecha = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.titulo


class ImagenAnuncio(models.Model):
    anuncio = models.ForeignKey(AnuncioMunicipal, on_delete=models.CASCADE)
    imagen = CloudinaryField("imagen")
    nombre = models.CharField(max_length=200, null=True, blank=True)
    peso = models.IntegerField(null=True, blank=True)  # en bytes
    fecha = models.DateTimeField(default=timezone.now)
    extension = models.CharField(max_length=30)

    def __str__(self):
        return f"Imagen para: {self.anuncio.titulo}"


class RespuestaMunicipal(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    publicacion = models.ForeignKey(Publicacion, on_delete=models.RESTRICT)
    fecha = models.DateTimeField(default=timezone.now)
    descripcion = models.TextField()
    acciones = models.CharField(max_length=400)
    situacion_inicial = models.CharField(max_length=100)
    situacion_posterior = models.CharField(max_length=100)
    puntuacion = models.IntegerField(
        default=0,
        choices=[(i, f"{i} estrella{'s' if i != 1 else ''}") for i in range(1, 6)],
        help_text="Puntuación del 1 al 5",
    )

    def __str__(self):
        return f"Respuesta para: {self.publicacion.titulo}"


class EvidenciaRespuesta(models.Model):
    """Evidencia adjunta a una respuesta municipal"""

    respuesta = models.ForeignKey(
        RespuestaMunicipal, on_delete=models.CASCADE, related_name="evidencias"
    )
    archivo = CloudinaryField("archivo")
    nombre = models.CharField(max_length=200, null=True, blank=True)
    peso = models.IntegerField(null=True, blank=True)  # en bytes
    fecha = models.DateTimeField(default=timezone.now)
    extension = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"Evidencia para respuesta: {self.respuesta.publicacion.titulo}"
