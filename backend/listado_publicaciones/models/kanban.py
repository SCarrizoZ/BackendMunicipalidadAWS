from django.db import models
from .organizaciones import DepartamentoMunicipal
from .usuarios import Usuario
from .publicaciones import Categoria, Publicacion

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
