from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from ..models import *
from ..services.geo_service import GeoService
from ..services.media_service import MediaService
from ..utils.validators import validar_rut, validar_email_unico


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
        return validar_rut(value, check_exists=not self.instance)

    def validate_email(self, value):
        if not self.instance:  # Solo al crear
            return validar_email_unico(value)
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


class DispositivoNotificacionSerializer(serializers.ModelSerializer):
    """Serializer para Dispositivo de Notificación"""

    class Meta:
        model = DispositivoNotificacion
        fields = [
            "id",
            "token_expo",
            "plataforma",
            "activo",
            "fecha_registro",
            "ultima_actualizacion",
        ]

        read_only_fields = ["id", "fecha_registro", "ultima_actualizacion"]

    def validate_token_expo(self, value):
        """Validación personalizada para token_expo"""
        if not value.startswith("ExponentPushToken[") and not value.startswith(
            "ExpoPushToken["
        ):
            raise serializers.ValidationError(
                "El token_expo no tiene un formato válido. Debe comenzar con 'ExponentPushToken[' o 'ExpoPushToken['."
            )

        return value

    def create(self, validated_data):
        """Crear o actualizar un nuevo Dispositivo de Notificación"""
        token = validated_data.get("token_expo")
        usuario = validated_data.get("usuario")

        # Si ya existe, reactivarlo y actualizar
        dispositivo, creado = DispositivoNotificacion.objects.update_or_create(
            token_expo=token,
            usuario=usuario,
            defaults={
                "plataforma": validated_data.get("plataforma"),
                "activo": True,
            },
        )

        return dispositivo


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["id"] = self.user.id
        data["es_administrador"] = self.user.es_administrador
        data["tipo_usuario"] = self.user.tipo_usuario
        data["tipo_usuario_display"] = self.user.get_tipo_usuario_display()
        data["ultimo_acceso"] = self.user.ultimo_acceso
        data["departamento_asignado"] = self.user.get_departamento_asignado() or "No aplica"
        data["nombre"] = self.user.nombre
        data["rut"] = self.user.rut
        data["email"] = self.user.email or "No registrado"
        data["numero_telefonico_movil"] = self.user.numero_telefonico_movil or "No registrado"
        data["fecha_registro"] = self.user.fecha_registro
        data["esta_activo"] = self.user.esta_activo

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
            "nombre",
            "peso",
            "fecha",
            "extension",
            "publicacion_id",
        ]

    def create(self, validated_data):
        # 1. Extraer archivo
        archivo = validated_data.pop("archivo")
        
        # 2. USAR EL SERVICIO (Limpio y reutilizable)
        ruta_relativa = MediaService.upload_image(archivo, folder="evidencias_publicaciones")
        
        # 3. Asignar la ruta procesada
        validated_data["archivo"] = ruta_relativa
        
        # 4. Procesar ID de publicación (tu lógica original)
        publicacion = validated_data.get("publicacion_id")
        if isinstance(publicacion, Publicacion):
            validated_data["publicacion_id"] = publicacion.id
            
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
        read_only_fields = ["departamento", "fecha_publicacion", "codigo", "situacion"]

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
                junta_mas_cercana = GeoService.encontrar_junta_vecinal_mas_cercana(
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
            junta_mas_cercana = GeoService.encontrar_junta_vecinal_mas_cercana(latitud, longitud)
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
        # Asignar departamento basado en la categoría
        categoria = validated_data.get('categoria')
        if categoria:
            validated_data['departamento'] = categoria.departamento

        instance = super().create(validated_data)

        # Calcular y almacenar distancia para la respuesta
        if instance.junta_vecinal:
            try:
                distancia = GeoService.calcular_distancia_haversine(
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
                distancia = GeoService.calcular_distancia_haversine(
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
                distancia = GeoService.calcular_distancia_haversine(
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
            "nombre",
            "peso",
            "fecha",
            "extension",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("imagen")
        
        # Reutilizamos el mismo servicio para otra entidad
        ruta_relativa = MediaService.upload_image(archivo, folder="anuncios_municipales")
        
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
            "nombre",
            "peso",
            "archivo",
            "fecha",
            "extension",
            "descripcion",
        ]

    def create(self, validated_data):
        archivo = validated_data.pop("archivo")
        ruta_relativa = MediaService.upload_image(archivo, folder="evidencias_respuestas")
        validated_data["archivo"] = ruta_relativa
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


class PublicacionConHistorialSerializer(PublicacionListSerializer):
    """
    Serializer para Publicacion que incluye el historial de modificaciones anidado.
    """

    # Reutilización  del serializer de historial
    modificaciones = HistorialModificacionesSerializer(
        many=True,
        read_only=True,
        source="historialmodificaciones",  # Este es el 'related_name' en el modelo
    )

    total_modificaciones = serializers.SerializerMethodField()

    class Meta(PublicacionListSerializer.Meta):
        # Heredamos los campos del PublicacionListSerializer y añadimos los nuevos
        fields = list(PublicacionListSerializer.Meta.fields) + [
            "modificaciones",
            "total_modificaciones",
        ]

    def get_total_modificaciones(self, obj):
        # 'obj' es una instancia de Publicacion
        # Esto es más eficiente si se usa prefetch_related en la vista
        if hasattr(obj, "historialmodificaciones"):
            return obj.historialmodificaciones.count()
        # Fallback por si no se hizo prefetch (menos eficiente)
        return obj.historialmodificaciones.count()
