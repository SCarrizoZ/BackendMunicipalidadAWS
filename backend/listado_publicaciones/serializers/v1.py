from rest_framework import serializers
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


# Serializer para Usuario
class UsuarioListSerializer(serializers.ModelSerializer):
    tipo_usuario_display = serializers.CharField(
        source="get_tipo_usuario_display", read_only=True
    )

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
        ]


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Solo para escritura
    tipo_usuario_display = serializers.CharField(
        source="get_tipo_usuario_display", read_only=True
    )

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
        ]

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


# Serializer para Categoria
class CategoriaSerializer(serializers.ModelSerializer):
    departamento = DepartamentoMunicipalSimpleSerializer(read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Categoria
        fields = [
            "id",
            "departamento",
            "nombre",
            "descripcion",
            "estado",
            "estado_display",
            "fecha_creacion",
        ]


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
        ]


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
