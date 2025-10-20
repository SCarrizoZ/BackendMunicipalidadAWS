from rest_framework import serializers
from django.db.models import Q
import math
from ..models import (
    Usuario,
    Categoria,
    DepartamentoMunicipal,
    UsuarioDepartamento,
    Evidencia,
    EvidenciaRespuesta,
    JuntaVecinal,
    Publicacion,
    RespuestaMunicipal,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
    HistorialModificaciones,
    Auditoria,
    Columna,
    Tarea,
    Comentario,
    Tablero,
)
import cloudinary
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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
        distancia = calcular_distancia_haversine(
            latitud, longitud, junta.latitud, junta.longitud
        )

        if distancia < distancia_minima:
            distancia_minima = distancia
            junta_mas_cercana = junta

    return junta_mas_cercana


# Serializer para Usuario
class UsuarioListSerializer(serializers.ModelSerializer):
    tipo_usuario_display = serializers.CharField(
        source="get_tipo_usuario_display", read_only=True
    )
    departamento_asignado = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "rut",
            "numero_telefonico_movil",
            "nombre",
            "email",
            "es_administrador",
            "fecha_registro",
            "esta_activo",
            "ultimo_acceso",
            "tipo_usuario",
            "tipo_usuario_display",
            "departamento_asignado",
        ]

    def get_departamento_asignado(self, obj):
        """Retorna el departamento asignado del usuario o 'No aplica'"""
        departamento = obj.get_departamento_asignado()
        if departamento:
            return {
                "id": departamento.id,
                "nombre": departamento.nombre,
                "descripcion": departamento.descripcion,
            }
        return "No aplica"


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Solo para escritura
    tipo_usuario_display = serializers.CharField(
        source="get_tipo_usuario_display", read_only=True
    )
    departamento_asignado = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "rut",
            "numero_telefonico_movil",
            "nombre",
            "password",
            "es_administrador",
            "email",
            "fecha_registro",
            "esta_activo",
            "ultimo_acceso",
            "tipo_usuario",
            "tipo_usuario_display",
            "departamento_asignado",
        ]

    def get_departamento_asignado(self, obj):
        """Retorna el departamento asignado del usuario o 'No aplica'"""
        departamento = obj.get_departamento_asignado()
        if departamento:
            return {
                "id": departamento.id,
                "nombre": departamento.nombre,
                "descripcion": departamento.descripcion,
            }
        return "No aplica"

    def validate_rut(self, value):
        """Validación personalizada para RUT"""
        if not value:
            raise serializers.ValidationError("El RUT es obligatorio")

        # Normalizar RUT (remover puntos y guiones)
        rut_normalizado = value.replace(".", "").replace("-", "")

        # Validar formato básico (8-9 dígitos + dígito verificador)
        if len(rut_normalizado) < 8 or len(rut_normalizado) > 9:
            raise serializers.ValidationError(
                "El RUT debe tener entre 8 y 9 caracteres"
            )

        # Verificar si ya existe (solo en creación)
        if not self.instance:  # Solo validar en creación, no en actualización
            # Buscar en múltiples formatos de RUT para detectar duplicados
            if Usuario.objects.filter(
                Q(rut=rut_normalizado)
                | Q(rut=value)
                | Q(
                    rut__in=[
                        value,  # Formato original
                        rut_normalizado,  # Sin puntos ni guiones
                        (
                            f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}"
                            if len(rut_normalizado) >= 2
                            else rut_normalizado
                        ),  # Con guión
                    ]
                )
            ).exists():
                raise serializers.ValidationError("Ya existe un usuario con este RUT")

        return rut_normalizado

    def validate_email(self, value):
        """Validación personalizada para email"""
        if not value:
            raise serializers.ValidationError("El email es obligatorio")

        # Verificar si ya existe (solo en creación)
        if not self.instance:  # Solo validar en creación, no en actualización
            if Usuario.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("Ya existe un usuario con este email")

        return value.lower()

    def validate(self, data):
        """Validación general del serializer"""
        # Validar que no se creen múltiples administradores si no es necesario
        if data.get("tipo_usuario") == "administrador" and data.get(
            "es_administrador", False
        ):
            # Limitar número de administradores si es necesario
            admin_count = Usuario.objects.filter(
                tipo_usuario="administrador", esta_activo=True
            ).count()
            if admin_count >= 3 and not self.instance:  # Máximo 3 admins
                raise serializers.ValidationError(
                    "No se pueden crear más de 3 administradores"
                )

        return data

    def create(self, validated_data):
        password = validated_data.pop("password")  # Extraer la contraseña
        usuario = Usuario.objects.create(**validated_data)
        usuario.set_password(password)  # Encriptar la contraseña
        usuario.save()
        return usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["id"] = self.user.id
        data["es_administrador"] = self.user.es_administrador
        data["tipo_usuario"] = self.user.tipo_usuario
        data["tipo_usuario_display"] = self.user.get_tipo_usuario_display()
        data["ultimo_acceso"] = self.user.ultimo_acceso

        return data


# Serializer para Departamento Municipal (versión simple para evitar referencias circulares)
class DepartamentoMunicipalSimpleSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = DepartamentoMunicipal
        fields = [
            "id",
            "nombre",
            "descripcion",
            "estado",
            "estado_display",
            "fecha_creacion",
        ]


# Serializer para Departamento Municipal (versión completa)
class DepartamentoMunicipalSerializer(serializers.ModelSerializer):
    jefe_departamento = UsuarioListSerializer(read_only=True)
    funcionarios_count = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = DepartamentoMunicipal
        fields = [
            "id",
            "nombre",
            "descripcion",
            "estado",
            "estado_display",
            "fecha_creacion",
            "jefe_departamento",
            "funcionarios_count",
        ]

    def get_funcionarios_count(self, obj):
        return obj.get_funcionarios_count()


class DepartamentoMunicipalCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartamentoMunicipal
        fields = [
            "id",
            "nombre",
            "descripcion",
            "estado",
            "fecha_creacion",
            "jefe_departamento",
        ]


# Serializer para UsuarioDepartamento
class UsuarioDepartamentoSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer(read_only=True)
    departamento = DepartamentoMunicipalSerializer(read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = UsuarioDepartamento
        fields = [
            "id",
            "usuario",
            "departamento",
            "fecha_asignacion",
            "fecha_fin_asignacion",
            "estado",
            "estado_display",
        ]


class UsuarioDepartamentoCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuarioDepartamento
        fields = [
            "id",
            "usuario",
            "departamento",
            "fecha_asignacion",
            "fecha_fin_asignacion",
            "estado",
        ]


# Serializer para Categoria
class CategoriaSerializer(serializers.ModelSerializer):
    departamento = DepartamentoMunicipalSimpleSerializer(read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    cantidad_publicaciones = serializers.IntegerField(
        source="get_cantidad_publicaciones", read_only=True
    )

    class Meta:
        model = Categoria
        fields = [
            "id",
            "departamento",
            "nombre",
            "descripcion",
            "estado",
            "estado_display",
            "cantidad_publicaciones",
            "fecha_creacion",
        ]

    def get_cantidad_publicaciones(self):
        return self.get_cantidad_publicaciones()


class CategoriaCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = [
            "id",
            "departamento",
            "nombre",
            "descripcion",
            "estado",
            "fecha_creacion",
        ]


# Serializer para Junta Vecinal
class JuntaVecinalSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = JuntaVecinal
        fields = [
            "id",
            "nombre_junta",
            "nombre_calle",
            "numero_calle",
            "latitud",
            "longitud",
            "estado",
            "estado_display",
            "fecha_creacion",
        ]


# Serializer para Situacion de Publicacion
class SituacionPublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SituacionPublicacion
        fields = ["id", "nombre", "descripcion"]


# Serializer para Evidencia
class EvidenciaSerializer(serializers.ModelSerializer):
    publicacion_id = serializers.PrimaryKeyRelatedField(
        queryset=Publicacion.objects.all()
    )

    class Meta:
        model = Evidencia
        fields = [
            "id",
            "archivo",
            "fecha",
            "extension",
            "publicacion_id",
        ]

    def create(self, validated_data):
        # Validar y procesar publicacion_id
        publicacion = validated_data.get("publicacion_id")
        if isinstance(publicacion, Publicacion):
            validated_data["publicacion_id"] = (
                publicacion.id
            )  # Convertir a ID si es un objeto
        # Procesar el archivo con Cloudinary
        archivo = validated_data.pop("archivo")
        upload_data = cloudinary.uploader.upload(archivo)
        url_completa = upload_data["url"]
        ruta_relativa = url_completa.split("de06451wd/")[1]
        validated_data["archivo"] = ruta_relativa
        # Crear y devolver la instancia de Evidencia
        return Evidencia.objects.create(**validated_data)


# Serializer para Publicacion
class PublicacionListSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer(read_only=True)
    junta_vecinal = JuntaVecinalSerializer(read_only=True)
    categoria = CategoriaSerializer(read_only=True)
    departamento = DepartamentoMunicipalSimpleSerializer(read_only=True)
    situacion = SituacionPublicacionSerializer(read_only=True)
    evidencias = EvidenciaSerializer(many=True, read_only=True, source="evidencia_set")
    prioridad_display = serializers.CharField(
        source="get_prioridad_display", read_only=True
    )
    encargado = UsuarioListSerializer(read_only=True)

    class Meta:
        model = Publicacion
        fields = [
            "id",
            "codigo",
            "ubicacion",
            "usuario",
            "junta_vecinal",
            "categoria",
            "departamento",
            "descripcion",
            "situacion",
            "es_incognito",
            "encargado",
            "fecha_publicacion",
            "titulo",
            "latitud",
            "longitud",
            "prioridad",
            "prioridad_display",
            "evidencias",
        ]


class PublicacionCreateUpdateSerializer(serializers.ModelSerializer):
    junta_vecinal = serializers.PrimaryKeyRelatedField(
        queryset=JuntaVecinal.objects.filter(estado="habilitado"),
        required=False,
        allow_null=True,
    )
    auto_detectar_junta = serializers.BooleanField(
        write_only=True,
        required=False,
        help_text="Si es True, detecta automáticamente la junta vecinal más cercana basada en latitud y longitud",
    )
    junta_vecinal_info = serializers.SerializerMethodField(read_only=True)
    distancia_a_junta_km = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Publicacion
        fields = [
            "id",
            "codigo",
            "ubicacion",
            "usuario",
            "junta_vecinal",
            "categoria",
            "departamento",
            "descripcion",
            "es_incognito",
            "encargado",
            "situacion",
            "fecha_publicacion",
            "titulo",
            "latitud",
            "longitud",
            "prioridad",
            "auto_detectar_junta",
            "junta_vecinal_info",
            "distancia_a_junta_km",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si es una actualización (instance existe), hacer campos opcionales
        if self.instance:
            self.fields["latitud"].required = False
            self.fields["longitud"].required = False
            # Por defecto, no auto-detectar en actualizaciones
            self.fields["auto_detectar_junta"].default = False
        else:
            # Si es creación, requerir coordenadas
            self.fields["latitud"].required = True
            self.fields["longitud"].required = True
            # Por defecto, auto-detectar en creaciones
            self.fields["auto_detectar_junta"].default = True

    def validate(self, data):
        """
        Validación personalizada para auto-detectar junta vecinal si es necesario.
        """
        auto_detectar = data.get(
            "auto_detectar_junta", self.fields["auto_detectar_junta"].default
        )

        # Si es creación, siempre requerir coordenadas
        if not self.instance:
            latitud = data.get("latitud")
            longitud = data.get("longitud")

            if not latitud or not longitud:
                raise serializers.ValidationError(
                    {
                        "latitud": "La latitud es requerida para crear una publicación.",
                        "longitud": "La longitud es requerida para crear una publicación.",
                    }
                )

            # Auto-detección para creación
            if auto_detectar and not data.get("junta_vecinal"):
                junta_mas_cercana = encontrar_junta_vecinal_mas_cercana(
                    latitud, longitud
                )
                if junta_mas_cercana:
                    data["junta_vecinal"] = junta_mas_cercana
                else:
                    raise serializers.ValidationError(
                        {
                            "junta_vecinal": "No se pudo encontrar una junta vecinal cercana. "
                            "Por favor, seleccione una manualmente o verifique las coordenadas."
                        }
                    )
            elif not data.get("junta_vecinal") and not auto_detectar:
                raise serializers.ValidationError(
                    {
                        "junta_vecinal": "Debe proporcionar una junta vecinal o habilitar la detección automática."
                    }
                )

        # Si es actualización y quiere auto-detectar, validar coordenadas
        elif auto_detectar:
            latitud = data.get("latitud") or self.instance.latitud
            longitud = data.get("longitud") or self.instance.longitud

            if not latitud or not longitud:
                raise serializers.ValidationError(
                    {
                        "coordenadas": "Se requieren coordenadas válidas (latitud y longitud) para auto-detectar junta vecinal."
                    }
                )

            # Auto-detección para actualización
            junta_mas_cercana = encontrar_junta_vecinal_mas_cercana(latitud, longitud)
            if junta_mas_cercana:
                data["junta_vecinal"] = junta_mas_cercana
            else:
                raise serializers.ValidationError(
                    {
                        "junta_vecinal": "No se pudo encontrar una junta vecinal cercana con las coordenadas proporcionadas."
                    }
                )

        # Remover el campo auto_detectar_junta antes de guardar
        data.pop("auto_detectar_junta", None)

        return data

    def create(self, validated_data):
        """Crear publicación con auditoría implícita del auto-detect"""
        instance = super().create(validated_data)

        # Calcular y almacenar distancia para la respuesta
        if instance.junta_vecinal:
            try:
                distancia = calcular_distancia_haversine(
                    instance.latitud,
                    instance.longitud,
                    instance.junta_vecinal.latitud,
                    instance.junta_vecinal.longitud,
                )
                instance._distancia_calculada = distancia
            except Exception:
                instance._distancia_calculada = None

        return instance

    def update(self, instance, validated_data):
        """Actualizar publicación manteniendo lógica de auto-detección"""
        updated_instance = super().update(instance, validated_data)

        # Calcular y almacenar distancia para la respuesta
        if updated_instance.junta_vecinal:
            try:
                distancia = calcular_distancia_haversine(
                    updated_instance.latitud,
                    updated_instance.longitud,
                    updated_instance.junta_vecinal.latitud,
                    updated_instance.junta_vecinal.longitud,
                )
                updated_instance._distancia_calculada = distancia
            except Exception:
                updated_instance._distancia_calculada = None

        return updated_instance

    def get_junta_vecinal_info(self, obj):
        """Información detallada de la junta vecinal asignada"""
        if obj.junta_vecinal:
            distancia = self.get_distancia_a_junta_km(obj)
            return {
                "id": obj.junta_vecinal.id,
                "nombre_junta": obj.junta_vecinal.nombre_junta,
                "direccion": f"{obj.junta_vecinal.nombre_calle} {obj.junta_vecinal.numero_calle}",
                "distancia_aproximada": distancia,
            }
        return None

    def get_distancia_a_junta_km(self, obj):
        """Calcula la distancia a la junta vecinal asignada"""
        # Si ya se calculó en create/update, usar ese valor
        if hasattr(obj, "_distancia_calculada"):
            return (
                round(obj._distancia_calculada, 2) if obj._distancia_calculada else None
            )

        # Calcular si no existe
        if obj.junta_vecinal and obj.latitud and obj.longitud:
            try:
                distancia = calcular_distancia_haversine(
                    obj.latitud,
                    obj.longitud,
                    obj.junta_vecinal.latitud,
                    obj.junta_vecinal.longitud,
                )
                return round(distancia, 2)
            except Exception:
                return None
        return None

    def to_representation(self, instance):
        """
        Personalizar la representación para incluir información adicional.
        """
        representation = super().to_representation(instance)

        # Asegurar que junta_vecinal_info y distancia estén disponibles
        if instance.junta_vecinal and not representation.get("junta_vecinal_info"):
            representation["junta_vecinal_info"] = self.get_junta_vecinal_info(instance)
            representation["distancia_a_junta_km"] = self.get_distancia_a_junta_km(
                instance
            )

        return representation


# Serializer para Imagen Anuncio
class ImagenAnuncioSerializer(serializers.ModelSerializer):
    anuncio = serializers.PrimaryKeyRelatedField(
        queryset=AnuncioMunicipal.objects.all()
    )

    class Meta:
        model = ImagenAnuncio
        fields = [
            "id",
            "anuncio",  # Usar solo este campo para IDs
            "imagen",
            "fecha",
            "extension",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("imagen")
        upload_data = cloudinary.uploader.upload(archivo)
        url_completa = upload_data["url"]
        ruta_relativa = url_completa.split("de06451wd/")[1]
        validated_data["imagen"] = ruta_relativa
        return ImagenAnuncio.objects.create(**validated_data)


# Serializer para Anuncio Municipal
class AnuncioMunicipalListSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer(read_only=True)
    categoria = CategoriaSerializer(read_only=True)
    imagenes = ImagenAnuncioSerializer(
        many=True, read_only=True, source="imagenanuncio_set"
    )

    class Meta:
        model = AnuncioMunicipal
        fields = [
            "id",
            "usuario",
            "titulo",
            "subtitulo",
            "estado",
            "descripcion",
            "categoria",
            "fecha",
            "imagenes",
        ]


class AnuncioMunicipalCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnuncioMunicipal
        fields = [
            "id",
            "usuario",
            "titulo",
            "subtitulo",
            "estado",
            "descripcion",
            "categoria",
            "fecha",
        ]


# Serializer para Evidencia de Respuesta
class EvidenciaRespuestaSerializer(serializers.ModelSerializer):
    respuesta = serializers.PrimaryKeyRelatedField(
        queryset=RespuestaMunicipal.objects.all()
    )

    class Meta:
        model = EvidenciaRespuesta
        fields = [
            "id",
            "respuesta",
            "archivo",
            "fecha",
            "extension",
            "descripcion",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("archivo")
        upload_data = cloudinary.uploader.upload(archivo)
        validated_data["archivo"] = upload_data["url"]
        return EvidenciaRespuesta.objects.create(**validated_data)


# Serializer para Respuesta Municipal
class RespuestaMunicipalCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RespuestaMunicipal
        fields = [
            "id",
            "usuario",
            "publicacion",
            "fecha",
            "descripcion",
            "acciones",
            "situacion_inicial",
            "situacion_posterior",
            "puntuacion",
        ]


class RespuestaMunicipalListSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer(read_only=True)
    publicacion = PublicacionListSerializer(read_only=True)
    evidencias = EvidenciaRespuestaSerializer(many=True, read_only=True)
    puntuacion_display = serializers.SerializerMethodField()

    class Meta:
        model = RespuestaMunicipal
        fields = [
            "id",
            "usuario",
            "publicacion",
            "fecha",
            "descripcion",
            "acciones",
            "situacion_inicial",
            "situacion_posterior",
            "puntuacion",
            "puntuacion_display",
            "evidencias",
        ]

    def get_puntuacion_display(self, obj):
        if obj.puntuacion:
            return f"{obj.puntuacion} estrella{'s' if obj.puntuacion != 1 else ''}"
        return "Sin puntuación"


class RespuestaMunicipalPuntuacionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RespuestaMunicipal
        fields = ["puntuacion"]

    def validate_puntuacion(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La puntuación debe estar entre 1 y 5.")
        return value


# Serializer para Historial de Modificaciones
class HistorialModificacionesSerializer(serializers.ModelSerializer):
    publicacion = PublicacionListSerializer(read_only=True)
    autor = UsuarioListSerializer(read_only=True)

    class Meta:
        model = HistorialModificaciones
        fields = [
            "id",
            "publicacion",
            "fecha",
            "campo_modificado",
            "valor_anterior",
            "valor_nuevo",
            "autor",
        ]


# Serializer para Auditoría
class AuditoriaSerializer(serializers.ModelSerializer):
    autor = UsuarioListSerializer(read_only=True)

    class Meta:
        model = Auditoria
        fields = [
            "id",
            "codigo",
            "autor",
            "accion",
            "fecha",
            "modulo",
            "descripcion",
            "es_exitoso",
        ]


# Serializers para Kanban
class ColumnaSimpleSerializer(serializers.ModelSerializer):
    tareas_count = serializers.SerializerMethodField()

    class Meta:
        model = Columna
        fields = [
            "id",
            "titulo",
            "fecha_creacion",
            "fecha_actualizacion",
            "limite_tareas",
            "tareas_count",
        ]

    def get_tareas_count(self, obj):
        return obj.tareas.count()


# Serializer simple para Publicacion (para evitar referencias circulares)
class PublicacionSimpleSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre", read_only=True)
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    prioridad_display = serializers.CharField(
        source="get_prioridad_display", read_only=True
    )

    class Meta:
        model = Publicacion
        fields = [
            "id",
            "codigo",
            "titulo",
            "descripcion",
            "fecha_publicacion",
            "prioridad",
            "prioridad_display",
            "usuario_nombre",
            "categoria_nombre",
        ]


class TareaListSerializer(serializers.ModelSerializer):
    columna = ColumnaSimpleSerializer(read_only=True)
    encargado = UsuarioListSerializer(read_only=True)
    categoria = CategoriaSerializer(read_only=True)
    publicaciones = PublicacionSimpleSerializer(many=True, read_only=True)
    prioridad_display = serializers.CharField(
        source="get_prioridad_display", read_only=True
    )

    class Meta:
        model = Tarea
        fields = [
            "id",
            "titulo",
            "descripcion",
            "columna",
            "fecha_creacion",
            "fecha_actualizacion",
            "fecha_limite",
            "encargado",
            "prioridad",
            "prioridad_display",
            "categoria",
            "publicaciones",
        ]


class ColumnaSerializer(serializers.ModelSerializer):
    tareas_count = serializers.SerializerMethodField()
    tareas = TareaListSerializer(many=True, read_only=True)

    class Meta:
        model = Columna
        fields = [
            "id",
            "titulo",
            "fecha_creacion",
            "fecha_actualizacion",
            "limite_tareas",
            "tareas_count",
            "tareas",
        ]

    def get_tareas_count(self, obj):
        return obj.tareas.count()


class TareaCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarea
        fields = [
            "id",
            "titulo",
            "descripcion",
            "columna",
            "fecha_limite",
            "encargado",
            "prioridad",
            "categoria",
            "publicaciones",
        ]


class ComentarioSerializer(serializers.ModelSerializer):
    tarea = TareaListSerializer(read_only=True)
    usuario = UsuarioListSerializer(read_only=True)

    class Meta:
        model = Comentario
        fields = [
            "id",
            "tarea",
            "usuario",
            "contenido",
            "fecha_creacion",
        ]


class TableroSerializer(serializers.ModelSerializer):
    columnas = ColumnaSerializer(many=True, read_only=True)
    departamento = DepartamentoMunicipalSimpleSerializer(read_only=True)

    class Meta:
        model = Tablero
        fields = [
            "id",
            "titulo",
            "fecha_creacion",
            "fecha_actualizacion",
            "departamento",
            "columnas",
        ]
