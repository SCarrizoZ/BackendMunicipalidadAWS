from ..models import (
    Publicacion,
    Usuario,
    Categoria,
    DepartamentoMunicipal,
    Evidencia,
    JuntaVecinal,
    RespuestaMunicipal,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
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
    RespuestaMunicipalCreateUpdateSerializer,
    RespuestaMunicipalListSerializer,
    SituacionPublicacionSerializer,
    AnuncioMunicipalListSerializer,
    AnuncioMunicipalCreateUpdateSerializer,
    ImagenAnuncioSerializer,
)
from rest_framework import viewsets, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
from ..pagination import DynamicPageNumberPagination
from ..filters import PublicacionFilter, AnuncioMunicipalFilter
from ..permissions import IsAdmin, IsAuthenticatedOrAdmin
from datetime import datetime
from django.db.models import Count, Q, F
from django.db.models.functions import TruncMonth
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import textwrap
from reportlab.lib.units import inch

import matplotlib
import matplotlib.pyplot as plt

import os

matplotlib.use("Agg")  # Para que no sea necesario tener un display
from io import BytesIO
from django.conf import settings

category_colors = {
    "Seguridad": "#FF6B6B",
    "Basura": "#4ECDC4",
    "Áreas verdes": "#45B7D1",
    "Asistencia Social": "#FFA07A",
    "Mantención de Calles": "#A0522D",
    "Señales de tránsito": "#F06292",
    "Semáforos": "#FFD700",
    "Escombros": "#98D8C8",
    "Comercio ilegal": "#BA68C8",
    "Construcción irregular": "#FF8C00",
    "Contaminación": "#20B2AA",
    "Otro fuera de clasificación": "#778899",
}


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


class AnunciosMunicipalesViewSet(viewsets.ModelViewSet):
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

    return response


class ResumenEstadisticas(APIView):
    def get(self, request, *args, **kwargs):
        # Filtrar las publicaciones usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        publicaciones_filtradas = filterset.qs

        total_publicaciones = publicaciones_filtradas.count()
        total_usuarios = Usuario.objects.filter(
            id__in=publicaciones_filtradas.values("usuario_id")
        ).count()

        # Suponiendo que hay una situación llamada "Resuelto"
        problemas_resueltos = publicaciones_filtradas.filter(
            situacion__nombre="Resuelto"
        ).count()

        respuesta = {
            "publicaciones": total_publicaciones,
            "usuarios": total_usuarios,
            "problemas_resueltos": problemas_resueltos,
        }

        return Response(respuesta)


class PublicacionesPorMesyCategoria(APIView):
    def get(self, request, *args, **kwargs):
        # Filtrar las publicaciones usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        publicaciones_filtradas = filterset.qs

        datos = (
            publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
            .values("mes", "categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        # Dar formato a los datos
        meses_dict = {}
        for dato in datos:
            mes_nombre = dato["mes"].strftime("%b")  # Ene, Feb, Mar, etc.
            if mes_nombre not in meses_dict:
                meses_dict[mes_nombre] = {"name": mes_nombre}

            meses_dict[mes_nombre][dato["categoria__nombre"]] = dato["total"]

        # Convertir a lista
        respuesta = list(meses_dict.values())
        return Response(respuesta)


class PublicacionesPorCategoria(APIView):
    def get(self, request, *args, **kwargs):
        # Filtrar las publicaciones usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        publicaciones_filtradas = filterset.qs

        # Agrupar por categoría y contar publicaciones
        datos = (
            publicaciones_filtradas.values("categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("-total")
        )  # Ordenar por total en orden descendente

        # Dar formato a los datos
        respuesta = [
            {"name": dato["categoria__nombre"], "value": dato["total"]}
            for dato in datos
        ]

        return Response(respuesta)


class ResueltosPorMes(APIView):
    def get(self, request, *args, **kwargs):
        # Aplicar filtros usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        publicaciones_filtradas = filterset.qs

        # Anotar publicaciones agrupadas por mes
        publicaciones_por_mes = (
            publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
            .values("mes")
            .annotate(
                recibidos=Count("id", filter=Q(situacion__nombre="Recibido")),
                resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
                en_curso=Count("id", filter=Q(situacion__nombre="En curso")),
            )
            .order_by("mes")
        )

        # Convertir el formato para la respuesta
        respuesta = []
        for dato in publicaciones_por_mes:
            mes = dato["mes"]
            respuesta.append(
                {
                    "name": mes.strftime("%b"),
                    "recibidos": dato["recibidos"],
                    "resueltos": dato["resueltos"],
                    "en_curso": dato["en_curso"],
                }
            )

        return Response(respuesta)


# Tasa de resolución según departamento y según mes
"""
Formato de respuesta esperado:
[
    "Depto": {
        "Ene": {
            "total": 10,
            "resueltos": 8,
            "tasa_resolucion": 0.8
        },
        "Feb": {
            "total": 15,
            "resueltos": 10,
            "tasa_resolucion": 0.67
        }
    },
    "Depto2": {}
]
"""


class TasaResolucionDepartamento(APIView):
    def get(self, request):
        # Aplicar filtros usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        publicaciones_filtradas = filterset.qs

        # Anotar publicaciones agrupadas por departamento y mes
        datos = (
            publicaciones_filtradas.annotate(
                mes=TruncMonth("fecha_publicacion"),
                departamento_nombre=F("departamento__nombre"),
            )
            .values("mes", "departamento_nombre")
            .annotate(
                total=Count("id"),
                resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
            )
            .order_by("mes", "departamento_nombre")
        )

        # Calcular la tasa de resolución
        respuesta = {}
        for dato in datos:
            mes_nombre = dato["mes"].strftime("%b")  # Ene, Feb, Mar, etc.
            depto = dato["departamento_nombre"]
            total = dato["total"]
            resueltos = dato["resueltos"]
            tasa_resolucion = resueltos / total if total > 0 else 0

            if depto not in respuesta:
                respuesta[depto] = {}

            respuesta[depto][mes_nombre] = {
                "total": total,
                "resueltos": resueltos,
                "tasa_resolucion": round(tasa_resolucion, 2),
            }

        return Response(respuesta)


class PublicacionesPorJuntaVecinalAPIView(APIView):
    """
    Vista para retornar datos con formato de Junta Vecinal y categorías
    aplicando filtros a las publicaciones.
    """

    def get(self, request, *args, **kwargs):
        # Aplicar el filtro a las publicaciones
        publicaciones = Publicacion.objects.all()
        filterset = PublicacionFilter(request.GET, queryset=publicaciones)

        if not filterset.is_valid():
            return Response(
                {"error": "Filtros inválidos", "detalles": filterset.errors},
                status=400,
            )

        publicaciones_filtradas = filterset.qs

        # Calcular el total global de publicaciones filtradas
        total_publicaciones = publicaciones_filtradas.count()

        # Agregar datos por junta vecinal
        datos = []
        juntas = JuntaVecinal.objects.all()

        for junta in juntas:
            # Filtrar publicaciones asociadas a esta junta
            publicaciones_junta = publicaciones_filtradas.filter(junta_vecinal=junta)
            total_junta = publicaciones_junta.count()

            if total_junta == 0:
                continue  # Saltar juntas sin publicaciones

            # Obtener recuento por categoría
            categorias_conteo = (
                publicaciones_junta.values("categoria__nombre")
                .annotate(conteo=Count("id"))
                .order_by("-conteo")
            )

            # Construir el resultado para esta junta
            junta_data = {
                "Junta_Vecinal": {
                    "latitud": junta.latitud,
                    "longitud": junta.longitud,
                    "nombre": junta.nombre_junta,
                    "total_publicaciones": total_junta,
                    "intensidad": (
                        total_junta / total_publicaciones
                        if total_publicaciones > 0
                        else 0
                    ),
                },
            }

            # Agregar categorías dinámicamente
            for categoria in categorias_conteo:
                junta_data[categoria["categoria__nombre"]] = categoria["conteo"]

            datos.append(junta_data)

        return Response(datos, status=200)


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

    def get_permissions(self):
        if self.action in ["list", "retrieve", "por_publicacion"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "por_publicacion"]:
            return RespuestaMunicipalListSerializer
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


class SituacionesPublicacionesViewSet(viewsets.ModelViewSet):
    queryset = SituacionPublicacion.objects.all()
    serializer_class = SituacionPublicacionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedOrAdmin]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


def generate_bar_chart(publicaciones_filtradas):
    """
    Genera un gráfico de barras apiladas con los datos proporcionados.
    """
    try:
        datos = (
            publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
            .values("mes", "categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        # Formatear los datos
        meses_dict = {}
        for dato in datos:
            mes_nombre = dato["mes"].strftime("%b")  # Ene, Feb, Mar, etc.
            if mes_nombre not in meses_dict:
                meses_dict[mes_nombre] = {"name": mes_nombre}

            meses_dict[mes_nombre][dato["categoria__nombre"]] = dato["total"]

        data = list(meses_dict.values())

        meses = [item["name"] for item in data]
        categorias = list(
            set(key for item in data for key in item.keys() if key != "name")
        )
        valores_por_categoria = {categoria: [] for categoria in categorias}

        for item in data:
            for categoria in categorias:
                valores_por_categoria[categoria].append(item.get(categoria, 0))

        plt.figure(figsize=(10, 6))
        bottom_stack = [0] * len(meses)

        for categoria, valores in valores_por_categoria.items():
            plt.bar(
                meses,
                valores,
                label=categoria,
                bottom=bottom_stack,
                color=category_colors.get(categoria, "#778899"),
            )
            bottom_stack = [i + j for i, j in zip(bottom_stack, valores)]

        plt.xlabel("Meses")
        plt.ylabel("Cantidad")
        plt.title("Publicaciones por Mes y Categoría")
        plt.legend(loc="upper left")
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(e)
        return None


def generate_pie_chart(publicaciones_filtradas):
    """
    Genera un gráfico circular con colores personalizados.
    """
    try:
        # Agrupar por categoría y contar publicaciones
        datos = (
            publicaciones_filtradas.values("categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("-total")
        )  # Ordenar por total en orden descendente

        # Dar formato a los datos
        respuesta = [
            {"name": dato["categoria__nombre"], "value": dato["total"]}
            for dato in datos
        ]
        categorias = [item["name"] for item in respuesta]
        valores = [item["value"] for item in respuesta]
        colores = [
            category_colors.get(categoria, "#778899") for categoria in categorias
        ]

        # Ajustar el tamaño y diseño del gráfico
        fig, ax = plt.subplots(figsize=(10, 10))
        wedges, texts, autotexts = ax.pie(
            valores,
            labels=None,  # Ocultar las etiquetas en el gráfico principal
            colors=colores,
            autopct="%1.1f%%",
            startangle=140,
            textprops={
                "color": "white",
                "fontsize": 14,
                "weight": "bold",
            },  # Cambiar color y tamaño del texto
        )
        ax.set_title("Distribución de Publicaciones por Categoría", fontsize=16)

        # Agregar leyendas externas
        ax.legend(
            loc="center left",
            bbox_to_anchor=(1, 0.5),  # Posicionar leyendas fuera del gráfico
            labels=[f"{c} ({v})" for c, v in zip(categorias, valores)],
            fontsize=10,
        )

        buffer = BytesIO()
        plt.tight_layout()  # Asegurar que los elementos no se superpongan
        plt.savefig(buffer, format="png", bbox_inches="tight")  # Ajustar al contenido
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(e)
        return None


def generate_line_chart(publicaciones_filtradas):
    """
    Genera un gráfico de líneas con los datos proporcionados.
    Utilizar vista "ResolucionesPorMes" para obtener datos.
    """

    try:

        # Anotar publicaciones agrupadas por mes
        publicaciones_por_mes = (
            publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
            .values("mes")
            .annotate(
                recibidos=Count("id", filter=Q(situacion__nombre="Recibido")),
                resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
                en_curso=Count("id", filter=Q(situacion__nombre="En curso")),
            )
            .order_by("mes")
        )

        # Convertir el formato para la respuesta
        respuesta = []
        for dato in publicaciones_por_mes:
            mes = dato["mes"]
            respuesta.append(
                {
                    "name": mes.strftime("%b"),
                    "recibidos": dato["recibidos"],
                    "resueltos": dato["resueltos"],
                    "en_curso": dato["en_curso"],
                }
            )

        # Crear el gráfico de líneas
        meses = [item["name"] for item in respuesta]
        recibidos = [item["recibidos"] for item in respuesta]
        resueltos = [item["resueltos"] for item in respuesta]
        en_curso = [item["en_curso"] for item in respuesta]

        plt.figure(figsize=(10, 6))
        plt.plot(
            meses,
            recibidos,
            label="Recibidos",
            marker="o",
            color="#82ca9d",
            linewidth=3,
        )
        plt.plot(
            meses,
            resueltos,
            label="Resueltos",
            marker="o",
            color="#8884d8",
            linewidth=3,
        )
        plt.plot(
            meses, en_curso, label="En curso", marker="o", color="#ff8042", linewidth=3
        )

        plt.xlabel("Meses")
        plt.ylabel("Cantidad")
        plt.title("Resoluciones por Mes")
        plt.legend(loc="upper left")
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(e)
        return None


def generate_tasa_resolucion_table(publicaciones_filtradas):
    """
    Genera una tabla con la tasa de resolución por departamento y mes.
    Utilizar vista "TasaResolucionDepartamento" para obtener datos.
    """
    try:
        datos = (
            publicaciones_filtradas.annotate(
                mes=TruncMonth("fecha_publicacion"),
                departamento_nombre=F("departamento__nombre"),
            )
            .values("mes", "departamento_nombre")
            .annotate(
                total=Count("id"),
                resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
            )
            .order_by("mes", "departamento_nombre")
        )

        print("datos", datos)

        # Formatear datos para la tabla
        encabezados = [
            "Departamento",
            "Mes",
            "Total",
            "Resueltos",
            "Tasa de Resolución",
        ]
        filas = []

        for dato in datos:
            mes_nombre = dato["mes"].strftime("%b")
            depto = dato["departamento_nombre"]
            total = dato["total"]
            resueltos = dato["resueltos"]
            tasa_resolucion = round(resueltos / total, 2) if total > 0 else 0
            filas.append(
                [depto, mes_nombre, total, resueltos, f"{tasa_resolucion*100:.2f}%"]
            )

        width, height = letter  # (612, 792) en puntos
        total_width = width * 0.9  # Usar el 90% del ancho de la página

        # Distribuir el ancho total entre las columnas (proporcionalmente)
        col_widths = [
            total_width * 0.25,  # Departamento (25%)
            total_width * 0.15,  # Mes (15%)
            total_width * 0.15,  # Total (15%)
            total_width * 0.15,  # Resueltos (15%)
            total_width * 0.30,  # Tasa de Resolución (30%)
        ]

        # Crear la tabla con los nuevos anchos
        tabla = Table([encabezados] + filas, colWidths=col_widths)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return tabla
    except Exception as e:
        print(e)
        return HttpResponse("Error al generar la tabla", status=500)


@api_view(["GET"])
@permission_classes([IsAdmin])
def generate_pdf_report(request):
    try:
        comentarios = request.GET.get(
            "comentarios", "No se proporcionaron comentarios."
        )
        departamento = request.GET.get("departamento_reporte", "")
        print(departamento)
        # Aplicar filtros usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return HttpResponse("Errores en los filtros", status=400)

        publicaciones_filtradas = filterset.qs

        if publicaciones_filtradas.count() == 0:
            return HttpResponse("No hay datos para generar el reporte", status=404)

        # Generar los gráficos
        bar_chart_buffer = generate_bar_chart(publicaciones_filtradas)
        pie_chart_buffer = generate_pie_chart(publicaciones_filtradas)
        line_chart_buffer = generate_line_chart(publicaciones_filtradas)
        table_buffer = generate_tasa_resolucion_table(publicaciones_filtradas)

        if (
            bar_chart_buffer is None
            or pie_chart_buffer is None
            or line_chart_buffer is None
            or table_buffer is None
        ):
            return HttpResponse("Error al generar el gráfico", status=500)

        # Crear el PDF
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="reporte.pdf"'

        # Crear el canvas de ReportLab
        pdf = canvas.Canvas(response, pagesize=letter)

        pdf.setTitle("Reporte de Publicaciones " + datetime.now().strftime("%d-%m-%Y"))
        width, height = letter

        # Agregar página de portada
        # Agregar logo
        # Agregar página de portada
        # Calcular la posición vertical para centrar el texto
        vertical_center = height / 2

        pdf.setFont("Helvetica-Bold", 60)
        pdf.drawCentredString(width / 2, vertical_center + 70, "Reporte")
        pdf.drawCentredString(width / 2, vertical_center, "de")
        pdf.drawCentredString(width / 2, vertical_center - 70, "Publicaciones")

        # Agregar logo
        logo_path = os.path.join(
            settings.BASE_DIR,
            "static",
            "images",
            "logo.png",
        )  # Ajusta la ruta según tu estructura
        if os.path.exists(logo_path):
            pdf.drawImage(
                logo_path,
                50,  # Posición X (arriba a la izquierda)
                height - 120,  # Posición Y (arriba a la izquierda)
                width=100,  # Ancho del logo
                height=100,  # Alto del logo
                preserveAspectRatio=True,
            )

        # Fecha
        pdf.setFont("Helvetica", 24)
        months = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre",
        }
        current_date = datetime.now()
        date_text = f"{months[current_date.month]} {current_date.year}"
        pdf.drawCentredString(width / 2, vertical_center - 150, date_text)

        # Subtítulos
        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(
            width / 2, vertical_center - 200, "Municipalidad de Calama"
        )
        pdf.drawCentredString(
            width / 2,
            vertical_center - 220,
            ("Departamento: " + departamento) if departamento else "General",
        )

        # Dibujar línea decorativa en la parte inferior
        pdf.setStrokeColor(colors.yellow)
        pdf.setLineWidth(3)
        pdf.line(100, 50, width / 2, 50)
        pdf.setStrokeColor(colors.orange)
        pdf.line(width / 2, 50, width - 100, 50)

        pdf.showPage()  # Finalizar la página de portada

        # Add header
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, height - 40, "Municipalidad de Calama")

        # Add logo (adjust path as needed)
        logo_path = os.path.join(settings.BASE_DIR, "static", "images", "logo.png")
        if os.path.exists(logo_path):
            pdf.drawImage(
                logo_path,
                width - 100,
                height - 60,
                width=50,
                height=50,
                preserveAspectRatio=True,
            )

        # Add title
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(width / 2, height - 80, "Resumen")

        # Comentarios
        pdf.setFont("Helvetica-Bold", 14)  # Tamaño de letra menor
        pdf.drawString(50, height - 110, "Comentarios:")
        pdf.setFont("Helvetica", 12)

        # Dividir comentarios en líneas si son muy largos
        y_position = height - 130
        max_width = 80  # Máximo número de caracteres por línea
        comentarios = comentarios if comentarios else "No hay comentarios."
        for linea in comentarios.split("\n"):
            for wrapped_line in textwrap.wrap(linea, max_width):
                pdf.drawString(50, y_position, wrapped_line.strip())
                y_position -= 20  # Espaciado entre líneas

        # Add footer
        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            50, 30, f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

        # Draw colored lines at the bottom
        pdf.setStrokeColor(colors.yellow)
        pdf.setLineWidth(10)
        pdf.line(50, 20, width / 2, 20)
        pdf.setStrokeColor(colors.orange)
        pdf.line(width / 2, 20, width - 50, 20)

        pdf.showPage()

        # Rotar la página a horizontal
        pdf.setPageSize((height, width))

        # Agregar gráfico de barras al PDF en una página completa
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, width - 50, "Gráfico de Barras")
        bar_chart_image = ImageReader(bar_chart_buffer)
        pdf.drawImage(
            bar_chart_image,
            0,
            0,
            width=height,
            height=width - 100,
            preserveAspectRatio=True,
        )
        pdf.showPage()

        # Rotar la página a horizontal
        pdf.setPageSize((height, width))

        # Agregar gráfico circular al PDF en una página completa
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, width - 50, "Gráfico Circular")
        pie_chart_image = ImageReader(pie_chart_buffer)
        pdf.drawImage(
            pie_chart_image,
            0,
            0,
            width=height,
            height=width
            - 100,  # Mantener proporciones para el gráfico circular ajustado
            preserveAspectRatio=True,
        )
        pdf.showPage()

        # Rotar la página a horizontal
        pdf.setPageSize((height, width))

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, width - 50, "Gráfico de Líneas")

        line_chart_image = ImageReader(line_chart_buffer)
        pdf.drawImage(
            line_chart_image,
            0,
            0,
            width=height,
            height=width - 100,
            preserveAspectRatio=True,
        )
        pdf.showPage()

        # Rotar la página a horizontal
        pdf.setPageSize((height, width))

        # Tabla con la tasa de resolución por departamento y mes

        pdf.setFont("Helvetica-Bold", 16)
        title = "Tasa de Resolución por Departamento y Mes"
        pdf.drawString(50, width - 50, title)

        table = generate_tasa_resolucion_table(publicaciones_filtradas)
        if table is not None:
            # Calcular dimensiones de la tabla
            table_width = height * 0.9  # 90% del ancho de la página
            table_height = width - 100  # Alto total menos espacio para título

            # Obtener el alto real de la tabla
            w, h = table.wrapOn(pdf, table_width, table_height)

            # Calcular posición para centrar vertical y horizontalmente
            x = (height - w) / 2  # Centrar horizontalmente
            y = (width - 100 - h) / 2  # Centrar verticalmente en el espacio disponible

            # Dibujar la tabla en la posición calculada
            table.drawOn(pdf, x, y)
        pdf.showPage()

        # Finalizar el PDF
        pdf.save()

        return response
    except Exception as e:
        print(e)
        return HttpResponse("Error al generar el PDF", status=500)
