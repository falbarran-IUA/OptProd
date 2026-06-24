#!/usr/bin/env python3
"""
Exportador Excel Simplificado
Optimizador de Producción v1.3.3
"""

import pandas as pd
import os
from typing import List, Dict

class ExportadorExcelSimple:
    """Exportador Excel simplificado y robusto"""
    
    def __init__(self):
        pass
    
    def generar_excel_simple(self, programacion: Dict, tareas: List[Dict], output_path: str) -> bool:
        """
        Generar Excel de forma simple usando pandas
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            output_path: Ruta donde guardar el Excel
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            print(f"DEBUG: Iniciando generación de Excel en: {output_path}")
            print(f"DEBUG: Número de tareas: {len(tareas)}")
            
            if not tareas:
                print("DEBUG: No hay tareas para exportar")
                return False
            
            # Preparar datos para Excel
            datos_excel = []
            
            for i, tarea in enumerate(tareas, 1):
                # Debug: ver qué datos llegan
                if i == 1:  # Solo para la primera tarea
                    print(f"DEBUG EXCEL TAREA 1: Keys={list(tarea.keys())}")
                    print(f"DEBUG EXCEL TAREA 1: inicio_hora={tarea.get('inicio_hora')}, fin_hora={tarea.get('fin_hora')}, dia_nombre={tarea.get('dia_nombre')}")
                    print(f"DEBUG EXCEL TAREA 1: inicio_planificado={tarea.get('inicio_planificado')}, fin_planificado={tarea.get('fin_planificado')}")
                
                # Usar datos procesados si están disponibles, sino calcular desde raw
                inicio_hora = tarea.get('inicio_hora')
                fin_hora = tarea.get('fin_hora')
                dia_nombre = tarea.get('dia_nombre')
                
                # Si no existen datos procesados, intentar calcular desde raw
                if not inicio_hora or not fin_hora or not dia_nombre:
                    # Calcular desde minutos acumulativos
                    inicio_min = tarea.get('inicio_planificado', 0)
                    fin_min = tarea.get('fin_planificado', 0)
                    inicio_hora = self._formatear_hora_simple(inicio_min)
                    fin_hora = self._formatear_hora_simple(fin_min)
                    dia_nombre = tarea.get('dia_semana', 'N/A')
                
                # Extraer letra de trabajo (ej: "A" desde "Trabajo A" o directamente "A")
                trabajo_id = tarea.get('trabajo_id', 'N/A')
                if 'Trabajo ' in str(trabajo_id):
                    trabajo_letra = str(trabajo_id).replace('Trabajo ', '')
                else:
                    trabajo_letra = trabajo_id
                
                # Formatear máquina (M01, M02, etc.)
                maquina_raw = tarea.get('maquina_id', 'N/A')
                if maquina_raw and maquina_raw != 'N/A':
                    if maquina_raw.startswith('M'):
                        maquina_formato = maquina_raw.replace('M', 'M').zfill(3)  # M01, M02, etc.
                    else:
                        maquina_formato = f"M{str(maquina_raw).zfill(2)}"
                else:
                    maquina_formato = 'M00'
                
                # Formatear operador (Op01, Op02, etc.)
                operador_raw = tarea.get('operador_id', 'Por asignar')
                if operador_raw and operador_raw != 'Por asignar':
                    if str(operador_raw).startswith('Op') or str(operador_raw).startswith('OP'):
                        operador_formato = str(operador_raw).replace('OP', 'Op')
                    else:
                        operador_formato = f"Op{str(operador_raw).zfill(2)}"
                else:
                    operador_formato = 'Por asignar'
                
                fila = {
                    'Número': i,
                    'Tarea': tarea.get('nombre', 'N/A'),
                    'Trabajo': trabajo_letra,
                    'Máquina': maquina_formato,
                    'Operador': operador_formato,
                    'Día': dia_nombre,
                    'Inicio': inicio_hora,
                    'Fin': fin_hora,
                    'Duración (min)': tarea.get('duracion_planificada', 0),
                    'Setup (min)': tarea.get('tiempo_setup', 0)
                }
                datos_excel.append(fila)
            
            print(f"DEBUG: Datos preparados: {len(datos_excel)} filas")
            
            # Crear DataFrame
            df = pd.DataFrame(datos_excel)
            print(f"DEBUG: DataFrame creado con {len(df)} filas y {len(df.columns)} columnas")
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Guardar Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Hoja principal con datos
                df.to_excel(writer, sheet_name='Planilla Producción', index=False)
                
                # Hoja con información de la programación
                info_data = {
                    'Campo': ['ID Programación', 'Semana', 'Año', 'Estado', 'Objetivo', 'Makespan (min)', 'Fecha Creación'],
                    'Valor': [
                        programacion.get('id', 'N/A'),
                        programacion.get('semana_produccion', 'N/A'),
                        programacion.get('anio', 'N/A'),
                        str(programacion.get('estado', 'N/A')),
                        programacion.get('objetivo_usado', 'N/A'),
                        programacion.get('makespan_planificado', 'N/A'),
                        str(programacion.get('fecha_creacion', 'N/A'))
                    ]
                }
                df_info = pd.DataFrame(info_data)
                df_info.to_excel(writer, sheet_name='Información', index=False)
            
            print(f"DEBUG: Excel guardado exitosamente en: {output_path}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Error generando Excel: {e}")
            print(f"DEBUG: Tipo de error: {type(e)}")
            import traceback
            print(f"DEBUG: Traceback completo: {traceback.format_exc()}")
            return False
    
    def generar_csv_simple(self, programacion: Dict, tareas: List[Dict], output_path: str) -> bool:
        """
        Generar CSV de forma simple
        
        Args:
            programacion: Datos de la programación
            tareas: Lista de tareas programadas
            output_path: Ruta donde guardar el CSV
            
        Returns:
            bool: True si se generó correctamente
        """
        try:
            print(f"DEBUG: Iniciando generación de CSV en: {output_path}")
            print(f"DEBUG: Número de tareas: {len(tareas)}")
            
            if not tareas:
                print("DEBUG: No hay tareas para exportar")
                return False
            
            # Preparar datos para CSV
            datos_csv = []
            
            for tarea in tareas:
                # Usar datos procesados si están disponibles, sino calcular desde raw
                inicio_hora = tarea.get('inicio_hora')
                fin_hora = tarea.get('fin_hora')
                dia_nombre = tarea.get('dia_nombre')
                
                # Si no existen datos procesados, intentar calcular desde raw
                if not inicio_hora or not fin_hora or not dia_nombre:
                    # Calcular desde minutos acumulativos
                    inicio_min = tarea.get('inicio_planificado', 0)
                    fin_min = tarea.get('fin_planificado', 0)
                    inicio_hora = self._formatear_hora_simple(inicio_min)
                    fin_hora = self._formatear_hora_simple(fin_min)
                    dia_nombre = tarea.get('dia_semana', 'N/A')
                
                # Extraer letra de trabajo
                trabajo_id = tarea.get('trabajo_id', 'N/A')
                if 'Trabajo ' in str(trabajo_id):
                    trabajo_letra = str(trabajo_id).replace('Trabajo ', '')
                else:
                    trabajo_letra = trabajo_id
                
                # Formatear máquina (M01, M02, etc.)
                maquina_raw = tarea.get('maquina_id', 'N/A')
                if maquina_raw and maquina_raw != 'N/A':
                    if maquina_raw.startswith('M'):
                        maquina_formato = maquina_raw.replace('M', 'M').zfill(3)  # M01, M02, etc.
                    else:
                        maquina_formato = f"M{str(maquina_raw).zfill(2)}"
                else:
                    maquina_formato = 'M00'
                
                # Formatear operador (Op01, Op02, etc.)
                operador_raw = tarea.get('operador_id', 'Por asignar')
                if operador_raw and operador_raw != 'Por asignar':
                    if str(operador_raw).startswith('Op') or str(operador_raw).startswith('OP'):
                        operador_formato = str(operador_raw).replace('OP', 'Op')
                    else:
                        operador_formato = f"Op{str(operador_raw).zfill(2)}"
                else:
                    operador_formato = 'Por asignar'
                
                fila = {
                    'programacion_id': programacion.get('id', 'N/A'),
                    'semana_produccion': programacion.get('semana_produccion', 'N/A'),
                    'anio': programacion.get('anio', 'N/A'),
                    'tarea_id': tarea.get('tarea_id', tarea.get('id', 'N/A')),
                    'tarea_nombre': tarea.get('nombre', 'N/A'),
                    'trabajo_nombre': trabajo_letra,
                    'maquina_id': maquina_formato,
                    'operador_id': operador_formato,
                    'dia_semana': dia_nombre,
                    'inicio_planificado': inicio_hora,
                    'fin_planificado': fin_hora,
                    'duracion_planificada': tarea.get('duracion_planificada', 0),
                    'tiempo_setup': tarea.get('tiempo_setup', 0),
                    'estado_programacion': str(programacion.get('estado', 'N/A')),
                    'objetivo_usado': programacion.get('objetivo_usado', 'N/A'),
                    'makespan_planificado': programacion.get('makespan_planificado', 'N/A')
                }
                datos_csv.append(fila)
            
            print(f"DEBUG: Datos CSV preparados: {len(datos_csv)} filas")
            
            # Crear DataFrame y guardar CSV
            df = pd.DataFrame(datos_csv)
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Guardar CSV
            df.to_csv(output_path, index=False, encoding='utf-8')
            
            print(f"DEBUG: CSV guardado exitosamente en: {output_path}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Error generando CSV: {e}")
            print(f"DEBUG: Tipo de error: {type(e)}")
            import traceback
            print(f"DEBUG: Traceback completo: {traceback.format_exc()}")
            return False
    
    def _formatear_hora(self, minutos: int) -> str:
        """Convertir minutos a formato HH:MM"""
        try:
            if minutos is None:
                return "00:00"
            horas = minutos // 60
            mins = minutos % 60
            return f"{horas:02d}:{mins:02d}"
        except:
            return "00:00"
    
    def _formatear_hora_simple(self, minutos_acumulativos: int) -> str:
        """Convertir minutos acumulativos a HH:MM (asumiendo día laboral de 540 min, 08:00 inicio)"""
        try:
            if minutos_acumulativos is None:
                return "00:00"
            # Extraer minutos del día (asumiendo 540 min por día, 08:00 inicio)
            minutos_por_dia = 540
            minutos_del_dia = minutos_acumulativos % minutos_por_dia
            # Calcular hora del día (08:00 + minutos_del_dia)
            horas_totales = 8 + (minutos_del_dia // 60)
            mins_totales = minutos_del_dia % 60
            return f"{horas_totales:02d}:{mins_totales:02d}"
        except:
            return "00:00"
