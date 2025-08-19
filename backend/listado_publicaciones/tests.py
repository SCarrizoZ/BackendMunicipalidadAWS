from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .views.v1 import ResumenEstadisticas
from .models import Publicacion, Usuario, Categoria

# filepath: d:\Inacap\ProyectoMunicipalAWS\backend\listado_publicaciones\test_tests.py


class CustomTokenObtainPairViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_token_obtain_pair(self):
        response = self.client.post(
            "/api/token/", {"username": "testuser", "password": "testpassword"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PublicacionViewSetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = APIClient()
        cls.categoria = Categoria.objects.create(nombre="Test Categoria")
        cls.usuario = Usuario.objects.create(
            nombre="Test Usuario", email="test@example.com"
        )
        cls.publicacion = Publicacion.objects.create(
            titulo="Test Publicacion",
            descripcion="Test Descripcion",
            categoria=cls.categoria,
            usuario=cls.usuario,
        )

    def test_list_publicaciones(self):
        response = self.client.get("/api/publicaciones/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_publicacion(self):
        response = self.client.get(f"/api/publicaciones/{self.publicacion.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ResumenEstadisticasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = APIClient()
        cls.categoria = Categoria.objects.create(nombre="Test Categoria")
        cls.usuario = Usuario.objects.create(
            nombre="Test Usuario", email="test@example.com"
        )
        cls.publicacion = Publicacion.objects.create(
            titulo="Test Publicacion",
            descripcion="Test Descripcion",
            categoria=cls.categoria,
            usuario=cls.usuario,
        )

    def test_resumen_estadisticas(self):
        response = self.client.get("/api/resumen-estadisticas/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("publicaciones", response.data)
        self.assertIn("usuarios", response.data)
        self.assertIn("problemas_resueltos", response.data)
