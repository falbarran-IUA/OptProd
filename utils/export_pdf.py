#!/usr/bin/env python3
"""
Módulo de Exportación PDF para Órdenes de Trabajo
Optimizador de Producción v1.3.3
"""

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime, timedelta
import os
import tempfile
from typing import List, Dict, Optional

class ExportadorPDF:
    """Clase para generar PDFs de órdenes de trabajo"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._configurar_estilos()
    
    def _leer_instrucciones_ot(self) -> List[str]:
        """Leer instrucciones desde el archivo instrucciones_ot.txt"""
        try:
            if os.path.exists('instrucciones_ot.txt'):
                with open('instrucciones_ot.txt', 'r', encoding='utf-8') as f:
                    contenido = f.read()
                    # Extraer solo las líneas que contienen instrucciones numeradas
                    lineas = contenido.split('\n')
                    instrucciones = []
                    for linea in lineas:
                        linea = linea.strip()
                        if linea and (linea[0].isdigit() or linea.startswith('INSTRUCCIONES')):
                            if linea.startswith('INSTRUCCIONES'):
                                continue  # Saltar el título
                            instrucciones.append(linea)
                    return instrucciones
            else:
                # Instrucciones por defecto si no existe el archivo
                return [
                    "1. Verificar herramientas necesarias",
                    "2. Revisar niveles de lubricante y refrigerante",
                    "3. Ajustar parámetros básicos",
                    "4. Ejecutar tareas en orden programado",
                    "5. Control de calidad durante producción",
                    "6. Limpiar al finalizar",
                    "7. Reportar problemas importantes",
                    "8. Registrar tiempos reales"
                ]
        except Exception as e:
            print(f"Error leyendo instrucciones_ot.txt: {e}")
            # Instrucciones por defecto en caso de error
            return [
                "1. Verificar herramientas necesarias",
                "2. Revisar niveles de lubricante y refrigerante",
                "3. Ajustar parámetros básicos",
                "4. Ejecutar tareas en orden programado",
                "5. Control de calidad durante producción",
                "6. Limpiar al finalizar",
                "7. Reportar problemas importantes",
                "8. Registrar tiempos reales"
            ]
    
    def _configurar_estilos(self):
        """Configurar estilos personalizados para los PDFs"""
        # Estilo para título principal
        self.styles.add(ParagraphStyle(
            name='TituloPrincipal',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Estilo para subtítulos
        self.styles.add(ParagraphStyle(
            name='Subtitulo',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkgreen
        ))
        
        # Estilo para información de trabajo
        self.styles.add(ParagraphStyle(
            name='InfoTrabajo',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            leftIndent=20
        ))
        
        # Estilo para información de tarea
        self.styles.add(ParagraphStyle(
            name='InfoTarea',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            leftIndent=30
        ))
    
    def generar_orden_trabajo_individual(self, programacion: Dict, tarea: Dict, output_path: str) -> bool:
        """
        Generar PDF de orden de trabajo individual para una tarea específica
        
        Args:
            programacion: Datos de la programación
            tarea: Datos de la tarea específica
            output_path: Ruta donde guardar el PDF
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # Título principal
            story.append(Paragraph("ORDEN DE TRABAJO", self.styles['TituloPrincipal']))
            story.append(Spacer(1, 20))
            
            # Información de la programación
            info_programacion = [
                ["Semana de Producción:", f"Semana {programacion['semana_produccion']} - {programacion['anio']}"],
                ["Estado:", programacion['estado'].value if hasattr(programacion['estado'], 'value') else str(programacion['estado'])],
                ["Fecha de Creación:", programacion['fecha_creacion'].strftime("%d/%m/%Y %H:%M") if programacion['fecha_creacion'] else "N/A"],
                ["Objetivo:", programacion['objetivo_usado']],
                ["Makespan Planificado:", f"{programacion['makespan_planificado']:.1f} minutos" if programacion['makespan_planificado'] else "N/A"]
            ]
            
            if programacion.get('aprobada_por'):
                info_programacion.append(["Aprobada por:", programacion['aprobada_por']])
            if programacion.get('fecha_aprobacion'):
                info_programacion.append(["Fecha de Aprobación:", programacion['fecha_aprobacion'].strftime("%d/%m/%Y %H:%M")])
            
            tabla_programacion = Table(info_programacion, colWidths=[2*inch, 3*inch])
            tabla_programacion.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_programacion)
            story.append(Spacer(1, 20))
            
            # Información de la tarea
            story.append(Paragraph("DETALLES DE LA TAREA", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            info_tarea = [
                ["Trabajo:", tarea.get('trabajo_nombre', tarea.get('trabajo_id', 'N/A'))],
                ["Tarea:", tarea.get('nombre', 'N/A')],
                ["Máquina:", f"{tarea['maquina_id']}"],
                ["Operador:", f"{tarea.get('operador_id', 'Sin asignar')}"],
                ["Duración Planificada:", f"{tarea['duracion_planificada']} minutos"],
                ["Hora de Inicio:", self._formatear_hora(tarea['inicio_planificado'])],
                ["Hora de Fin:", self._formatear_hora(tarea['fin_planificado'])],
                ["Prioridad:", tarea.get('prioridad', 'Normal')]
            ]
            
            tabla_tarea = Table(info_tarea, colWidths=[2*inch, 3*inch])
            tabla_tarea.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_tarea)
            story.append(Spacer(1, 20))
            
            # Instrucciones de trabajo
            story.append(Paragraph("INSTRUCCIONES DE TRABAJO", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            instrucciones = [
                "1. Verificar que la máquina esté disponible y en condiciones óptimas",
                "2. Revisar las herramientas y materiales necesarios",
                "3. Confirmar la hora de inicio programada",
                "4. Registrar la hora de inicio real",
                "5. Ejecutar la tarea según las especificaciones",
                "6. Registrar la hora de fin real",
                "7. Reportar cualquier problema o desviación",
                "8. Confirmar la calidad del trabajo realizado"
            ]
            
            for instruccion in instrucciones:
                story.append(Paragraph(instruccion, self.styles['InfoTarea']))
            
            story.append(Spacer(1, 20))
            
            # Sección de registro
            story.append(Paragraph("REGISTRO DE EJECUCIÓN", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            registro_data = [
                ["Hora de Inicio Real:", "_________________"],
                ["Hora de Fin Real:", "_________________"],
                ["Problemas Encontrados:", "_________________"],
                ["Observaciones:", "_________________"],
                ["", ""],
                ["Firma del Operador:", "_________________"],
                ["Fecha:", "_________________"]
            ]
            
            tabla_registro = Table(registro_data, colWidths=[2*inch, 3*inch])
            tabla_registro.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_registro)
            
            # Pie de página
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                                 self.styles['Normal']))
            
            # Construir el PDF
            doc.build(story)
            return True
            
        except Exception as e:
            print(f"Error generando PDF de orden individual: {e}")
            return False
    
    def generar_resumen_semanal(self, programacion: Dict, tareas: List[Dict], output_path: str) -> bool:
        """
        Generar PDF de resumen semanal con Gantt
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            output_path: Ruta donde guardar el PDF
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            # DEBUG: Log de inicio
            print(f"🔍 DEBUG PDF: Iniciando generación de PDF")
            print(f"🔍 DEBUG PDF: Programación ID: {programacion.get('id', 'N/A')}")
            print(f"🔍 DEBUG PDF: Total tareas: {len(tareas)}")
            print(f"🔍 DEBUG PDF: Output path: {output_path}")
            
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # Título principal
            story.append(Paragraph("RESUMEN SEMANAL DE PRODUCCIÓN", self.styles['TituloPrincipal']))
            story.append(Spacer(1, 20))
            
            # Información general
            info_general = [
                ["Semana de Producción:", f"Semana {programacion['semana_produccion']} - {programacion['anio']}"],
                ["Estado:", programacion['estado'].value if hasattr(programacion['estado'], 'value') else str(programacion['estado'])],
                ["Total de Tareas:", str(len(tareas))],
                ["Makespan Planificado:", f"{programacion['makespan_planificado']:.1f} minutos" if programacion['makespan_planificado'] else "N/A"],
                ["Objetivo:", programacion['objetivo_usado']]
            ]
            
            tabla_general = Table(info_general, colWidths=[2*inch, 3*inch])
            tabla_general.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_general)
            story.append(Spacer(1, 20))
            
            # Tabla de tareas
            story.append(Paragraph("DETALLE DE TAREAS PROGRAMADAS", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            # Preparar datos para la tabla
            tabla_data = [["Trabajo", "Tarea", "Día", "Máquina", "Operador", "Inicio", "Fin", "Duración"]]
            
            # DEBUG: Crear archivo TXT con los datos que llegan al PDF
            debug_file = "debug_pdf_data.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"=== DATOS QUE LLEGAN AL PDF ===\n")
                f.write(f"Total tareas: {len(tareas)}\n")
                f.write(f"Programación ID: {programacion.get('id', 'N/A')}\n")
                f.write(f"Programación Estado: {programacion.get('estado', 'N/A')}\n\n")
                
                for i, t in enumerate(tareas):
                    f.write(f"TAREA {i+1}:\n")
                    f.write(f"  ID: {t.get('tarea_id', 'N/A')}\n")
                    f.write(f"  Nombre: {t.get('nombre', 'N/A')}\n")
                    f.write(f"  Es dividida: {t.get('es_dividida', 'N/A')}\n")
                    f.write(f"  Parte numero: {t.get('parte_numero', 'N/A')}\n")
                    f.write(f"  Inicio planificado: {t.get('inicio_planificado', 'N/A')}\n")
                    f.write(f"  Fin planificado: {t.get('fin_planificado', 'N/A')}\n")
                    f.write(f"  Duración: {t.get('duracion_planificada', 'N/A')}\n")
                    f.write(f"  Máquina: {t.get('maquina_id', 'N/A')}\n")
                    f.write(f"  Operador: {t.get('operador_id', 'N/A')}\n")
                    f.write(f"  Trabajo: {t.get('trabajo_id', 'N/A')}\n")
                    f.write(f"  Trabajo nombre: {t.get('trabajo_nombre', 'N/A')}\n")
                    f.write("\n")
            
            for tarea in tareas:
                # Mejorar formato del nombre del trabajo
                trabajo_nombre = tarea.get('trabajo_nombre', tarea.get('trabajo_id', 'N/A'))
                if trabajo_nombre.startswith('Trabajo '):
                    trabajo_nombre = trabajo_nombre.replace('Trabajo ', '')
                
                # Usar el ID completo de la tarea (ej: A2.P1, A2.P2)
                tarea_id = tarea.get('tarea_id', 'N/A')
                
                fila = [
                    tarea.get('trabajo_id', 'N/A'),  # Trabajo
                    tarea_id,  # Tarea
                    tarea.get('dia', 'N/A')[:3],  # Día
                    f"{tarea['maquina_id']}",  # Máquina
                    f"{tarea.get('operador_id', 'Sin asignar')}",  # Operador
                    tarea['inicio_planificado'],  # Inicio (ya en formato HH:MM)
                    tarea['fin_planificado'],  # Fin (ya en formato HH:MM)
                    f"{tarea['duracion_planificada']} min"  # Duración
                ]
                tabla_data.append(fila)
            
            tabla_tareas = Table(tabla_data, colWidths=[0.5*inch, 1.2*inch, 0.6*inch, 0.7*inch, 0.9*inch, 0.7*inch, 0.7*inch, 0.7*inch])
            tabla_tareas.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_tareas)
            story.append(Spacer(1, 20))
            
            # Resumen por máquina
            story.append(Paragraph("RESUMEN POR MÁQUINA", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            # Agrupar tareas por máquina
            tareas_por_maquina = {}
            for tarea in tareas:
                maquina = tarea['maquina_id']
                if maquina not in tareas_por_maquina:
                    tareas_por_maquina[maquina] = []
                tareas_por_maquina[maquina].append(tarea)
            
            for maquina, tareas_maq in tareas_por_maquina.items():
                story.append(Paragraph(f"Máquina {maquina}: {len(tareas_maq)} tareas", self.styles['InfoTrabajo']))
                
                # Calcular tiempo total por máquina
                tiempo_total = sum(t['duracion_planificada'] for t in tareas_maq)
                story.append(Paragraph(f"Tiempo total: {tiempo_total} minutos ({tiempo_total/60:.1f} horas)", 
                                     self.styles['InfoTarea']))
                story.append(Spacer(1, 5))
            
            # Pie de página
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                                 self.styles['Normal']))
            
            # Construir el PDF
            doc.build(story)
            print(f"🔍 DEBUG PDF: PDF generado exitosamente en {output_path}")
            return True
            
        except Exception as e:
            print(f"Error generando PDF de resumen semanal: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _formatear_hora(self, tiempo_input) -> str:
        """
        Convertir tiempo de entrada a formato HH:MM
        Si recibe minutos desde inicio (int), los convierte a HH:MM
        Si recibe string HH:MM, lo devuelve tal como está
        """
        if tiempo_input is None:
            return "N/A"
        
        # Si ya es un string HH:MM, devolverlo tal como está
        if isinstance(tiempo_input, str):
            return tiempo_input
        
        # Si es un número (minutos acumulativos), usar la lógica original
        minutos_desde_inicio = tiempo_input
        
        # Horario de trabajo: 8:00 AM a 6:00 PM (9 horas efectivas = 540 minutos)
        # Cada día laboral tiene 540 minutos de trabajo efectivo
        minutos_por_dia = 540  # 9 horas * 60 minutos
        
        # Calcular qué día es (0 = Lunes, 1 = Martes, etc.)
        dia = minutos_desde_inicio // minutos_por_dia
        minutos_del_dia = minutos_desde_inicio % minutos_por_dia
        
        # CASO ESPECIAL: Si minutos_del_dia es 0 y minutos_desde_inicio > 0,
        # significa que estamos exactamente al inicio de un nuevo día
        # En este caso, debemos mostrar 18:00 del día anterior, no 08:00 del día actual
        if minutos_del_dia == 0 and minutos_desde_inicio > 0:
            return "18:00"  # 18:00 del día anterior
        
        # Convertir minutos del día a hora real (empezando a las 8:00 AM)
        hora_base = 8  # 8:00 AM
        horas_totales = hora_base + (minutos_del_dia // 60)
        minutos = minutos_del_dia % 60
        
        # Ajustar para formato 24h
        if horas_totales >= 24:
            horas_totales = horas_totales % 24
        
        return f"{horas_totales:02d}:{minutos:02d}"
    
    def _obtener_dia_semana(self, tiempo_input) -> str:
        """
        Obtener día de la semana desde tiempo de entrada
        Si recibe minutos acumulativos (int), los convierte a día
        Si recibe string HH:MM, usa el campo 'dia' de la tarea
        """
        if tiempo_input is None:
            return "N/A"
        
        # Si es un string (HH:MM), significa que los datos ya están procesados
        if isinstance(tiempo_input, str):
            # En este caso, necesitamos el campo 'dia' de la tarea
            # Por ahora retornamos un valor por defecto
            return "Lunes"  # Valor por defecto, se debería pasar el día real
        
        # Si es un número (minutos acumulativos), usar la lógica original
        minutos_por_dia = 540  # 9 horas * 60 minutos
        dia_numero = int(tiempo_input // minutos_por_dia)
        
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        
        if 0 <= dia_numero < len(dias_semana):
            return dias_semana[dia_numero]
        else:
            return f"Día {dia_numero + 1}"
    
    def generar_ordenes_completas(self, programacion: Dict, tareas: List[Dict], output_path: str) -> bool:
        """
        Generar PDF completo con múltiples páginas:
        - Página 1: Resumen General
        - Páginas siguientes: Órdenes individuales por operador y máquina
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de todas las tareas programadas
            output_path: Ruta donde guardar el PDF
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            # DEBUG: Log de inicio
            print("DEBUG ORDENES: Iniciando generacion de ordenes completas")
            print("DEBUG ORDENES: Programacion ID:", programacion.get('id', 'N/A'))
            print("DEBUG ORDENES: Total tareas:", len(tareas))
            print("DEBUG ORDENES: Output path:", output_path)
            
            # DEBUG: Crear archivo TXT con los datos que llegan
            debug_file = "debug_ordenes_data.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"=== DATOS QUE LLEGAN A ÓRDENES COMPLETAS ===\n")
                f.write(f"Total tareas: {len(tareas)}\n")
                f.write(f"Programación ID: {programacion.get('id', 'N/A')}\n")
                f.write(f"Programación Estado: {programacion.get('estado', 'N/A')}\n")
                f.write(f"Fecha generación: {programacion.get('fecha_creacion', 'N/A')}\n\n")
                
                f.write("=== ESTRUCTURA DE LA TABLA PDF ===\n")
                f.write("Columnas: Trabajo | Tarea | Día | Máquina | Operador | Inicio | Fin | Duración\n\n")
                
                f.write("=== TODAS LAS TAREAS ===\n")
                for i, t in enumerate(tareas):
                    f.write(f"TAREA {i+1}:\n")
                    f.write(f"  Trabajo ID: {t.get('trabajo_id', 'N/A')}\n")
                    f.write(f"  Tarea ID: {t.get('tarea_id', 'N/A')}\n")
                    f.write(f"  Día: {t.get('dia', 'N/A')}\n")
                    f.write(f"  Máquina ID: {t.get('maquina_id', 'N/A')}\n")
                    f.write(f"  Operador ID: {t.get('operador_id', 'N/A')}\n")
                    f.write(f"  Inicio planificado: {t.get('inicio_planificado', 'N/A')}\n")
                    f.write(f"  Fin planificado: {t.get('fin_planificado', 'N/A')}\n")
                    f.write(f"  Duración: {t.get('duracion_planificada', 'N/A')}\n")
                    f.write(f"  Es dividida: {t.get('es_dividida', 'N/A')}\n")
                    f.write(f"  Parte numero: {t.get('parte_numero', 'N/A')}\n")
                    f.write(f"  Nombre: {t.get('nombre', 'N/A')}\n")
                    f.write("\n")
                
                f.write("=== FORMATO FINAL PARA PDF ===\n")
                for i, t in enumerate(tareas):
                    trabajo = t.get('trabajo_id', 'N/A')
                    tarea_id = t.get('tarea_id', 'N/A')
                    dia = t.get('dia', 'N/A')[:3] if t.get('dia') else 'N/A'
                    maquina = f"Máquina {t.get('maquina_id', 'N/A')}"
                    operador = f"Operador {t.get('operador_id', 'Sin asignar')}"
                    inicio = self._formatear_hora(t.get('inicio_planificado', 'N/A'))
                    fin = self._formatear_hora(t.get('fin_planificado', 'N/A'))
                    duracion = f"{t.get('duracion_planificada', 'N/A')} min"
                    
                    f.write(f"Fila {i+1}: {trabajo} | {tarea_id} | {dia} | {maquina} | {operador} | {inicio} | {fin} | {duracion}\n")
            
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # ===== PÁGINA 1: RESUMEN GENERAL =====
            story.append(Paragraph("RESUMEN SEMANAL DE PRODUCCIÓN", self.styles['TituloPrincipal']))
            story.append(Spacer(1, 20))
            
            # Información general
            info_general = [
                ["Semana de Producción:", f"Semana {programacion['semana_produccion']} - {programacion['anio']}"],
                ["Estado:", programacion['estado'].value if hasattr(programacion['estado'], 'value') else str(programacion['estado'])],
                ["Total de Tareas:", str(len(tareas))],
                ["Makespan Planificado:", f"{programacion['makespan_planificado']:.1f} minutos" if programacion['makespan_planificado'] else "N/A"],
                ["Objetivo:", programacion['objetivo_usado']]
            ]
            
            tabla_general = Table(info_general, colWidths=[2*inch, 3*inch])
            tabla_general.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_general)
            story.append(Spacer(1, 20))
            
            # Tabla de tareas (versión compacta)
            story.append(Paragraph("DETALLE DE TAREAS PROGRAMADAS", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            tabla_data = [["Trabajo", "Tarea", "Día", "Máquina", "Operador", "Inicio", "Fin", "Duración"]]
            
            for tarea in tareas:
                trabajo_nombre = tarea.get('trabajo_nombre', tarea.get('trabajo_id', 'N/A'))
                if trabajo_nombre.startswith('Trabajo '):
                    trabajo_nombre = trabajo_nombre.replace('Trabajo ', '')
                
                # Extraer nombre base y parte por separado
                nombre_tarea = tarea.get('nombre', 'N/A')
                parte = ""
                
                if tarea.get('es_dividida', False):
                    parte_num = tarea.get('parte_numero', 1)
                    parte = f"P{parte_num}"
                else:
                    parte = "-"
                
                # Limpiar el nombre base (remover (P1), (P2), etc. si están)
                nombre_base = nombre_tarea
                if " (P" in nombre_base:
                    nombre_base = nombre_base.split(" (P")[0]
                
                fila = [
                    tarea.get('trabajo_id', 'N/A'),  # Trabajo
                    tarea.get('tarea_id', 'N/A'),  # Tarea (ID completo con subíndices)
                    tarea.get('dia', 'N/A')[:3],   # Día (abreviado)
                    f"{tarea.get('maquina_id', 'N/A')}",  # Máquina
                    f"{tarea.get('operador_id', 'Sin asignar')}",  # Operador
                    tarea['inicio_planificado'],  # Inicio (ya en formato HH:MM)
                    tarea['fin_planificado'],  # Fin (ya en formato HH:MM)
                    f"{tarea['duracion_planificada']} min"  # Duración
                ]
                tabla_data.append(fila)
            
            tabla_tareas = Table(tabla_data, colWidths=[0.5*inch, 1.0*inch, 0.5*inch, 0.6*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.6*inch])
            tabla_tareas.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_tareas)
            story.append(Spacer(1, 20))
            
            # Resumen por máquina (compacto)
            story.append(Paragraph("RESUMEN POR MÁQUINA", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            tareas_por_maquina = {}
            for tarea in tareas:
                maquina = tarea['maquina_id']
                if maquina not in tareas_por_maquina:
                    tareas_por_maquina[maquina] = []
                tareas_por_maquina[maquina].append(tarea)
            
            for maquina, tareas_maq in tareas_por_maquina.items():
                tiempo_total = sum(t['duracion_planificada'] for t in tareas_maq)
                story.append(Paragraph(f"Máquina M{maquina}: {len(tareas_maq)} tareas - {tiempo_total} minutos ({tiempo_total/60:.1f} horas)", 
                                     self.styles['InfoTrabajo']))
            
            # Salto de página
            story.append(PageBreak())
            
            # ===== PÁGINAS DE ÓRDENES POR OPERADOR =====
            tareas_por_operador = {}
            for tarea in tareas:
                operador = f"{tarea.get('operador_id', 'Sin asignar')}"
                if operador not in tareas_por_operador:
                    tareas_por_operador[operador] = []
                tareas_por_operador[operador].append(tarea)
            
            for operador, tareas_op in tareas_por_operador.items():
                story.append(Paragraph(f"ORDEN DE TRABAJO - OPERADOR {operador}", self.styles['TituloPrincipal']))
                story.append(Spacer(1, 20))
                
                # Información del operador
                info_operador = [
                    ["Semana de Producción:", f"Semana {programacion['semana_produccion']} - {programacion['anio']}"],
                    ["Operador:", operador],
                    ["Total de Tareas:", str(len(tareas_op))],
                    ["Estado:", programacion['estado'].value if hasattr(programacion['estado'], 'value') else str(programacion['estado'])]
                ]
                
                tabla_operador = Table(info_operador, colWidths=[2*inch, 3*inch])
                tabla_operador.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(tabla_operador)
                story.append(Spacer(1, 20))
                
                # Lista de tareas del operador
                story.append(Paragraph("TAREAS ASIGNADAS", self.styles['Subtitulo']))
                story.append(Spacer(1, 10))
                
                for i, tarea in enumerate(tareas_op, 1):
                    story.append(Paragraph(f"Tarea {i}: {tarea.get('nombre', 'N/A')}", self.styles['InfoTrabajo']))
                    story.append(Paragraph(f"Trabajo: {tarea.get('trabajo_id', 'N/A')}", self.styles['InfoTarea']))
                    story.append(Paragraph(f"Máquina: {tarea['maquina_id']}", self.styles['InfoTarea']))
                    story.append(Paragraph(f"Día: {tarea.get('dia', 'N/A')}", self.styles['InfoTarea']))
                    story.append(Paragraph(f"Hora de Inicio: {self._formatear_hora(tarea['inicio_planificado'])}", self.styles['InfoTarea']))
                    story.append(Paragraph(f"Hora de Fin: {self._formatear_hora(tarea['fin_planificado'])}", self.styles['InfoTarea']))
                    story.append(Paragraph(f"Duración: {tarea['duracion_planificada']} minutos", self.styles['InfoTarea']))
                    story.append(Spacer(1, 10))
                
                # Instrucciones específicas
                story.append(Paragraph("INSTRUCCIONES DE TRABAJO Y SETUP", self.styles['Subtitulo']))
                story.append(Spacer(1, 10))
                
                # Leer instrucciones desde archivo
                instrucciones = self._leer_instrucciones_ot()
                
                for instruccion in instrucciones:
                    story.append(Paragraph(instruccion, self.styles['InfoTarea']))
                
                # Sección de registro
                story.append(Spacer(1, 20))
                story.append(Paragraph("REGISTRO DE EJECUCIÓN", self.styles['Subtitulo']))
                story.append(Spacer(1, 10))
                
                registro_data = [
                    ["Fecha:", "_________________"],
                    ["Hora de Inicio Real:", "_________________"],
                    ["Hora de Fin Real:", "_________________"],
                    ["Problemas Encontrados:", "_________________"],
                    ["Observaciones:", "_________________"],
                    ["", ""],
                    ["Firma del Operador:", "_________________"],
                    ["Firma del Supervisor:", "_________________"]
                ]
                
                tabla_registro = Table(registro_data, colWidths=[2*inch, 3*inch])
                tabla_registro.setStyle(TableStyle([
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(tabla_registro)
                
                # Salto de página (excepto para el último operador)
                if operador != list(tareas_por_operador.keys())[-1]:
                    story.append(PageBreak())
            
            # ===== ELIMINADAS: PÁGINAS DE ÓRDENES POR MÁQUINA =====
            # Las órdenes de máquina se han integrado en las órdenes de operador
            # para simplificar el proceso en PYMEs donde el operador hace su propio setup
            
            # Pie de página final
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                                 self.styles['Normal']))
            
            # Construir el PDF
            doc.build(story)
            print("DEBUG ORDENES: PDF de ordenes completas generado exitosamente en", output_path)
            return True
            
        except Exception as e:
            print(f"Error generando PDF de órdenes completas: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generar_orden_maquina(self, programacion: Dict, tareas_maquina: List[Dict], 
                            numero_maquina: int, output_path: str) -> bool:
        """
        Generar PDF de orden de trabajo para una máquina específica
        
        Args:
            programacion: Datos de la programación
            tareas_maquina: Lista de tareas para la máquina
            numero_maquina: Número de la máquina
            output_path: Ruta donde guardar el PDF
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            
            # Título principal
            story.append(Paragraph(f"ORDEN DE TRABAJO - MÁQUINA {numero_maquina}", 
                                 self.styles['TituloPrincipal']))
            story.append(Spacer(1, 20))
            
            # Información de la programación
            info_programacion = [
                ["Semana de Producción:", f"Semana {programacion['semana_produccion']} - {programacion['anio']}"],
                ["Máquina:", f"M{numero_maquina}"],
                ["Total de Tareas:", str(len(tareas_maquina))],
                ["Estado:", programacion['estado'].value if hasattr(programacion['estado'], 'value') else str(programacion['estado'])]
            ]
            
            tabla_programacion = Table(info_programacion, colWidths=[2*inch, 3*inch])
            tabla_programacion.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(tabla_programacion)
            story.append(Spacer(1, 20))
            
            # Lista de tareas
            story.append(Paragraph("TAREAS PROGRAMADAS", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            for i, tarea in enumerate(tareas_maquina, 1):
                story.append(Paragraph(f"Tarea {i}: {tarea.get('nombre', 'N/A')}", self.styles['InfoTrabajo']))
                story.append(Paragraph(f"Trabajo: {tarea.get('trabajo_id', 'N/A')}", self.styles['InfoTarea']))
                story.append(Paragraph(f"Operador: {tarea.get('operador_id', 'Sin asignar')}", self.styles['InfoTarea']))
                story.append(Paragraph(f"Hora de Inicio: {self._formatear_hora(tarea['inicio_planificado'])}", self.styles['InfoTarea']))
                story.append(Paragraph(f"Hora de Fin: {self._formatear_hora(tarea['fin_planificado'])}", self.styles['InfoTarea']))
                story.append(Paragraph(f"Duración: {tarea['duracion_planificada']} minutos", self.styles['InfoTarea']))
                story.append(Spacer(1, 10))
            
            # Instrucciones generales
            story.append(Paragraph("INSTRUCCIONES GENERALES", self.styles['Subtitulo']))
            story.append(Spacer(1, 10))
            
            instrucciones = [
                "1. Verificar que la máquina esté en condiciones óptimas",
                "2. Revisar herramientas y materiales necesarios",
                "3. Ejecutar las tareas en el orden programado",
                "4. Registrar tiempos reales de inicio y fin",
                "5. Reportar cualquier problema o desviación",
                "6. Confirmar la calidad del trabajo realizado"
            ]
            
            for instruccion in instrucciones:
                story.append(Paragraph(instruccion, self.styles['InfoTarea']))
            
            # Pie de página
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                                 self.styles['Normal']))
            
            # Construir el PDF
            doc.build(story)
            return True
            
        except Exception as e:
            print(f"Error generando PDF de orden de máquina: {e}")
            return False
