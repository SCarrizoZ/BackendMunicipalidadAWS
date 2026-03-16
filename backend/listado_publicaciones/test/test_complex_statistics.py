from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import pandas as pd
from decimal import Decimal
from ..models import (
    Publicacion, JuntaVecinal, Categoria, DepartamentoMunicipal, 
    Usuario, SituacionPublicacion, RespuestaMunicipal
)
from ..services.statistics_service import StatisticsService

class ComplexStatisticsTest(TestCase):
    def setUp(self):
        # 1. Configuración Base (Usuarios, Deptos, Categorías)
        self.usuario = Usuario.objects.create(rut="1-9", email="test@muni.cl", nombre="Tester")
        self.depto = DepartamentoMunicipal.objects.create(nombre="Obras")
        self.cat = Categoria.objects.create(nombre="Baches", departamento=self.depto)
        
        # Situaciones clave
        self.sit_pendiente = SituacionPublicacion.objects.create(id=4, nombre="Pendiente")
        self.sit_resuelto = SituacionPublicacion.objects.create(id=1, nombre="Resuelto")
        
        # 2. Escenario: Junta "Caótica" (Pocas denuncias, pero MUY antiguas/vencidas)
        self.junta_caos = JuntaVecinal.objects.create(
            nombre_junta="Villa Caos", latitud=0, longitud=0, numero_calle=1
        )
        
        # 3. Escenario: Junta "Activa" (Muchas denuncias, pero todas recientes/nuevas)
        self.junta_activa = JuntaVecinal.objects.create(
            nombre_junta="Villa Activa", latitud=0, longitud=0, numero_calle=2
        )

        # 4. Escenario: Junta "Eficiente" (Todo resuelto y calificado)
        self.junta_eficiente = JuntaVecinal.objects.create(
            nombre_junta="Villa Eficiente", latitud=0, longitud=0, numero_calle=3
        )

    def test_calculo_criticidad_dias_habiles(self):
        """
        Prueba que el sistema detecte correctamente 'Urgentes' basándose en días hábiles.
        - Caso A: Publicación hecha hace 25 días naturales (aprox 17-18 hábiles) -> NO VENCIDA
        - Caso B: Publicación hecha hace 40 días naturales (aprox 28 hábiles) -> VENCIDA (>20)
        """
        ahora = timezone.now()
        
        # Publicación A: Antigua pero dentro del plazo legal (menos de 20 días hábiles)
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=self.junta_activa, categoria=self.cat, 
            departamento=self.depto, situacion=self.sit_pendiente, titulo="Caso A",
            fecha_publicacion=ahora - timedelta(days=25), latitud=0, longitud=0
        )

        # Publicación B: Muy antigua (Vencida)
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=self.junta_caos, categoria=self.cat, 
            departamento=self.depto, situacion=self.sit_pendiente, titulo="Caso B",
            fecha_publicacion=ahora - timedelta(days=45), latitud=0, longitud=0
        )

        # Ejecutar análisis
        resultados = StatisticsService.get_analisis_criticidad_juntas()
        
        # Convertir a diccionario para fácil acceso por nombre
        mapa_resultados = {r['Junta_Vecinal']['nombre']: r['Junta_Vecinal'] for r in resultados}

        # Verificaciones
        # Junta Activa: 1 pendiente, 0 urgentes (porque 25 días naturales < 20 hábiles usualmente)
        self.assertEqual(mapa_resultados["Villa Activa"]["pendientes"], 1)
        self.assertEqual(mapa_resultados["Villa Activa"]["urgentes"], 0)
        self.assertEqual(mapa_resultados["Villa Activa"]["porcentaje_urgentes"], 0.0)

        # Junta Caos: 1 pendiente, 1 urgente (porque 45 días > 20 hábiles)
        self.assertEqual(mapa_resultados["Villa Caos"]["pendientes"], 1)
        self.assertEqual(mapa_resultados["Villa Caos"]["urgentes"], 1)
        self.assertEqual(mapa_resultados["Villa Caos"]["porcentaje_urgentes"], 100.0)

    def test_indice_ponderado_criticidad(self):
        """
        Prueba que la fórmula (50% Volumen + 50% Retraso) funcione.
        Junta Caos (100% retraso, poco volumen) vs Junta Activa (0% retraso, poco volumen)
        """
        ahora = timezone.now()
        
        # Caos: 1 publicación, 100% vencida
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=self.junta_caos, categoria=self.cat, departamento=self.depto,
            situacion=self.sit_pendiente, titulo="Vencida",
            fecha_publicacion=ahora - timedelta(days=50), latitud=0, longitud=0
        )

        # Activa: 5 publicaciones, 0% vencidas (son de hoy)
        for i in range(5):
            Publicacion.objects.create(
                usuario=self.usuario, junta_vecinal=self.junta_activa, categoria=self.cat, departamento=self.depto,
                situacion=self.sit_pendiente, titulo=f"Nueva {i}",
                fecha_publicacion=ahora, latitud=0, longitud=0
            )

        resultados = StatisticsService.get_analisis_criticidad_juntas()
        mapa = {r['Junta_Vecinal']['nombre']: r['Junta_Vecinal']['indice_criticidad'] for r in resultados}

        # Cálculo manual esperado:
        # Caos: (Volumen: 1/20 = 5%) * 0.5 + (Retraso: 100%) * 0.5 => 2.5 + 50 = 52.5
        # Activa: (Volumen: 5/20 = 25%) * 0.5 + (Retraso: 0%) * 0.5 => 12.5 + 0 = 12.5
        
        self.assertGreater(mapa["Villa Caos"], mapa["Villa Activa"])
        self.assertAlmostEqual(mapa["Villa Caos"], 52.5, delta=1.0) # Delta por redondeos

    def test_mapa_frio_metricas_calidad(self):
        """
        Prueba el cálculo de eficiencia, tiempo de respuesta y satisfacción (estrellas).
        """
        ahora = timezone.now()
        
        # Crear publicación resuelta
        pub = Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=self.junta_eficiente, categoria=self.cat, 
            departamento=self.depto, situacion=self.sit_resuelto, titulo="Resuelta Bien",
            fecha_publicacion=ahora - timedelta(days=10), latitud=0, longitud=0
        )

        # Crear respuesta municipal (hace 5 días -> tardó 5 días en resolver)
        RespuestaMunicipal.objects.create(
            usuario=self.usuario, publicacion=pub, 
            fecha=ahora - timedelta(days=5), 
            descripcion="Listo", acciones="Arreglado", 
            situacion_inicial="Malo", situacion_posterior="Bueno",
            puntuacion=5 # 5 Estrellas
        )

        # Ejecutar análisis
        resultados = StatisticsService.get_analisis_frio_juntas()
        dato_junta = resultados[0]["Junta_Vecinal"]

        self.assertEqual(dato_junta["nombre"], "Villa Eficiente")
        self.assertEqual(dato_junta["total_resueltas"], 1)
        self.assertEqual(dato_junta["eficiencia"], 100.0) # 1 de 1 resuelta
        
        # Verificar promedio de calificación
        self.assertEqual(dato_junta["calificacion_promedio"], 5.0)
        
        # Verificar tiempo de resolución (10 días atrás pub, 5 días atrás resp = 5 días demora)
        # Nota: La lógica usa días naturales para este promedio
        tiempo_texto = resultados[0]["tiempo_promedio_resolucion"]
        self.assertIn("5", tiempo_texto) # Debe decir "5 días" o similar

    def test_junta_mas_critica_vacia(self):
        """Si no hay datos, no debe fallar"""
        Publicacion.objects.all().delete()
        resultados = StatisticsService.get_analisis_criticidad_juntas()
        self.assertEqual(len(resultados), 0)