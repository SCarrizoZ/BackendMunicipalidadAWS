import pandas as pd
from django.db.models import Count, Q, Case, When, F, FloatField, ExpressionWrapper, Avg, Prefetch
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
from ..utils.constants import MESES_ESPANOL

class StatisticsService:
    MESES_ESPANOL = MESES_ESPANOL

    @staticmethod
    def get_resumen_estadisticas(queryset_filtro=None):
        queryset_filtro = Publicacion.objects.all() if queryset_filtro is None else queryset_filtro
        data = queryset_filtro.aggregate(
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
    def get_publicaciones_por_mes_categoria(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()

        datos = (
            qs.annotate(mes=TruncMonth("fecha_publicacion"))
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
    def get_publicaciones_por_categoria(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        return (
            qs.values("categoria__nombre")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

    @staticmethod
    def get_resueltos_por_mes(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()

        datos = (
            qs
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
    def get_tasa_resolucion_departamento(queryset_filtro=None):
        """
        Calcula la tasa de resolución por departamento y por MES.
        Restaura la granularidad temporal de la rama Main.
        """
        # 1. Usar el queryset filtrado o todos
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()

        # 2. Agrupar por Mes Y Departamento (Lógica restaurada)
        datos = (
            qs.annotate(
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

        # 3. Formatear como Diccionario anidado { Depto: { Mes: Stats } }
        # Esto coincide con la estructura de VistaAnterior.py
        respuesta = {}
        for dato in datos:
            # Manejo seguro de fecha
            if not dato["mes"]: 
                continue
            
            mes_nombre = StatisticsService.MESES_ESPANOL[dato["mes"].month]
            depto = dato["departamento_nombre"]
            total = dato["total"]
            resueltos = dato["resueltos"]
            
            # Cálculo de tasa
            tasa = (resueltos / total * 100) if total > 0 else 0

            if depto not in respuesta:
                respuesta[depto] = {}

            respuesta[depto][mes_nombre] = {
                "total": total,
                "resueltos": resueltos,
                "tasa_resolucion": round(tasa, 2),
            }

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
    def get_analisis_eficiencia_juntas(queryset_filtro=None):
        """
        Calcula la eficiencia basada en Volumen y Cumplimiento de Plazo Legal (20 días hábiles).
        Restaura la lógica compleja de negocio usando Pandas.
        """
        # 1. Definir QuerySet Base
        if queryset_filtro is not None:
            publicaciones = queryset_filtro
        else:
            publicaciones = Publicacion.objects.all()

        # 2. Optimización: Traer todo lo necesario en una sola consulta grande
        # Evitamos el N+1 query del código original usando select_related y prefetch_related
        publicaciones = publicaciones.select_related(
            'junta_vecinal'
        ).prefetch_related(
            'respuestamunicipal_set' # Asumiendo que este es el related_name, o 'respuestamunicipal'
        )

        juntas_data = {}
        DIAS_HABILES_LIMITE = 20
        ahora = timezone.now().date()

        # 3. Procesamiento en Memoria (Más rápido para cálculos complejos con Pandas)
        for pub in publicaciones:
            junta = pub.junta_vecinal
            if not junta:
                continue
            
            if junta.id not in juntas_data:
                juntas_data[junta.id] = {
                    "junta_obj": junta,
                    "total": 0,
                    "resueltas_en_plazo": 0,
                    "dias_resolucion_acumulados": 0,
                    "total_resueltas": 0
                }
            
            # Conteo total
            juntas_data[junta.id]["total"] += 1

            # Verificar si está resuelta (ID 4 es situación inicial/pendiente o NULL)
            # Ajusta la condición según tus IDs reales de Situacion
            es_resuelta = pub.situacion_id != 4 and pub.situacion is not None
            
            if es_resuelta:
                juntas_data[junta.id]["total_resueltas"] += 1
                
                # Obtener la primera respuesta (gracias al prefetch no hace query extra)
                # Nota: Asume que la respuesta define la fecha de resolución
                respuestas = list(pub.respuestamunicipal_set.all())
                if respuestas:
                    # Usamos la última respuesta como fecha de resolución
                    respuesta = sorted(respuestas, key=lambda x: x.fecha, reverse=True)[0]
                    
                    # Cálculo de días hábiles con Pandas (Lógica Original Restaurada)
                    try:
                        rango_dias = pd.bdate_range(start=pub.fecha_publicacion.date(), end=respuesta.fecha.date())
                        dias_habiles = len(rango_dias) - 1
                        
                        if dias_habiles <= DIAS_HABILES_LIMITE:
                            juntas_data[junta.id]["resueltas_en_plazo"] += 1
                            
                        # Días naturales para promedio
                        dias_naturales = (respuesta.fecha.date() - pub.fecha_publicacion.date()).days
                        if dias_naturales >= 0:
                            juntas_data[junta.id]["dias_resolucion_acumulados"] += dias_naturales
                    except Exception:
                        pass

        # 4. Calcular Índices Finales
        resultados = []
        for j_id, data in juntas_data.items():
            total = data["total"]
            if total == 0: 
                continue

            # Factor Volumen (50%): Normalizado a 20 publicaciones máx.
            factor_volumen = min(total / 20, 1) * 100

            # Factor Cumplimiento Legal (50%): Sobre el TOTAL de publicaciones
            porcentaje_cumplimiento = (data["resueltas_en_plazo"] / total) * 100
            
            # Índice Final
            indice_eficiencia = (factor_volumen * 0.5) + (porcentaje_cumplimiento * 0.5)
            
            tiempo_promedio = 0
            if data["total_resueltas"] > 0:
                tiempo_promedio = data["dias_resolucion_acumulados"] // data["total_resueltas"]

            junta_obj = data["junta_obj"]
            
            resultados.append({
                "junta": {
                    "id": junta_obj.id,
                    "nombre": junta_obj.nombre_junta or f"{junta_obj.nombre_calle} {junta_obj.numero_calle}",
                    "latitud": junta_obj.latitud,
                    "longitud": junta_obj.longitud,
                },
                "metricas": {
                    "total_publicaciones": total,
                    "publicaciones_resueltas": data["total_resueltas"],
                    "resueltas_en_plazo_legal": data["resueltas_en_plazo"],
                    "tiempo_promedio_resolucion": tiempo_promedio,
                    "porcentaje_resueltas": round((data["total_resueltas"] / total * 100), 2),
                    "factor_cumplimiento": round(porcentaje_cumplimiento, 2),
                    "indice_eficiencia": round(indice_eficiencia, 2),
                }
            })

        # 5. Ordenar por índice de eficiencia
        resultados.sort(key=lambda x: x["metricas"]["indice_eficiencia"], reverse=True)
        
        return resultados

    @staticmethod
    def get_estadisticas_eficiencia_completa(request_filters=None):
        """Método público que devuelve la estructura completa para la vista"""
        
        # Aplicar filtros si existen (para mantener compatibilidad con PublicacionFilter)
        qs = Publicacion.objects.all()
        if request_filters:
            # Aquí podrías aplicar el filterset manualmente si lo pasas desde la vista
            qs = request_filters
            
        ranking = StatisticsService.get_analisis_eficiencia_juntas(qs)
        
        return {
            "total_juntas_analizadas": len(ranking),
            "junta_mas_eficiente": ranking[0] if ranking else None,
            "top_5_eficientes": ranking[:5],
            "criterios_calculo": {
                "factor_volumen": "50% del índice (Capacidad de gestión)",
                "factor_cumplimiento": "50% del índice (Resoluciones dentro de 20 días hábiles sobre el total)",
                "nota": "Cálculo alineado a normativa legal de 20 días hábiles",
            },
        }

    @staticmethod
    def get_analisis_criticidad_juntas(queryset_filtro=None):
        """
        Calcula el índice de criticidad para todas las juntas.
        Recupera la lógica de negocio: Volumen + Retraso Legal (Días Hábiles).
        """
        import pandas as pd # Asegúrate de tener este import arriba
        
        # 1. QuerySet Base Optimizado
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        qs = qs.select_related('junta_vecinal', 'situacion')

        juntas_data = {}
        ahora = timezone.now()
        DIAS_HABILES_LIMITE = 20

        # 2. Procesamiento (Iteración única sobre resultados cacheados)
        for pub in qs:
            junta = pub.junta_vecinal
            if not junta:
                continue

            if junta.id not in juntas_data:
                juntas_data[junta.id] = {
                    "junta_obj": junta,
                    "total": 0,
                    "pendientes": 0,
                    "vencidas": 0,
                    "dias_pendientes_acum": 0,
                    "categorias_conteo": {} 
                }
            
            data = juntas_data[junta.id]
            data["total"] += 1
            
            # Conteo de Categorías para el gráfico del frontend
            cat_name = pub.categoria.nombre
            data["categorias_conteo"][cat_name] = data["categorias_conteo"].get(cat_name, 0) + 1

            # Lógica de Pendientes (ID 4 o Null)
            # Ajusta la condición según tu modelo exacto de Situacion
            es_pendiente = pub.situacion_id == 4 or pub.situacion is None
            
            if es_pendiente:
                data["pendientes"] += 1
                
                # Cálculo de días hábiles de retraso
                try:
                    # Días naturales
                    dias_naturales = (ahora.date() - pub.fecha_publicacion.date()).days
                    data["dias_pendientes_acum"] += dias_naturales

                    # Días hábiles (Regla de Negocio)
                    rango = pd.bdate_range(start=pub.fecha_publicacion.date(), end=ahora.date())
                    dias_habiles = len(rango) - 1
                    
                    if dias_habiles > DIAS_HABILES_LIMITE:
                        data["vencidas"] += 1
                except Exception:
                    pass

        # 3. Calcular Índices y Formatear
        resultados = []
        for j_id, d in juntas_data.items():
            total = d["total"]
            if total == 0:
                continue

            # Fórmulas Originales Restauradas
            factor_volumen = min(total / 20, 1) * 100
            porcentaje_vencidas = (d["vencidas"] / total) * 100
            indice_criticidad = (factor_volumen * 0.5) + (porcentaje_vencidas * 0.5)
            
            tiempo_prom = d["dias_pendientes_acum"] // d["pendientes"] if d["pendientes"] > 0 else 0

            junta_dict = {
                "Junta_Vecinal": {
                    "id": d["junta_obj"].id,
                    "nombre": d["junta_obj"].nombre_junta,
                    "latitud": d["junta_obj"].latitud,
                    "longitud": d["junta_obj"].longitud,
                    "total_publicaciones": total,
                    "pendientes": d["pendientes"],
                    "urgentes": d["vencidas"], # Métrica clave recuperada
                    "indice_criticidad": round(indice_criticidad, 2),
                    "porcentaje_pendientes": round(d["pendientes"]/total*100, 2),
                    "porcentaje_urgentes": round(porcentaje_vencidas, 2)
                },
                "tiempo_promedio_pendiente": f"{tiempo_prom} días",
            }
            # Agregar conteo de categorías dinámicamente (requerido por frontend)
            junta_dict.update(d["categorias_conteo"])
            
            resultados.append(junta_dict)

        # Ordenar por defecto por índice de criticidad
        resultados.sort(key=lambda x: x["Junta_Vecinal"]["indice_criticidad"], reverse=True)
        return resultados

    @staticmethod
    def get_analisis_frio_juntas(queryset_filtro=None):
        """
        Calcula estadísticas de publicaciones resueltas (Mapa de Frío).
        Recupera: Eficiencia, Tiempos de resolución y Calificación de vecinos.
        """
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        
        # Pre-carga crítica: Respuestas municipales con sus puntuaciones
        qs = qs.select_related('junta_vecinal', 'situacion', 'categoria')\
               .prefetch_related('respuestamunicipal_set')

        juntas_data = {}
        
        for pub in qs:
            junta = pub.junta_vecinal
            if not junta:
                continue
            
            if junta.id not in juntas_data:
                juntas_data[junta.id] = {
                    "junta": junta,
                    "total": 0,
                    "resueltas": 0,
                    "alta_prioridad_resueltas": 0,
                    "dias_resolucion_sum": 0,
                    "suma_puntuacion": 0,
                    "count_puntuacion": 0,
                    "ultima_resolucion": None,
                    "categorias": {}
                }
            
            d = juntas_data[junta.id]
            d["total"] += 1
            
            # Lógica: NO Pendiente (ID 4) y NO Null = Resuelta/En Proceso avanzado
            if pub.situacion_id != 4 and pub.situacion is not None:
                d["resueltas"] += 1
                
                # Categorías (solo de las resueltas/gestionadas)
                cat = pub.categoria.nombre
                d["categorias"][cat] = d["categorias"].get(cat, 0) + 1
                
                if pub.prioridad == 'alta':
                    d["alta_prioridad_resueltas"] += 1
                
                # Analizar respuestas (fechas y puntuación)
                respuestas = list(pub.respuestamunicipal_set.all())
                if respuestas:
                    # Ordenar para obtener la última y calcular tiempos
                    respuestas.sort(key=lambda r: r.fecha, reverse=True)
                    ultima = respuestas[0]
                    
                    # Guardar fecha más reciente global de la junta
                    if d["ultima_resolucion"] is None or ultima.fecha > d["ultima_resolucion"]:
                        d["ultima_resolucion"] = ultima.fecha
                    
                    # Tiempo resolución
                    dias = (ultima.fecha.date() - pub.fecha_publicacion.date()).days
                    if dias >= 0:
                        d["dias_resolucion_sum"] += dias
                    
                    # Puntuación (Satisfacción vecinal)
                    if ultima.puntuacion > 0:
                        d["suma_puntuacion"] += ultima.puntuacion
                        d["count_puntuacion"] += 1

        # Formatear salida
        resultados = []
        for j_id, d in juntas_data.items():
            if d["total"] == 0:
                continue
            
            eficiencia = (d["resueltas"] / d["total"]) * 100
            intensidad_frio = eficiencia / 100 # 0 a 1
            
            promedio_calif = 0
            if d["count_puntuacion"] > 0:
                promedio_calif = d["suma_puntuacion"] / d["count_puntuacion"]
                
            tiempo_prom = 0
            if d["resueltas"] > 0:
                tiempo_prom = d["dias_resolucion_sum"] // d["resueltas"]

            item = {
                "Junta_Vecinal": {
                    "nombre": d["junta"].nombre_junta,
                    "latitud": d["junta"].latitud,
                    "longitud": d["junta"].longitud,
                    "total_publicaciones": d["total"],
                    "total_resueltas": d["resueltas"],
                    "eficiencia": round(eficiencia, 2),
                    "intensidad_frio": round(intensidad_frio, 2),
                    "calificacion_promedio": round(promedio_calif, 1), # Dato clave recuperado
                    "total_valoraciones": d["count_puntuacion"],
                    "casos_alta_prioridad_resueltos": d["alta_prioridad_resueltas"]
                },
                "tiempo_promedio_resolucion": f"{tiempo_prom} días",
                "ultima_resolucion": d["ultima_resolucion"].isoformat() if d["ultima_resolucion"] else None
            }
            item.update(d["categorias"])
            resultados.append(item)
            
        resultados.sort(key=lambda x: x["Junta_Vecinal"]["eficiencia"], reverse=True)
        return resultados

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
