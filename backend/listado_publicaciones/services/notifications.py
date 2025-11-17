import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class ExpoNotificationService:
    """
    Servicio para enviar notificaciones push usando Expo
    """

    @staticmethod
    def enviar_notificacion(
        tokens: List[str],
        titulo: str,
        mensaje: str,
        datos: Optional[Dict[str, Any]] = None,
        prioridad: str = "high",
        sonido: str = "default",
        badge: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Enviar notificación push a tokens de Expo

        Args:
            tokens: Lista de tokens de Expo
            titulo: Título de la notificación
            mensaje: Cuerpo del mensaje
            datos: Datos adicionales (JSON)
            prioridad: 'default', 'normal', 'high'
            sonido: 'default' o nombre del archivo
            badge: Número para badge (iOS)

        Returns:
            Diccionario con resultado
        """

        if not tokens:
            logger.warning("No hay tokens para enviar notificación")
            return {"success": False, "error": "No hay tokens"}

        # Construir mensajes
        messages = []
        for token in tokens:
            message = {
                "to": token,
                "sound": sonido,
                "title": titulo,
                "body": mensaje,
                "priority": prioridad,
                "channelId": "default",
            }

            if datos:
                message["data"] = datos

            if badge is not None:
                message["badge"] = badge

            messages.append(message)

        try:
            logger.info(f"📤 Enviando {len(messages)} notificaciones...")

            response = requests.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            response.raise_for_status()
            result = response.json()

            # Verificar errores en respuesta
            if "data" in result:
                for idx, item in enumerate(result["data"]):
                    status = item.get("status")

                    if status == "error":
                        error_msg = item.get("message", "Unknown error")
                        logger.error(f"❌ Error en notificación {idx}: {error_msg}")

                        # Desactivar tokens inválidos
                        if (
                            "DeviceNotRegistered" in error_msg
                            or "InvalidCredentials" in error_msg
                        ):
                            token = tokens[idx]
                            ExpoNotificationService._desactivar_token(token)

                    elif status == "ok":
                        logger.info(f"✅ Notificación {idx} enviada")

            return {"success": True, "data": result}

        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout enviando notificaciones")
            return {"success": False, "error": "Timeout"}

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de red: {str(e)}")
            return {"success": False, "error": str(e)}

        except Exception as e:
            logger.error(f"❌ Error inesperado: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _desactivar_token(token: str):
        """Desactivar token inválido"""
        from ..models import DispositivoNotificacion

        try:
            DispositivoNotificacion.objects.filter(token_expo=token).update(
                activo=False
            )

            logger.info(f"🔴 Token desactivado: {token[:30]}...")
        except Exception as e:
            logger.error(f"Error desactivando token: {str(e)}")

    @staticmethod
    def notificar_nueva_respuesta(publicacion_id: int):
        """
        Notificar al usuario cuando hay nueva respuesta

        Args:
            publicacion_id: ID de la publicación
        """
        from ..models import Publicacion, DispositivoNotificacion

        try:
            publicacion = Publicacion.objects.select_related("usuario").get(
                id=publicacion_id
            )
            usuario = publicacion.usuario

            logger.info(f"📬 Notificando nueva respuesta a: {usuario.nombre}")

            # Obtener tokens activos
            dispositivos = DispositivoNotificacion.objects.filter(
                usuario=usuario, activo=True
            )

            if not dispositivos.exists():
                logger.warning(f"⚠️ Usuario {usuario.rut} sin dispositivos")
                return

            tokens = list(dispositivos.values_list("token_expo", flat=True))
            logger.info(f"📱 Enviando a {len(tokens)} dispositivos")

            # Enviar notificación
            ExpoNotificationService.enviar_notificacion(
                tokens=tokens,
                titulo=f"Nueva respuesta - {publicacion.codigo}",
                mensaje="La municipalidad ha respondido a tu denuncia",
                datos={
                    "tipo": "nueva_respuesta",
                    "publicacion_id": publicacion_id,
                    "codigo": publicacion.codigo,
                    "screen": "historial",
                },
                prioridad="high",
                badge=1,
            )

        except Publicacion.DoesNotExist:
            logger.error(f"❌ Publicación {publicacion_id} no existe")
        except Exception as e:
            logger.error(f"❌ Error notificando: {str(e)}")

    @staticmethod
    def notificar_cambio_estado(publicacion_id: int, nuevo_estado: str):
        """
        Notificar cambio de estado

        Args:
            publicacion_id: ID de la publicación
            nuevo_estado: Nuevo estado/situación
        """
        from ..models import Publicacion, DispositivoNotificacion

        try:
            publicacion = Publicacion.objects.select_related("usuario").get(
                id=publicacion_id
            )
            usuario = publicacion.usuario

            dispositivos = DispositivoNotificacion.objects.filter(
                usuario=usuario, activo=True
            )

            if not dispositivos.exists():
                return

            tokens = list(dispositivos.values_list("token_expo", flat=True))

            # Mensajes según estado
            mensajes = {
                "en_proceso": "Tu denuncia está siendo revisada",
                "resuelto": "¡Tu denuncia ha sido resuelta!",
                "rechazado": "Tu denuncia ha sido rechazada",
                "cerrado": "Tu denuncia ha sido cerrada",
            }

            mensaje = mensajes.get(
                nuevo_estado.lower(), f"Estado actualizado a: {nuevo_estado}"
            )

            ExpoNotificationService.enviar_notificacion(
                tokens=tokens,
                titulo=f"Actualización - {publicacion.codigo}",
                mensaje=mensaje,
                datos={
                    "tipo": "cambio_estado",
                    "publicacion_id": publicacion_id,
                    "codigo": publicacion.codigo,
                    "nuevo_estado": nuevo_estado,
                    "screen": "historial",
                },
                prioridad="high",
            )

        except Exception as e:
            logger.error(f"❌ Error notificando cambio estado: {str(e)}")
