from django.apps import AppConfig


class ListadoPublicacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "listado_publicaciones"

    def ready(self):
        import listado_publicaciones.signals
