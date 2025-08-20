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
    TIPO_USUARIO_CHOICES = [
        ("vecino", "Vecino"),
        ("personal", "Personal Municipal"),
        ("jefe_departamento", "Jefe de Departamento"),
        ("administrador", "Administrador Municipal"),
    ]

    rut = models.CharField(max_length=12, unique=True)
    numero_telefonico_movil = models.CharField(max_length=9, null=True, blank=True)
    nombre = models.CharField(max_length=120)
    es_administrador = models.BooleanField(default=False)
    email = models.EmailField(max_length=200, unique=True)
    fecha_registro = models.DateTimeField(default=timezone.now)
    esta_activo = models.BooleanField(default=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)
    tipo_usuario = models.CharField(
        max_length=20, choices=TIPO_USUARIO_CHOICES, default="vecino"
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "rut"
    REQUIRED_FIELDS = ["email", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def is_staff(self):
        return self.es_administrador or self.tipo_usuario in [
            "personal",
            "jefe_departamento",
            "administrador",
        ]

    @property
    def is_active(self):
        """Django requiere is_active para la autenticación"""
        return self.esta_activo

    @property
    def es_municipal(self):
        """Retorna True si el usuario es personal municipal (cualquier tipo excepto vecino)"""
        return self.tipo_usuario in ["personal", "jefe_departamento", "administrador"]

    @property
    def es_jefe_departamento(self):
        """Retorna True si el usuario es jefe de departamento"""
        return self.tipo_usuario == "jefe_departamento"


class DepartamentoMunicipal(models.Model):
    nombre = models.CharField(max_length=100)
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
    # Relación con el jefe del departamento
    jefe_departamento = models.OneToOneField(
        "Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departamento_dirigido",
        limit_choices_to={"tipo_usuario": "jefe_departamento"},
    )

    def __str__(self):
        return self.nombre

    def get_funcionarios(self):
        """Retorna todos los funcionarios asignados a este departamento"""
        return self.funcionarios.filter(usuario__esta_activo=True)

    def get_funcionarios_count(self):
        """Retorna el número de funcionarios asignados al departamento"""
        return self.get_funcionarios().count()


class UsuarioDepartamento(models.Model):
    """Modelo para manejar la asignación de funcionarios a departamentos"""

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="asignaciones_departamento",
        limit_choices_to={
            "tipo_usuario__in": ["personal", "jefe_departamento"],
            "esta_activo": True,
        },
    )
    departamento = models.ForeignKey(
        DepartamentoMunicipal, on_delete=models.CASCADE, related_name="funcionarios"
    )
    fecha_asignacion = models.DateTimeField(default=timezone.now)
    fecha_fin_asignacion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[("activo", "Activo"), ("inactivo", "Inactivo")],
        default="activo",
    )

    class Meta:
        unique_together = ["usuario", "departamento"]
        verbose_name = "Asignación Usuario-Departamento"
        verbose_name_plural = "Asignaciones Usuario-Departamento"

    def __str__(self):
        return f"{self.usuario.nombre} - {self.departamento.nombre}"

    def save(self, *args, **kwargs):
        # Validar que solo personal municipal puede ser asignado
        if not self.usuario.es_municipal:
            raise ValueError(
                "Solo el personal municipal puede ser asignado a departamentos"
            )
        super().save(*args, **kwargs)


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


class JuntaVecinal(models.Model):
    nombre_junta = models.CharField(max_length=200, unique=True, null=True, blank=True)
    nombre_calle = models.CharField(max_length=60, null=True, blank=True)
    numero_calle = models.IntegerField()
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
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
    fecha = models.DateTimeField(default=timezone.now)
    extension = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"Evidencia para respuesta: {self.respuesta.publicacion.titulo}"


class HistorialModificaciones(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)
    campo_modificado = models.CharField(max_length=100)
    valor_anterior = models.TextField()
    valor_nuevo = models.TextField()
    autor = models.ForeignKey(Usuario, on_delete=models.RESTRICT)

    def __str__(self):
        return f"Historial de cambios para: {self.publicacion.titulo}"


class Auditoria(models.Model):
    codigo = models.CharField(max_length=30, unique=True, blank=True, null=True)
    autor = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    accion = models.CharField(max_length=100)
    fecha = models.DateTimeField(default=timezone.now)
    modulo = models.CharField(max_length=100)
    descripcion = models.TextField()
    es_exitoso = models.BooleanField(default=True)

    def __str__(self):
        return f"Auditoría de cambios para: {self.codigo}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            current_year = str(datetime.now().year)
            current_month = str(datetime.now().month)
            while True:
                codigo_generado = f"AUD-{current_year}-{current_month.zfill(2)}-{uuid.uuid4().hex[:8].upper()}"
                if not Auditoria.objects.filter(codigo=codigo_generado).exists():
                    self.codigo = codigo_generado
                    break
        super().save(*args, **kwargs)


""" 
Clases para el tablero Kanban
"""


class Tablero(models.Model):
    titulo = models.CharField(max_length=100)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    departamento = models.ForeignKey(
        DepartamentoMunicipal, on_delete=models.RESTRICT, related_name="tableros"
    )

    def __str__(self):
        return f"{self.titulo} - {self.departamento.nombre}"


class Columna(models.Model):
    titulo = models.CharField(max_length=100)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    limite_tareas = models.PositiveIntegerField(default=0)
    tablero = models.ForeignKey(
        Tablero, on_delete=models.CASCADE, related_name="columnas"
    )

    def __str__(self):
        return f"{self.titulo} - {self.tablero.titulo}"


class Tarea(models.Model):
    titulo = models.CharField(max_length=100)
    descripcion = models.TextField()
    columna = models.ForeignKey(
        Columna, on_delete=models.CASCADE, related_name="tareas"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_limite = models.DateTimeField(null=True, blank=True)
    encargado = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    prioridad = models.CharField(
        max_length=50,
        choices=[
            ("baja", "Baja"),
            ("media", "Media"),
            ("alta", "Alta"),
        ],
    )
    categoria = models.ForeignKey(Categoria, on_delete=models.RESTRICT)
    publicaciones = models.ManyToManyField(
        Publicacion, blank=True, related_name="tareas_asociadas"
    )

    def __str__(self):
        return self.titulo


class Comentario(models.Model):
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    contenido = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comentario de {self.usuario} en {self.tarea}"
