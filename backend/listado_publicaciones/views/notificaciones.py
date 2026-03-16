from rest_framework.decorators import api_view, permission_classes
from listado_publicaciones.permissions import IsAdmin, IsAuthenticatedOrAdmin
from rest_framework.response import Response
from rest_framework import status
from ..models import DispositivoNotificacion
from ..serializers.v1 import DispositivoNotificacionSerializer
import logging

logger = logging.getLogger(__name__)

@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def registrar_dispositivo(request):
    """
    Registrar token de dispositivo para notificaciones

    POST /api/v1/notificaciones/registrar/

    Body:
    {
        "token": "ExponentPushToken[xxxxxx]",
        "plataforma": "android",
    }
    """
    token = request.data.get("token")
    plataforma = request.data.get("plataforma", "android")

    if not token:
        return Response(
            {"error": "Token requerido"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        dispositivo, created = DispositivoNotificacion.objects.update_or_create(
            usuario=request.user,
            token_expo=token,
            defaults={
                "plataforma": plataforma,
                "activo": True,
            },
        )

        logger.info(
            f"{'✅ Nuevo' if created else '🔄 Actualizado'} dispositivo: "
            f"{request.user.rut} - {plataforma}"
        )

        serializer = DispositivoNotificacionSerializer(dispositivo)

        return Response(
            {
                "message": "Dispositivo registrado exitosamente",
                "dispositivo": serializer.data,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"❌ Error registrando dispositivo: {str(e)}")
        return Response(
            {"error": "Error interno del servidor"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrAdmin])
def desactivar_dispositivo(request):
    """
    Desactivar notificaciones (al cerrar sesión)

    POST /api/v1/notificaciones/desactivar/

    Body:
    {
        "token": "ExponentPushToken[xxxxxx]"
    }
    """
    token = request.data.get("token")

    if not token:
        return Response(
            {"error": "Token requerido"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        count = DispositivoNotificacion.objects.filter(
            usuario=request.user, token_expo=token
        ).update(activo=False)

        if count > 0:
            logger.info(f"🔴 Dispositivo desactivado: {request.user.rut}")
            return Response({"message": "Dispositivo desactivado"})
        else:
            return Response(
                {"message": "Dispositivo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except Exception as e:
        logger.error(f"❌ Error desactivando: {str(e)}")
        return Response(
            {"error": "Error interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrAdmin])
def mis_dispositivos(request):
    """
    Listar dispositivos del usuario

    GET /api/v1/notificaciones/mis-dispositivos/
    """
    dispositivos = DispositivoNotificacion.objects.filter(
        usuario=request.user
    ).order_by("-ultima_actualizacion")

    serializer = DispositivoNotificacionSerializer(dispositivos, many=True)

    return Response(
        {
            "total": dispositivos.count(),
            "activos": dispositivos.filter(activo=True).count(),
            "dispositivos": serializer.data,
        }
    )
