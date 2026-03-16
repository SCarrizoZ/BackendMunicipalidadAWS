from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from ..models import (
    Publicacion, Usuario, Categoria, DepartamentoMunicipal, 
    JuntaVecinal, SituacionPublicacion
)

class IntegrationFiltersTest(APITestCase):
    def setUp(self):
        # 1. Configuración de Usuario
        self.admin = Usuario.objects.create(
            rut="11111111-1", email="admin@muni.cl", nombre="Admin", es_administrador=True
        )
        self.client.force_authenticate(user=self.admin)

        # 2. Datos Maestros
        self.depto_aseo = DepartamentoMunicipal.objects.create(nombre="Aseo")
        self.depto_seguridad = DepartamentoMunicipal.objects.create(nombre="Seguridad")
        
        self.cat_basura = Categoria.objects.create(nombre="Basura", departamento=self.depto_aseo)
        self.cat_robo = Categoria.objects.create(nombre="Robo", departamento=self.depto_seguridad)
        
        self.junta_norte = JuntaVecinal.objects.create(nombre_junta="Norte", latitud=0, longitud=0, numero_calle=1)
        self.junta_sur = JuntaVecinal.objects.create(nombre_junta="Sur", latitud=0, longitud=0, numero_calle=2)
        
        # Aseguramos IDs específicos para las situaciones si el código depende de ello (ej. ID 4 = Pendiente)
        self.sit_resuelto = SituacionPublicacion.objects.create(id=1, nombre="Resuelto")
        self.sit_pendiente = SituacionPublicacion.objects.create(id=4, nombre="Pendiente")

        ahora = timezone.now()

        # 3. Datos Escenario A: "Aseo Antiguo" (5 publicaciones)
        for i in range(5):
            Publicacion.objects.create(
                usuario=self.admin, junta_vecinal=self.junta_norte, categoria=self.cat_basura,
                departamento=self.depto_aseo, situacion=self.sit_resuelto, titulo=f"Basura {i}",
                fecha_publicacion=ahora - timedelta(days=60), latitud=0, longitud=0
            )

        # 4. Datos Escenario B: "Seguridad Reciente" (3 publicaciones)
        for i in range(3):
            Publicacion.objects.create(
                usuario=self.admin, junta_vecinal=self.junta_sur, categoria=self.cat_robo,
                departamento=self.depto_seguridad, situacion=self.sit_pendiente, titulo=f"Robo {i}",
                fecha_publicacion=ahora, latitud=0, longitud=0
            )

    def test_filtro_categoria_impacta_todo(self):
        """
        Prueba: Al filtrar por Categoría 'Basura', todos los widgets se actualizan.
        """
        # CORRECCIÓN: Usamos el nombre porque filter_categoria usa icontains
        params = f"?categoria={self.cat_basura.nombre}"
        
        # 1. Widget Resumen
        resp_resumen = self.client.get(f"/api/v1/estadisticas/resumen/{params}")
        # Esperamos 5 (solo las de basura)
        self.assertEqual(resp_resumen.data['total_publicaciones'], 5, "Filtro categoría falló en Resumen")
        self.assertEqual(resp_resumen.data['resueltos'], 5)
        self.assertEqual(resp_resumen.data['pendientes'], 0)

        # 2. Widget Tasa Resolución (Debe salir Aseo)
        resp_tasa = self.client.get(f"/api/v1/estadisticas/tasa-resolucion/{params}")
        self.assertIn("Aseo", resp_tasa.data, "El depto Aseo debería aparecer")
        self.assertNotIn("Seguridad", resp_tasa.data, "El depto Seguridad no debería aparecer")

    def test_filtro_departamento_impacta_todo(self):
        """Prueba filtro por Departamento (por nombre)"""
        params = f"?departamento={self.depto_seguridad.nombre}"
        
        resp_resumen = self.client.get(f"/api/v1/estadisticas/resumen/{params}")
        # Esperamos 3 (solo las de seguridad/robo)
        self.assertEqual(resp_resumen.data['total_publicaciones'], 3, "Filtro departamento falló")

    def test_filtro_fecha_rango(self):
        """
        Prueba: Rango de fechas (DateFromToRangeFilter).
        """
        # CORRECCIÓN: Usamos _after y _before que son los defaults de Django Filter
        inicio = (timezone.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        fin = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        params = f"?fecha_publicacion_after={inicio}&fecha_publicacion_before={fin}"

        resp = self.client.get(f"/api/v1/estadisticas/resumen/{params}")
        
        # Solo las 3 de "hoy" (Robo) entran en el rango. Las de basura son de hace 60 días.
        self.assertEqual(resp.data['total_publicaciones'], 3, "El filtro de fechas falló")


class PaginationTest(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create(rut="3-3", email="p@p.cl", nombre="Pag", es_administrador=True)
        self.client.force_authenticate(user=self.usuario)
        self.depto = DepartamentoMunicipal.objects.create(nombre="D")
        self.cat = Categoria.objects.create(nombre="C", departamento=self.depto)
        self.junta = JuntaVecinal.objects.create(nombre_junta="J", latitud=0, longitud=0, numero_calle=1)
        self.sit = SituacionPublicacion.objects.create(id=1, nombre="S")
        
        # Crear 25 items
        for i in range(25):
            Publicacion.objects.create(
                usuario=self.usuario, junta_vecinal=self.junta, categoria=self.cat,
                departamento=self.depto, titulo=f"Item {i}", latitud=0, longitud=0, situacion=self.sit
            )

    def test_paginacion_navegacion(self):
        # Página 1
        resp_p1 = self.client.get("/api/v1/publicaciones/")
        self.assertEqual(resp_p1.status_code, status.HTTP_200_OK)
        self.assertIn('next', resp_p1.data)
        
        # Página 2
        if resp_p1.data['next']:
            resp_p2 = self.client.get(resp_p1.data['next'])
            self.assertEqual(resp_p2.status_code, status.HTTP_200_OK)
            self.assertNotEqual(resp_p1.data['results'][0]['id'], resp_p2.data['results'][0]['id'])

    def test_paginacion_tamano_dinamico(self):
        # Forzar tamaño de página a 5
        resp = self.client.get("/api/v1/publicaciones/?page_size=5")
        self.assertEqual(len(resp.data['results']), 5)