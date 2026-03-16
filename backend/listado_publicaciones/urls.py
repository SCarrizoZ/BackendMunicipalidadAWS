from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.auth import (
    CustomTokenObtainPairView,
    RegistroUsuarioView,
    verificar_usuario_existente,
    logout_view,
)
from .views.publicaciones import (
    PublicacionViewSet,
    EvidenciasViewSet,
    SituacionesPublicacionesViewSet,
    AnunciosMunicipalesViewSet,
    ImagenesAnunciosViewSet,
)
from .views.organizaciones import (
    CategoriasViewSet,
    DepartamentosMunicipalesViewSet,
    UsuarioDepartamentoViewSet,
    JuntasVecinalesViewSet,
    JuntaVecinalPaginatedViewSet,
    RespuestasMunicipalesViewSet,
    EvidenciaRespuestaViewSet,
    UsuariosViewSet,
)
from .views.estadisticas import (
    ResumenEstadisticas,
    PublicacionesPorMesyCategoria,
    PublicacionesPorCategoria,
    ResueltosPorMes,
    TasaResolucionDepartamento,
    PublicacionesPorJuntaVecinalAPIView,
    junta_mas_critica,
    publicaciones_resueltas_por_junta_vecinal,
    junta_mas_eficiente,
    estadisticas_departamentos,
    estadisticas_kanban,
    estadisticas_respuestas,
    estadisticas_gestion_datos,
    estadisticas_historial_modificaciones,
)
from .views.reportes import export_to_excel, generate_pdf_report
from .views.kanban import (
    TableroViewSet,
    ColumnaViewSet,
    TareaViewSet,
    ComentarioViewSet,
)
from .views.auditoria import HistorialModificacionesViewSet, AuditoriaViewSet
from .views.notificaciones import (
    registrar_dispositivo,
    desactivar_dispositivo,
    mis_dispositivos,
)
from rest_framework_simplejwt.views import TokenRefreshView

# Configuración del router
router = DefaultRouter()
router.register(r"publicaciones", PublicacionViewSet)
router.register(r"categorias", CategoriasViewSet)
router.register(r"departamentos", DepartamentosMunicipalesViewSet)
router.register(r"evidencias", EvidenciasViewSet)
router.register(r"juntas-vecinales", JuntasVecinalesViewSet, basename="juntas-vecinales")
router.register(r"juntas-vecinales-paginated", JuntaVecinalPaginatedViewSet, basename="juntas-vecinales-paginated")
router.register(r"respuestas", RespuestasMunicipalesViewSet)
router.register(r"situaciones", SituacionesPublicacionesViewSet)
router.register(r"anuncios", AnunciosMunicipalesViewSet)
router.register(r"imagenes-anuncios", ImagenesAnunciosViewSet)
router.register(r"usuarios-departamento", UsuarioDepartamentoViewSet)
router.register(r"evidencias-respuesta", EvidenciaRespuestaViewSet)
router.register(r"historial-modificaciones", HistorialModificacionesViewSet)
router.register(r"auditorias", AuditoriaViewSet)
router.register(r"usuarios", UsuariosViewSet)

# Rutas para Kanban
router.register(r"tableros", TableroViewSet)
router.register(r"columnas", ColumnaViewSet)
router.register(r"tareas", TareaViewSet)
router.register(r"comentarios", ComentarioViewSet)

urlpatterns = [
    # API Router
    path("v1/", include(router.urls)),
    # Autenticación
    path(
        "v1/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),  # Login
    path("v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("v1/registro/", RegistroUsuarioView.as_view(), name="registro_usuario"),
    path(
        "v1/verificar-usuario/",
        verificar_usuario_existente,
        name="verificar_usuario",
    ),
    path("v1/logout/", logout_view, name="logout"),
    # Estadísticas
    path(
        "v1/estadisticas/resumen/",
        ResumenEstadisticas,
        name="resumen_estadisticas",
    ),
    path(
        "v1/estadisticas/publicaciones-mes-categoria/",
        PublicacionesPorMesyCategoria,
        name="publicaciones_mes_categoria",
    ),
    path(
        "v1/estadisticas/publicaciones-categoria/",
        PublicacionesPorCategoria,
        name="publicaciones_categoria",
    ),
    path(
        "v1/estadisticas/resueltos-mes/",
        ResueltosPorMes,
        name="resueltos_mes",
    ),
    path(
        "v1/estadisticas/tasa-resolucion/",
        TasaResolucionDepartamento,
        name="tasa_resolucion",
    ),
    path(
        "v1/estadisticas/publicaciones-junta/",
        PublicacionesPorJuntaVecinalAPIView,
        name="publicaciones_junta",
    ),
    path(
        "v1/estadisticas/junta-critica/",
        junta_mas_critica,
        name="junta_critica",
    ),
    path(
        "v1/estadisticas/junta-eficiente/",
        junta_mas_eficiente,
        name="junta_eficiente",
    ),
    path(
        "v1/estadisticas/resueltas-junta/",
        publicaciones_resueltas_por_junta_vecinal,
        name="resueltas_junta",
    ),
    path(
        "v1/estadisticas/departamentos/",
        estadisticas_departamentos,
        name="estadisticas_departamentos",
    ),
    path(
        "v1/estadisticas/kanban/",
        estadisticas_kanban,
        name="estadisticas_kanban",
    ),
    path(
        "v1/estadisticas/respuestas/",
        estadisticas_respuestas,
        name="estadisticas_respuestas",
    ),
    path(
        "v1/estadisticas/gestion-datos/",
        estadisticas_gestion_datos,
        name="estadisticas_gestion_datos",
    ),
    path(
        "v1/estadisticas/historial-modificaciones/",
        estadisticas_historial_modificaciones,
        name="estadisticas_historial_modificaciones",
    ),
    # Reportes
    path("v1/reportes/excel/", export_to_excel, name="export_to_excel"),
    path("v1/reportes/pdf/", generate_pdf_report, name="generate_pdf_report"),
    # Notificaciones
    path(
        "v1/notificaciones/registrar/",
        registrar_dispositivo,
        name="registrar_dispositivo",
    ),
    path(
        "v1/notificaciones/desactivar/",
        desactivar_dispositivo,
        name="desactivar_dispositivo",
    ),
    path(
        "v1/notificaciones/mis-dispositivos/",
        mis_dispositivos,
        name="mis_dispositivos",
    ),
]
