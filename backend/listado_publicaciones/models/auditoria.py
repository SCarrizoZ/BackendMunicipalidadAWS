from django.db import models
from django.utils import timezone
import uuid
from datetime import datetime
from .usuarios import Usuario
from .publicaciones import Publicacion

class HistorialModificaciones(models.Model):
    publicacion = models.ForeignKey(
        Publicacion, on_delete=models.CASCADE, related_name="historialmodificaciones"
    )
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
