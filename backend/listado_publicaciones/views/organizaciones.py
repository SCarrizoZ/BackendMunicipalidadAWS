from rest_framework import viewsets
from ..models import (
    Categoria,
    DepartamentoMunicipal,
    UsuarioDepartamento,
    JuntaVecinal,
    RespuestaMunicipal,
    EvidenciaRespuesta,
    Usuario,
)
from ..serializers.v1 import (
    CategoriaSerializer,
    CategoriaCreateUpdateSerializer,
    DepartamentoMunicipalSerializer,
    DepartamentoMunicipalCreateUpdateSerializer,
    UsuarioDepartamentoSerializer,
    UsuarioDepartamentoCreateUpdateSerializer,
    JuntaVecinalSerializer,
    RespuestaMunicipalListSerializer,
    RespuestaMunicipalPuntuacionUpdateSerializer,
    RespuestaMunicipalCreateUpdateSerializer,
    EvidenciaRespuestaSerializer,
)
from ..pagination import DynamicPageNumberPagination
from ..filters import JuntaVecinalFilter, UsuarioRolFilter
from ..permissions import (
    IsAdmin,
    IsAuthenticatedOrAdmin,
    IsPublicationOwner,
    IsMunicipalStaff,
)
from .auditoria import AuditMixin
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from ..services.notifications import ExpoNotificationService
from ..services.geo_service import GeoService
import logging

logger = logging.getLogger(__name__)

class CategoriasViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by("-fecha_creacion")

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return CategoriaSerializer
        return CategoriaCreateUpdateSerializer

    def get_audit_module_name(self):
        return "Categorías"


class DepartamentosMunicipalesViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = DepartamentoMunicipal.objects.all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return DepartamentoMunicipalCreateUpdateSerializer
        return DepartamentoMunicipalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_audit_module_name(self):
        return "Departamentos Municipales"


class UsuarioDepartamentoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar asignaciones de usuarios a departamentos"""

    queryset = UsuarioDepartamento.objects.all()
    permission_classes = [IsAdmin | IsMunicipalStaff]

    def get_serializer_class(self):
        if self.action in ["create", "update"]:
            return UsuarioDepartamentoCreateUpdateSerializer
        return UsuarioDepartamentoSerializer

    def get_queryset(self):
        queryset = UsuarioDepartamento.objects.all()
        departamento_id = self.request.query_params.get("departamento", None)
        usuario_id = self.request.query_params.get("usuario", None)

        if departamento_id is not None:
            queryset = queryset.filter(departamento_id=departamento_id)
        if usuario_id is not None:
            queryset = queryset.filter(usuario_id=usuario_id)

        return queryset


class JuntasVecinalesViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = JuntaVecinal.objects.all()
    serializer_class = JuntaVecinalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "mas_cercana", "cercanas"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_audit_module_name(self):
        return "Juntas Vecinales"

    @action(detail=False, methods=["get"], url_path="mas-cercana")
    def mas_cercana(self, request):
        """
        Endpoint para obtener la junta vecinal más cercana a unas coordenadas específicas.
        Parámetros: ?latitud=X&longitud=Y
        """
        try:
            latitud = request.query_params.get("latitud")
            longitud = request.query_params.get("longitud")

            if not latitud or not longitud:
                return Response(
                    {"error": "Se requieren los parámetros latitud y longitud"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Usar GeoService
            junta_mas_cercana = GeoService.encontrar_junta_vecinal_mas_cercana(
                float(latitud), float(longitud)
            )

            if not junta_mas_cercana:
                return Response(
                    {"error": "No se encontraron juntas vecinales cercanas"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Calcular la distancia
            distancia = GeoService.calcular_distancia_haversine(
                float(latitud),
                float(longitud),
                junta_mas_cercana.latitud,
                junta_mas_cercana.longitud,
            )

            serializer = self.get_serializer(junta_mas_cercana)
            response_data = serializer.data
            response_data["distancia_km"] = round(distancia, 2)

            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError:
            return Response(
                {"error": "Las coordenadas deben ser números válidos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Error interno: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="cercanas")
    def cercanas(self, request):
        """
        Endpoint para obtener las N juntas vecinales más cercanas a unas coordenadas.
        Parámetros: ?latitud=X&longitud=Y&limite=N (por defecto 5)
        """
        try:
            latitud = request.query_params.get("latitud")
            longitud = request.query_params.get("longitud")
            limite = int(request.query_params.get("limite", 5))

            if not latitud or not longitud:
                return Response(
                    {"error": "Se requieren los parámetros latitud y longitud"},
                    status=status.HTTP_400_BAD_REQUEST,
                )



            lat_float = float(latitud)
            lon_float = float(longitud)

            # Obtener todas las juntas vecinales habilitadas
            juntas_vecinales = JuntaVecinal.objects.filter(estado="habilitado")

            if not juntas_vecinales.exists():
                return Response(
                    {"error": "No hay juntas vecinales disponibles"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Calcular distancias y ordenar
            juntas_con_distancia = []
            for junta in juntas_vecinales:
                distancia = GeoService.calcular_distancia_haversine(
                    lat_float, lon_float, junta.latitud, junta.longitud
                )
                juntas_con_distancia.append({"junta": junta, "distancia": distancia})

            # Ordenar por distancia y tomar solo el límite especificado
            juntas_ordenadas = sorted(
                juntas_con_distancia, key=lambda x: x["distancia"]
            )[:limite]

            # Serializar los resultados
            resultados = []
            for item in juntas_ordenadas:
                serializer = self.get_serializer(item["junta"])
                junta_data = serializer.data
                junta_data["distancia_km"] = round(item["distancia"], 2)
                resultados.append(junta_data)

            return Response(
                {
                    "total": len(resultados),
                    "coordenadas_consulta": {
                        "latitud": lat_float,
                        "longitud": lon_float,
                    },
                    "juntas_cercanas": resultados,
                },
                status=status.HTTP_200_OK,
            )

        except ValueError:
            return Response(
                {"error": "Las coordenadas y límite deben ser números válidos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Error interno: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class JuntaVecinalPaginatedViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = JuntaVecinal.objects.all().order_by("-fecha_creacion")
    serializer_class = JuntaVecinalSerializer
    pagination_class = DynamicPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = JuntaVecinalFilter
    search_fields = ["nombre_junta", "nombre_calle"]
    ordering_fields = ["fecha_creacion", "estado", "nombre_junta"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_audit_module_name(self):
        return "Juntas Vecinales Paginadas"


class RespuestasMunicipalesViewSet(viewsets.ModelViewSet):
    queryset = RespuestaMunicipal.objects.all()

    def get_permissions(self):
        if self.action in ["list", "retrieve", "por_publicacion"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        elif self.action == "puntuar":
            permission_classes = [IsPublicationOwner]
        else:
            permission_classes = [IsAdmin | IsMunicipalStaff]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "por_publicacion"]:
            return RespuestaMunicipalListSerializer
        elif self.action == "puntuar":
            return RespuestaMunicipalPuntuacionUpdateSerializer
        return RespuestaMunicipalCreateUpdateSerializer

    @action(
        detail=False,
        methods=["get"],
        url_path="por-publicacion/(?P<publicacion_id>[^/.]+)",
    )
    def por_publicacion(self, request, publicacion_id=None):
        """
        Endpoint personalizado para obtener todas las respuestas municipales
        asociadas a una publicación específica.
        """
        respuestas = self.queryset.filter(publicacion_id=publicacion_id)

        if not respuestas.exists():
            return Response(
                {"detail": "No se encontraron respuestas para esta publicación."},
                status=404,
            )

        serializer = self.get_serializer(respuestas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="puntuar")
    def puntuar(self, request, pk=None):
        """
        Permite al autor de la publicación original calificar la respuesta municipal.
        """
        respuesta = self.get_object()
        serializer = self.get_serializer(respuesta, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Al crear respuesta, enviar notificación automáticamente
        """
        respuesta = serializer.save()

        logger.info(f"📝 Nueva respuesta para: {respuesta.publicacion.codigo}")

        # Enviar notificación push
        try:
            ExpoNotificationService.notificar_nueva_respuesta(
                publicacion_id=respuesta.publicacion.id
            )
        except Exception as e:
            # No fallar la creación si falla la notificación
            logger.error(f"Error enviando notificación: {str(e)}")

    def perform_update(self, serializer):
        """
        Al actualizar, verificar cambio de estado
        """
        instance = self.get_object()
        estado_anterior = instance.situacion_posterior

        respuesta = serializer.save()

        # Si cambió estado, notificar
        if respuesta.situacion_posterior != estado_anterior:
            try:
                ExpoNotificationService.notificar_cambio_estado(
                    publicacion_id=respuesta.publicacion.id,
                    nuevo_estado=respuesta.situacion_posterior,
                )
            except Exception as e:
                logger.error(f"Error enviando notificación: {str(e)}")


class EvidenciaRespuestaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar evidencias de respuestas municipales"""

    queryset = EvidenciaRespuesta.objects.all()
    serializer_class = EvidenciaRespuestaSerializer
    permission_classes = [IsAuthenticatedOrAdmin]

    def get_queryset(self):
        queryset = EvidenciaRespuesta.objects.all()
        respuesta_id = self.request.query_params.get("respuesta", None)

        if respuesta_id is not None:
            queryset = queryset.filter(respuesta_id=respuesta_id)

        return queryset


class UsuariosViewSet(AuditMixin, viewsets.ModelViewSet):
    from ..serializers.v1 import UsuarioListSerializer, UsuarioSerializer  # Import local
    
    queryset = Usuario.objects.all().order_by("-fecha_registro")
    filterset_class = UsuarioRolFilter
    filter_backends = (DjangoFilterBackend,)

    def get_permissions(self):
        if self.action in ["retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        from ..serializers.v1 import UsuarioListSerializer, UsuarioSerializer
        if self.action in ["list", "retrieve"]:
            return UsuarioListSerializer
        return UsuarioSerializer

    def get_audit_module_name(self):
        return "Usuarios"

    def get_audit_object_name(self, instance):
        return f"{instance.nombre} (ID: {instance.id})"
