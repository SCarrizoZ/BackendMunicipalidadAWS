from ..models import (
    Publicacion,
    Usuario,
    Categoria,
    DepartamentoMunicipal,
    Evidencia,
    JuntaVecinal,
    RespuestaMunicipal,
    SituacionPublicacion,
)
from ..serializers.v1 import (
    PublicacionListSerializer,
    PublicacionCreateUpdateSerializer,
    UsuarioListSerializer,
    UsuarioSerializer,
    CustomTokenObtainPairSerializer,
    CategoriaSerializer,
    DepartamentoMunicipalSerializer,
    EvidenciaSerializer,
    JuntaVecinalSerializer,
    RespuestaMunicipalSerializer,
    SituacionPublicacionSerializer,
)
from rest_framework import viewsets, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
from ..pagination import DynamicPageNumberPagination
from ..filters import PublicacionFilter
from ..permissions import IsAdmin, IsAuthenticatedOrAdmin


# Create your views here.
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class PublicacionViewSet(viewsets.ModelViewSet):
    queryset = Publicacion.objects.all().order_by("-fecha_publicacion")
    permission_classes = [IsAuthenticatedOrAdmin]
    pagination_class = DynamicPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PublicacionFilter
    ordering_fields = ["fecha_publicacion"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return PublicacionListSerializer
        return PublicacionCreateUpdateSerializer


@api_view(["GET"])
@permission_classes([IsAdmin])
def export_to_excel(request):
    # Usa Django Filters para obtener los filtros
    publicaciones = PublicacionFilter(
        request.GET, queryset=Publicacion.objects.all()
    ).qs

    # Crear un DataFrame con los datos filtrados
    data = list(
        publicaciones.values()
    )  # Puedes especificar los campos que deseas incluir
    df = pd.DataFrame(data)

    if "fecha_publicacion" in df.columns:
        df["fecha_publicacion"] = pd.to_datetime(df["fecha_publicacion"])
        df["fecha_publicacion"] = df["fecha_publicacion"].dt.strftime("%d-%m-%Y %H:%M")

    # Generar el archivo Excel
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="publicaciones.xlsx"'

    # Guardar el DataFrame como un archivo Excel
    df.to_excel(response, index=False)

    return response


class UsuariosViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()

    def get_permissions(self):
        if self.action in ["retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return UsuarioListSerializer
        return UsuarioSerializer


class RegistroUsuarioView(APIView):
    permission_classes = [AllowAny]  # No requiere autenticación

    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoriasViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


class DepartamentosMunicipalesViewSet(viewsets.ModelViewSet):
    queryset = DepartamentoMunicipal.objects.all()
    serializer_class = DepartamentoMunicipalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


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


class JuntasVecinalesViewSet(viewsets.ModelViewSet):
    queryset = JuntaVecinal.objects.all()
    serializer_class = JuntaVecinalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


class RespuestasMunicipalesViewSet(viewsets.ModelViewSet):
    queryset = RespuestaMunicipal.objects.all()
    serializer_class = RespuestaMunicipalSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
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
