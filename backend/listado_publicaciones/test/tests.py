from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

# Importamos desde las NUEVAS ubicaciones para verificar que el __init__.py funciona
from ..models import (
    Publicacion, 
    Categoria, 
    DepartamentoMunicipal, 
    JuntaVecinal, 
    SituacionPublicacion
)

Usuario = get_user_model()

class RefactoringModelImportTest(TestCase):
    """
    Prueba que los modelos se pueden importar correctamente desde el paquete models
    gracias al archivo __init__.py.
    """
    def test_imports_work(self):
        try:
            p = Publicacion()
            c = Categoria()
            d = DepartamentoMunicipal()
        except ImportError as e:
            self.fail(f"La refactorización rompió las importaciones de modelos: {e}")

class PublicacionViewSetTest(APITestCase):
    def setUp(self):
        # 1. Crear datos de prueba básicos
        self.usuario = Usuario.objects.create(
            rut="12345678-9", 
            email="test@muni.cl", 
            nombre="Test Admin", 
            es_administrador=True,
            tipo_usuario="administrador"
        )
        self.depto = DepartamentoMunicipal.objects.create(nombre="Aseo y Ornato")
        self.categoria = Categoria.objects.create(nombre="Basura", departamento=self.depto)
        self.junta = JuntaVecinal.objects.create(
            nombre_junta="Junta Central", 
            latitud=Decimal("-22.0"), 
            longitud=Decimal("-68.0"),
            numero_calle=123
        )
        self.situacion = SituacionPublicacion.objects.create(nombre="Pendiente", id=4)

        # 2. Autenticar cliente
        self.client.force_authenticate(user=self.usuario)

        # 3. URL base (ajustar según tu urls.py)
        self.url = "/api/v1/publicaciones/"

    def test_crear_publicacion(self):
        """
        Verifica que el ViewSet refactorizado en views/publicaciones.py funciona
        """
        data = {
            "titulo": "Hoyo en la calle",
            "descripcion": "Peligroso",
            "latitud": -22.456,
            "longitud": -68.901,
            "categoria": self.categoria.id,
            "junta_vecinal": self.junta.id,
            "prioridad": "alta",
            # Campos automáticos o requeridos por el serializer
            "usuario": self.usuario.id, 
            "auto_detectar_junta": False 
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Publicacion.objects.count(), 1)
        self.assertEqual(Publicacion.objects.get().titulo, "Hoyo en la calle")

    def test_listar_publicaciones(self):
        """Verifica GET /publicaciones/"""
        Publicacion.objects.create(
            usuario=self.usuario,
            junta_vecinal=self.junta,
            categoria=self.categoria,
            departamento=self.depto,
            titulo="Pub 1",
            latitud=0, longitud=0,
            situacion=self.situacion
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)

class EstadisticasViewTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(
            rut="99999999-K", 
            email="stats@muni.cl", 
            nombre="Stats User", 
            es_administrador=True,
            tipo_usuario="administrador"
        )
        self.client.force_authenticate(user=self.usuario)
        
        # Crear datos para estadísticas
        depto = DepartamentoMunicipal.objects.create(nombre="Estadistica Dept")
        cat = Categoria.objects.create(nombre="Test Cat", departamento=depto)
        junta = JuntaVecinal.objects.create(nombre_junta="Junta Stats", latitud=0, longitud=0, numero_calle=1)
        sit_resuelto = SituacionPublicacion.objects.create(nombre="Resuelto")
        sit_pendiente = SituacionPublicacion.objects.create(nombre="Pendiente")

        # Crear 1 resuelta y 1 pendiente
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=junta, categoria=cat, departamento=depto,
            titulo="Resuelta", latitud=0, longitud=0, situacion=sit_resuelto
        )
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=junta, categoria=cat, departamento=depto,
            titulo="Pendiente", latitud=0, longitud=0, situacion=sit_pendiente
        )

    def test_resumen_estadisticas(self):
        """
        Verifica que views/estadisticas.py calcula correctamente los totales
        """
        url = "/api/v1/estadisticas/resumen/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Debería haber 2 publicaciones en total
        self.assertEqual(response.data['total_publicaciones'], 2)
        # Debería haber 1 resuelta
        self.assertEqual(response.data['resueltos'], 1)
        # Tasa de resolución debería ser 50%
        self.assertEqual(response.data['tasa_resolucion'], 50.0)

    def test_junta_mas_critica(self):
        """Verifica la lógica de junta más crítica"""
        url = "/api/v1/estadisticas/junta-critica/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # La junta creada tiene 1 pendiente, debería aparecer
        self.assertEqual(response.data['junta_vecinal__nombre_junta'], "Junta Stats")
        self.assertEqual(response.data['total_pendientes'], 1)

class ReportesViewTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(
            rut="88888888-8", email="report@muni.cl", nombre="Report User", es_administrador=True
        )
        self.client.force_authenticate(user=self.usuario)

    def test_generar_excel(self):
        """Verifica que la vista de reporte Excel responde y genera archivo"""
        url = "/api/v1/reportes/excel/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.get('Content-Type'), 
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_generar_pdf(self):
        """Verifica que la vista de reporte PDF responde"""
        url = "/api/v1/reportes/pdf/"
        # Se requiere al menos un dato para no dar 404 en el reporte
        # (Depende de tu lógica si retorna 404 cuando count=0)
        
        # ... crear datos dummy ...
        depto = DepartamentoMunicipal.objects.create(nombre="PDF Dept")
        cat = Categoria.objects.create(nombre="PDF Cat", departamento=depto)
        junta = JuntaVecinal.objects.create(nombre_junta="Junta PDF", latitud=0, longitud=0, numero_calle=1)
        sit = SituacionPublicacion.objects.create(nombre="Recibido")
        Publicacion.objects.create(
            usuario=self.usuario, junta_vecinal=junta, categoria=cat, departamento=depto,
            titulo="PDF Pub", latitud=0, longitud=0, situacion=sit
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), "application/pdf")