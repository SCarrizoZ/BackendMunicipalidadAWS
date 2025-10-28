from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.v1 import (
    PublicacionViewSet,
    UsuariosViewSet,
    CustomTokenObtainPairView,
    RegistroUsuarioView,
    CategoriasViewSet,
    DepartamentosMunicipalesViewSet,
    EvidenciasViewSet,
    JuntasVecinalesViewSet,
    RespuestasMunicipalesViewSet,
    SituacionesPublicacionesViewSet,
    AnunciosMunicipalesViewSet,
    ImagenesAnunciosViewSet,
    PublicacionesPorMesyCategoria,
    PublicacionesPorCategoria,
    ResumenEstadisticas,
    ResueltosPorMes,
    TasaResolucionDepartamento,
    PublicacionesPorJuntaVecinalAPIView,
    export_to_excel,
    generate_pdf_report,
    # Nuevas vistas
    UsuarioDepartamentoViewSet,
    EvidenciaRespuestaViewSet,
    HistorialModificacionesViewSet,
    AuditoriaViewSet,
    TableroViewSet,
    ColumnaViewSet,
    TareaViewSet,
    ComentarioViewSet,
    estadisticas_departamentos,
    estadisticas_kanban,
    estadisticas_respuestas,
    estadisticas_gestion_datos,
    # Nuevos endpoints de verificación
    verificar_usuario_existente,
    logout_view,
    junta_mas_critica,
    publicaciones_resueltas_por_junta_vecinal,
    junta_mas_eficiente,
    estadisticas_historial_modificaciones,
)

from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"publicaciones", PublicacionViewSet, basename="publicaciones")
router.register(r"usuarios", UsuariosViewSet, basename="usuarios")
router.register(r"categorias", CategoriasViewSet, basename="categorias")
router.register(
    r"departamentos-municipales",
    DepartamentosMunicipalesViewSet,
    basename="departamentos-municipales",
)
router.register(r"evidencias", EvidenciasViewSet, basename="evidencias")
router.register(
    r"juntas-vecinales", JuntasVecinalesViewSet, basename="juntas-vecinales"
)
router.register(
    r"respuestas-municipales",
    RespuestasMunicipalesViewSet,
    basename="respuestas-municipales",
)
router.register(
    r"situaciones-publicaciones",
    SituacionesPublicacionesViewSet,
    basename="situaciones-publicaciones",
)
router.register(
    r"anuncios-municipales", AnunciosMunicipalesViewSet, basename="anuncios"
)
router.register(
    r"imagenes-anuncios", ImagenesAnunciosViewSet, basename="imagenes-anuncios"
)

# Nuevas rutas
router.register(
    r"usuario-departamento",
    UsuarioDepartamentoViewSet,
    basename="usuario-departamento",
)
router.register(
    r"evidencia-respuesta",
    EvidenciaRespuestaViewSet,
    basename="evidencia-respuesta",
)
router.register(
    r"historial-modificaciones",
    HistorialModificacionesViewSet,
    basename="historial-modificaciones",
)
router.register(r"auditoria", AuditoriaViewSet, basename="auditoria")
router.register(r"tableros", TableroViewSet, basename="tableros")
router.register(r"columnas", ColumnaViewSet, basename="columnas")
router.register(r"tareas", TareaViewSet, basename="tareas")
router.register(r"comentarios", ComentarioViewSet, basename="comentarios")

urlpatterns = [
    path("v1/", include(router.urls)),
    path("v1/token/", CustomTokenObtainPairView.as_view(), name="token_refresh"),
    path("v1/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("v1/registro/", RegistroUsuarioView.as_view(), name="registro"),
    # Nuevos endpoints de verificación de usuarios
    path(
        "v1/verificar-usuario/", verificar_usuario_existente, name="verificar_usuario"
    ),
    path("v1/logout/", logout_view, name="logout"),
    path(
        "v1/publicaciones-por-mes-y-categoria/", PublicacionesPorMesyCategoria.as_view()
    ),
    path("v1/publicaciones-por-categoria/", PublicacionesPorCategoria.as_view()),
    path("v1/resumen-estadisticas/", ResumenEstadisticas.as_view()),
    path("v1/resueltos-por-mes/", ResueltosPorMes.as_view()),
    path("v1/tasa-resolucion-departamento/", TasaResolucionDepartamento.as_view()),
    path(
        "v1/publicaciones-por-junta-vecinal/",
        PublicacionesPorJuntaVecinalAPIView.as_view(),
    ),
    path("v1/export-to-excel/", export_to_excel),
    path("v1/generate-pdf-report/", generate_pdf_report),
    # Nuevas rutas de estadísticas
    path("v1/estadisticas-departamentos/", estadisticas_departamentos),
    path("v1/estadisticas-kanban/", estadisticas_kanban),
    path("v1/estadisticas-respuestas/", estadisticas_respuestas),
    path("v1/estadisticas-gestion-datos/", estadisticas_gestion_datos),
    path("v1/junta-mas-critica/", junta_mas_critica, name="junta_mas_critica"),
    path(
        "v1/publicaciones-resueltas-por-junta-vecinal/",
        publicaciones_resueltas_por_junta_vecinal,
        name="publicaciones_resueltas_por_junta_vecinal",
    ),
    path("v1/junta-mas-eficiente/", junta_mas_eficiente, name="junta_mas_eficiente"),
    path(
        "v1/estadisticas-historial-modificaciones/",
        estadisticas_historial_modificaciones,
        name="estadisticas_historial_modificaciones",
    ),
]
