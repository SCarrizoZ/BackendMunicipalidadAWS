from rest_framework.decorators import api_view, permission_classes
from listado_publicaciones.permissions import IsAdmin, IsAuthenticatedOrAdmin
from rest_framework.response import Response
from rest_framework import status
from ..services.statistics_service import StatisticsService
from ..filters import PublicacionFilter
from ..models import Publicacion

@api_view(["GET"])
@permission_classes([IsAdmin])
def ResumenEstadisticas(request):
    """
    Retorna estadísticas generales para el dashboard.
    """
    data = StatisticsService.get_resumen_estadisticas()
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorMesyCategoria(request):
    """
    Retorna la cantidad de publicaciones por mes y categoría.
    """
    data = StatisticsService.get_publicaciones_por_mes_categoria()
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorCategoria(request):
    """
    Retorna la cantidad total de publicaciones por categoría.
    """
    data = StatisticsService.get_publicaciones_por_categoria()
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def ResueltosPorMes(request):
    """
    Retorna la cantidad de publicaciones resueltas vs recibidas por mes.
    """
    data = StatisticsService.get_resueltos_por_mes()
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def TasaResolucionDepartamento(request):
    """
    Calcula la tasa de resolución por departamento.
    """
    data = StatisticsService.get_tasa_resolucion_departamento()
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
@permission_classes([IsAdmin])
def junta_mas_critica(request):
    """
    Identifica la junta más crítica usando el índice ponderado (Volumen + Retraso).
    """
    filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
    
    # Reutilizamos el análisis completo y sacamos la primera (ya viene ordenada)
    ranking = StatisticsService.get_analisis_criticidad_juntas(filterset.qs)
    
    if ranking:
        # Adaptamos la respuesta al formato que espera el frontend para este widget específico
        top_1 = ranking[0]
        # Devolvemos una estructura simplificada o la completa según necesite tu front
        # Aquí reconstruyo lo que devolvía tu vista original 'junta_mas_critica' refactorizada, 
        # pero con datos reales de criticidad.
        return Response({
            "junta": top_1["Junta_Vecinal"], # Incluye nombre, id, lat, lon
            "metricas": top_1["Junta_Vecinal"] # Incluye índices
        })
        
    return Response({"mensaje": "No hay datos suficientes"})


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
