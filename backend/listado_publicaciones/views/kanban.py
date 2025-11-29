from rest_framework import viewsets
from ..models import Tablero, Columna, Tarea, Comentario, Publicacion
from ..serializers.v1 import (
    TableroSerializer,
    ColumnaSerializer,
    TareaListSerializer,
    TareaCreateUpdateSerializer,
    ComentarioSerializer,
)
from listado_publicaciones.permissions import IsAdmin, IsAuthenticatedOrAdmin
from rest_framework.decorators import action
from rest_framework.response import Response

class TableroViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar tableros Kanban"""

    queryset = Tablero.objects.all().order_by("-fecha_creacion")
    serializer_class = TableroSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = Tablero.objects.all().order_by("-fecha_creacion")
        departamento_id = self.request.query_params.get("departamento", None)

        if departamento_id is not None:
            queryset = queryset.filter(departamento_id=departamento_id)

        return queryset


class ColumnaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar columnas del tablero Kanban"""

    queryset = Columna.objects.all().order_by("fecha_creacion")
    serializer_class = ColumnaSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = Columna.objects.all().order_by("fecha_creacion")
        tablero_id = self.request.query_params.get("tablero", None)

        if tablero_id is not None:
            queryset = queryset.filter(tablero_id=tablero_id)

        return queryset


class TareaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar tareas del tablero Kanban"""

    queryset = Tarea.objects.all().order_by("-fecha_creacion")
    permission_classes = [IsAuthenticatedOrAdmin]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return TareaListSerializer
        return TareaCreateUpdateSerializer

    def get_queryset(self):
        queryset = Tarea.objects.all().order_by("-fecha_creacion")
        columna_id = self.request.query_params.get("columna", None)
        encargado_id = self.request.query_params.get("encargado", None)
        categoria_id = self.request.query_params.get("categoria", None)

        if columna_id is not None:
            queryset = queryset.filter(columna_id=columna_id)
        if encargado_id is not None:
            queryset = queryset.filter(encargado_id=encargado_id)
        if categoria_id is not None:
            queryset = queryset.filter(categoria_id=categoria_id)

        return queryset

    @action(detail=True, methods=["post"])
    def agregar_publicacion(self, request, pk=None):
        """Agregar una publicación a la tarea"""
        tarea = self.get_object()
        publicacion_id = request.data.get("publicacion_id")

        try:
            publicacion = Publicacion.objects.get(id=publicacion_id)
            tarea.publicaciones.add(publicacion)
            return Response({"status": "Publicación agregada"})
        except Publicacion.DoesNotExist:
            return Response({"error": "Publicación no encontrada"}, status=404)

    @action(detail=True, methods=["post"])
    def remover_publicacion(self, request, pk=None):
        """Remover una publicación de la tarea"""
        tarea = self.get_object()
        publicacion_id = request.data.get("publicacion_id")

        try:
            publicacion = Publicacion.objects.get(id=publicacion_id)
            tarea.publicaciones.remove(publicacion)
            return Response({"status": "Publicación removida"})
        except Publicacion.DoesNotExist:
            return Response({"error": "Publicación no encontrada"}, status=404)


class ComentarioViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar comentarios de tareas"""

    queryset = Comentario.objects.all().order_by("-fecha_creacion")
    serializer_class = ComentarioSerializer
    permission_classes = [IsAuthenticatedOrAdmin]

    def get_queryset(self):
        queryset = Comentario.objects.all().order_by("-fecha_creacion")
        tarea_id = self.request.query_params.get("tarea", None)
        usuario_id = self.request.query_params.get("usuario", None)

        if tarea_id is not None:
            queryset = queryset.filter(tarea_id=tarea_id)
        if usuario_id is not None:
            queryset = queryset.filter(usuario_id=usuario_id)

        return queryset

    def perform_create(self, serializer):
        # Asignar automáticamente el usuario actual al comentario
        serializer.save(usuario=self.request.user)
