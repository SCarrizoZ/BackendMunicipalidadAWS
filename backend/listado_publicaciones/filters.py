import django_filters
from .models import Publicacion, AnuncioMunicipal, Usuario, JuntaVecinal
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
    usuario_id = django_filters.CharFilter(
        method="filter_usuario_id",
        label="Usuario ID",
    )
    fecha_publicacion = (
        django_filters.DateFromToRangeFilter()
    )  # Filtro de rango de fechas
    con_modificaciones = django_filters.BooleanFilter(
        method="filter_con_modificaciones",
        label="Indica si la publicación tiene modificaciones en su historial",
    )

    def filter_con_modificaciones(self, queryset, name, value):
        """
        Filtra las publicaciones basado en si tienen o no modificaciones.
        'value' será True o False.
        """
        related_name = "historialmodificaciones"

        if value:
            # Si ?con_modificaciones=true
            return queryset.filter(**{f"{related_name}__isnull": False}).distinct()

        # Si es ?con_modificaciones=false
        return queryset.filter(**{f"{related_name}__isnull": True}).distinct()

    def filter_junta_vecinal(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            junta_vecinal_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for junta in junta_vecinal_list:
                query |= Q(junta_vecinal__nombre_junta__icontains=junta)
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

    def filter_usuario_id(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            usuario_id_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for usuario_id in usuario_id_list:
                try:
                    # Validamos que sea un ID válido (entero)
                    usuario_id_int = int(usuario_id.strip())
                    query |= Q(usuario_id=usuario_id_int)
                except ValueError:
                    # Si no es un entero válido, lo ignoramos
                    continue
            return queryset.filter(query) if query.children else queryset
        return queryset

    class Meta:
        model = Publicacion
        fields = [
            "junta_vecinal",
            "departamento",
            "categoria",
            "situacion",
            "usuario_id",
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


class UsuarioRolFilter(django_filters.FilterSet):
    tipo_usuario = django_filters.CharFilter(
        method="filter_tipo_usuario",
        label="Tipo Usuario",
    )

    def filter_tipo_usuario(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            tipo_usuario_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for tipo in tipo_usuario_list:
                query |= Q(tipo_usuario__icontains=tipo)
            return queryset.filter(query)
        return queryset

    class Meta:
        model = Usuario  # Cambia esto al modelo adecuado si es necesario
        fields = [
            "tipo_usuario",
        ]


class JuntaVecinalFilter(django_filters.FilterSet):
    estado = django_filters.CharFilter(
        method="filter_estado",
        label="Estado",
    )
    fecha_inicio = django_filters.DateFilter(
        field_name="fecha_creacion", lookup_expr="gte", label="Fecha Inicio"
    )
    fecha_fin = django_filters.DateFilter(
        field_name="fecha_creacion", lookup_expr="lte", label="Fecha Fin"
    )
    nombre = django_filters.CharFilter(
        method="filter_nombre",
        label="Nombre (Título)",
    )

    def filter_estado(self, queryset, name, value):
        if value:
            # Dividimos los valores en caso de que lleguen como una cadena
            estado_list = value.split(",")
            # Creamos una Q para filtrar usando OR
            query = Q()
            for estado in estado_list:
                query |= Q(estado__iexact=estado.strip())
            return queryset.filter(query)
        return queryset

    def filter_nombre(self, queryset, name, value):
        if value:
            # Buscar por nombre_junta o nombre_calle
            return queryset.filter(
                Q(nombre_junta__icontains=value) | Q(nombre_calle__icontains=value)
            )
        return queryset

    class Meta:
        model = JuntaVecinal
        fields = [
            "estado",
            "fecha_inicio",
            "fecha_fin",
            "nombre",
        ]

