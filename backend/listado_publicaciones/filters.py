import django_filters
from .models import Publicacion, AnuncioMunicipal
from django.db.models import Q


class PublicacionFilter(django_filters.FilterSet):
    junta_vecinal = django_filters.CharFilter(
        method="filter_junta_vecinal",
        label="Junta Vecinal",
    )
    departamento = django_filters.CharFilter(
        method="filter_departamento_municipal",
        label="Departamento Municipal",
    )
    categoria = django_filters.CharFilter(
        method="filter_categoria",
        label="Categoria",
    )
    situacion = django_filters.CharFilter(
        method="filter_situacion_publicacion",
        label="Situacion Publicacion",
    )
    fecha_publicacion = (
        django_filters.DateFromToRangeFilter()
    )  # Filtro de rango de fechas

    def filter_junta_vecinal(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            junta_vecinal_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for junta in junta_vecinal_list:
                query |= Q(junta_vecinal__nombre_calle__icontains=junta)
            return queryset.filter(query)
        return queryset

    def filter_departamento_municipal(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            departamento_municipal_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for departamento in departamento_municipal_list:
                query |= Q(departamento__nombre__icontains=departamento)
            return queryset.filter(query)
        return queryset

    def filter_categoria(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            categoria_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for categoria in categoria_list:
                query |= Q(categoria__nombre__icontains=categoria)
            return queryset.filter(query)
        return queryset

    def filter_situacion_publicacion(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            situacion_publicacion_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for situacion in situacion_publicacion_list:
                query |= Q(situacion__nombre__icontains=situacion)
            return queryset.filter(query)
        return queryset

    class Meta:
        model = Publicacion
        fields = [
            "junta_vecinal",
            "departamento",
            "categoria",
            "situacion",
            "fecha_publicacion",
        ]


class AnuncioMunicipalFilter(django_filters.FilterSet):
    categoria = django_filters.CharFilter(
        method="filter_categoria",
        label="Categoria",
    )
    fecha = django_filters.DateFromToRangeFilter()  # Filtro de rango de fechas
    estado = django_filters.CharFilter(
        method="filter_estado",
        label="Estado",
    )

    def filter_categoria(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            categoria_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for categoria in categoria_list:
                query |= Q(categoria__nombre__icontains=categoria)
            return queryset.filter(query)
        return queryset

    def filter_estado(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            estado_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for estado in estado_list:
                query |= Q(estado__icontains=estado)
            return queryset.filter(query)
        return queryset

    class Meta:
        model = AnuncioMunicipal
        fields = [
            "categoria",
            "fecha",
            "estado",
        ]
