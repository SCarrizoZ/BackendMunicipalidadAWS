from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.es_administrador


class IsAuthenticatedOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated or request.user.es_administrador
