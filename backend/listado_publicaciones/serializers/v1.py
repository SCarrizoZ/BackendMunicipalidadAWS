from rest_framework import serializers
from ..models import (
    Usuario,
    Categoria,
    DepartamentoMunicipal,
    Evidencia,
    JuntaVecinal,
    Publicacion,
    RespuestaMunicipal,
    SituacionPublicacion,
    AnuncioMunicipal,
    ImagenAnuncio,
)
import cloudinary
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# Serializer para Usuario
class UsuarioListSerializer(serializers.ModelSerializer):
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
        ]


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Solo para escritura

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

        return data


# Serializer para Departamento Municipal
class DepartamentoMunicipalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartamentoMunicipal
        fields = ["id", "nombre", "descripcion"]


# Serializer para Categoria
class CategoriaSerializer(serializers.ModelSerializer):
    departamento = DepartamentoMunicipalSerializer()

    class Meta:
        model = Categoria
        fields = ["id", "departamento", "nombre", "descripcion"]


# Serializer para Junta Vecinal
class JuntaVecinalSerializer(serializers.ModelSerializer):
    class Meta:
        model = JuntaVecinal
        fields = [
            "id",
            "nombre_calle",
            "numero_calle",
            "departamento",
            "villa",
            "comuna",
            "latitud",
            "longitud",
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
            "publicacion",
            "archivo",
            "fecha",
            "extension",
            "publicacion_id",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("archivo")
        upload_data = cloudinary.uploader.upload(archivo)
        validated_data["archivo"] = upload_data["url"]
        return Evidencia.objects.create(**validated_data)


# Serializer para Publicacion
class PublicacionListSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer(read_only=True)
    junta_vecinal = JuntaVecinalSerializer(read_only=True)
    categoria = CategoriaSerializer(read_only=True)
    departamento = DepartamentoMunicipalSerializer(read_only=True)
    situacion = SituacionPublicacionSerializer(read_only=True)
    evidencias = EvidenciaSerializer(many=True, read_only=True, source="evidencia_set")

    class Meta:
        model = Publicacion
        fields = [
            "id",
            "usuario",
            "junta_vecinal",
            "categoria",
            "departamento",
            "descripcion",
            "situacion",
            "fecha_publicacion",
            "titulo",
            "latitud",
            "longitud",
            "evidencias",
        ]


class PublicacionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicacion
        fields = [
            "id",
            "usuario",
            "junta_vecinal",
            "categoria",
            "departamento",
            "descripcion",
            "situacion",
            "fecha_publicacion",
            "titulo",
            "latitud",
            "longitud",
        ]


# Serializer para Imagen Anuncio
class ImagenAnuncioSerializer(serializers.ModelSerializer):
    anuncio_id = serializers.PrimaryKeyRelatedField(
        queryset=AnuncioMunicipal.objects.all()
    )

    class Meta:
        model = ImagenAnuncio
        fields = [
            "id",
            "anuncio",
            "imagen",
            "fecha",
            "extension",
            "anuncio_id",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("imagen")
        upload_data = cloudinary.uploader.upload(archivo)
        validated_data["imagen"] = upload_data["url"]
        return ImagenAnuncio.objects.create(**validated_data)


# Serializer para Anuncio Municipal
class AnuncioMunicipalSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer()
    categoria = CategoriaSerializer()
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


# Serializer para Respuesta Municipal
class RespuestaMunicipalSerializer(serializers.ModelSerializer):
    usuario = UsuarioListSerializer()
    publicacion = PublicacionListSerializer()

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
        ]
