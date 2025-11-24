from ..models import (
    Publicacion,
    Usuario,
    Categoria,
    DepartamentoMunicipal,
    UsuarioDepartamento,
    Evidencia,
    EvidenciaRespuesta,
    JuntaVecinal,
    RespuestaMunicipal,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
    HistorialModificaciones,
    Auditoria,
    Tablero,
    Columna,
    Tarea,
    Comentario,
    DispositivoNotificacion,
)
from ..serializers.v1 import (
    PublicacionListSerializer,
    PublicacionCreateUpdateSerializer,
    PublicacionConHistorialSerializer,
    UsuarioListSerializer,
    UsuarioSerializer,
    CustomTokenObtainPairSerializer,
    CategoriaSerializer,
    CategoriaCreateUpdateSerializer,
    DepartamentoMunicipalSerializer,
    DepartamentoMunicipalCreateUpdateSerializer,
    UsuarioDepartamentoSerializer,
    UsuarioDepartamentoCreateUpdateSerializer,
    EvidenciaSerializer,
    EvidenciaRespuestaSerializer,
    JuntaVecinalSerializer,
    RespuestaMunicipalCreateUpdateSerializer,
    RespuestaMunicipalListSerializer,
    RespuestaMunicipalPuntuacionUpdateSerializer,
    SituacionPublicacionSerializer,
    AnuncioMunicipalListSerializer,
    AnuncioMunicipalCreateUpdateSerializer,
    ImagenAnuncioSerializer,
    HistorialModificacionesSerializer,
    AuditoriaSerializer,
    TableroSerializer,
    ColumnaSerializer,
    TareaListSerializer,
    TareaCreateUpdateSerializer,
    ComentarioSerializer,
    DispositivoNotificacionSerializer,
)
from ..services.notifications import ExpoNotificationService
from rest_framework import viewsets, status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
from ..pagination import DynamicPageNumberPagination
from ..filters import PublicacionFilter, AnuncioMunicipalFilter, UsuarioRolFilter, JuntaVecinalFilter
from ..permissions import (
    IsAdmin,
    IsAuthenticatedOrAdmin,
    IsPublicationOwner,
    IsMunicipalStaff,
)
from datetime import datetime
from django.utils import timezone
from django.db.models import Count, Q, F, Prefetch, Avg
from django.db.models.functions import TruncMonth
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import textwrap

import matplotlib
import matplotlib.pyplot as plt

import os

matplotlib.use("Agg")  # Para que no sea necesario tener un display
from io import BytesIO
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

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

meses_espanol = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


# Create your views here.
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


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # Si el login fue exitoso, actualizar el último acceso
        if response.status_code == 200:
            try:
                # Obtener el usuario por RUT (USERNAME_FIELD)
                rut = request.data.get("rut")
                if rut:
                    usuario = Usuario.objects.get(rut=rut)
                    usuario.ultimo_acceso = timezone.now()
                    usuario.save(update_fields=["ultimo_acceso"])

                    # Auditoría de LOGIN exitoso
                    crear_auditoria(
                        usuario=usuario,
                        accion="LOGIN",
                        modulo="Autenticación",
                        descripcion=f"Inicio de sesión exitoso desde IP: {self.get_client_ip(request)}",
                        es_exitoso=True,
                    )
            except Usuario.DoesNotExist:
                pass  # No hacer nada si el usuario no existe
        else:
            # Auditoría de LOGIN fallido
            rut = request.data.get("rut", "Desconocido")
            try:
                usuario = Usuario.objects.get(rut=rut)
                crear_auditoria(
                    usuario=usuario,
                    accion="LOGIN",
                    modulo="Autenticación",
                    descripcion=f"Intento de inicio de sesión fallido desde IP: {self.get_client_ip(request)}",
                    es_exitoso=False,
                )
            except Usuario.DoesNotExist:
                # Para usuarios que no existen, no crear auditoría específica
                pass

        return response

    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


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

    """
    No considerado ya que registra las acciones de los vecinos y el enfoque debe estar en los funcionarios.
    Consultar con el cliente

    def perform_create(self, serializer):
        Auditoría para creación de publicaciones
        instance = serializer.save()

        # Crear auditoría
        crear_auditoria(
            usuario=self.request.user,
            accion="CREATE",
            modulo="Publicaciones",
            descripcion=f"Creada publicación: {instance.titulo} (ID: {instance.id})",
            es_exitoso=True,
        )

    """

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
            mes_nombre = meses_espanol[dato["mes"].month]  # Ene, Feb, Mar, etc.
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
                    "name": meses_espanol[mes.month],
                    "recibidos": dato["recibidos"],
                    "resueltos": dato["resueltos"],
                    "en_curso": dato["en_curso"],
                }
            )

        return Response(respuesta)


# Tasa de resolución según departamento y según mes
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
            mes_nombre = meses_espanol[dato["mes"].month]  # Ene, Feb, Mar, etc.
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
    Vista para retornar datos con formato de Junta Vecinal y métricas.
    ACTUALIZADO: Cálculo de criticidad simplificado (Volumen + Retraso Legal).
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
        total_publicaciones_global = publicaciones_filtradas.count()

        datos = []
        juntas = JuntaVecinal.objects.all()
        ahora = timezone.now()
        DIAS_HABILES_LIMITE = 20

        for junta in juntas:
            # Filtrar publicaciones de esta junta
            publicaciones_junta = publicaciones_filtradas.filter(junta_vecinal=junta)
            total_junta = publicaciones_junta.count()

            if total_junta == 0:
                continue

            # --- CÁLCULO DE CRITICIDAD SIMPLIFICADO ---
            
            # 1. Identificar Pendientes
            publicaciones_pendientes_qs = publicaciones_junta.filter(
                Q(situacion_id=4) | Q(situacion__isnull=True)
            )
            cantidad_pendientes = publicaciones_pendientes_qs.count()

            # 2. Calcular Vencidas (Pendientes > 20 días hábiles)
            cantidad_vencidas = 0
            dias_pendientes_acumulados = []

            for pub in publicaciones_pendientes_qs:
                # Días naturales (solo informativo)
                dias_naturales = (ahora - pub.fecha_publicacion).days
                dias_pendientes_acumulados.append(dias_naturales)

                # Días hábiles (criterio legal)
                try:
                    # pd.bdate_range cuenta los días laborales entre fechas
                    dias_habiles = len(pd.bdate_range(start=pub.fecha_publicacion.date(), end=ahora.date())) - 1
                    if dias_habiles > DIAS_HABILES_LIMITE:
                        cantidad_vencidas += 1
                except Exception:
                    pass

            tiempo_promedio_pendiente = (
                sum(dias_pendientes_acumulados) // len(dias_pendientes_acumulados)
                if dias_pendientes_acumulados
                else 0
            )

            # --- FÓRMULA DE ÍNDICE (0-100) ---
            # Factor Volumen (50%): Normalizado a 20 publicaciones máx.
            factor_volumen = min(total_junta / 20, 1) * 100
            
            # Factor Retraso (50%): % de publicaciones totales que están vencidas
            porcentaje_vencidas = (
                (cantidad_vencidas / total_junta) * 100 if total_junta > 0 else 0
            )

            indice_criticidad = (factor_volumen * 0.5) + (porcentaje_vencidas * 0.5)

            # --- 2. CÁLCULO DE SATISFACCIÓN (NUEVO) ---
            
            # Buscar respuestas asociadas a las publicaciones de esta junta que tengan puntuación (>0)
            respuestas_puntuadas = RespuestaMunicipal.objects.filter(
                publicacion__in=publicaciones_junta,
                puntuacion__gt=0
            )
            
            cantidad_valoraciones = respuestas_puntuadas.count()
            promedio_calificacion = 0.0
            
            if cantidad_valoraciones > 0:
                promedio_calificacion = respuestas_puntuadas.aggregate(promedio=Avg('puntuacion'))['promedio'] or 0.0

            # Obtener datos extra (categorías, última publicación)
            ultima_publicacion = publicaciones_junta.order_by("-fecha_publicacion").first()
            categorias_conteo = (
                publicaciones_junta.values("categoria__nombre")
                .annotate(conteo=Count("id"))
                .order_by("-conteo")
            )

            # Construir respuesta manteniendo compatibilidad con frontend
            junta_data = {
                "Junta_Vecinal": {
                    "latitud": junta.latitud,
                    "longitud": junta.longitud,
                    "nombre": junta.nombre_junta,
                    "total_publicaciones": total_junta,
                    "intensidad": (
                        total_junta / total_publicaciones_global
                        if total_publicaciones_global > 0
                        else 0
                    ),
                    "pendientes": cantidad_pendientes,
                    "urgentes": cantidad_vencidas, # Reemplazamos urgentes por vencidas para visualización
                    "indice_criticidad": round(indice_criticidad, 2),
                    "porcentaje_pendientes": round((cantidad_pendientes / total_junta * 100), 2),
                    "porcentaje_urgentes": round(porcentaje_vencidas, 2), # Refleja % vencidas
                    # Métricas de Satisfacción (NUEVO)
                    "calificacion_promedio": round(promedio_calificacion, 1), # Ej: 4.5
                    "total_valoraciones": cantidad_valoraciones,
                },
                "tiempo_promedio_pendiente": f"{tiempo_promedio_pendiente} días",
                "ultima_publicacion": (
                    ultima_publicacion.fecha_publicacion.isoformat()
                    if ultima_publicacion
                    else None
                ),
            }

            for categoria in categorias_conteo:
                junta_data[categoria["categoria__nombre"]] = categoria["conteo"]

            datos.append(junta_data)

        return Response(datos, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def junta_mas_critica(request):
    """
    Endpoint para obtener la junta vecinal más crítica basado en:
    1. Cantidad de publicaciones (Volumen)
    2. Cantidad de publicaciones que excedieron 20 días hábiles (Legal)
    """
    # Aplicar el filtro a las publicaciones
    publicaciones = Publicacion.objects.all()
    filterset = PublicacionFilter(request.GET, queryset=publicaciones)

    if not filterset.is_valid():
        return Response(
            {"error": "Filtros inválidos", "detalles": filterset.errors},
            status=400,
        )

    publicaciones_filtradas = filterset.qs
    juntas_criticidad = []
    ahora = timezone.now()
    
    # Límite legal de días hábiles
    DIAS_HABILES_LIMITE = 20

    for junta in JuntaVecinal.objects.all():
        publicaciones_junta = publicaciones_filtradas.filter(junta_vecinal=junta)
        total_junta = publicaciones_junta.count()

        if total_junta == 0:
            continue

        # 1. Obtener publicaciones pendientes (Situación 4 o Nula)
        publicaciones_pendientes_qs = publicaciones_junta.filter(
            Q(situacion_id=4) | Q(situacion__isnull=True)
        )
        
        cantidad_pendientes = publicaciones_pendientes_qs.count()

        # 2. Calcular cuántas han excedido el tiempo de respuesta (20 días hábiles)
        cantidad_vencidas = 0
        tiempo_promedio_pendiente = 0
        dias_pendientes_acumulados = []

        if publicaciones_pendientes_qs.exists():
            for pub in publicaciones_pendientes_qs:
                # Calcular días naturales para el promedio (mantener métrica informativa)
                dias_naturales = (ahora - pub.fecha_publicacion).days
                dias_pendientes_acumulados.append(dias_naturales)

                # Calcular días HÁBILES para la criticidad legal
                # Usamos pandas bdate_range que ya excluye fines de semana
                # Nota: Para feriados específicos se requeriría una lista de 'holidays'
                try:
                    dias_habiles = len(pd.bdate_range(start=pub.fecha_publicacion.date(), end=ahora.date())) - 1
                    if dias_habiles > DIAS_HABILES_LIMITE:
                        cantidad_vencidas += 1
                except Exception:
                    # Fallback simple si falla pandas: 20 días hábiles aprox 28 días naturales
                    if dias_naturales > 28:
                        cantidad_vencidas += 1

            tiempo_promedio_pendiente = (
                sum(dias_pendientes_acumulados) // len(dias_pendientes_acumulados)
                if dias_pendientes_acumulados else 0
            )

        # --- NUEVA LÓGICA DE CÁLCULO ---
        
        # Factor 1: Volumen (50% del índice)
        # Normalizamos: Si tiene 20 o más publicaciones, obtiene el puntaje máximo de volumen
        factor_volumen = min(total_junta / 20, 1) * 100

        # Factor 2: Retraso Legal (50% del índice)
        # Porcentaje de las publicaciones totales de la junta que están vencidas
        porcentaje_vencidas = (
            (cantidad_vencidas / total_junta) * 100 if total_junta > 0 else 0
        )
        
        # Índice Final
        indice_criticidad = (factor_volumen * 0.5) + (porcentaje_vencidas * 0.5)

        # Mantenemos las claves que espera el frontend, pero actualizamos los valores
        # Agregamos 'cantidad_vencidas' como dato extra si el frontend decide usarlo a futuro
        juntas_criticidad.append(
            {
                "junta": {
                    "id": junta.id,
                    "nombre": junta.nombre_junta
                    or f"{junta.nombre_calle} {junta.numero_calle}",
                    "latitud": junta.latitud,
                    "longitud": junta.longitud,
                },
                "metricas": {
                    "total_publicaciones": total_junta,
                    "publicaciones_pendientes": cantidad_pendientes,
                    "casos_urgentes": cantidad_vencidas, # Reutilizamos campo para visualización o creamos uno nuevo
                    "cantidad_vencidas_legal": cantidad_vencidas, # Campo nuevo explícito
                    "tiempo_promedio_pendiente": tiempo_promedio_pendiente,
                    "porcentaje_pendientes": round((cantidad_pendientes/total_junta)*100, 2),
                    "porcentaje_urgentes": round(porcentaje_vencidas, 2), # Aquí ponemos el % de vencidas
                    "indice_criticidad": round(indice_criticidad, 2),
                },
            }
        )

    # Ordenar por índice de criticidad (mayor a menor)
    juntas_criticidad.sort(
        key=lambda x: x["metricas"]["indice_criticidad"], reverse=True
    )

    # Estadísticas generales actualizadas
    estadisticas = {
        "total_juntas_analizadas": len(juntas_criticidad),
        "junta_mas_critica": juntas_criticidad[0] if juntas_criticidad else None,
        "top_5_criticas": juntas_criticidad[:5],
        "promedio_criticidad": (
            round(
                sum(j["metricas"]["indice_criticidad"] for j in juntas_criticidad)
                / len(juntas_criticidad),
                2,
            )
            if juntas_criticidad
            else 0
        ),
        "criterios_calculo": {
            "factor_volumen": "50% del índice (Basado en total de publicaciones)",
            "factor_retraso_legal": "50% del índice (Publicaciones que exceden 20 días hábiles)",
            "nota": "Cálculo simplificado según requerimiento legal",
            "rango_indice": "0-100 (mayor = más crítico)",
        },
    }

    return Response(estadisticas, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def publicaciones_resueltas_por_junta_vecinal(request):
    """
    Vista para retornar datos de publicaciones RESUELTAS por junta vecinal (Mapa de Frío)
    - Publicaciones resueltas son las que NO tienen situación inicial (4) o null
    - Calcula eficiencia, tiempo promedio de resolución y otras métricas positivas
    """
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

        # Calcular publicaciones resueltas (NO situación inicial = 4 o null)
        publicaciones_resueltas = publicaciones_junta.exclude(
            Q(situacion_id=4) | Q(situacion__isnull=True)
        ).count()

        # Calcular eficiencia (porcentaje de publicaciones resueltas)
        eficiencia = (
            (publicaciones_resueltas / total_junta) * 100 if total_junta > 0 else 0
        )

        # Solo incluir juntas con al menos alguna publicación resuelta
        if publicaciones_resueltas == 0:
            continue

        # Calcular casos de alta prioridad resueltos
        casos_alta_prioridad_resueltos = (
            publicaciones_junta.filter(prioridad="alta")
            .exclude(Q(situacion_id=4) | Q(situacion__isnull=True))
            .count()
        )

        # Calcular tiempo promedio de resolución (días desde publicación hasta resolución)
        publicaciones_resueltas_qs = publicaciones_junta.exclude(
            Q(situacion_id=4) | Q(situacion__isnull=True)
        )

        tiempo_promedio_resolucion = 0
        if publicaciones_resueltas_qs.exists():
            # Para este ejemplo, usamos la fecha de la respuesta municipal más reciente
            # En un caso real, necesitarías un campo de fecha_resolucion en el modelo
            dias_resolucion = []

            for pub in publicaciones_resueltas_qs:
                # Buscar la respuesta municipal asociada para obtener fecha de resolución
                respuesta = RespuestaMunicipal.objects.filter(publicacion=pub).first()
                if respuesta:
                    dias = (respuesta.fecha - pub.fecha_publicacion).days
                    if (
                        dias >= 0
                    ):  # Solo contar si la resolución fue después de la publicación
                        dias_resolucion.append(dias)

            tiempo_promedio_resolucion = (
                sum(dias_resolucion) // len(dias_resolucion) if dias_resolucion else 0
            )

        # Obtener la última resolución de esta junta
        ultima_respuesta = (
            RespuestaMunicipal.objects.filter(publicacion__junta_vecinal=junta)
            .order_by("-fecha")
            .first()
        )
        fecha_ultima_resolucion = ultima_respuesta.fecha if ultima_respuesta else None

        # Calcular intensidad de frío (eficiencia normalizada)
        intensidad_frio = eficiencia / 100  # Normalizar a 0-1

        # Obtener recuento por categoría (solo resueltas)
        categorias_conteo = (
            publicaciones_resueltas_qs.values("categoria__nombre")
            .annotate(conteo=Count("id"))
            .order_by("-conteo")
        )

        # Construir el resultado para esta junta
        junta_data = {
            "Junta_Vecinal": {
                "latitud": junta.latitud,
                "longitud": junta.longitud,
                "nombre": junta.nombre_junta
                or f"{junta.nombre_calle} {junta.numero_calle}",
                "total_publicaciones": total_junta,
                "total_resueltas": publicaciones_resueltas,
                "intensidad_frio": round(intensidad_frio, 2),
                "eficiencia": round(eficiencia, 2),
                "casos_alta_prioridad_resueltos": casos_alta_prioridad_resueltos,
                "intensidad": (
                    total_junta / total_publicaciones if total_publicaciones > 0 else 0
                ),
            },
            "tiempo_promedio_resolucion": f"{tiempo_promedio_resolucion} días",
            "ultima_resolucion": (
                fecha_ultima_resolucion.isoformat() if fecha_ultima_resolucion else None
            ),
        }

        # Agregar categorías dinámicamente (solo resueltas)
        for categoria in categorias_conteo:
            junta_data[categoria["categoria__nombre"]] = categoria["conteo"]

        datos.append(junta_data)

    # Ordenar por eficiencia (mayor a menor)
    datos.sort(key=lambda x: x["Junta_Vecinal"]["eficiencia"], reverse=True)

    return Response(datos, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def junta_mas_eficiente(request):
    """
    Endpoint para obtener la junta vecinal más eficiente.
    ACTUALIZADO: Eficiencia basada en Volumen y Cumplimiento de Plazo Legal (20 días hábiles).
    """
    publicaciones = Publicacion.objects.all()
    filterset = PublicacionFilter(request.GET, queryset=publicaciones)

    if not filterset.is_valid():
        return Response(
            {"error": "Filtros inválidos", "detalles": filterset.errors},
            status=400,
        )

    publicaciones_filtradas = filterset.qs
    juntas_eficiencia = []
    DIAS_HABILES_LIMITE = 20

    for junta in JuntaVecinal.objects.all():
        publicaciones_junta = publicaciones_filtradas.filter(junta_vecinal=junta)
        total_junta = publicaciones_junta.count()

        if total_junta == 0:
            continue

        # Filtrar solo resueltas
        publicaciones_resueltas_qs = publicaciones_junta.exclude(
            Q(situacion_id=4) | Q(situacion__isnull=True)
        )
        total_resueltas = publicaciones_resueltas_qs.count()

        # Calcular cuántas se resolvieron DENTRO del plazo legal
        resueltas_en_plazo = 0
        dias_resolucion_acumulados = 0

        if publicaciones_resueltas_qs.exists():
            for pub in publicaciones_resueltas_qs:
                respuesta = RespuestaMunicipal.objects.filter(publicacion=pub).first()
                if respuesta:
                    # Días naturales para promedio informativo
                    dias_naturales = (respuesta.fecha - pub.fecha_publicacion).days
                    if dias_naturales >= 0:
                        dias_resolucion_acumulados += dias_naturales

                    # Días hábiles para métrica de eficiencia
                    try:
                        dias_habiles = len(pd.bdate_range(start=pub.fecha_publicacion.date(), end=respuesta.fecha.date())) - 1
                        if dias_habiles <= DIAS_HABILES_LIMITE:
                            resueltas_en_plazo += 1
                    except Exception:
                        pass
        
        tiempo_promedio_resolucion = (
            dias_resolucion_acumulados // total_resueltas if total_resueltas > 0 else 0
        )

        # --- FÓRMULA DE EFICIENCIA SIMPLIFICADA ---
        
        # Factor Volumen (50%): Manejar alto volumen es eficiente
        factor_volumen = min(total_junta / 20, 1) * 100

        # Factor Cumplimiento Legal (50%): 
        # Porcentaje del TOTAL de publicaciones que fueron resueltas en plazo.
        # (Usamos total_junta para penalizar las que se quedaron sin resolver)
        porcentaje_cumplimiento = (
            (resueltas_en_plazo / total_junta) * 100 if total_junta > 0 else 0
        )

        indice_eficiencia = (factor_volumen * 0.5) + (porcentaje_cumplimiento * 0.5)

        if total_resueltas > 0:
            juntas_eficiencia.append(
                {
                    "junta": {
                        "id": junta.id,
                        "nombre": junta.nombre_junta
                        or f"{junta.nombre_calle} {junta.numero_calle}",
                        "latitud": junta.latitud,
                        "longitud": junta.longitud,
                    },
                    "metricas": {
                        "total_publicaciones": total_junta,
                        "publicaciones_resueltas": total_resueltas,
                        "resueltas_en_plazo_legal": resueltas_en_plazo,
                        "tiempo_promedio_resolucion": tiempo_promedio_resolucion,
                        "porcentaje_resueltas": round((total_resueltas / total_junta * 100), 2),
                        "factor_cumplimiento": round(porcentaje_cumplimiento, 2),
                        "indice_eficiencia": round(indice_eficiencia, 2),
                    },
                }
            )

    # Ordenar por índice de eficiencia (mayor a menor)
    juntas_eficiencia.sort(
        key=lambda x: x["metricas"]["indice_eficiencia"], reverse=True
    )

    estadisticas = {
        "total_juntas_analizadas": len(juntas_eficiencia),
        "junta_mas_eficiente": juntas_eficiencia[0] if juntas_eficiencia else None,
        "top_5_eficientes": juntas_eficiencia[:5],
        "criterios_calculo": {
            "factor_volumen": "50% del índice (Capacidad de gestión)",
            "factor_cumplimiento": "50% del índice (Resoluciones dentro de 20 días hábiles sobre el total)",
            "nota": "Cálculo alineado a normativa legal de 20 días hábiles",
        },
    }

    return Response(estadisticas, status=200)


class UsuariosViewSet(AuditMixin, viewsets.ModelViewSet):
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
        if self.action in ["list", "retrieve"]:
            return UsuarioListSerializer
        return UsuarioSerializer

    def get_audit_module_name(self):
        return "Usuarios"

    def get_audit_object_name(self, instance):
        return f"{instance.nombre} (ID: {instance.id})"


class RegistroUsuarioView(APIView):
    permission_classes = [AllowAny]  # No requiere autenticación

    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def verificar_usuario_existente(request):
    """
    Endpoint optimizado para verificar si un usuario ya existe por RUT o email
    """
    try:
        rut = request.data.get("rut")
        email = request.data.get("email")

        if not rut and not email:
            return Response(
                {"error": "Se requiere RUT o email para la verificación"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {}

        if rut:
            # Normalizar RUT para búsqueda (remover puntos y guiones)
            rut_normalizado = rut.replace(".", "").replace("-", "")

            # Buscar tanto en formato normalizado como con guión
            usuario_rut = Usuario.objects.filter(
                Q(rut=rut_normalizado)
                | Q(rut=rut)
                | Q(
                    rut__in=[
                        rut,  # Formato original del frontend
                        rut_normalizado,  # Sin puntos ni guiones
                        f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}",  # Con guión al final
                    ]
                )
            ).first()
            response_data["rut_disponible"] = usuario_rut is None
            if usuario_rut:
                response_data["usuario_rut"] = {
                    "id": usuario_rut.id,
                    "nombre": usuario_rut.nombre,
                    "email": usuario_rut.email,
                    "tipo_usuario": usuario_rut.get_tipo_usuario_display(),
                    "esta_activo": usuario_rut.esta_activo,
                }

        if email:
            usuario_email = Usuario.objects.filter(email__iexact=email).first()
            response_data["email_disponible"] = usuario_email is None
            if usuario_email:
                response_data["usuario_email"] = {
                    "id": usuario_email.id,
                    "nombre": usuario_email.nombre,
                    "rut": usuario_email.rut,
                    "tipo_usuario": usuario_email.get_tipo_usuario_display(),
                    "esta_activo": usuario_email.esta_activo,
                }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al verificar usuario: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def logout_view(request):
    """Endpoint para cerrar sesión con auditoría"""
    try:
        # Crear auditoría de LOGOUT
        crear_auditoria(
            usuario=request.user,
            accion="LOGOUT",
            modulo="Autenticación",
            descripcion=f"Cierre de sesión desde IP: {request.META.get('REMOTE_ADDR', 'Desconocida')}",
            es_exitoso=True,
        )

        # En JWT no hay logout real en el servidor, pero podemos registrar la acción
        return Response({"message": "Logout exitoso"}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error en logout: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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

            # Importar la función desde serializers
            from ..serializers.v1 import (
                encontrar_junta_vecinal_mas_cercana,
                calcular_distancia_haversine,
            )

            junta_mas_cercana = encontrar_junta_vecinal_mas_cercana(
                float(latitud), float(longitud)
            )

            if not junta_mas_cercana:
                return Response(
                    {"error": "No se encontraron juntas vecinales cercanas"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Calcular la distancia
            distancia = calcular_distancia_haversine(
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

            # Importar la función desde serializers
            from ..serializers.v1 import calcular_distancia_haversine

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
                distancia = calcular_distancia_haversine(
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
            mes_nombre = meses_espanol[dato["mes"].month]  # Ene, Feb, Mar, etc.
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
                    "name": meses_espanol[mes.month],
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

        # Formatear datos para la tabla
        encabezados = [
            "Departamento",
            "Mes",
            "Total",
            "Resueltos",
            "Tasa de Resolución",
        ]
        filas = []
        # Calcular la tasa de resolución
        for dato in datos:
            mes_nombre = meses_espanol[dato["mes"].month]
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

        pdf.setFont("Helvetica", 12)
        y_position = height - 130  # Posición inicial (debajo del encabezado)
        max_width = 80  # Máximo número de caracteres por línea

        if not comentarios:
            comentarios = "No hay comentarios."

        for linea in comentarios.split("\n"):
            # Dividir la línea en fragmentos que quepan en el ancho permitido
            for wrapped_line in textwrap.wrap(linea, max_width):
                if y_position < 70:  # Si se acerca al footer, crear nueva página
                    pdf.showPage()
                    y_position = height - 90  # Reiniciar posición en nueva página
                    pdf.setFont(
                        "Helvetica", 12
                    )  # Restablecer la fuente después del salto

                # Dibujar la línea en la posición actual
                pdf.drawString(50, y_position, wrapped_line.strip())
                y_position -= 20  # Espaciado entre líneas

        # Agregar footer en la última página
        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            50, 30, f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

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

        # Crear descripción detallada de los filtros aplicados
        filtros_aplicados = []
        if departamento:
            filtros_aplicados.append(f"Departamento: {departamento}")

        # Obtener otros filtros de la query string
        filtros_query = []
        for key, value in request.GET.items():
            if key not in ["comentarios", "departamento_reporte"] and value:
                filtros_query.append(f"{key}: {value}")

        if filtros_query:
            filtros_aplicados.extend(filtros_query)

        descripcion_detallada = f"Generación de reporte PDF de publicaciones ({publicaciones_filtradas.count()} registros)"
        if filtros_aplicados:
            descripcion_detallada += f" - Filtros: {', '.join(filtros_aplicados)}"

        crear_auditoria(
            usuario=request.user,
            accion="GENERAR_REPORTE_PDF",
            modulo="Reportes",
            descripcion=descripcion_detallada,
            es_exitoso=True,
        )

        return response
    except Exception as e:
        # Registrar error en auditoría
        crear_auditoria(
            usuario=request.user,
            accion="GENERAR_REPORTE_PDF",
            modulo="Reportes",
            descripcion=f"Error al generar reporte PDF: {str(e)}",
            es_exitoso=False,
        )
        print(e)
        return HttpResponse("Error al generar el PDF", status=500)


# ViewSets para los nuevos modelos


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


# ViewSets para Sistema Kanban


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


# Vistas de estadísticas extendidas


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_departamentos(request):
    """Estadísticas generales de departamentos y funcionarios"""
    departamentos = DepartamentoMunicipal.objects.all()

    stats = []
    for depto in departamentos:
        funcionarios = UsuarioDepartamento.objects.filter(
            departamento=depto, estado="activo"
        )

        stats.append(
            {
                "departamento": depto.nombre,
                "total_funcionarios": funcionarios.count(),
                "jefe_departamento": (
                    depto.jefe_departamento.nombre if depto.jefe_departamento else None
                ),
                "estado": depto.estado,
                "publicaciones_asignadas": Publicacion.objects.filter(
                    departamento=depto
                ).count(),
            }
        )

    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_kanban(request):
    """Estadísticas del sistema Kanban por departamento"""
    departamento_id = request.query_params.get("departamento", None)

    tableros_query = Tablero.objects.all()
    if departamento_id:
        tableros_query = tableros_query.filter(departamento_id=departamento_id)

    stats = []
    for tablero in tableros_query:
        columnas = Columna.objects.filter(tablero=tablero)
        total_tareas = 0
        total_vencidas = 0

        for columna in columnas:
            tareas = Tarea.objects.filter(columna=columna)
            total_tareas += tareas.count()
            tareas_vencidas = (
                tareas.filter(fecha_limite__lt=timezone.now()).count()
                if tareas.exists()
                else 0
            )
            total_vencidas += tareas_vencidas

        stats.append(
            {
                "tablero": tablero.titulo,
                "departamento": tablero.departamento.nombre,
                "total_columnas": columnas.count(),
                "total_tareas": total_tareas,
                "tareas_vencidas": total_vencidas,
            }
        )

    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_respuestas(request):
    """Estadísticas de respuestas municipales con puntuaciones"""
    # Estadísticas de puntuaciones
    respuestas = RespuestaMunicipal.objects.exclude(puntuacion=0)

    if not respuestas.exists():
        return Response({"mensaje": "No hay respuestas con puntuación disponibles"})

    # Calcular estadísticas de puntuación
    puntuaciones = respuestas.values_list("puntuacion", flat=True)
    puntuacion_promedio = sum(puntuaciones) / len(puntuaciones)

    # Distribución de puntuaciones
    distribucion = {}
    for i in range(1, 6):
        distribucion[f"{i}_estrella"] = respuestas.filter(puntuacion=i).count()

    # Respuestas con evidencia
    respuestas_con_evidencia = (
        respuestas.filter(evidencias__isnull=False).distinct().count()
    )

    stats = {
        "total_respuestas_puntuadas": respuestas.count(),
        "puntuacion_promedio": round(puntuacion_promedio, 2),
        "distribucion_puntuaciones": distribucion,
        "respuestas_con_evidencia": respuestas_con_evidencia,
        "porcentaje_con_evidencia": (
            round((respuestas_con_evidencia / respuestas.count() * 100), 2)
            if respuestas.count() > 0
            else 0
        ),
    }

    return Response(stats)


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
        import logging

        logger = logging.getLogger(__name__)
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
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error en historial de modificaciones: {e}")


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def estadisticas_gestion_datos(request):
    juntas_vecinales = JuntaVecinal.objects.all()
    categorias = Categoria.objects.all()
    departamentos = DepartamentoMunicipal.objects.all()

    estadisticas = {
        "juntasVecinales": {
            "total": juntas_vecinales.count(),
            "habilitados": juntas_vecinales.filter(estado="habilitado").count(),
            "pendientes": juntas_vecinales.filter(estado="pendiente").count(),
            "deshabilitados": juntas_vecinales.filter(estado="deshabilitado").count(),
        },
        "categorias": {
            "total": categorias.count(),
            "habilitados": categorias.filter(estado="habilitado").count(),
            "pendientes": categorias.filter(estado="pendiente").count(),
            "deshabilitados": categorias.filter(estado="deshabilitado").count(),
        },
        "departamentos": {
            "total": departamentos.count(),
            "habilitados": departamentos.filter(estado="habilitado").count(),
            "pendientes": departamentos.filter(estado="pendiente").count(),
            "deshabilitados": departamentos.filter(estado="deshabilitado").count(),
        },
    }

    return Response(estadisticas)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def estadisticas_historial_modificaciones(request):
    """
    Endpoint para obtener estadísticas del historial de modificaciones,
    diferenciadas por rol de usuario (Jefe de Departamento vs. otro).
    """
    usuario = request.user
    es_jefe = usuario.tipo_usuario == "jefe_departamento"

    # Obtener el departamento del usuario para filtrar por equipo
    departamento = usuario.get_departamento_asignado()

    # Queryset base de modificaciones
    modificaciones_qs = HistorialModificaciones.objects.all()

    modificaciones_qs = modificaciones_qs.select_related(
        "autor"
    )  # Pre-carga datos del autor

    miembros_equipo_ids = None  # Inicializamos fuera del if

    if departamento:
        miembros_equipo_ids = Usuario.objects.filter(
            asignaciones_departamento__departamento=departamento, esta_activo=True
        ).values_list("id", flat=True)
        modificaciones_qs = modificaciones_qs.filter(autor_id__in=miembros_equipo_ids)
    else:
        modificaciones_qs = modificaciones_qs.filter(autor=usuario)
    modificaciones_por_usuario_qs = (
        modificaciones_qs.values(
            "autor_id",  # Agrupar por ID de autor
            "autor__nombre",  # Incluir el nombre del autor
        )
        .annotate(total_modificaciones=Count("id"))  # Contar modificaciones por grupo
        .order_by("-total_modificaciones")
    )  # Ordenar de más a menos activo

    modificaciones_por_usuario_lista = [
        {
            "usuario_id": item["autor_id"],
            "nombre_usuario": item["autor__nombre"],
            "modificaciones": item["total_modificaciones"],
        }
        for item in modificaciones_por_usuario_qs
    ]

    if es_jefe:
        if not departamento:
            return Response(
                {"error": "El Jefe de departamento no tiene un departamento asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_modificaciones = modificaciones_qs.count()
        hoy = timezone.now().date()
        modificaciones_hoy = modificaciones_qs.filter(fecha__date=hoy).count()

        # Usamos los IDs que ya teníamos o calculamos si es necesario
        miembros_equipo_count = (
            len(miembros_equipo_ids)
            if miembros_equipo_ids is not None
            else Usuario.objects.filter(id=usuario.id).count()
        )

        # Miembro más activo ya lo tenemos de la consulta anterior
        miembro_mas_activo_data = modificaciones_por_usuario_qs.first()
        miembro_mas_activo = None
        if miembro_mas_activo_data:
            miembro_mas_activo = {
                "miembro": {
                    "id": miembro_mas_activo_data.get("autor_id"),
                    "nombre": miembro_mas_activo_data.get("autor__nombre"),
                },
                "modificaciones": miembro_mas_activo_data.get(
                    "total_modificaciones", 0
                ),
            }

        estadisticas = {
            "totalModificaciones": total_modificaciones,
            "modificacionesHoy": modificaciones_hoy,
            "miembroMasActivo": miembro_mas_activo,
            "miembrosEquipo": miembros_equipo_count,
            "modificacionesPorUsuario": modificaciones_por_usuario_lista,
        }

    else:
        # Lógica para un usuario que NO es Jefe
        total_modificaciones = modificaciones_qs.count()
        mis_modificaciones = modificaciones_qs.filter(autor=usuario).count()
        modificaciones_equipo = modificaciones_qs.exclude(autor=usuario).count()

        estadisticas = {
            "totalModificaciones": total_modificaciones,
            "misModificaciones": mis_modificaciones,
            "modificacionesEquipo": modificaciones_equipo,
            "modificacionesPorUsuario": modificaciones_por_usuario_lista,
        }

    return Response(estadisticas, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def registrar_dispositivo(request):
    """
    Registrar token de dispositivo para notificaciones

    POST /api/v1/notificaciones/registrar/

    Body:
    {
        "token": "ExponentPushToken[xxxxxx]",
        "plataforma": "android",
    }
    """
    token = request.data.get("token")
    plataforma = request.data.get("plataforma", "android")

    if not token:
        return Response(
            {"error": "Token requerido"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        dispositivo, created = DispositivoNotificacion.objects.update_or_create(
            usuario=request.user,
            token_expo=token,
            defaults={
                "plataforma": plataforma,
                "activo": True,
            },
        )

        logger.info(
            f"{'✅ Nuevo' if created else '🔄 Actualizado'} dispositivo: "
            f"{request.user.rut} - {plataforma}"
        )

        serializer = DispositivoNotificacionSerializer(dispositivo)

        return Response(
            {
                "message": "Dispositivo registrado exitosamente",
                "dispositivo": serializer.data,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"❌ Error registrando dispositivo: {str(e)}")
        return Response(
            {"error": "Error interno del servidor"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def desactivar_dispositivo(request):
    """
    Desactivar notificaciones (al cerrar sesión)

    POST /api/v1/notificaciones/desactivar/

    Body:
    {
        "token": "ExponentPushToken[xxxxxx]"
    }
    """
    token = request.data.get("token")

    if not token:
        return Response(
            {"error": "Token requerido"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        count = DispositivoNotificacion.objects.filter(
            usuario=request.user, token_expo=token
        ).update(activo=False)

        if count > 0:
            logger.info(f"🔴 Dispositivo desactivado: {request.user.rut}")
            return Response({"message": "Dispositivo desactivado"})
        else:
            return Response(
                {"message": "Dispositivo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except Exception as e:
        logger.error(f"❌ Error desactivando: {str(e)}")
        return Response(
            {"error": "Error interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def mis_dispositivos(request):
    """
    Listar dispositivos del usuario

    GET /api/v1/notificaciones/mis-dispositivos/
    """
    dispositivos = DispositivoNotificacion.objects.filter(
        usuario=request.user
    ).order_by("-ultima_actualizacion")

    serializer = DispositivoNotificacionSerializer(dispositivos, many=True)

    return Response(
        {
            "total": dispositivos.count(),
            "activos": dispositivos.filter(activo=True).count(),
            "dispositivos": serializer.data,
        }
    )
