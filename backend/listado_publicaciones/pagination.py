from rest_framework.pagination import PageNumberPagination


# Paginación de las publicaciones
class DynamicPageNumberPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "pagesize"
    max_page_size = 100
