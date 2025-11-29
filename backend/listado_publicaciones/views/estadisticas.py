from rest_framework.decorators import api_view, permission_classes
from listado_publicaciones.permissions import IsAdmin, IsAuthenticatedOrAdmin
from rest_framework.response import Response
from rest_framework import status
from ..services.statistics_service import StatisticsService
from ..filters import PublicacionFilter
from ..models import Publicacion

# Helper para no repetir código de filtrado
def get_filtered_queryset(request):
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return None, filterset.errors
    return filterset.qs, None

@api_view(["GET"])
@permission_classes([IsAdmin])
def ResumenEstadisticas(request):
    """
    Retorna estadísticas generales.
    CORRECCIÓN: Ahora aplica filtros globales (fecha, departamento, etc.)
    """
    qs, errors = get_filtered_queryset(request)
    if errors: return Response(errors, status=400)
    
    data = StatisticsService.get_resumen_estadisticas(qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorMesyCategoria(request):
    """
    Retorna publicaciones por mes y categoría.
    CORRECCIÓN: Ahora respeta el rango de fechas seleccionado.
    """
    qs, errors = get_filtered_queryset(request)
    if errors: return Response(errors, status=400)

    data = StatisticsService.get_publicaciones_por_mes_categoria(qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorCategoria(request):
    """
    Retorna total por categoría.
    CORRECCIÓN: Ahora permite filtrar por zona o fecha.
    """
    qs, errors = get_filtered_queryset(request)
    if errors: return Response(errors, status=400)

    data = StatisticsService.get_publicaciones_por_categoria(qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def ResueltosPorMes(request):
    """
    Retorna la cantidad de publicaciones resueltas vs recibidas por mes.
    """
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=400)
    data = StatisticsService.get_resueltos_por_mes(filterset.qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def TasaResolucionDepartamento(request):
    """
    Calcula la tasa de resolución por departamento y mes.
    FIX: Ahora soporta filtros y devuelve desglose mensual.
    """

    # 1. Aplicar filtros
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=400)

    # 2. Llamar al servicio corregido pasando el QS filtrado
    data = StatisticsService.get_tasa_resolucion_departamento(filterset.qs)
    
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorJuntaVecinalAPIView(request):
    """
    Retorna datos completos de las juntas incluyendo índice de criticidad y mapa de calor.
    """
    # 1. Aplicar filtros
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=400)

    # 2. Usar el nuevo método con lógica completa
    data = StatisticsService.get_analisis_criticidad_juntas(filterset.qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def junta_mas_critica(request):
    """
    Identifica la junta más crítica usando la lógica completa y formato compatible con Main.
    """
    # 1. Filtros
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=400)
    
    # 2. Llamar al nuevo WRAPPER
    # Esto devuelve { "total_juntas...", "junta_mas_critica": { "junta":..., "metricas":... } }
    data = StatisticsService.get_estadisticas_criticidad_completa(filterset.qs)
    
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def publicaciones_resueltas_por_junta_vecinal(request):
    """
    Retorna métricas de eficiencia y satisfacción (Mapa de Frío).
    """
    # 1. Aplicar filtros
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    if not filterset.is_valid():
        return Response(filterset.errors, status=400)

    # 2. Usar el nuevo método con lógica completa
    data = StatisticsService.get_analisis_frio_juntas(filterset.qs)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin]) # O el permiso que corresponda
def junta_mas_eficiente(request):
    """
    Identifica la junta vecinal con mayor tasa de resolución considerando plazos legales.
    """
    # 1. Aplicar filtros igual que en el código original
    publicaciones = Publicacion.objects.all()
    filterset = PublicacionFilter(request.GET, queryset=publicaciones)

    if not filterset.is_valid():
        return Response(
            {"error": "Filtros inválidos", "detalles": filterset.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Llamar al servicio pasando el QuerySet filtrado
    stats = StatisticsService.get_estadisticas_eficiencia_completa(filterset.qs)
    
    return Response(stats, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_departamentos(request):
    """Estadísticas generales de departamentos y funcionarios"""
    stats = StatisticsService.get_estadisticas_departamentos()
    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_kanban(request):
    """Estadísticas del sistema Kanban por departamento"""
    departamento_id = request.query_params.get("departamento", None)
    stats = StatisticsService.get_estadisticas_kanban(departamento_id)
    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAdmin])
def estadisticas_respuestas(request):
    """Estadísticas de respuestas municipales con puntuaciones"""
    stats = StatisticsService.get_estadisticas_respuestas()
    if stats:
        return Response(stats)
    return Response({"mensaje": "No hay respuestas con puntuación disponibles"})


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def estadisticas_gestion_datos(request):
    estadisticas = StatisticsService.get_estadisticas_gestion_datos()
    return Response(estadisticas)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def estadisticas_historial_modificaciones(request):
    """
    Endpoint para obtener estadísticas del historial de modificaciones,
    diferenciadas por rol de usuario (Jefe de Departamento vs. otro).
    """
    try:
        estadisticas = StatisticsService.get_estadisticas_historial_modificaciones(
            request.user
        )
        return Response(estadisticas, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Error interno: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
