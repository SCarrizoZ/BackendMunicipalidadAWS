from django.test import TestCase
from decimal import Decimal
from ..models import JuntaVecinal, Publicacion, Categoria, DepartamentoMunicipal, Usuario, SituacionPublicacion
from ..services.geo_service import GeoService
from ..services.statistics_service import StatisticsService

class GeoServiceTest(TestCase):
    def setUp(self):
        # Creamos 3 Juntas Vecinales en ubicaciones conocidas (Coordenadas aproximadas de ejemplo)
        # Junta 1: Plaza de Armas de Santiago (Referencia central)
        self.junta_centro = JuntaVecinal.objects.create(
            nombre_junta="Junta Centro",
            nombre_calle="Calle A",
            numero_calle=1,
            latitud=Decimal("-33.4372"),
            longitud=Decimal("-70.6506"),
            estado="habilitado"
        )
        
        # Junta 2: Cerro Santa Lucía (Aprox 1km al este)
        self.junta_este = JuntaVecinal.objects.create(
            nombre_junta="Junta Santa Lucia",
            nombre_calle="Calle B",
            numero_calle=2,
            latitud=Decimal("-33.4410"),
            longitud=Decimal("-70.6400"),
            estado="habilitado"
        )

        # Junta 3: Parque O'Higgins (Aprox 2-3km al sur)
        self.junta_sur = JuntaVecinal.objects.create(
            nombre_junta="Junta Parque",
            nombre_calle="Calle C",
            numero_calle=3,
            latitud=Decimal("-33.4650"),
            longitud=Decimal("-70.6600"),
            estado="habilitado"
        )
        
        # Junta Deshabilitada (Muy cerca del centro, pero no debería ser seleccionada)
        self.junta_inactiva = JuntaVecinal.objects.create(
            nombre_junta="Junta Inactiva",
            nombre_calle="Calle D",
            numero_calle=4,
            latitud=Decimal("-33.4373"), # Casi igual a Junta Centro
            longitud=Decimal("-70.6507"),
            estado="deshabilitado"
        )

    def test_calculo_distancia_haversine(self):
        """
        Prueba que la fórmula matemática de Haversine sea precisa.
        Distancia entre (-33.4372, -70.6506) y (-33.4410, -70.6400)
        """
        # Lat/Lon del Centro vs Santa Lucía
        distancia = GeoService.calcular_distancia_haversine(
            -33.4372, -70.6506,
            -33.4410, -70.6400
        )
        # La distancia debería ser aprox 1km (entre 0.9 y 1.1 km)
        self.assertTrue(0.9 < distancia < 1.1, f"La distancia calculada {distancia}km no es la esperada")

    def test_encontrar_junta_mas_cercana_caso_exacto(self):
        """Si estoy parado exactamente en la junta, debe devolver esa junta"""
        junta = GeoService.encontrar_junta_vecinal_mas_cercana(-33.4372, -70.6506)
        self.assertEqual(junta, self.junta_centro)

    def test_encontrar_junta_mas_cercana_punto_medio(self):
        """
        Si estoy en un punto intermedio, debe elegir la más cercana matemáticamente.
        Probamos un punto ligeramente más cerca del Este que del Centro.
        """
        # Punto más cercano a Santa Lucía (-33.4400, -70.6410)
        junta = GeoService.encontrar_junta_vecinal_mas_cercana(-33.4400, -70.6410)
        self.assertEqual(junta, self.junta_este)

    def test_ignorar_juntas_deshabilitadas(self):
        """
        La 'Junta Inactiva' está casi en la misma posición que el usuario,
        pero como está deshabilitada, el servicio debe devolver la 'Junta Centro'.
        """
        # Coordenadas de la junta inactiva
        junta = GeoService.encontrar_junta_vecinal_mas_cercana(-33.4373, -70.6507)
        
        self.assertNotEqual(junta, self.junta_inactiva)
        self.assertEqual(junta, self.junta_centro)

    def test_sin_juntas_disponibles(self):
        """Si borramos todas las juntas habilitadas, debe devolver None"""
        JuntaVecinal.objects.filter(estado="habilitado").delete()
        junta = GeoService.encontrar_junta_vecinal_mas_cercana(-33.4372, -70.6506)
        self.assertIsNone(junta)


class StatisticsServiceTest(TestCase):
    def setUp(self):
        # Configuración básica para estadísticas
        self.usuario = Usuario.objects.create(rut="1-9", email="a@a.cl", nombre="A")
        self.depto = DepartamentoMunicipal.objects.create(nombre="Depto A")
        self.categoria = Categoria.objects.create(nombre="Cat A", departamento=self.depto)
        self.junta = JuntaVecinal.objects.create(
            nombre_junta="Junta A", latitud=0, longitud=0, numero_calle=1
        )
        
        # Situaciones
        self.sit_resuelto = SituacionPublicacion.objects.create(nombre="Resuelto")
        self.sit_pendiente = SituacionPublicacion.objects.create(nombre="Pendiente")
        
        # Crear datos: 3 Resueltas, 1 Pendiente en Depto A
        for _ in range(3):
            Publicacion.objects.create(
                usuario=self.usuario, junta_vecinal=self.junta, categoria=self.categoria,
                departamento=self.depto, titulo="Resuelta", latitud=0, longitud=0,
                situacion=self.sit_resuelto
            )
        
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=self.junta, categoria=self.categoria,
            departamento=self.depto, titulo="Pendiente", latitud=0, longitud=0,
            situacion=self.sit_pendiente
        )

    def test_calculo_tasa_resolucion_departamento(self):
        """Prueba que el cálculo de porcentaje sea correcto en el servicio"""
        stats = StatisticsService.get_tasa_resolucion_departamento()
        
        # Deberíamos tener 1 departamento en la lista
        self.assertEqual(len(stats), 1)
        stat_depto = stats[0]
        
        self.assertEqual(stat_depto['departamento'], "Depto A")
        self.assertEqual(stat_depto['total'], 4)
        self.assertEqual(stat_depto['resueltos'], 3)
        # 3 de 4 es 75%
        self.assertEqual(stat_depto['tasa'], 75.0)

    def test_resumen_estadisticas_servicio(self):
        """Verifica los totales globales"""
        resumen = StatisticsService.get_resumen_estadisticas()
        
        self.assertEqual(resumen['total_publicaciones'], 4)
        self.assertEqual(resumen['resueltos'], 3)
        self.assertEqual(resumen['pendientes'], 1)
        self.assertEqual(resumen['tasa_resolucion'], 75.0)