from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
from django.db.models import Q

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

    def get_departamento_asignado(self):
        """Retorna el departamento asignado del usuario"""
        from .organizaciones import DepartamentoMunicipal  # Importación local para evitar ciclo
        
        # Si es jefe de departamento, buscar el departamento que dirige
        if self.tipo_usuario == "jefe_departamento":
            try:
                return self.departamento_dirigido
            except DepartamentoMunicipal.DoesNotExist:
                pass

        # Si es personal municipal, buscar asignación activa
        if self.tipo_usuario in ["personal", "jefe_departamento"]:
            asignacion_activa = self.asignaciones_departamento.filter(
                estado="activo", fecha_fin_asignacion__isnull=True
            ).first()
            if asignacion_activa:
                return asignacion_activa.departamento

        return None

    @classmethod
    def buscar_duplicados(cls, rut=None, email=None, excluir_id=None):
        """
        Método optimizado para buscar usuarios duplicados
        """
        duplicados = {}

        if rut:
            rut_normalizado = rut.replace(".", "").replace("-", "")
            # Buscar en múltiples formatos de RUT
            query = cls.objects.filter(
                Q(rut=rut_normalizado)
                | Q(rut=rut)
                | Q(
                    rut__in=[
                        rut,
                        rut_normalizado,
                        (
                            f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}"
                            if len(rut_normalizado) >= 2
                            else rut_normalizado
                        ),
                    ]
                )
            )
            if excluir_id:
                query = query.exclude(id=excluir_id)
            usuario_rut = query.first()
            if usuario_rut:
                duplicados["rut"] = usuario_rut

        if email:
            query = cls.objects.filter(email__iexact=email)
            if excluir_id:
                query = query.exclude(id=excluir_id)
            usuario_email = query.first()
            if usuario_email:
                duplicados["email"] = usuario_email

        return duplicados

    @classmethod
    def normalizar_rut(cls, rut):
        """Normaliza un RUT removiendo puntos"""
        if not rut:
            return rut
        return rut.replace(".", "")

    @classmethod
    def existe_usuario(cls, rut=None, email=None):
        """
        Verifica rápidamente si existe un usuario con el RUT o email dados
        """
        if rut:
            rut_normalizado = cls.normalizar_rut(rut)
            # Buscar en múltiples formatos
            if cls.objects.filter(
                Q(rut=rut_normalizado)
                | Q(rut=rut)
                | Q(
                    rut__in=[
                        rut,
                        rut_normalizado,
                        (
                            f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}"
                            if len(rut_normalizado) >= 2
                            else rut_normalizado
                        ),
                    ]
                )
            ).exists():
                return True

        if email:
            if cls.objects.filter(email__iexact=email).exists():
                return True

        return False

    def save(self, *args, **kwargs):
        """Override save para normalizar RUT automáticamente"""
        if self.rut:
            self.rut = self.normalizar_rut(self.rut)
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


class DispositivoNotificacion(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="dispositivos_notificacion",
        help_text="Usuario al que pertenece el dispositivo",
    )
    token_expo = models.CharField(
        max_length=255, unique=True, help_text="Token de Expo para notificaciones push"
    )
    plataforma = models.CharField(
        max_length=50,
        choices=[("ios", "iOS"), ("android", "Android")],
        help_text="Plataforma del dispositivo (iOS, Android)",
    )
    activo = models.BooleanField(
        default=True,
        help_text="Indica si el dispositivo está activo para notificaciones",
    )
    fecha_registro = models.DateTimeField(
        default=timezone.now, help_text="Fecha de registro del dispositivo"
    )
    ultima_actualizacion = models.DateTimeField(
        auto_now=True, help_text="Última actualización del dispositivo"
    )

    class Meta:
        db_table = "dispositivos_notificacion"
        verbose_name = "Dispositivo de Notificación"
        verbose_name_plural = "Dispositivos de Notificación"
        ordering = ["-ultima_actualizacion"]

        # Un usuario puede tener el mismo token solo una vez
        unique_together = [["usuario", "token_expo"]]

        # Index para búsquedas rápidas por token
        indexes = [
            models.Index(fields=["usuario", "activo"], name="idx_usuario_activo"),
            models.Index(fields=["token_expo"], name="idx_token_expo"),
        ]

    def __str__(self):
        return f"Dispositivo de {self.usuario.nombre} - {self.plataforma} ({self.token_expo[:20]}...)"

    def desactivar(self):
        """Marca el dispositivo como inactivo"""
        self.activo = False
        self.save()
