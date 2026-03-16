from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt
from io import BytesIO
from django.db.models import Count, Q, F
from django.db.models.functions import TruncMonth
from datetime import datetime
import os
from django.conf import settings
import textwrap
import matplotlib
from ..utils.constants import PALETA_COLORES, MESES_ESPANOL
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
import base64

# Configuración de Matplotlib para evitar problemas de threading
matplotlib.use("Agg")

class ReportService:
    # Colores para gráficos
    MESES_ESPANOL = MESES_ESPANOL

    @staticmethod
    def _get_image_base64(buffer):
        """Convierte el buffer de matplotlib a string base64 para HTML"""
        if not buffer: 
            return None
        image_png = buffer.getvalue()
        buffer.close()
        graphic = base64.b64encode(image_png)
        return graphic.decode('utf-8')

    @staticmethod
    def _get_local_image_base64(path):
        """Lee una imagen local y la convierte a base64"""
        if os.path.exists(path):
            with open(path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        return None
    
    @staticmethod
    def _get_color_determinista(categoria_nombre):
        """
        Asigna un color consistente a una categoría basado en su nombre.
        Si la categoría siempre se llama igual, el color siempre será el mismo.
        """
        if not categoria_nombre:
            return "#D3D3D3" # Gris por defecto para nulos
            
        # 1. Calcular un número único basado en las letras del nombre
        # Usamos sum(ord(c)) para obtener un número estable (hash() de python varía entre reinicios)
        hash_val = sum(ord(c) for c in categoria_nombre)
        
        # 2. Usar el operador módulo (%) para obtener un índice válido dentro de la paleta
        indice = hash_val % len(PALETA_COLORES)
        
        return PALETA_COLORES[indice]

    @staticmethod
    def generate_excel_report(publicaciones):
        """Genera un archivo Excel con las publicaciones dadas."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Publicaciones"

        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="4F81BD", end_color="4F81BD", fill_type="solid"
        )
        alignment = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        
        # TODO: Analizar que datos se agregan en el excel. Además se podría colorear la celda de la situacion

        # Encabezados
        headers = [
            "ID", "Codigo", "Título", "Categoría", "Junta Vecinal", "Fecha",
            "Situación", "Prioridad", "Descripción",
        ]
        ws.append(headers)

        # Aplicar estilos a los encabezados
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment
            cell.border = border

        # Agregar datos
        for pub in publicaciones:
            row = [
                pub.id,
                pub.codigo,
                pub.titulo,
                pub.categoria.nombre,
                pub.junta_vecinal.nombre_junta,
                pub.fecha_publicacion.strftime("%Y-%m-%d"),
                pub.situacion.nombre if pub.situacion else "N/A",
                pub.prioridad,
                pub.descripcion,
            ]
            ws.append(row)

            # Aplicar bordes a las celdas de datos
            for cell in ws[ws.max_row]:
                cell.border = border

        # Ajustar ancho de columnas
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception as e:
                    print(e)
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[column].width = adjusted_width

        return wb

    @staticmethod
    def generate_pdf_report(publicaciones_filtradas, comentarios, departamento):
        # 1. Generar Gráficos (Buffers)
        bar_buffer = ReportService._generate_bar_chart(publicaciones_filtradas)
        pie_buffer = ReportService._generate_pie_chart(publicaciones_filtradas)
        line_buffer = ReportService._generate_line_chart(publicaciones_filtradas)
        
        # 2. Obtener Datos Tabulares (Ahora devuelve datos, no un dibujo)
        tasa_data = ReportService._get_tasa_resolucion_data(publicaciones_filtradas)

        # 3. Procesar Logo
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
        logo_b64 = ReportService._get_local_image_base64(logo_path)

        # 4. Preparar Contexto para el HTML
        context = {
            'publicaciones': publicaciones_filtradas, # Por si quieres listar todas
            'comentarios': comentarios,
            'departamento': departamento or "General",
            'fecha_reporte': datetime.now(),
            'logo': logo_b64,
            # Gráficos en Base64
            'bar_chart': ReportService._get_image_base64(bar_buffer),
            'pie_chart': ReportService._get_image_base64(pie_buffer),
            'line_chart': ReportService._get_image_base64(line_buffer),
            # Datos para tablas
            'tasa_data': tasa_data,
        }

        # 5. Renderizar y Generar PDF
        html_string = render_to_string('reportes/reporte_publicaciones.html', context)
        
        pdf_file = BytesIO()
        HTML(string=html_string, base_url=request.build_absolute_uri() if 'request' in locals() else '/').write_pdf(target=pdf_file)
        
        pdf_file.seek(0)
        return pdf_file

    # TODO: Gráfico de lineas posee errores (Se muestran 4 líneas siendo que son 3 estados)

    @staticmethod
    def _generate_bar_chart(publicaciones_filtradas):
        try:
            datos = (
                publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
                .values("mes", "categoria__nombre")
                .annotate(total=Count("id"))
                .order_by("mes")
            )

            meses_dict = {}
            for dato in datos:
                mes_nombre = ReportService.MESES_ESPANOL[dato["mes"].month]
                if mes_nombre not in meses_dict:
                    meses_dict[mes_nombre] = {"name": mes_nombre}
                meses_dict[mes_nombre][dato["categoria__nombre"]] = dato["total"]

            data = list(meses_dict.values())
            if not data:
                return None

            meses = [item["name"] for item in data]
            categorias = list(set(key for item in data for key in item.keys() if key != "name"))
            valores_por_categoria = {categoria: [] for categoria in categorias}

            for item in data:
                for categoria in categorias:
                    valores_por_categoria[categoria].append(item.get(categoria, 0))

            plt.figure(figsize=(10, 6))
            bottom_stack = [0] * len(meses)

            for categoria, valores in valores_por_categoria.items():
                color = ReportService._get_color_determinista(categoria)
                plt.bar(
                    meses, valores, label=categoria, bottom=bottom_stack,
                    color=color,
                )
                bottom_stack = [i + j for i, j in zip(bottom_stack, valores)]

            plt.xlabel("Meses")
            plt.ylabel("Cantidad")
            plt.title("Publicaciones por Mes y Categoría")
            plt.legend(loc="upper left")
            plt.tight_layout()

            buffer = BytesIO()
            plt.savefig(buffer, format="png")
            buffer.seek(0)
            plt.close()
            return buffer
        except Exception as e:
            print(e)
            return None

    @staticmethod
    def _generate_pie_chart(publicaciones_filtradas):
        try:
            datos = (
                publicaciones_filtradas.values("categoria__nombre")
                .annotate(total=Count("id"))
                .order_by("-total")
            )

            if not datos:
                return None

            respuesta = [{"name": dato["categoria__nombre"], "value": dato["total"]} for dato in datos]
            categorias = [item["name"] for item in respuesta]
            valores = [item["value"] for item in respuesta]
            colores = [ReportService._get_color_determinista(categoria) for categoria in categorias]

            fig, ax = plt.subplots(figsize=(10, 10))
            wedges, texts, autotexts = ax.pie(
                valores, labels=None, colors=colores, autopct="%1.1f%%", startangle=140,
                textprops={"color": "white", "fontsize": 14, "weight": "bold"},
            )
            ax.set_title("Distribución de Publicaciones por Categoría", fontsize=16)
            ax.legend(
                loc="center left", bbox_to_anchor=(1, 0.5),
                labels=[f"{c} ({v})" for c, v in zip(categorias, valores)], fontsize=10,
            )

            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format="png", bbox_inches="tight")
            buffer.seek(0)
            plt.close()
            return buffer
        except Exception as e:
            print(e)
            return None

    @staticmethod
    def _generate_line_chart(publicaciones_filtradas):
        """Genera el gráfico de líneas de resoluciones por mes"""
        try:
            publicaciones_por_mes = (
                publicaciones_filtradas.annotate(mes=TruncMonth("fecha_publicacion"))
                .values("mes")
                .annotate(
                    recibidos=Count("id", filter=Q(situacion__nombre="Recibido")),
                    resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
                    en_curso=Count("id", filter=Q(situacion__nombre="En curso")),
                )
                .order_by("mes")
            )

            if not publicaciones_por_mes: 
                return None

            meses = []
            recibidos = []
            resueltos = []
            en_curso = []

            for dato in publicaciones_por_mes:
                mes_nombre = ReportService.MESES_ESPANOL[dato["mes"].month]
                meses.append(mes_nombre)
                recibidos.append(dato["recibidos"])
                resueltos.append(dato["resueltos"])
                en_curso.append(dato["en_curso"])

            plt.figure(figsize=(10, 6))
            plt.plot(meses, recibidos, label="Recibidos", marker="o", color="#82ca9d", linewidth=3)
            plt.plot(meses, resueltos, label="Resueltos", marker="o", color="#8884d8", linewidth=3)
            plt.plot(meses, en_curso, label="En curso", marker="o", color="#ff8042", linewidth=3)

            plt.xlabel("Meses")
            plt.ylabel("Cantidad")
            plt.title("Resoluciones por Mes")
            plt.legend(loc="upper left")
            plt.grid(True, linestyle='--', alpha=0.7) # Agregué grid para mejor lectura
            plt.tight_layout()

            buffer = BytesIO()
            plt.savefig(buffer, format="png")
            buffer.seek(0)
            plt.close()
            return buffer
        except Exception as e:
            print(f"Error generando line chart: {e}")
            return None

    @staticmethod
    def _get_tasa_resolucion_data(publicaciones_filtradas):
        """
        Calcula los datos para la tabla de tasas.
        Retorna una LISTA de diccionarios, no un objeto visual.
        """
        try:
            datos = (
                publicaciones_filtradas.annotate(
                    mes=TruncMonth("fecha_publicacion"),
                    departamento_nombre=F("departamento__nombre"),
                )
                .values("mes", "departamento_nombre")
                .annotate(
                    total=Count("id"),
                    resueltos=Count("id", filter=Q(situacion__nombre="Resuelto")),
                )
                .order_by("mes", "departamento_nombre")
            )

            data_list = []
            for dato in datos:
                mes_nombre = ReportService.MESES_ESPANOL[dato["mes"].month]
                total = dato["total"]
                resueltos = dato["resueltos"]
                tasa = (resueltos / total * 100) if total > 0 else 0
                
                data_list.append({
                    "departamento": dato["departamento_nombre"],
                    "mes": mes_nombre,
                    "total": total,
                    "resueltos": resueltos,
                    "tasa": f"{tasa:.1f}%" # Formateado como string
                })
            
            return data_list
        except Exception as e:
            print(f"Error calculando tabla tasas: {e}")
            return []