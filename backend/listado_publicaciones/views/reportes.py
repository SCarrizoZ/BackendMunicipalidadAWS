from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from listado_publicaciones.permissions import IsAdmin
from ..models import Publicacion
from ..filters import PublicacionFilter
from .auditoria import crear_auditoria
from ..services.report_service import ReportService

@api_view(["GET"])
@permission_classes([IsAdmin])
def export_to_excel(request):
    try:
        # Aplicar filtros usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return HttpResponse("Errores en los filtros", status=400)

        publicaciones = filterset.qs

        # Generar reporte usando el servicio
        wb = ReportService.generate_excel_report(publicaciones)

        # Preparar respuesta HTTP
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="publicaciones.xlsx"'
        wb.save(response)

        # Crear descripción detallada de los filtros aplicados
        filtros_aplicados = []
        for key, value in request.GET.items():
            if value:
                filtros_aplicados.append(f"{key}: {value}")

        descripcion_detallada = f"Exportación de {publicaciones.count()} registros a Excel"
        if filtros_aplicados:
            descripcion_detallada += f" - Filtros: {', '.join(filtros_aplicados)}"

        # Registrar auditoría
        crear_auditoria(
            usuario=request.user,
            accion="READ",
            modulo="Reportes",
            descripcion=descripcion_detallada,
            es_exitoso=True,
        )

        return response

    except Exception as e:
        # Registrar error en auditoría
        crear_auditoria(
            usuario=request.user,
            accion="READ",
            modulo="Reportes",
            descripcion=f"Error al exportar a Excel: {str(e)}",
            es_exitoso=False,
        )
        return HttpResponse("Error al generar el archivo Excel", status=500)


@api_view(["GET"])
@permission_classes([IsAdmin])
def generate_pdf_report(request):
    try:
        comentarios = request.GET.get(
            "comentarios", "No se proporcionaron comentarios."
        )
        departamento = request.GET.get("departamento_reporte", "")
        # Aplicar filtros usando PublicacionFilter
        filterset = PublicacionFilter(request.GET, queryset=Publicacion.objects.all())
        if not filterset.is_valid():
            return HttpResponse("Errores en los filtros", status=400)

        publicaciones_filtradas = filterset.qs

        if publicaciones_filtradas.count() == 0:
            return HttpResponse("No hay datos para generar el reporte", status=404)

        # Generar PDF usando el servicio
        buffer = ReportService.generate_pdf_report(
            publicaciones_filtradas, comentarios, departamento
        )

        # Crear respuesta HTTP
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="reporte.pdf"'

        # Crear descripción detallada de los filtros aplicados
        filtros_aplicados = []
        if departamento:
            filtros_aplicados.append(f"Departamento: {departamento}")

        # Obtener otros filtros de la query string
        filtros_query = []
        for key, value in request.GET.items():
            if key not in ["comentarios", "departamento_reporte"] and value:
                filtros_query.append(f"{key}: {value}")

        if filtros_query:
            filtros_aplicados.extend(filtros_query)

        descripcion_detallada = f"Generación de reporte PDF de publicaciones ({publicaciones_filtradas.count()} registros)"
        if filtros_aplicados:
            descripcion_detallada += f" - Filtros: {', '.join(filtros_aplicados)}"

        crear_auditoria(
            usuario=request.user,
            accion="GENERAR_REPORTE_PDF",
            modulo="Reportes",
            descripcion=descripcion_detallada,
            es_exitoso=True,
        )

        return response
    except Exception as e:
        # Registrar error en auditoría
        crear_auditoria(
            usuario=request.user,
            accion="GENERAR_REPORTE_PDF",
            modulo="Reportes",
            descripcion=f"Error al generar reporte PDF: {str(e)}",
            es_exitoso=False,
        )
        print(e)
        return HttpResponse("Error al generar el PDF", status=500)
