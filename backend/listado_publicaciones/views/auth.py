from rest_framework_simplejwt.views import TokenObtainPairView
from ..serializers.v1 import (
    CustomTokenObtainPairSerializer,
    UsuarioSerializer,
)
from ..models import Usuario
from ..views.auditoria import crear_auditoria
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from listado_publicaciones.permissions import IsAdmin, IsMunicipalStaff, IsAuthenticatedOrAdmin
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from django.db.models import Q

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # Si el login fue exitoso, actualizar el último acceso
        if response.status_code == 200:
            try:
                # Obtener el usuario por RUT (USERNAME_FIELD)
                rut = request.data.get("rut")
                if rut:
                    usuario = Usuario.objects.get(rut=rut)
                    usuario.ultimo_acceso = timezone.now()
                    usuario.save(update_fields=["ultimo_acceso"])

                    # Auditoría de LOGIN exitoso
                    crear_auditoria(
                        usuario=usuario,
                        accion="LOGIN",
                        modulo="Autenticación",
                        descripcion=f"Inicio de sesión exitoso desde IP: {self.get_client_ip(request)}",
                        es_exitoso=True,
                    )
            except Usuario.DoesNotExist:
                pass  # No hacer nada si el usuario no existe
        else:
            # Auditoría de LOGIN fallido
            rut = request.data.get("rut", "Desconocido")
            try:
                usuario = Usuario.objects.get(rut=rut)
                crear_auditoria(
                    usuario=usuario,
                    accion="LOGIN",
                    modulo="Autenticación",
                    descripcion=f"Intento de inicio de sesión fallido desde IP: {self.get_client_ip(request)}",
                    es_exitoso=False,
                )
            except Usuario.DoesNotExist:
                # Para usuarios que no existen, no crear auditoría específica
                pass

        return response

    def get_client_ip(self, request):
        """Obtener IP del cliente"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class RegistroUsuarioView(APIView):
    permission_classes = [AllowAny]  # No requiere autenticación

    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def verificar_usuario_existente(request):
    """
    Endpoint optimizado para verificar si un usuario ya existe por RUT o email
    """
    try:
        rut = request.data.get("rut")
        email = request.data.get("email")

        if not rut and not email:
            return Response(
                {"error": "Se requiere RUT o email para la verificación"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {}

        if rut:
            # Normalizar RUT para búsqueda (remover puntos y guiones)
            rut_normalizado = rut.replace(".", "").replace("-", "")

            # Buscar tanto en formato normalizado como con guión
            usuario_rut = Usuario.objects.filter(
                Q(rut=rut_normalizado)
                | Q(rut=rut)
                | Q(
                    rut__in=[
                        rut,  # Formato original del frontend
                        rut_normalizado,  # Sin puntos ni guiones
                        f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}",  # Con guión al final
                    ]
                )
            ).first()
            response_data["rut_disponible"] = usuario_rut is None
            if usuario_rut:
                response_data["usuario_rut"] = {
                    "id": usuario_rut.id,
                    "nombre": usuario_rut.nombre,
                    "email": usuario_rut.email,
                    "tipo_usuario": usuario_rut.get_tipo_usuario_display(),
                    "esta_activo": usuario_rut.esta_activo,
                }

        if email:
            usuario_email = Usuario.objects.filter(email__iexact=email).first()
            response_data["email_disponible"] = usuario_email is None
            if usuario_email:
                response_data["usuario_email"] = {
                    "id": usuario_email.id,
                    "nombre": usuario_email.nombre,
                    "rut": usuario_email.rut,
                    "tipo_usuario": usuario_email.get_tipo_usuario_display(),
                    "esta_activo": usuario_email.esta_activo,
                }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error al verificar usuario: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def logout_view(request):
    """Endpoint para cerrar sesión con auditoría"""
    try:
        # Crear auditoría de LOGOUT
        crear_auditoria(
            usuario=request.user,
            accion="LOGOUT",
            modulo="Autenticación",
            descripcion=f"Cierre de sesión desde IP: {request.META.get('REMOTE_ADDR', 'Desconocida')}",
            es_exitoso=True,
        )

        # En JWT no hay logout real en el servidor, pero podemos registrar la acción
        return Response({"message": "Logout exitoso"}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Error en logout: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
