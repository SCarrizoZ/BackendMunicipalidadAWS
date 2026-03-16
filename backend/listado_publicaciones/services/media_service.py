import cloudinary.uploader

class MediaService:
    @staticmethod
    def upload_image(archivo, folder="evidencias"):
        """
        Sube una imagen a Cloudinary y retorna la ruta relativa.
        Maneja errores de conexión aquí si es necesario.
        """
        try:
            # Aquí centralizas la configuración de upload
            upload_data = cloudinary.uploader.upload(
                archivo,
                folder=folder,
                resource_type="auto"
            )
            
            # Obtienes la URL completa
            url_completa = upload_data.get("url")
            
            # Lógica de recorte de URL (si es necesaria para tu frontend)
            # Asegúrate que este string 'de06451wd/' sea una constante en settings
            # para no tenerlo hardcodeado.
            if "de06451wd/" in url_completa:
                return url_completa.split("de06451wd/")[1]
            
            return url_completa
            
        except Exception as e:
            # Aquí podrías loguear el error
            print(f"Error subiendo a Cloudinary: {e}")
            raise e
