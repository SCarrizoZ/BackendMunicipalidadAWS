from django.db.models.signals import post_delete
from django.dispatch import receiver
from cloudinary.uploader import destroy
from .models import ImagenAnuncio


@receiver(post_delete, sender=ImagenAnuncio)
def eliminar_imagen_cloudinary(sender, instance, **kwargs):
    """
    Señal que elimina las imágenes de Cloudinary cuando se elimina una instancia de ImagenAnuncio.
    """
    if instance.imagen:
        try:
            # Obtener el public_id directamente desde el objeto CloudinaryResource
            public_id = instance.imagen.public_id
            destroy(public_id)  # Elimina la imagen de Cloudinary
        except Exception as e:
            print(f"Error al eliminar la imagen en Cloudinary: {e}")