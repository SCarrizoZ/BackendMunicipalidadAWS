from django.contrib import admin
from .models import (
    Usuario,
    UsuarioDepartamento,
    Publicacion,
    Categoria,
    Evidencia,
    JuntaVecinal,
    DepartamentoMunicipal,
    Tablero,
    Columna,
    Tarea,
    Auditoria,
    HistorialModificaciones,
    RespuestaMunicipal,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
    EvidenciaRespuesta,
    Comentario,
    DispositivoNotificacion,
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


@admin.register(DispositivoNotificacion)
class DispositivoNotificacionAdmin(admin.ModelAdmin):
    list_display = ["usuario", "plataforma", "activo", "fecha_registro", "token_corto"]
    list_filter = ["plataforma", "activo", "fecha_registro"]
    search_fields = ["usuario__rut", "usuario__nombre", "token_expo"]
    readonly_fields = ["fecha_registro", "ultima_actualizacion"]

    def token_corto(self, obj):
        return f"{obj.token_expo[:30]}..."

    token_corto.short_description = "Token"
