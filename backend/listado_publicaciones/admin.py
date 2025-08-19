from django.contrib import admin
from .models import (
    Usuario,
    DepartamentoMunicipal,
    Categoria,
    JuntaVecinal,
    Publicacion,
    Evidencia,
    SituacionPublicacion,
    RespuestaMunicipal,
    AnuncioMunicipal,
    ImagenAnuncio,
    HistorialModificaciones,
    Auditoria,
    Columna,
    Tarea,
    Comentario,
    Tablero,
    UsuarioDepartamento,
)

# Registro de modelos básicos en el admin
admin.site.register(Usuario)
admin.site.register(DepartamentoMunicipal)
admin.site.register(Categoria)
admin.site.register(JuntaVecinal)
admin.site.register(Publicacion)
admin.site.register(Evidencia)
admin.site.register(SituacionPublicacion)
admin.site.register(RespuestaMunicipal)
admin.site.register(AnuncioMunicipal)
admin.site.register(ImagenAnuncio)
admin.site.register(HistorialModificaciones)
admin.site.register(Auditoria)
admin.site.register(Columna)
admin.site.register(Tarea)
admin.site.register(Comentario)
admin.site.register(Tablero)
admin.site.register(UsuarioDepartamento)
