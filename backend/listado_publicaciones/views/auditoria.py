from rest_framework import viewsets
from ..models import HistorialModificaciones, Auditoria
from ..serializers.v1 import (
    HistorialModificacionesSerializer,
    AuditoriaSerializer,
)
from ..pagination import DynamicPageNumberPagination
from listado_publicaciones.permissions import IsAdmin, IsMunicipalStaff
import logging

logger = logging.getLogger(__name__)

def crear_auditoria(usuario, accion, modulo, descripcion, es_exitoso=True):
    """Función auxiliar para crear registros de auditoría"""
    try:
        # Validar que la acción sea válida
        acciones_validas = [
            "CREATE",
            "READ",
            "UPDATE",
            "DELETE",
            "LOGIN",
            "LOGOUT",
            "GENERAR_REPORTE_PDF",
        ]
        if accion not in acciones_validas:
            raise ValueError(
                f"Acción inválida: {accion}. Debe ser una de: {acciones_validas}"
            )

        Auditoria.objects.create(
            autor=usuario,
            accion=accion,
            modulo=modulo,
            descripcion=descripcion,
            es_exitoso=es_exitoso,
        )
    except Exception as e:
        # Si falla la auditoría, no debe afectar la operación principal
        print(f"Error al crear auditoría: {e}")
        logger.error(f"Error en auditoría: {e}")


def crear_historial_modificacion(
    publicacion, campo, valor_anterior, valor_nuevo, autor
):
    """Función auxiliar para crear registros de historial de modificaciones"""
    try:
        HistorialModificaciones.objects.create(
            publicacion=publicacion,
            campo_modificado=campo,
            valor_anterior=str(valor_anterior) if valor_anterior is not None else "",
            valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else "",
            autor=autor,
        )
    except Exception as e:
        print(f"Error al crear historial de modificaciones: {e}")
        logger.error(f"Error en historial de modificaciones: {e}")


class AuditMixin:
    """Mixin para agregar auditoría automática a ViewSets"""

    def get_audit_module_name(self):
        """Override este método para personalizar el nombre del módulo"""
        return self.__class__.__name__.replace("ViewSet", "")

    def get_audit_object_name(self, instance):
        """Override este método para personalizar cómo se identifica el objeto"""
        return getattr(
            instance, "titulo", getattr(instance, "nombre", f"ID: {instance.id}")
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        crear_auditoria(
            usuario=self.request.user,
            accion="CREATE",
            modulo=self.get_audit_module_name(),
            descripcion=f"Creado {self.get_audit_module_name()}: {self.get_audit_object_name(instance)}",
            es_exitoso=True,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        crear_auditoria(
            usuario=self.request.user,
            accion="UPDATE",
            modulo=self.get_audit_module_name(),
            descripcion=f"Actualizado {self.get_audit_module_name()}: {self.get_audit_object_name(instance)}",
            es_exitoso=True,
        )

    def perform_destroy(self, instance):
        nombre = self.get_audit_object_name(instance)
        instance.delete()
        crear_auditoria(
            usuario=self.request.user,
            accion="DELETE",
            modulo=self.get_audit_module_name(),
            descripcion=f"Eliminado {self.get_audit_module_name()}: {nombre}",
            es_exitoso=True,
        )


class HistorialModificacionesViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para consultar historial de modificaciones (solo lectura)"""

    queryset = HistorialModificaciones.objects.all().order_by("-fecha")
    serializer_class = HistorialModificacionesSerializer
    permission_classes = [IsAdmin | IsMunicipalStaff]

    def get_queryset(self):
        queryset = HistorialModificaciones.objects.all().order_by("-fecha")
        publicacion_id = self.request.query_params.get("publicacion", None)
        autor_id = self.request.query_params.get("autor", None)

        if publicacion_id is not None:
            queryset = queryset.filter(publicacion_id=publicacion_id)
        if autor_id is not None:
            queryset = queryset.filter(autor_id=autor_id)

        return queryset


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para consultar auditorías (solo lectura)"""

    queryset = Auditoria.objects.all().order_by("-fecha")
    serializer_class = AuditoriaSerializer
    permission_classes = [IsAdmin]
    pagination_class = DynamicPageNumberPagination

    def get_queryset(self):
        queryset = Auditoria.objects.all().order_by("-fecha")
        autor_id = self.request.query_params.get("autor", None)
        modulo = self.request.query_params.get("modulo", None)
        es_exitoso = self.request.query_params.get("es_exitoso", None)

        if autor_id is not None:
            queryset = queryset.filter(autor_id=autor_id)
        if modulo is not None:
            queryset = queryset.filter(modulo__icontains=modulo)
        if es_exitoso is not None:
            queryset = queryset.filter(es_exitoso=es_exitoso.lower() == "true")

        return queryset
