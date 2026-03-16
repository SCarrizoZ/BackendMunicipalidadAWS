from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from decimal import Decimal
from ..models import JuntaVecinal, Publicacion, Categoria, DepartamentoMunicipal, Usuario, SituacionPublicacion, Evidencia
from ..services.geo_service import GeoService
from ..services.statistics_service import StatisticsService
from ..services.media_service import MediaService

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
        
        # 1. Verificar que el departamento existe como CLAVE del diccionario
        # (El servicio devuelve { "Nombre Depto": { "Mes": datos } })
        self.assertIn("Depto A", stats)
        
        # 2. Obtener los datos del departamento
        datos_depto = stats["Depto A"]
        
        # 3. Como no sabemos el mes exacto (depende de la fecha actual),
        # tomamos el primer mes disponible en los valores
        stat_mes = list(datos_depto.values())[0]
        
        # 4. Validar los cálculos
        self.assertEqual(stat_mes['total'], 4)
        self.assertEqual(stat_mes['resueltos'], 3)
        # 3 de 4 es 75%
        self.assertEqual(stat_mes['tasa_resolucion'], 75.0)

    def test_resumen_estadisticas_servicio(self):
        """Verifica los totales globales"""
        resumen = StatisticsService.get_resumen_estadisticas()
        
        self.assertEqual(resumen['total_publicaciones'], 4)
        self.assertEqual(resumen['resueltos'], 3)
        self.assertEqual(resumen['pendientes'], 1)
        self.assertEqual(resumen['tasa_resolucion'], 75.0)

class EvidenciaUploadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # 1. Crear usuario y autenticar
        self.usuario = Usuario.objects.create(
            rut="12345678-9", email="test@muni.cl", nombre="Vecino Test"
        )
        self.client.force_authenticate(user=self.usuario)

        # 2. Crear datos base necesarios para una publicación
        self.depto = DepartamentoMunicipal.objects.create(nombre="Aseo")
        self.categoria = Categoria.objects.create(nombre="Basura", departamento=self.depto)
        self.junta = JuntaVecinal.objects.create(
            nombre_junta="Junta A", latitud=0, longitud=0, numero_calle=100
        )
        self.situacion = SituacionPublicacion.objects.create(nombre="Pendiente")

        # 3. Crear la publicación a la que adjuntaremos la evidencia
        self.publicacion = Publicacion.objects.create(
            titulo="Basura en la calle",
            usuario=self.usuario,
            junta_vecinal=self.junta,
            categoria=self.categoria,
            departamento=self.depto,
            situacion=self.situacion,
            latitud=0, longitud=0
        )

    # El 'patch' intercepta la llamada al servicio real
    @patch('listado_publicaciones.services.media_service.MediaService.upload_image')
    def test_subir_evidencia_con_mock(self, mock_upload):
        """
        Prueba la creación de una evidencia simulando la respuesta de Cloudinary/MediaService.
        """
        # A. Configurar el comportamiento del Mock
        # Le decimos: "Cuando te llamen, no hagas nada y devuelve este string"
        mock_upload.return_value = "v1/evidencias/imagen_falsa.jpg"

        # B. Crear un archivo falso en memoria (imagen dummy)
        imagen_dummy = SimpleUploadedFile(
            name='foto_denuncia.jpg',
            content=b'imagen_falsa',
            content_type='image/jpeg'
        )

        # C. Datos del POST
        data = {
            "publicacion_id": self.publicacion.id,
            "archivo": imagen_dummy,
            "nombre": "Foto de la basura",
            "extension": "jpg"
        }

        # D. Ejecutar la petición
        # Nota: format='multipart' es OBLIGATORIO para subir archivos
        response = self.client.post('/api/v1/evidencias/', data, format='multipart')

        # E. Aserciones (Validaciones)
        
        # 1. Verificar que la API respondió 201 Created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 2. Verificar que nuestro servicio fue llamado (y no Cloudinary real)
        mock_upload.assert_called_once() 

        # 3. Verificar que se guardó en la base de datos con la URL simulada
        evidencia_creada = Evidencia.objects.get(id=response.data['id'])
        # Convertimos el objeto CloudinaryResource a string para compararlo
        self.assertEqual(str(evidencia_creada.archivo), "evidencias/imagen_falsa")
        self.assertEqual(evidencia_creada.publicacion, self.publicacion)