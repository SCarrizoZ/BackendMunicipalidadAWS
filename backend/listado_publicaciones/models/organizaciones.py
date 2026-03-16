from django.db import models
from django.utils import timezone
from .usuarios import Usuario

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
        Usuario,
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
