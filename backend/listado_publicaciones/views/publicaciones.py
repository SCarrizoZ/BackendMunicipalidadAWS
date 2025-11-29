from rest_framework import viewsets
from ..models import (
    Publicacion,
    Evidencia,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
    HistorialModificaciones,
)
from ..serializers.v1 import (
    PublicacionListSerializer,
    PublicacionCreateUpdateSerializer,
    PublicacionConHistorialSerializer,
    EvidenciaSerializer,
    SituacionPublicacionSerializer,
    AnuncioMunicipalListSerializer,
    AnuncioMunicipalCreateUpdateSerializer,
    ImagenAnuncioSerializer,
)
from ..pagination import DynamicPageNumberPagination
from ..filters import PublicacionFilter, AnuncioMunicipalFilter
from ..permissions import (
    IsAdmin,
    IsAuthenticatedOrAdmin,
)
from .auditoria import AuditMixin, crear_auditoria, crear_historial_modificacion
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch

class PublicacionViewSet(viewsets.ModelViewSet):
    queryset = Publicacion.objects.all().order_by("-fecha_publicacion")
    permission_classes = [IsAuthenticatedOrAdmin]
    pagination_class = DynamicPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PublicacionFilter
    ordering_fields = ["fecha_publicacion"]

    def get_serializer_class(self):
        if self.action == "con_historial":
            return PublicacionConHistorialSerializer
        if self.action in ["list", "retrieve"]:
            return PublicacionListSerializer
        return PublicacionCreateUpdateSerializer

    def perform_update(self, serializer):
        """Auditoría para actualización de publicaciones"""
        instance = serializer.instance
        old_data = {
            "titulo": instance.titulo,
            "descripcion": instance.descripcion,
            "prioridad": instance.prioridad,
            "situacion_id": instance.situacion_id if instance.situacion else None,
            "encargado_id": instance.encargado_id if instance.encargado else None,
        }

        # Guardar cambios
        updated_instance = serializer.save()

        # Crear historial de modificaciones para campos específicos
        for field, old_value in old_data.items():
            new_value = getattr(updated_instance, field)
            if old_value != new_value:
                crear_historial_modificacion(
                    publicacion=updated_instance,
                    campo=field,
                    valor_anterior=old_value,
                    valor_nuevo=new_value,
                    autor=self.request.user,
                )

        # Crear auditoría
        crear_auditoria(
            usuario=self.request.user,
            accion="UPDATE",
            modulo="Publicaciones",
            descripcion=f"Actualizada publicación: {updated_instance.titulo} (ID: {updated_instance.id})",
            es_exitoso=True,
        )

    def perform_destroy(self, instance):
        """Auditoría para eliminación de publicaciones"""
        titulo = instance.titulo
        publicacion_id = instance.id

        # Eliminar la instancia
        instance.delete()

        # Crear auditoría
        crear_auditoria(
            usuario=self.request.user,
            accion="DELETE",
            modulo="Publicaciones",
            descripcion=f"Eliminada publicación: {titulo} (ID: {publicacion_id})",
            es_exitoso=True,
        )

    def retrieve(self, request, *args, **kwargs):
        """Auditar consulta de publicación específica"""
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            publicacion_id = kwargs.get("pk", "N/A")
            crear_auditoria(
                usuario=request.user,
                accion="READ",
                modulo="Publicaciones",
                descripcion=f"Consultó publicación ID: {publicacion_id}",
                es_exitoso=True,
            )

        return response

    @action(detail=False, methods=["get"], url_path="con-historial")
    def con_historial(self, request, *args, **kwargs):
        """
        Obtiene un listado de publicaciones con su historial de modificaciones anidado.
        Permite usar los filtros de PublicacionFilter (ej. ?departamento=1)
        """

        # Optimización: Pre-cargamos el historial y el autor de cada modificación
        # para evitar N+1 queries.
        historial_queryset = HistorialModificaciones.objects.select_related(
            "autor"
        ).order_by("-fecha")

        base_queryset = self.get_queryset().prefetch_related(
            Prefetch("historialmodificaciones", queryset=historial_queryset)
        )

        # Aplicamos los filtros estándar de PublicacionFilter (como ?departamento=... etc.)
        queryset = self.filter_queryset(base_queryset)

        # Aplicamos paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Serializamos la respuesta
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class EvidenciasViewSet(viewsets.ModelViewSet):
    queryset = Evidencia.objects.all()
    serializer_class = EvidenciaSerializer

    def get_permissions(self):
        if self.action in [
            "list",
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


class SituacionesPublicacionesViewSet(viewsets.ModelViewSet):
    queryset = SituacionPublicacion.objects.all()
    serializer_class = SituacionPublicacionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


class AnunciosMunicipalesViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = AnuncioMunicipal.objects.all().order_by("-fecha")
    pagination_class = DynamicPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = AnuncioMunicipalFilter
    ordering_fields = ["fecha"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return AnuncioMunicipalListSerializer
        return AnuncioMunicipalCreateUpdateSerializer

    def get_audit_object_name(self, instance):
        return f"{instance.titulo} (ID: {instance.id})"

    def perform_create(self, serializer):
        instance = serializer.save()
        crear_auditoria(
            usuario=self.request.user,
            accion="CREATE",
            modulo="Anuncios Municipales",
            descripcion=f"Creado anuncio: {self.get_audit_object_name(instance)}",
            es_exitoso=True,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        crear_auditoria(
            usuario=self.request.user,
            accion="UPDATE",
            modulo="Anuncios Municipales",
            descripcion=f"Actualizado anuncio: {self.get_audit_object_name(instance)}",
            es_exitoso=True,
        )

    def perform_destroy(self, instance):
        nombre = self.get_audit_object_name(instance)
        instance.delete()
        crear_auditoria(
            usuario=self.request.user,
            accion="DELETE",
            modulo="Anuncios Municipales",
            descripcion=f"Eliminado anuncio: {nombre}",
            es_exitoso=True,
        )


class ImagenesAnunciosViewSet(viewsets.ModelViewSet):
    queryset = ImagenAnuncio.objects.all()
    serializer_class = ImagenAnuncioSerializer

    def get_permissions(self):
        if self.action in [
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticatedOrAdmin]
        return [permission() for permission in permission_classes]
