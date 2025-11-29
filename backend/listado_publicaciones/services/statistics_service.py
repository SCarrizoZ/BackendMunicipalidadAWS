from django.db.models import Count, Q, Case, When, F, FloatField, ExpressionWrapper, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from ..models import (
    Publicacion,
    JuntaVecinal,
    Categoria,
    DepartamentoMunicipal,
    Tablero,
    RespuestaMunicipal,
    HistorialModificaciones,
    Usuario,
)


class StatisticsService:
    MESES_ESPANOL = {
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

    @staticmethod
    def get_resumen_estadisticas():
        data = Publicacion.objects.aggregate(
            total=Count("id"),
            resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
            pendientes=Count("id", filter=Q(situacion__nombre="Pendiente")),
        )

        total = data["total"]
        resueltos = data["resueltos"]

        tasa_resolucion = (resueltos / total * 100) if total > 0 else 0

        return {
            "total_publicaciones": total,
            "resueltos": resueltos,
            "pendientes": data["pendientes"],
            "tasa_resolucion": round(tasa_resolucion, 2),
        }

    @staticmethod
    def get_publicaciones_por_mes_categoria():
        fecha_inicio = timezone.now() - timezone.timedelta(days=180)

        datos = (
            Publicacion.objects.filter(fecha_publicacion__gte=fecha_inicio)
            .annotate(mes=TruncMonth("fecha_publicacion"))
            .values("mes", "categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("mes")
        )

        meses_dict = {}
        for dato in datos:
            mes_nombre = StatisticsService.MESES_ESPANOL[dato["mes"].month]
            if mes_nombre not in meses_dict:
                meses_dict[mes_nombre] = {"name": mes_nombre}

            meses_dict[mes_nombre][dato["categoria__nombre"]] = dato["total"]

        return list(meses_dict.values())

    @staticmethod
    def get_publicaciones_por_categoria():
        return (
            Publicacion.objects.values("categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

    @staticmethod
    def get_resueltos_por_mes():
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
                    "name": StatisticsService.MESES_ESPANOL[dato["mes"].month],
                    "recibidos": dato["recibidos"],
                    "resueltos": dato["resueltos"],
                    "en_curso": dato["en_curso"],
                }
            )
        return respuesta

    @staticmethod
    def get_tasa_resolucion_departamento():
        datos = (
            Publicacion.objects.values("departamento__nombre")
            .annotate(
                total=Count("id"),
                resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
            )
            .annotate(
                tasa=Case(
                    When(
                        total__gt=0,
                        then=ExpressionWrapper(
                            F("resueltos") * 100.0 / F("total"),
                            output_field=FloatField(),
                        ),
                    ),
                    default=0.0,
                    output_field=FloatField(),
                )
            )
            .order_by("-total")
        )

        respuesta = []
        for dato in datos:
            respuesta.append(
                {
                    "departamento": dato["departamento__nombre"],
                    "total": dato["total"],
                    "resueltos": dato["resueltos"],
                    "tasa": round(dato["tasa"], 1),
                }
            )
        return respuesta

    @staticmethod
    def get_publicaciones_por_junta_vecinal():
        return (
            Publicacion.objects.values("junta_vecinal__nombre_junta")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

    @staticmethod
    def get_junta_mas_critica():
        return (
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

    @staticmethod
    def get_publicaciones_resueltas_por_junta_vecinal():
        return (
            Publicacion.objects.filter(situacion__nombre="Resuelto")
            .values("junta_vecinal__nombre_junta")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

    @staticmethod
    def get_junta_mas_eficiente():
        mejor_junta = (
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
            .annotate(
                tasa_resolucion=ExpressionWrapper(
                    F("resueltos") * 100.0 / F("total"), output_field=FloatField()
                )
            )
            .order_by("-tasa_resolucion")
            .first()
        )

        if mejor_junta:
            mejor_junta["tasa_resolucion"] = round(mejor_junta["tasa_resolucion"], 2)

        return mejor_junta

    @staticmethod
    def get_estadisticas_departamentos():
        departamentos = DepartamentoMunicipal.objects.annotate(
            total_funcionarios=Count(
                "usuariodepartamento", filter=Q(usuariodepartamento__estado="activo")
            ),
            total_publicaciones=Count("publicacion"),
        ).select_related("jefe_departamento")

        stats = []
        for depto in departamentos:
            stats.append(
                {
                    "departamento": depto.nombre,
                    "total_funcionarios": depto.total_funcionarios,
                    "jefe_departamento": (
                        depto.jefe_departamento.nombre
                        if depto.jefe_departamento
                        else None
                    ),
                    "estado": depto.estado,
                    "publicaciones_asignadas": depto.total_publicaciones,
                }
            )
        return stats

    @staticmethod
    def get_estadisticas_kanban(departamento_id=None):
        tableros_query = Tablero.objects.all()
        if departamento_id:
            tableros_query = tableros_query.filter(departamento_id=departamento_id)

        tableros = tableros_query.annotate(
            total_columnas=Count("columna", distinct=True),
            total_tareas=Count("columna__tarea", distinct=True),
            tareas_vencidas=Count(
                "columna__tarea",
                filter=Q(columna__tarea__fecha_limite__lt=timezone.now()),
                distinct=True,
            ),
        ).select_related("departamento")

        stats = []
        for tablero in tableros:
            stats.append(
                {
                    "tablero": tablero.titulo,
                    "departamento": tablero.departamento.nombre,
                    "total_columnas": tablero.total_columnas,
                    "total_tareas": tablero.total_tareas,
                    "tareas_vencidas": tablero.tareas_vencidas,
                }
            )
        return stats

    @staticmethod
    def get_estadisticas_respuestas():
        qs = RespuestaMunicipal.objects.exclude(puntuacion=0)

        # Si no hay respuestas, retornamos early
        if not qs.exists():
            return None

        # 1. Calcular todo en UNA sola consulta a la BD
        aggregates = qs.aggregate(
            promedio=Avg("puntuacion"),
            total=Count("id"),
            estrella_1=Count("id", filter=Q(puntuacion=1)),
            estrella_2=Count("id", filter=Q(puntuacion=2)),
            estrella_3=Count("id", filter=Q(puntuacion=3)),
            estrella_4=Count("id", filter=Q(puntuacion=4)),
            estrella_5=Count("id", filter=Q(puntuacion=5)),
            con_evidencia=Count(
                "id", filter=Q(evidencias__isnull=False), distinct=True
            ),
        )

        total = aggregates["total"]

        # Construir la respuesta con los datos ya calculados
        distribucion = {
            f"{i}_estrella": aggregates[f"estrella_{i}"] for i in range(1, 6)
        }

        return {
            "total_respuestas_puntuadas": total,
            "puntuacion_promedio": round(aggregates["promedio"] or 0, 2),
            "distribucion_puntuaciones": distribucion,
            "respuestas_con_evidencia": aggregates["con_evidencia"],
            "porcentaje_con_evidencia": (
                round((aggregates["con_evidencia"] / total * 100), 2)
                if total > 0
                else 0
            ),
        }

    @staticmethod
    def get_estadisticas_gestion_datos():
        juntas_vecinales = JuntaVecinal.objects.all()
        categorias = Categoria.objects.all()
        departamentos = DepartamentoMunicipal.objects.all()

        return {
            "juntasVecinales": {
                "total": juntas_vecinales.count(),
                "habilitados": juntas_vecinales.filter(estado="habilitado").count(),
                "pendientes": juntas_vecinales.filter(estado="pendiente").count(),
                "deshabilitados": juntas_vecinales.filter(
                    estado="deshabilitado"
                ).count(),
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

    @staticmethod
    def get_estadisticas_historial_modificaciones(usuario):
        es_jefe = usuario.tipo_usuario == "jefe_departamento"
        departamento = usuario.get_departamento_asignado()

        modificaciones_qs = HistorialModificaciones.objects.select_related("autor")
        miembros_equipo_ids = None

        if departamento:
            miembros_equipo_ids = Usuario.objects.filter(
                asignaciones_departamento__departamento=departamento, esta_activo=True
            ).values_list("id", flat=True)
            modificaciones_qs = modificaciones_qs.filter(
                autor_id__in=miembros_equipo_ids
            )
        else:
            modificaciones_qs = modificaciones_qs.filter(autor=usuario)

        modificaciones_por_usuario_qs = (
            modificaciones_qs.values("autor_id", "autor__nombre")
            .annotate(total_modificaciones=Count("id"))
            .order_by("-total_modificaciones")
        )

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
                raise ValueError(
                    "El Jefe de departamento no tiene un departamento asignado."
                )

            total_modificaciones = modificaciones_qs.count()
            hoy = timezone.now().date()
            modificaciones_hoy = modificaciones_qs.filter(fecha__date=hoy).count()

            miembros_equipo_count = (
                len(miembros_equipo_ids)
                if miembros_equipo_ids is not None
                else Usuario.objects.filter(id=usuario.id).count()
            )

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

            return {
                "totalModificaciones": total_modificaciones,
                "modificacionesHoy": modificaciones_hoy,
                "miembroMasActivo": miembro_mas_activo,
                "miembrosEquipo": miembros_equipo_count,
                "modificacionesPorUsuario": modificaciones_por_usuario_lista,
            }
        else:
            total_modificaciones = modificaciones_qs.count()
            mis_modificaciones = modificaciones_qs.filter(autor=usuario).count()
            modificaciones_equipo = modificaciones_qs.exclude(autor=usuario).count()

            return {
                "totalModificaciones": total_modificaciones,
                "misModificaciones": mis_modificaciones,
                "modificacionesEquipo": modificaciones_equipo,
                "modificacionesPorUsuario": modificaciones_por_usuario_lista,
            }
