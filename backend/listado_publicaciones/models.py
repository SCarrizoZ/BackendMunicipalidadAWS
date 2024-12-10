from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from cloudinary.models import CloudinaryField
from django.utils import timezone
import uuid
from datetime import datetime

# Create your models here.


class UsuarioManager(BaseUserManager):
    def create_user(self, rut, email, nombre, password=None, **extra_fields):
        """Crea y guarda un usuario normal."""
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        usuario = self.model(rut=rut, email=email, nombre=nombre, **extra_fields)
        usuario.set_password(password)  # Encripta la contraseña
        usuario.save()
        return usuario

    def create_superuser(self, rut, email, nombre, password=None, **extra_fields):
        """Crea y guarda un usuario administrador."""
        extra_fields.setdefault("es_administrador", True)
        extra_fields.setdefault("esta_activo", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("is_superuser"):
            raise ValueError("El superusuario debe tener is_superuser=True.")
        return self.create_user(rut, email, nombre, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    rut = models.CharField(max_length=12, unique=True)
    numero_telefonico_movil = models.CharField(max_length=9, null=True, blank=True)
    nombre = models.CharField(max_length=120)
    es_administrador = models.BooleanField(default=False)
    email = models.EmailField(max_length=200, unique=True)
    fecha_registro = models.DateTimeField(default=timezone.now)
    esta_activo = models.BooleanField(default=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "rut"
    REQUIRED_FIELDS = ["email", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def is_staff(self):
        return self.es_administrador


class DepartamentoMunicipal(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    departamento = models.ForeignKey(DepartamentoMunicipal, on_delete=models.RESTRICT)
    nombre = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self):
        return self.nombre


class SituacionPublicacion(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self):
        return self.nombre


class JuntaVecinal(models.Model):
    nombre_junta = models.CharField(max_length=200, unique=True, null=True, blank=True)
    nombre_calle = models.CharField(max_length=60, null=True, blank=True)
    numero_calle = models.IntegerField()
    departamento = models.CharField(max_length=40, null=True, blank=True)
    villa = models.CharField(max_length=40, null=True, blank=True)
    comuna = models.CharField(max_length=40, null=True, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.nombre_calle} {self.numero_calle}"


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
    descripcion = models.TextField()
    fecha_publicacion = models.DateTimeField(default=timezone.now)
    titulo = models.CharField(max_length=100)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    nombre_calle = models.CharField(max_length=100, null=True, blank=True)
    numero_calle = models.IntegerField()
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)

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

    def __str__(self):
        return f"Respuesta para: {self.publicacion.titulo}"
