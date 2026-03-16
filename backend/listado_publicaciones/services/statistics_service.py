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

        total = data["total"] or 0
        resueltos = data["resueltos"] or 0
        tasa_resolucion = (resueltos / total * 100) if total > 0 else 0

        return {
            "total_publicaciones": total,
            "resueltos": resueltos,
            "pendientes": data["pendientes"] or 0,
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
            if not dato["mes"]: continue
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
            if not dato["mes"]: continue
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
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
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
        respuesta = {}
        for dato in datos:
            if not dato["mes"]: continue
            mes_nombre = StatisticsService.MESES_ESPANOL[dato["mes"].month]
            depto = dato["departamento_nombre"]
            total = dato["total"]
            resueltos = dato["resueltos"]
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
    def get_publicaciones_por_junta_vecinal(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        return (
            qs.values("junta_vecinal__nombre_junta")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

    # -------------------------------------------------------
    # LÓGICA CRÍTICA (Junta más crítica)
    # -------------------------------------------------------

    @staticmethod
    def get_analisis_criticidad_juntas(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        qs = qs.select_related('junta_vecinal', 'situacion', 'categoria')

        juntas_data = {}
        ahora = timezone.now()
        DIAS_HABILES_LIMITE = 20

        for pub in qs:
            junta = pub.junta_vecinal
            if not junta: continue

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
            cat_name = pub.categoria.nombre
            data["categorias_conteo"][cat_name] = data["categorias_conteo"].get(cat_name, 0) + 1

            if pub.situacion_id == 4 or pub.situacion is None:
                data["pendientes"] += 1
                try:
                    dias_naturales = (ahora.date() - pub.fecha_publicacion.date()).days
                    data["dias_pendientes_acum"] += dias_naturales
                    rango = pd.bdate_range(start=pub.fecha_publicacion.date(), end=ahora.date())
                    dias_habiles = len(rango) - 1
                    if dias_habiles > DIAS_HABILES_LIMITE:
                        data["vencidas"] += 1
                except Exception:
                    pass

        resultados = []
        for j_id, d in juntas_data.items():
            total = d["total"]
            if total == 0: continue

            factor_volumen = min(total / 20, 1) * 100
            porcentaje_vencidas = (d["vencidas"] / total) * 100
            indice_criticidad = (factor_volumen * 0.5) + (porcentaje_vencidas * 0.5)
            tiempo_prom = d["dias_pendientes_acum"] // d["pendientes"] if d["pendientes"] > 0 else 0

            junta_dict = {
                "Junta_Vecinal": {
                    "id": d["junta_obj"].id,
                    "nombre": d["junta_obj"].nombre_junta or f"{d['junta_obj'].nombre_calle} {d['junta_obj'].numero_calle}",
                    "latitud": d["junta_obj"].latitud,
                    "longitud": d["junta_obj"].longitud,
                    "total_publicaciones": total,
                    "pendientes": d["pendientes"],
                    "urgentes": d["vencidas"],
                    "indice_criticidad": round(indice_criticidad, 2),
                    "porcentaje_pendientes": round(d["pendientes"]/total*100, 2),
                    "porcentaje_urgentes": round(porcentaje_vencidas, 2)
                },
                "tiempo_promedio_pendiente": f"{tiempo_prom} días",
            }
            junta_dict.update(d["categorias_conteo"])
            resultados.append(junta_dict)

        resultados.sort(key=lambda x: x["Junta_Vecinal"]["indice_criticidad"], reverse=True)
        return resultados

    @staticmethod
    def get_estadisticas_criticidad_completa(queryset_filtro=None):
        ranking = StatisticsService.get_analisis_criticidad_juntas(queryset_filtro)
        
        def formatear_item(item_plano):
            datos = item_plano["Junta_Vecinal"]
            return {
                "junta": {
                    "id": datos.get("id"),
                    "nombre": datos.get("nombre"),
                    "latitud": datos.get("latitud"),
                    "longitud": datos.get("longitud")
                },
                "metricas": {
                    "total_publicaciones": datos.get("total_publicaciones"),
                    "publicaciones_pendientes": datos.get("pendientes"),
                    "casos_urgentes": datos.get("urgentes"),
                    "cantidad_vencidas_legal": datos.get("urgentes"),
                    "tiempo_promedio_pendiente": item_plano.get("tiempo_promedio_pendiente"),
                    "porcentaje_pendientes": datos.get("porcentaje_pendientes"),
                    "porcentaje_urgentes": datos.get("porcentaje_urgentes"),
                    "indice_criticidad": datos.get("indice_criticidad")
                }
            }

        promedio = 0
        if ranking:
            total_indices = sum(r["Junta_Vecinal"]["indice_criticidad"] for r in ranking)
            promedio = round(total_indices / len(ranking), 2)

        return {
            "total_juntas_analizadas": len(ranking),
            "junta_mas_critica": formatear_item(ranking[0]) if ranking else None,
            "top_5_criticas": [formatear_item(r) for r in ranking[:5]],
            "promedio_criticidad": promedio,
            "criterios_calculo": {
                "factor_volumen": "50% del índice",
                "factor_retraso_legal": "50% del índice",
            },
        }

    # -------------------------------------------------------
    # LÓGICA EFICIENCIA / FRÍO (Junta más eficiente y Mapa de Frío)
    # -------------------------------------------------------

    @staticmethod
    def get_analisis_frio_juntas(queryset_filtro=None):
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        qs = qs.select_related('junta_vecinal', 'situacion', 'categoria').prefetch_related('respuestamunicipal_set')

        juntas_data = {}
        for pub in qs:
            junta = pub.junta_vecinal
            if not junta: continue
            
            if junta.id not in juntas_data:
                juntas_data[junta.id] = {
                    "junta": junta, "total": 0, "resueltas": 0, "alta_prioridad_resueltas": 0,
                    "dias_resolucion_sum": 0, "suma_puntuacion": 0, "count_puntuacion": 0,
                    "ultima_resolucion": None, "categorias": {}
                }
            d = juntas_data[junta.id]
            d["total"] += 1
            
            if pub.situacion_id != 4 and pub.situacion is not None:
                d["resueltas"] += 1
                cat = pub.categoria.nombre
                d["categorias"][cat] = d["categorias"].get(cat, 0) + 1
                if pub.prioridad == 'alta': d["alta_prioridad_resueltas"] += 1
                
                respuestas = list(pub.respuestamunicipal_set.all())
                if respuestas:
                    respuestas.sort(key=lambda r: r.fecha, reverse=True)
                    ultima = respuestas[0]
                    if d["ultima_resolucion"] is None or ultima.fecha > d["ultima_resolucion"]:
                        d["ultima_resolucion"] = ultima.fecha
                    dias = (ultima.fecha.date() - pub.fecha_publicacion.date()).days
                    if dias >= 0: d["dias_resolucion_sum"] += dias
                    if ultima.puntuacion > 0:
                        d["suma_puntuacion"] += ultima.puntuacion
                        d["count_puntuacion"] += 1

        resultados = []
        for j_id, d in juntas_data.items():
            if d["total"] == 0: continue
            eficiencia = (d["resueltas"] / d["total"]) * 100
            intensidad_frio = eficiencia / 100
            promedio_calif = d["suma_puntuacion"] / d["count_puntuacion"] if d["count_puntuacion"] > 0 else 0
            tiempo_prom = d["dias_resolucion_sum"] // d["resueltas"] if d["resueltas"] > 0 else 0

            item = {
                "Junta_Vecinal": {
                    "nombre": d["junta"].nombre_junta,
                    "latitud": d["junta"].latitud,
                    "longitud": d["junta"].longitud,
                    "total_publicaciones": d["total"],
                    "total_resueltas": d["resueltas"],
                    "eficiencia": round(eficiencia, 2),
                    "intensidad_frio": round(intensidad_frio, 2),
                    "calificacion_promedio": round(promedio_calif, 1),
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
    def get_analisis_eficiencia_juntas(queryset_filtro=None):
        """
        Lógica para calcular la junta más eficiente considerando Plazo Legal (20 días hábiles).
        Esta es la función que faltaba y causaba el AttributeError.
        """
        qs = queryset_filtro if queryset_filtro is not None else Publicacion.objects.all()
        qs = qs.select_related('junta_vecinal').prefetch_related('respuestamunicipal_set')

        juntas_data = {}
        DIAS_HABILES_LIMITE = 20
        
        for pub in qs:
            junta = pub.junta_vecinal
            if not junta: continue
            
            if junta.id not in juntas_data:
                juntas_data[junta.id] = {
                    "junta": junta, "total": 0, "resueltas_en_plazo": 0,
                    "dias_resolucion_acum": 0, "total_resueltas": 0
                }
            d = juntas_data[junta.id]
            d["total"] += 1

            # Si no es pendiente
            if pub.situacion_id != 4 and pub.situacion is not None:
                d["total_resueltas"] += 1
                respuestas = list(pub.respuestamunicipal_set.all())
                if respuestas:
                    respuesta = sorted(respuestas, key=lambda x: x.fecha, reverse=True)[0]
                    try:
                        rango = pd.bdate_range(start=pub.fecha_publicacion.date(), end=respuesta.fecha.date())
                        if (len(rango) - 1) <= DIAS_HABILES_LIMITE:
                            d["resueltas_en_plazo"] += 1
                        
                        dias_nat = (respuesta.fecha.date() - pub.fecha_publicacion.date()).days
                        if dias_nat >= 0: d["dias_resolucion_acum"] += dias_nat
                    except Exception: pass

        resultados = []
        for j_id, d in juntas_data.items():
            total = d["total"]
            if total == 0: continue

            factor_volumen = min(total / 20, 1) * 100
            # Eficiencia real: Cumplimiento legal sobre el total
            porcentaje_cumplimiento = (d["resueltas_en_plazo"] / total) * 100
            indice_eficiencia = (factor_volumen * 0.5) + (porcentaje_cumplimiento * 0.5)
            
            tiempo_prom = d["dias_resolucion_acum"] // d["total_resueltas"] if d["total_resueltas"] > 0 else 0

            resultados.append({
                "junta": {
                    "id": d["junta"].id,
                    "nombre": d["junta"].nombre_junta,
                    "latitud": d["junta"].latitud,
                    "longitud": d["junta"].longitud,
                },
                "metricas": {
                    "total_publicaciones": total,
                    "publicaciones_resueltas": d["total_resueltas"],
                    "resueltas_en_plazo_legal": d["resueltas_en_plazo"],
                    "tiempo_promedio_resolucion": tiempo_prom,
                    "porcentaje_resueltas": round((d["total_resueltas"]/total*100), 2),
                    "factor_cumplimiento": round(porcentaje_cumplimiento, 2),
                    "indice_eficiencia": round(indice_eficiencia, 2),
                }
            })
            
        resultados.sort(key=lambda x: x["metricas"]["indice_eficiencia"], reverse=True)
        return resultados

    @staticmethod
    def get_estadisticas_eficiencia_completa(request_filters=None):
        # Usamos el método que acabamos de restaurar
        ranking = StatisticsService.get_analisis_eficiencia_juntas(request_filters)
        
        return {
            "total_juntas_analizadas": len(ranking),
            "junta_mas_eficiente": ranking[0] if ranking else None,
            "top_5_eficientes": ranking[:5],
             "criterios_calculo": {
                "factor_volumen": "50% del índice",
                "factor_cumplimiento": "50% del índice (Plazo legal 20 días)",
            },
        }

    # -------------------------------------------------------
    # MÉTODOS SIMPLES
    # -------------------------------------------------------

    @staticmethod
    def get_estadisticas_departamentos():
        departamentos = DepartamentoMunicipal.objects.annotate(
            total_funcionarios=Count("usuariodepartamento", filter=Q(usuariodepartamento__estado="activo")),
            total_publicaciones=Count("publicacion"),
        ).select_related("jefe_departamento")
        stats = []
        for depto in departamentos:
            stats.append({
                "departamento": depto.nombre,
                "total_funcionarios": depto.total_funcionarios,
                "jefe_departamento": depto.jefe_departamento.nombre if depto.jefe_departamento else None,
                "estado": depto.estado,
                "publicaciones_asignadas": depto.total_publicaciones,
            })
        return stats
    
    @staticmethod
    def get_estadisticas_kanban(departamento_id=None):
        tableros_query = Tablero.objects.all()
        if departamento_id:
            tableros_query = tableros_query.filter(departamento_id=departamento_id)
        tableros = tableros_query.annotate(
            total_columnas=Count("columna", distinct=True),
            total_tareas=Count("columna__tarea", distinct=True),
            tareas_vencidas=Count("columna__tarea", filter=Q(columna__tarea__fecha_limite__lt=timezone.now()), distinct=True),
        ).select_related("departamento")
        stats = []
        for tablero in tableros:
            stats.append({
                "tablero": tablero.titulo,
                "departamento": tablero.departamento.nombre,
                "total_columnas": tablero.total_columnas,
                "total_tareas": tablero.total_tareas,
                "tareas_vencidas": tablero.tareas_vencidas,
            })
        return stats

    @staticmethod
    def get_estadisticas_respuestas():
        qs = RespuestaMunicipal.objects.exclude(puntuacion=0)
        if not qs.exists(): return None
        aggregates = qs.aggregate(
            promedio=Avg("puntuacion"),
            total=Count("id"),
            estrella_1=Count("id", filter=Q(puntuacion=1)),
            estrella_2=Count("id", filter=Q(puntuacion=2)),
            estrella_3=Count("id", filter=Q(puntuacion=3)),
            estrella_4=Count("id", filter=Q(puntuacion=4)),
            estrella_5=Count("id", filter=Q(puntuacion=5)),
            con_evidencia=Count("id", filter=Q(evidencias__isnull=False), distinct=True),
        )
        total = aggregates["total"]
        distribucion = {f"{i}_estrella": aggregates[f"estrella_{i}"] for i in range(1, 6)}
        return {
            "total_respuestas_puntuadas": total,
            "puntuacion_promedio": round(aggregates["promedio"] or 0, 2),
            "distribucion_puntuaciones": distribucion,
            "respuestas_con_evidencia": aggregates["con_evidencia"],
            "porcentaje_con_evidencia": (round((aggregates["con_evidencia"] / total * 100), 2) if total > 0 else 0),
        }

    @staticmethod
    def get_estadisticas_gestion_datos():
        return {
            "juntasVecinales": {"total": JuntaVecinal.objects.count(), "habilitados": JuntaVecinal.objects.filter(estado="habilitado").count(), "pendientes": JuntaVecinal.objects.filter(estado="pendiente").count(), "deshabilitados": JuntaVecinal.objects.filter(estado="deshabilitado").count()},
            "categorias": {"total": Categoria.objects.count(), "habilitados": Categoria.objects.filter(estado="habilitado").count(), "pendientes": Categoria.objects.filter(estado="pendiente").count(), "deshabilitados": Categoria.objects.filter(estado="deshabilitado").count()},
            "departamentos": {"total": DepartamentoMunicipal.objects.count(), "habilitados": DepartamentoMunicipal.objects.filter(estado="habilitado").count(), "pendientes": DepartamentoMunicipal.objects.filter(estado="pendiente").count(), "deshabilitados": DepartamentoMunicipal.objects.filter(estado="deshabilitado").count()},
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
            modificaciones_qs = modificaciones_qs.filter(autor_id__in=miembros_equipo_ids)
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
                raise ValueError("El Jefe de departamento no tiene un departamento asignado.")

            total_modificaciones = modificaciones_qs.count()
            hoy = timezone.now().date()
            modificaciones_hoy = modificaciones_qs.filter(fecha__date=hoy).count()
            miembros_equipo_count = len(miembros_equipo_ids) if miembros_equipo_ids is not None else 1
            
            miembro_mas_activo_data = modificaciones_por_usuario_qs.first()
            miembro_mas_activo = None
            if miembro_mas_activo_data:
                miembro_mas_activo = {
                    "miembro": {"id": miembro_mas_activo_data.get("autor_id"), "nombre": miembro_mas_activo_data.get("autor__nombre")},
                    "modificaciones": miembro_mas_activo_data.get("total_modificaciones", 0),
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