from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Permiso para administradores municipales"""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return request.user.is_authenticated and (
            request.user.es_administrador
            or request.user.tipo_usuario == "administrador"
        )


class IsAuthenticatedOrAdmin(BasePermission):
    """Permiso para usuarios autenticados o administradores"""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return request.user.is_authenticated and (
            request.user.es_administrador
            or request.user.tipo_usuario
            in ["administrador", "personal", "jefe_departamento", "vecino"]
        )


class IsMunicipalStaff(BasePermission):
    """Permiso para personal municipal (excluye vecinos)"""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return request.user.is_authenticated and request.user.es_municipal


class IsDepartmentHead(BasePermission):
    """Permiso para jefes de departamento"""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        return request.user.is_authenticated and request.user.es_jefe_departamento
