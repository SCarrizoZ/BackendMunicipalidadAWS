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
from datetime import datetime


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
    # Aplicar filtros de Django Filters a las publicaciones
    publicaciones = PublicacionFilter(
        request.GET, queryset=Publicacion.objects.all()
    ).qs

    # Crear un DataFrame para las publicaciones
    data = list(publicaciones.values())
    df_publicaciones = pd.DataFrame(data)

    if "fecha_publicacion" in df_publicaciones.columns:
        df_publicaciones["fecha_publicacion"] = pd.to_datetime(
            df_publicaciones["fecha_publicacion"]
        ).dt.tz_localize(None)

    # Obtener datos relacionados y crear DataFrames para cada relación
    categorias = Categoria.objects.all()
    departamentos = DepartamentoMunicipal.objects.all()
    juntas_vecinales = JuntaVecinal.objects.all()
    situaciones = SituacionPublicacion.objects.all()

    usuarios = Usuario.objects.all().values(
        "id",
        "nombre",
        "email",
        "numero_telefonico_movil",
        "fecha_registro",
        "esta_activo",
    )
    df_usuarios = pd.DataFrame(list(usuarios))

    if "fecha_registro" in df_usuarios.columns:
        df_usuarios["fecha_registro"] = pd.to_datetime(
            df_usuarios["fecha_registro"]
        ).dt.tz_localize(None)

    evidencias = Evidencia.objects.all()
    df_evidencias = pd.DataFrame(evidencias.values())

    if "fecha" in df_evidencias.columns:
        df_evidencias["fecha"] = pd.to_datetime(df_evidencias["fecha"]).dt.tz_localize(
            None
        )

    df_categorias = pd.DataFrame(list(categorias.values()))
    df_juntas_vecinales = pd.DataFrame(list(juntas_vecinales.values()))
    df_situaciones = pd.DataFrame(list(situaciones.values()))
    df_departamentos = pd.DataFrame(list(departamentos.values()))
    # Generar la respuesta HTTP para la descarga
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="publicaciones_{datetime.now().strftime("%d-%m-%Y_%H:%M")}.xlsx"'
    )

    # Escribir los DataFrames en múltiples hojas de Excel
    with pd.ExcelWriter(response, engine="openpyxl") as writer:
        # Hoja principal: Publicaciones
        df_publicaciones.to_excel(writer, sheet_name="Publicaciones", index=False)

        # Hojas adicionales con relaciones
        df_usuarios.to_excel(writer, sheet_name="Usuarios", index=False)
        df_categorias.to_excel(writer, sheet_name="Categorías", index=False)
        df_departamentos.to_excel(writer, sheet_name="Departamentos", index=False)
        df_juntas_vecinales.to_excel(writer, sheet_name="Juntas Vecinales", index=False)
        df_situaciones.to_excel(writer, sheet_name="Situaciones", index=False)
        df_evidencias.to_excel(writer, sheet_name="Evidencias", index=False)

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
