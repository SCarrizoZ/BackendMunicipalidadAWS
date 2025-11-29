from rest_framework.decorators import api_view, permission_classes
from listado_publicaciones.permissions import IsAdmin, IsAuthenticatedOrAdmin
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, F
from django.db.models.functions import TruncMonth
from django.utils import timezone
from ..models import (
    Publicacion,
    JuntaVecinal,
    Categoria,
    DepartamentoMunicipal,
    UsuarioDepartamento,
    Tablero,
    Columna,
    Tarea,
    RespuestaMunicipal,
    HistorialModificaciones,
    Usuario,
)
from ..serializers.v1 import JuntaVecinalSerializer
from datetime import datetime

# Mapeo de meses
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

@api_view(["GET"])
@permission_classes([IsAdmin])
def ResumenEstadisticas(request):
    """
    Retorna estadísticas generales para el dashboard.
    """
    total_publicaciones = Publicacion.objects.count()
    resueltos = Publicacion.objects.filter(situacion__nombre="Resuelto").count()
    pendientes = Publicacion.objects.filter(situacion__nombre="Pendiente").count()

    # Calcular tasa de resolución
    tasa_resolucion = (
        (resueltos / total_publicaciones * 100) if total_publicaciones > 0 else 0
    )

    data = {
        "total_publicaciones": total_publicaciones,
        "resueltos": resueltos,
        "pendientes": pendientes,
        "tasa_resolucion": round(tasa_resolucion, 2),
    }
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorMesyCategoria(request):
    """
    Retorna la cantidad de publicaciones por mes y categoría.
    """
    # Obtener fecha de inicio (hace 6 meses)
    fecha_inicio = timezone.now() - timezone.timedelta(days=180)

    datos = (
        Publicacion.objects.filter(fecha_publicacion__gte=fecha_inicio)
        .annotate(mes=TruncMonth("fecha_publicacion"))
        .values("mes", "categoria__nombre")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    # Formatear los datos para el frontend
    meses_dict = {}
    for dato in datos:
        mes_nombre = meses_espanol[dato["mes"].month]
        if mes_nombre not in meses_dict:
            meses_dict[mes_nombre] = {"name": mes_nombre}

        meses_dict[mes_nombre][dato["categoria__nombre"]] = dato["total"]

    return Response(list(meses_dict.values()))


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorCategoria(request):
    """
    Retorna la cantidad total de publicaciones por categoría.
    """
    datos = (
        Publicacion.objects.values("categoria__nombre")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return Response(datos)


@api_view(["GET"])
@permission_classes([IsAdmin])
def ResueltosPorMes(request):
    """
    Retorna la cantidad de publicaciones resueltas vs recibidas por mes.
    """
    fecha_inicio = timezone.now() - timezone.timedelta(days=180)

    datos = (
        Publicacion.objects.filter(fecha_publicacion__gte=fecha_inicio)
        .annotate(mes=TruncMonth("fecha_publicacion"))
        .values("mes")
        .annotate(
            recibidos=Count("id", filter=Q(situacion__nombre="Recibido")),
            resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
            en_curso=Count("id", filter=Q(situacion__nombre="En curso")),
        )
        .order_by("mes")
    )

    respuesta = []
    for dato in datos:
        respuesta.append(
            {
                "name": meses_espanol[dato["mes"].month],
                "recibidos": dato["recibidos"],
                "resueltos": dato["resueltos"],
                "en_curso": dato["en_curso"],
            }
        )

    return Response(respuesta)


@api_view(["GET"])
@permission_classes([IsAdmin])
def TasaResolucionDepartamento(request):
    """
    Calcula la tasa de resolución por departamento.
    """
    datos = (
        Publicacion.objects.values("departamento__nombre")
        .annotate(
            total=Count("id"),
            resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
        )
        .order_by("-total")
    )

    respuesta = []
    for dato in datos:
        total = dato["total"]
        resueltos = dato["resueltos"]
        tasa = (resueltos / total * 100) if total > 0 else 0
        respuesta.append(
            {
                "departamento": dato["departamento__nombre"],
                "total": total,
                "resueltos": resueltos,
                "tasa": round(tasa, 1),
            }
        )

    return Response(respuesta)


@api_view(["GET"])
@permission_classes([IsAdmin])
def PublicacionesPorJuntaVecinalAPIView(request):
    """
    Retorna la cantidad de publicaciones por junta vecinal.
    """
    datos = (
        Publicacion.objects.values("junta_vecinal__nombre_junta")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]  # Top 10
    )

    return Response(datos)


@api_view(["GET"])
@permission_classes([IsAdmin])
def junta_mas_critica(request):
    """
    Identifica la junta vecinal con más problemas sin resolver.
    """
    junta_critica = (
        Publicacion.objects.exclude(situacion__nombre="Resuelto")
        .values(
            "junta_vecinal__id",
            "junta_vecinal__nombre_junta",
            "junta_vecinal__latitud",
            "junta_vecinal__longitud",
        )
        .annotate(total_pendientes=Count("id"))
        .order_by("-total_pendientes")
        .first()
    )

    if junta_critica:
        return Response(junta_critica)
    return Response({"mensaje": "No hay datos suficientes"})


@api_view(["GET"])
@permission_classes([IsAdmin])
def publicaciones_resueltas_por_junta_vecinal(request):
    """
    Retorna la cantidad de publicaciones resueltas por junta vecinal.
    """
    datos = (
        Publicacion.objects.filter(situacion__nombre="Resuelto")
        .values("junta_vecinal__nombre_junta")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]  # Top 10
    )

    return Response(datos)


@api_view(["GET"])
@permission_classes([IsAdmin])
def junta_mas_eficiente(request):
    """
    Identifica la junta vecinal con mayor tasa de resolución.
    """
    # Obtener todas las juntas con al menos una publicación
    juntas = (
        Publicacion.objects.values(
            "junta_vecinal__id",
            "junta_vecinal__nombre_junta",
            "junta_vecinal__latitud",
            "junta_vecinal__longitud",
        )
        .annotate(
            total=Count("id"),
            resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
        )
        .filter(total__gt=0)
    )

    # Calcular eficiencia en Python
    mejor_junta = None
    mejor_tasa = -1

    for junta in juntas:
        tasa = (junta["resueltos"] / junta["total"]) * 100
        if tasa > mejor_tasa:
            mejor_tasa = tasa
            mejor_junta = junta
            mejor_junta["tasa_resolucion"] = round(tasa, 2)

    if mejor_junta:
        return Response(mejor_junta)
    return Response({"mensaje": "No hay datos suficientes"})


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
