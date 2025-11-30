#!/usr/bin/env python3
"""
Módulo Principal de Exportación de Órdenes de Trabajo
Optimizador de Producción v1.3.3
"""

import os
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import streamlit as st

from utils.export_pdf import ExportadorPDF
from utils.export_excel_simple import ExportadorExcelSimple

class GestorExportacion:
    """Clase principal para gestionar todas las exportaciones"""
    
    def __init__(self):
        self.exportador_pdf = ExportadorPDF()
        self.exportador_excel = ExportadorExcelSimple()
        self.directorio_exportaciones = "exportaciones"
        self._crear_directorio_exportaciones()
    
    def _crear_directorio_exportaciones(self):
        """Crear directorio para exportaciones si no existe"""
        if not os.path.exists(self.directorio_exportaciones):
            os.makedirs(self.directorio_exportaciones)
    
    def exportar_programacion_completa(self, programacion: Dict, tareas: List[Dict]) -> Dict[str, str]:
        """
        Exportar programación completa en todos los formatos
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            
        Returns:
            Dict con rutas de archivos generados
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        semana = programacion['semana_produccion']
        anio = programacion['anio']
        
        archivos_generados = {}
        
        try:
            # 1. PDF - Resumen semanal
            nombre_resumen = f"Resumen_Semana_{semana}_{anio}_{timestamp}.pdf"
            ruta_resumen = os.path.join(self.directorio_exportaciones, nombre_resumen)
            
            if self.exportador_pdf.generar_resumen_semanal(programacion, tareas, ruta_resumen):
                archivos_generados['resumen_pdf'] = ruta_resumen
                st.success(f"✅ Resumen semanal PDF generado: {nombre_resumen}")
            
            return archivos_generados
            
        except Exception as e:
            st.error(f"❌ Error en exportación completa: {e}")
            return {}
    
    def exportar_ordenes_completas(self, programacion: Dict, tareas: List[Dict]) -> Optional[str]:
        """
        Exportar PDF multi-página con órdenes completas (resumen + órdenes por operador y máquina)
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            
        Returns:
            str: Ruta del archivo PDF generado o None si hay error
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            semana = programacion['semana_produccion']
            anio = programacion['anio']
            nombre_pdf = f"Ordenes_Semana_{semana}_{anio}_{timestamp}.pdf"
            ruta_pdf = os.path.join(self.directorio_exportaciones, nombre_pdf)
            
            resultado = self.exportador_pdf.generar_ordenes_completas(programacion, tareas, ruta_pdf)
            
            if resultado:
                st.success(f"✅ Órdenes de trabajo generadas: {nombre_pdf}")
                st.success("✅ PDF multi-página generado exitosamente")
                return ruta_pdf
            else:
                st.error(f"❌ No se pudo generar las órdenes de trabajo: {nombre_pdf}")
                return None
                
        except Exception as e:
            st.error(f"❌ Error en exportación de órdenes completas: {e}")
            return None
    
    def exportar_excel_simple(self, programacion: Dict, tareas: List[Dict]) -> Optional[str]:
        """
        Exportar solo Excel de forma simple
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            
        Returns:
            str: Ruta del archivo generado o None si hay error
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            semana = programacion['semana_produccion']
            anio = programacion['anio']
            
            nombre_planilla = f"Planilla_Semana_{semana}_{anio}_{timestamp}.xlsx"
            ruta_planilla = os.path.join(self.directorio_exportaciones, nombre_planilla)
            
            print(f"DEBUG: Intentando generar Excel en: {ruta_planilla}")
            print(f"DEBUG: Número de tareas: {len(tareas)}")
            
            resultado = self.exportador_excel.generar_excel_simple(programacion, tareas, ruta_planilla)
            print(f"DEBUG: Resultado Excel: {resultado}")
            
            if resultado:
                st.success(f"✅ Planilla Excel generada: {nombre_planilla}")
                st.success("✅ Excel generado exitosamente")
                return ruta_planilla
            else:
                st.error(f"❌ No se pudo generar Excel: {nombre_planilla}")
                return None
                
        except Exception as e:
            st.error(f"❌ Error generando Excel: {e}")
            print(f"DEBUG: Error completo: {e}")
            return None
    
    def exportar_csv_simple(self, programacion: Dict, tareas: List[Dict]) -> Optional[str]:
        """
        Exportar solo CSV de forma simple
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            
        Returns:
            str: Ruta del archivo generado o None si hay error
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            semana = programacion['semana_produccion']
            anio = programacion['anio']
            
            nombre_csv = f"Datos_Semana_{semana}_{anio}_{timestamp}.csv"
            ruta_csv = os.path.join(self.directorio_exportaciones, nombre_csv)
            
            print(f"DEBUG: Intentando generar CSV en: {ruta_csv}")
            print(f"DEBUG: Número de tareas: {len(tareas)}")
            
            resultado = self.exportador_excel.generar_csv_simple(programacion, tareas, ruta_csv)
            print(f"DEBUG: Resultado CSV: {resultado}")
            
            if resultado:
                st.success(f"✅ Datos CSV generados: {nombre_csv}")
                st.success("✅ CSV generado exitosamente")
                return ruta_csv
            else:
                st.error(f"❌ No se pudo generar CSV: {nombre_csv}")
                return None
                
        except Exception as e:
            st.error(f"❌ Error generando CSV: {e}")
            print(f"DEBUG: Error completo: {e}")
            return None
    
    def _generar_ordenes_maquinas(self, programacion: Dict, tareas: List[Dict], timestamp: str) -> Dict[str, str]:
        """Generar órdenes individuales por máquina"""
        archivos_maquinas = {}
        
        # Agrupar tareas por máquina
        tareas_por_maquina = {}
        for tarea in tareas:
            maquina = tarea['maquina_id']
            if maquina not in tareas_por_maquina:
                tareas_por_maquina[maquina] = []
            tareas_por_maquina[maquina].append(tarea)
        
        # Generar PDF para cada máquina
        for maquina, tareas_maq in tareas_por_maquina.items():
            nombre_maquina = f"Orden_Maquina_{maquina}_Semana_{programacion['semana_produccion']}_{programacion['anio']}_{timestamp}.pdf"
            ruta_maquina = os.path.join(self.directorio_exportaciones, nombre_maquina)
            
            if self.exportador_pdf.generar_orden_maquina(programacion, tareas_maq, maquina, ruta_maquina):
                archivos_maquinas[f'maquina_{maquina}_pdf'] = ruta_maquina
                st.success(f"✅ Orden de máquina {maquina} generada: {nombre_maquina}")
        
        return archivos_maquinas
    
    def exportar_orden_trabajo_individual(self, programacion: Dict, tarea: Dict) -> Optional[str]:
        """
        Exportar orden de trabajo individual para una tarea específica
        
        Args:
            programacion: Datos de la programación
            tarea: Datos de la tarea específica
            
        Returns:
            str: Ruta del archivo generado o None si hay error
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            semana = programacion['semana_produccion']
            anio = programacion['anio']
            maquina = tarea['maquina_id']
            
            # Crear nombre de archivo seguro
            nombre_trabajo = tarea.get('trabajo_nombre', tarea.get('trabajo_id', 'Trabajo')).replace(' ', '_').replace('/', '_')[:20]
            nombre_tarea = tarea.get('nombre', 'Tarea').replace(' ', '_').replace('/', '_')[:20]
            
            nombre_archivo = f"Orden_{nombre_trabajo}_{nombre_tarea}_M{maquina}_{timestamp}.pdf"
            ruta_archivo = os.path.join(self.directorio_exportaciones, nombre_archivo)
            
            if self.exportador_pdf.generar_orden_trabajo_individual(programacion, tarea, ruta_archivo):
                st.success(f"✅ Orden de trabajo individual generada: {nombre_archivo}")
                return ruta_archivo
            else:
                st.error("❌ Error generando orden de trabajo individual")
                return None
                
        except Exception as e:
            st.error(f"❌ Error en exportación individual: {e}")
            return None
    
    def obtener_archivos_exportacion(self) -> List[Dict[str, str]]:
        """
        Obtener lista de archivos de exportación disponibles
        
        Returns:
            Lista de diccionarios con información de archivos
        """
        archivos = []
        
        if not os.path.exists(self.directorio_exportaciones):
            return archivos
        
        for nombre_archivo in os.listdir(self.directorio_exportaciones):
            ruta_completa = os.path.join(self.directorio_exportaciones, nombre_archivo)
            
            if os.path.isfile(ruta_completa):
                # Obtener información del archivo
                stat = os.stat(ruta_completa)
                fecha_modificacion = datetime.fromtimestamp(stat.st_mtime)
                tamaño = stat.st_size
                
                # Determinar tipo de archivo
                tipo = "PDF" if nombre_archivo.endswith('.pdf') else "Excel" if nombre_archivo.endswith('.xlsx') else "CSV"
                
                archivos.append({
                    'nombre': nombre_archivo,
                    'ruta': ruta_completa,
                    'tipo': tipo,
                    'fecha': fecha_modificacion,
                    'tamaño': tamaño
                })
        
        # Ordenar por fecha de modificación (más recientes primero)
        archivos.sort(key=lambda x: x['fecha'], reverse=True)
        
        return archivos
    
    def limpiar_archivos_antiguos(self, dias_antiguedad: int = 30):
        """
        Limpiar archivos de exportación más antiguos que el número de días especificado
        
        Args:
            dias_antiguedad: Número de días de antigüedad para considerar archivo como antiguo
        """
        try:
            archivos = self.obtener_archivos_exportacion()
            fecha_limite = datetime.now().timestamp() - (dias_antiguedad * 24 * 60 * 60)
            
            archivos_eliminados = 0
            for archivo in archivos:
                if archivo['fecha'].timestamp() < fecha_limite:
                    os.remove(archivo['ruta'])
                    archivos_eliminados += 1
            
            if archivos_eliminados > 0:
                st.info(f"🧹 Se eliminaron {archivos_eliminados} archivos de exportación antiguos")
                
        except Exception as e:
            st.error(f"❌ Error limpiando archivos antiguos: {e}")
    
    def obtener_estadisticas_exportacion(self) -> Dict[str, int]:
        """
        Obtener estadísticas de archivos de exportación
        
        Returns:
            Diccionario con estadísticas
        """
        archivos = self.obtener_archivos_exportacion()
        
        estadisticas = {
            'total_archivos': len(archivos),
            'archivos_pdf': len([a for a in archivos if a['tipo'] == 'PDF']),
            'archivos_excel': len([a for a in archivos if a['tipo'] == 'Excel']),
            'archivos_csv': len([a for a in archivos if a['tipo'] == 'CSV']),
            'tamaño_total_mb': sum(a['tamaño'] for a in archivos) / (1024 * 1024)
        }
        
        return estadisticas
