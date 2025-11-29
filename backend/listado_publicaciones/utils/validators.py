from rest_framework import serializers
from ..models.usuarios import Usuario
from django.db.models import Q

def validar_rut(value, check_exists=False):
    """
    Valida formato y opcionalmente existencia de RUT.
    Retorna el RUT formateado.
    """
    if not value:
        raise serializers.ValidationError("El RUT es obligatorio")

    # 1. Normalizar
    rut_normalizado = value.replace(".", "").replace("-", "")

    # 2. Validar largo
    if len(rut_normalizado) < 8 or len(rut_normalizado) > 9:
        raise serializers.ValidationError("El RUT debe tener entre 8 y 9 caracteres")

    # 3. Verificar existencia (solo si se pide)
    if check_exists:
        # Buscar en múltiples formatos
        exists = Usuario.objects.filter(
            Q(rut=rut_normalizado) | 
            Q(rut=value) | 
            Q(rut__in=[value, rut_normalizado, f"{rut_normalizado[:-1]}-{rut_normalizado[-1]}"])
        ).exists()
        
        if exists:
            raise serializers.ValidationError("Ya existe un usuario con este RUT")

    # 4. Formatear para guardar
    cuerpo = rut_normalizado[:-1]
    dv = rut_normalizado[-1]
    return f"{cuerpo}-{dv}"

def validar_email_unico(value):
    """Verifica que el email no esté registrado."""
    if not value:
        raise serializers.ValidationError("El email es obligatorio")
        
    if Usuario.objects.filter(email__iexact=value).exists():
        raise serializers.ValidationError("Ya existe un usuario con este email")
        
    return value.lower()
