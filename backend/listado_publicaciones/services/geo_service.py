import math
from ..models import JuntaVecinal

class GeoService:
    @staticmethod
    def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
        """
        Calcula la distancia entre dos puntos geográficos usando la fórmula de Haversine.
        Retorna la distancia en kilómetros.
        """
        # Convertir grados a radianes
        lat1, lon1, lat2, lon2 = map(
            math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
        )

        # Fórmula de Haversine
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Radio de la Tierra en kilómetros
        r = 6371
        return c * r

    @staticmethod
    def encontrar_junta_vecinal_mas_cercana(latitud, longitud):
        """
        Encuentra la junta vecinal más cercana a las coordenadas dadas.
        Retorna la instancia de JuntaVecinal más cercana.
        """
        juntas_vecinales = JuntaVecinal.objects.filter(estado="habilitado")

        if not juntas_vecinales.exists():
            return None

        distancia_minima = float("inf")
        junta_mas_cercana = None

        for junta in juntas_vecinales:
            distancia = GeoService.calcular_distancia_haversine(
                latitud, longitud, junta.latitud, junta.longitud
            )

            if distancia < distancia_minima:
                distancia_minima = distancia
                junta_mas_cercana = junta

        return junta_mas_cercana
