#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación Web para Optimización de Programación de Producción SEMANAL
Interfaz Streamlit para el optimizador de producción con soporte para múltiples trabajos
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import io
import base64
from optimizador_produccion import OptimizadorProduccion

# Imports BD
from utils.db_helpers import (
    inicializar_bd_si_necesario,
    guardar_programacion_desde_resultado,
    guardar_simulacion_con_tareas_divididas,
    aprobar_programacion_actual,
    cancelar_programacion,
    eliminar_programacion_guardada,
    obtener_historial_programaciones,
    obtener_semana_actual,
    convertir_estado_a_emoji,
    convertir_estado_a_color
)
from utils.visualizacion_historico import (
    obtener_asignaciones_como_dataframe,
    comparar_programaciones
)
import modelos.database as database
from modelos.database_models import EstadoProgramacion

# Funciones auxiliares
def minutos_a_hora_dia(minutos_acumulativos, minutos_por_dia_laboral=None):
    """Convierte minutos acumulativos a hora del día"""
    from datetime import time as dt_time, datetime
    
    if minutos_acumulativos is not None:
        try:
            minutos_acumulativos = int(float(minutos_acumulativos))
        except (ValueError, TypeError):
            minutos_acumulativos = None
    
    if minutos_acumulativos is None:
        # Usar hora_inicio de configuración o default 08:00
        hora_inicio = st.session_state.get('hora_inicio')
        if hora_inicio:
            return hora_inicio if isinstance(hora_inicio, dt_time) else datetime.strptime(str(hora_inicio), "%H:%M:%S").time()
        return dt_time(8, 0)
    
    hora_inicio = st.session_state.get('hora_inicio')
    hora_fin = st.session_state.get('hora_fin')
    
    if not hora_inicio:
        hora_inicio = dt_time(8, 0)
    elif not isinstance(hora_inicio, dt_time):
        try:
            hora_inicio = datetime.strptime(str(hora_inicio), "%H:%M:%S").time()
        except:
            hora_inicio = dt_time(8, 0)
    
    if not hora_fin:
        hora_fin = dt_time(18, 0)
    elif not isinstance(hora_fin, dt_time):
        try:
            hora_fin = datetime.strptime(str(hora_fin), "%H:%M:%S").time()
        except:
            hora_fin = dt_time(18, 0)
    
    if minutos_por_dia_laboral is None:
        minutos_por_dia_laboral = st.session_state.get('minutos_por_dia_laboral', 540)
    
    try:
        minutos_por_dia_laboral = int(float(minutos_por_dia_laboral))
    except (ValueError, TypeError):
        minutos_por_dia_laboral = 540
    
    minutos_del_dia = minutos_acumulativos % minutos_por_dia_laboral
    
    if minutos_del_dia == 0 and minutos_acumulativos > 0:
        return hora_inicio
    
    minutos_del_dia = int(minutos_del_dia)
    horas_agregadas = minutos_del_dia // 60
    minutos_agregados = minutos_del_dia % 60
    hora_del_dia_int = int(hora_inicio.hour + horas_agregadas)
    minuto_del_dia_int = int(hora_inicio.minute + minutos_agregados)
    
    # Manejar overflow de minutos
    if minuto_del_dia_int >= 60:
        hora_del_dia_int += 1
        minuto_del_dia_int -= 60
    
    hora_inicio_minutos = hora_inicio.hour * 60 + hora_inicio.minute
    hora_fin_minutos = hora_fin.hour * 60 + hora_fin.minute
    hora_calculada_minutos = hora_del_dia_int * 60 + minuto_del_dia_int
    
    if hora_calculada_minutos >= hora_fin_minutos:
        # Si excede hora_fin, usar hora_fin
        return hora_fin
    elif hora_calculada_minutos < hora_inicio_minutos:
        # Si es menor que hora_inicio, usar hora_inicio
        return hora_inicio
    
    return dt_time(hora_del_dia_int, minuto_del_dia_int)

# Función para procesar datos del resultado de optimización para PDF
def obtener_datos_programacion_detallada(resultado):
    """Procesar datos del resultado de optimización para generar datos formateados para PDF"""
    from datetime import time as dt_time
    
    if not resultado or not resultado.get('solucion') or not resultado['solucion'].get('programacion'):
        return []
    
    programacion_data = []
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    minutos_por_dia = st.session_state.get('minutos_por_dia_laboral', 540)
    
    for tarea_prog in resultado['solucion']['programacion']:
        tarea_id = tarea_prog['tarea_id']
        tarea_indice = tarea_prog.get('tarea_indice', 0)
        
        if tarea_indice < len(st.session_state.tareas_df):
            tarea_original = st.session_state.tareas_df.iloc[tarea_indice]
            inicio_min = tarea_prog['inicio']
            fin_min = tarea_prog['fin']
            duracion_asignada = fin_min - inicio_min
            
            # Calcular en qué día empieza y termina la tarea
            dia_inicio = int(inicio_min // minutos_por_dia)
            dia_fin = int(fin_min // minutos_por_dia)
            debe_dividirse = (dia_inicio != dia_fin)
            
            if debe_dividirse:
                # Dividir la tarea en partes
                tiempo_actual = inicio_min
                tiempo_restante = duracion_asignada
                parte_num = 1
                
                while tiempo_restante > 0:
                    dia_numero = int(tiempo_actual // minutos_por_dia)
                    dia_nombre = dias_semana[dia_numero] if dia_numero < len(dias_semana) else 'N/A'
                    fin_dia_actual = (dia_numero + 1) * minutos_por_dia
                    tiempo_disponible_dia = fin_dia_actual - tiempo_actual
                    duracion_parte = min(tiempo_restante, tiempo_disponible_dia)
                    fin_parte = tiempo_actual + duracion_parte
                    
                    inicio_real = minutos_a_hora_dia(tiempo_actual, minutos_por_dia)
                    
                    # CASO ESPECIAL: Si fin_parte es exactamente el inicio del día siguiente,
                    # significa que la tarea termina al final del día actual (18:00)
                    # Verificar si fin_parte es múltiplo exacto de minutos_por_dia
                    print(f"DEBUG: {tarea_id}.P{parte_num} - fin_parte={fin_parte}, minutos_por_dia={minutos_por_dia}, modulo={fin_parte % minutos_por_dia}")
                    if fin_parte > 0 and fin_parte % minutos_por_dia == 0:
                        fin_real = dt_time(18, 0)  # 18:00 del día actual
                        print(f"DEBUG: {tarea_id}.P{parte_num} - Usando 18:00")
                    else:
                        fin_real = minutos_a_hora_dia(fin_parte, minutos_por_dia)
                        print(f"DEBUG: {tarea_id}.P{parte_num} - Usando minutos_a_hora_dia: {fin_real}")
                    
                    id_tarea = f"{tarea_id}.P{parte_num}"
                    
                    programacion_data.append({
                        'tarea_id': id_tarea,
                        'nombre': f"{tarea_original['nombre']} (P{parte_num})",
                        'maquina_id': maquina_a_usar if isinstance(maquina_a_usar, str) and maquina_a_usar.startswith('M') else f"M01",
                        'operador_id': f"Op{int(str(tarea_prog.get('operador', 1)).replace('OP', '')):02d}",
                        'trabajo_id': tarea_original['trabajo'],
                        'trabajo_nombre': tarea_original['trabajo'],
                        'inicio_planificado': inicio_real.strftime('%H:%M'),
                        'fin_planificado': fin_real.strftime('%H:%M'),
                        'duracion_planificada': duracion_parte,
                        'es_dividida': True,
                        'parte_numero': parte_num,
                        'dia': dia_nombre[:3]
                    })
                    
                    tiempo_restante -= duracion_parte
                    tiempo_actual = fin_parte
                    parte_num += 1
            else:
                # Tarea que cabe en un solo día
                dia_numero = int(inicio_min // minutos_por_dia)
                dia_nombre = dias_semana[dia_numero] if dia_numero < len(dias_semana) else 'N/A'
                inicio_real = minutos_a_hora_dia(inicio_min, minutos_por_dia)
                fin_real = minutos_a_hora_dia(fin_min, minutos_por_dia)
                
                programacion_data.append({
                    'tarea_id': tarea_id,
                    'nombre': tarea_original['nombre'],
                    'maquina_id': maquina_a_usar if isinstance(maquina_a_usar, str) and maquina_a_usar.startswith('M') else f"M01",
                    'operador_id': f"Op{int(str(tarea_prog.get('operador', 1)).replace('OP', '')):02d}",
                    'trabajo_id': tarea_original['trabajo'],
                    'trabajo_nombre': tarea_original['trabajo'],
                    'inicio_planificado': inicio_real.strftime('%H:%M'),
                    'fin_planificado': fin_real.strftime('%H:%M'),
                    'duracion_planificada': duracion_asignada,
                    'es_dividida': False,
                    'parte_numero': 1,
                    'dia': dia_nombre[:3]
                })
    
    return programacion_data

# Función para procesar datos RAW de la base de datos para PDF
def procesar_tareas_desde_bd(tareas_raw, configuracion=None):
    """Procesar datos RAW de la base de datos para generar datos formateados para PDF"""
    if not tareas_raw:
        return []
    
    programacion_data = []
    # IMPORTANTE: Usar los días laborales de la configuración guardada, NO de session_state
    # Si no se pasa configuración, usar session_state como fallback
    if configuracion:
        dias_laborales = configuracion.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
        minutos_por_dia = configuracion.get('minutos_por_dia_laboral', 540)
    else:
        dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
        minutos_por_dia = st.session_state.get('minutos_por_dia_laboral', 540)
    
    for tarea_raw in tareas_raw:
        # Extraer datos de la tarea RAW
        tarea_id = tarea_raw.get('tarea_id', 'N/A')
        nombre = tarea_raw.get('nombre', 'N/A')
        maquina = tarea_raw.get('maquina_id', 'N/A')
        operador = tarea_raw.get('operador_id', 'N/A')
        trabajo = tarea_raw.get('trabajo_id', 'N/A')
        
        # PRIORIDAD 1: Si ya existen datos procesados del UI (inicio_hora, fin_hora, dia_nombre), usarlos directamente
        if tarea_raw.get('inicio_hora') and tarea_raw.get('fin_hora') and tarea_raw.get('dia_nombre'):
            # Usar los datos procesados que se guardaron con la programación
            inicio_hora_str = tarea_raw.get('inicio_hora')
            fin_hora_str = tarea_raw.get('fin_hora')
            dia_nombre = tarea_raw.get('dia_nombre')
            # Normalizar dia_nombre a 3 caracteres si es necesario
            if len(dia_nombre) > 3:
                dia_nombre = dia_nombre[:3]
            
            # Convertir de string HH:MM a time
            from datetime import time as dt_time
            try:
                h_inicio, m_inicio = map(int, inicio_hora_str.split(':'))
                inicio_real = dt_time(h_inicio, m_inicio)
            except:
                inicio_real = dt_time(8, 0)
            
            try:
                h_fin, m_fin = map(int, fin_hora_str.split(':'))
                fin_real = dt_time(h_fin, m_fin)
            except:
                fin_real = dt_time(18, 0)
            
            duracion = tarea_raw.get('duracion_planificada', 0)
        else:
            # PRIORIDAD 2: Calcular desde datos RAW (compatibilidad con BD antigua)
            inicio_min = tarea_raw.get('inicio_planificado', 0)
            fin_min = tarea_raw.get('fin_planificado', 0)
            duracion = fin_min - inicio_min
            
            # Calcular día
            dia_numero = int(inicio_min // minutos_por_dia)
            dia_nombre_completo = dias_laborales[dia_numero] if dia_numero < len(dias_laborales) else 'N/A'
            dia_nombre = dia_nombre_completo[:3] if dia_nombre_completo != 'N/A' else 'N/A'  # Solo 3 caracteres
            
            # Convertir minutos a HH:MM
            inicio_real = minutos_a_hora_dia(inicio_min, minutos_por_dia)
            
            # CASO ESPECIAL: Si fin_min es exactamente el inicio del día siguiente,
            # significa que la tarea termina al final del día actual (18:00)
            from datetime import time as dt_time
            if fin_min > 0 and fin_min % minutos_por_dia == 0:
                fin_real = dt_time(18, 0)  # 18:00 del día actual
            else:
                fin_real = minutos_a_hora_dia(fin_min, minutos_por_dia)
        
        # Formatear IDs
        if maquina == 'N/A' or not maquina:
            maquina_id = 'M00'
        elif maquina.startswith('M'):
            maquina_id = f"M{int(maquina[1:]):02d}"
        else:
            maquina_id = f"M{int(maquina[1:]):02d}"
        
        if operador == 'N/A' or not operador:
            operador_id = 'Op00'
        elif str(operador).startswith('OP') or str(operador).startswith('Op'):
            # Ya tiene el formato Op02, solo normalizamos
            operador_id = str(operador).replace('OP', 'Op')
        else:
            # Es un número, agregarle el prefijo
            operador_id = f"Op{int(operador):02d}"
        
        # Extraer solo la letra del trabajo (ej: "Trabajo A" -> "A")
        if trabajo == 'N/A' or not trabajo:
            trabajo_id = 'N/A'
        elif trabajo.startswith('Trabajo '):
            trabajo_id = trabajo.replace('Trabajo ', '')
        else:
            trabajo_id = trabajo
        
        programacion_data.append({
            'tarea_id': tarea_id,
            'nombre': nombre,
            'maquina_id': maquina_id,
            'operador_id': operador_id,
            'trabajo_id': trabajo_id,
            'trabajo_nombre': trabajo_id,
            'inicio_planificado': inicio_real.strftime('%H:%M'),
            'fin_planificado': fin_real.strftime('%H:%M'),
            'duracion_planificada': duracion,
            'es_dividida': False,
            'parte_numero': 1,
            'dia': dia_nombre[:3],
            # Campos adicionales para Excel/CSV
            'inicio_hora': inicio_real.strftime('%H:%M'),
            'fin_hora': fin_real.strftime('%H:%M'),
            'dia_nombre': dia_nombre[:3]
        })
    
    return programacion_data

# Funciones para importar/exportar desde Excel
def crear_plantilla_excel():
    """Crear plantilla Excel para importar trabajos"""
    # Crear DataFrame de ejemplo con la estructura esperada
    ejemplo_data = {
        'Trabajo': ['Trabajo A', 'Trabajo A', 'Trabajo A', 'Trabajo B', 'Trabajo B', 'Trabajo C'],
        'ID_Tarea': ['A1', 'A2', 'A3', 'B1', 'B2', 'C1'],
        'Nombre_Tarea': ['Corte de Material', 'Soldadura', 'Pintura', 'Preparación', 'Procesamiento', 'Corte Especial'],
        'Duracion_Minutos': [360, 540, 270, 240, 600, 300],
        'Tiempo_Setup_Minutos': [15, 30, 20, 10, 25, 15],
        'Maquina': ['M1', 'M2', 'M3', 'M1', 'M2', 'M1'],
        'Operador': ['Juan', 'María', 'Pedro', 'Juan', 'María', 'Pedro']
    }
    
    df = pd.DataFrame(ejemplo_data)
    
    # Convertir a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Trabajos', index=False)
        
        # Agregar hoja de instrucciones
        instrucciones = pd.DataFrame({
            'INSTRUCCIONES': [
                '1. Complete la hoja "Trabajos" con sus datos',
                '2. Columnas obligatorias:',
                '   - Trabajo: Nombre del trabajo (agrupa tareas)',
                '   - ID_Tarea: Identificador único de la tarea',
                '   - Nombre_Tarea: Descripción de la tarea',
                '   - Duracion_Minutos: Duración en minutos (número entero)',
                '   - Tiempo_Setup_Minutos: Tiempo de preparación en minutos (número entero, puede ser 0)',
                '   - Maquina: Máquina asignada (M1, M2, M3, etc.)',
                '3. Columna opcional:',
                '   - Operador: Nombre del operador asignado',
                '4. Las tareas del mismo trabajo se ejecutarán en orden',
                '5. El tiempo de setup se suma automáticamente a la duración',
                '6. Guarde el archivo y cárguelo en la aplicación',
                '',
                'EJEMPLO:',
                'Trabajo A con 3 tareas (Corte, Soldadura, Pintura)',
                'Trabajo B con 2 tareas (Preparación, Procesamiento)',
                '',
                'NOTAS:',
                '- No cambie los nombres de las columnas',
                '- Asegúrese de que las máquinas existan',
                '- Las duraciones y tiempos de setup deben ser números positivos',
                '- Los IDs de tarea deben ser únicos'
            ]
        })
        instrucciones.to_excel(writer, sheet_name='Instrucciones', index=False)
    
    output.seek(0)
    return output

def importar_trabajos_desde_excel(archivo_excel):
    """Importar trabajos desde un archivo Excel"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(archivo_excel, sheet_name='Trabajos')
        
        # Validar columnas obligatorias
        columnas_requeridas = ['Trabajo', 'ID_Tarea', 'Nombre_Tarea', 'Duracion_Minutos', 'Tiempo_Setup_Minutos', 'Maquina']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            return None, f"❌ Faltan columnas obligatorias: {', '.join(columnas_faltantes)}"
        
        # Validar datos
        if df.empty:
            return None, "❌ El archivo Excel está vacío"
        
        # Validar que las duraciones sean números positivos
        if not all(df['Duracion_Minutos'] > 0):
            return None, "❌ Todas las duraciones deben ser números positivos"
        
        # Convertir DataFrame a estructura de trabajos
        trabajos = {}
        errores = []
        
        for trabajo_nombre in df['Trabajo'].unique():
            tareas_trabajo = df[df['Trabajo'] == trabajo_nombre]
            tareas_lista = []
            
            for idx, row in tareas_trabajo.iterrows():
                try:
                    tarea = {
                        'id': str(row['ID_Tarea']),
                        'nombre': str(row['Nombre_Tarea']),
                        'duracion': int(row['Duracion_Minutos']),
                        'tiempo_setup': int(row['Tiempo_Setup_Minutos']) if pd.notna(row['Tiempo_Setup_Minutos']) else 0,
                        'maquina': str(row['Maquina'])
                    }
                    
                    # Agregar operador si existe
                    if 'Operador' in row and pd.notna(row['Operador']):
                        tarea['operador'] = str(row['Operador'])
                    
                    tareas_lista.append(tarea)
                except Exception as e:
                    errores.append(f"Error en fila {idx+2}: {str(e)}")
            
            if tareas_lista:
                trabajos[trabajo_nombre] = tareas_lista
        
        if errores:
            return trabajos, f"⚠️ Trabajos importados con advertencias:\n" + "\n".join(errores)
        
        return trabajos, f"✅ {len(trabajos)} trabajos importados exitosamente con {len(df)} tareas totales"
        
    except Exception as e:
        return None, f"❌ Error al leer el archivo Excel: {str(e)}"

def exportar_trabajos_a_excel(trabajos):
    """Exportar trabajos actuales a Excel"""
    try:
        # Convertir trabajos a DataFrame
        data = []
        for trabajo_nombre, trabajo_data in trabajos.items():
            # Compatibilidad con ambos formatos
            if isinstance(trabajo_data, dict):
                tareas = trabajo_data.get('tareas', [])
            else:
                tareas = trabajo_data
                
            for tarea in tareas:
                fila = {
                    'Trabajo': trabajo_nombre,
                    'ID_Tarea': tarea['id'],
                    'Nombre_Tarea': tarea['nombre'],
                    'Duracion_Minutos': tarea['duracion'],
                    'Tiempo_Setup_Minutos': tarea.get('tiempo_setup', 0),
                    'Maquina': tarea['maquina'],
                    'Operador': tarea.get('operador', '')
                }
                data.append(fila)
        
        df = pd.DataFrame(data)
        
        # Convertir a Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Trabajos', index=False)
        
        output.seek(0)
        return output
        
    except Exception as e:
        st.error(f"❌ Error al exportar: {str(e)}")
        return None

# Configuración de la página
st.set_page_config(
    page_title="Optimización de Producción Semanal",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialización BD
# Inicializar base de datos al cargar la aplicación
if 'bd_inicializada' not in st.session_state:
    try:
        inicializar_bd_si_necesario()
        st.session_state.bd_inicializada = True
    except Exception as e:
        st.error(f"Error inicializando base de datos: {e}")
        st.session_state.bd_inicializada = False

# Funciones auxiliares para múltiples trabajos
def crear_trabajos_ejemplo(num_maquinas=3):
    """Crear trabajos de ejemplo para la aplicación semanal"""
    # Generar máquinas disponibles dinámicamente
    maquinas_disponibles = [f"M{i+1}" for i in range(num_maquinas)]
    
    trabajos = {
        "Trabajo A": [
            {"id": "A1", "nombre": "Corte de Material", "duracion": 360, "tiempo_setup": 15, "maquina": maquinas_disponibles[0]},
            {"id": "A2", "nombre": "Soldadura", "duracion": 540, "tiempo_setup": 30, "maquina": maquinas_disponibles[min(1, len(maquinas_disponibles)-1)]},
            {"id": "A3", "nombre": "Pintura", "duracion": 270, "tiempo_setup": 20, "maquina": maquinas_disponibles[min(2, len(maquinas_disponibles)-1)]},
            {"id": "A4", "nombre": "Ensamblaje", "duracion": 450, "tiempo_setup": 25, "maquina": maquinas_disponibles[0]},
        ],
        "Trabajo B": [
            {"id": "B1", "nombre": "Preparación", "duracion": 240, "tiempo_setup": 10, "maquina": maquinas_disponibles[0]},
            {"id": "B2", "nombre": "Procesamiento", "duracion": 600, "tiempo_setup": 35, "maquina": maquinas_disponibles[min(1, len(maquinas_disponibles)-1)]},
            {"id": "B3", "nombre": "Control Calidad", "duracion": 180, "tiempo_setup": 15, "maquina": maquinas_disponibles[min(2, len(maquinas_disponibles)-1)]},
        ],
        "Trabajo C": [
            {"id": "C1", "nombre": "Corte Especial", "duracion": 300, "tiempo_setup": 20, "maquina": maquinas_disponibles[0]},
            {"id": "C2", "nombre": "Acabado", "duracion": 240, "tiempo_setup": 15, "maquina": maquinas_disponibles[min(1, len(maquinas_disponibles)-1)]},
            {"id": "C3", "nombre": "Empaque", "duracion": 120, "tiempo_setup": 10, "maquina": maquinas_disponibles[min(2, len(maquinas_disponibles)-1)]},
        ]
    }
    return trabajos

def convertir_trabajos_a_dataframe(trabajos):
    """Convertir diccionario de trabajos a DataFrame para compatibilidad"""
    todas_las_tareas = []
    for trabajo_nombre, tareas in trabajos.items():
        for tarea in tareas:
            # Verificar que tarea sea un diccionario
            if not isinstance(tarea, dict):
                continue  # Saltar si tarea no es un diccionario válido
                
            tarea_con_trabajo = tarea.copy()
            tarea_con_trabajo["trabajo"] = trabajo_nombre
            todas_las_tareas.append(tarea_con_trabajo)
    
    return pd.DataFrame(todas_las_tareas)

def crear_datos_ejemplo(num_maquinas=3):
    """Crear datos de ejemplo para compatibilidad con versión original"""
    trabajos = crear_trabajos_ejemplo(num_maquinas)
    return convertir_trabajos_a_dataframe(trabajos)

def validar_tarea(tarea):
    """Validar que una tarea tenga todos los campos requeridos"""
    campos_requeridos = ['id', 'nombre', 'duracion', 'maquina']
    for campo in campos_requeridos:
        if campo not in tarea or pd.isna(tarea[campo]) or tarea[campo] == '':
            return False, f"Campo '{campo}' es requerido"
    
    # Validar tipos de datos
    try:
        if not isinstance(tarea['duracion'], (int, float)) or tarea['duracion'] <= 0:
            return False, "Duración debe ser un número positivo"
    except:
        return False, "Duración debe ser un número válido"
    
    return True, "OK"

def limpiar_dataframe(df):
    """Limpiar y validar un DataFrame de tareas"""
    if df.empty:
        return df
    
    # Eliminar filas completamente vacías
    df = df.dropna(how='all')
    
    # Rellenar valores faltantes con valores por defecto
    df['id'] = df['id'].fillna('')
    df['nombre'] = df['nombre'].fillna('')
    df['duracion'] = df['duracion'].fillna(0)
    df['maquina'] = df['maquina'].fillna('M1')
    
    # Convertir tipos de datos
    df['duracion'] = pd.to_numeric(df['duracion'], errors='coerce').fillna(0)
    
    # Asegurar que duración sea positiva
    df['duracion'] = df['duracion'].apply(lambda x: max(1, int(x)))
    
    return df

def crear_gantt_semanal(tareas_df, resultado=None, horas_efectivas=10):
    """Crear diagrama de Gantt semanal con múltiples trabajos"""
    if tareas_df.empty:
        return None
    
    # Mapeo de días a números para ordenamiento y cálculo de posición
    dias_orden = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
    
    # Crear datos para el Gantt semanal
    gantt_data = []
    
    # Si hay resultado de optimización, usar los tiempos reales y días calculados
    if resultado and resultado.get("solucion") and resultado["solucion"].get("programacion"):
        for tarea_prog in resultado["solucion"]["programacion"]:
            tarea_id = tarea_prog["tarea_id"]
            tarea_indice = tarea_prog.get('tarea_indice', 0)  # Usar índice numérico
            if tarea_indice < len(tareas_df):
                tarea_original = tareas_df.iloc[tarea_indice]
                
                # Usar máquina de la solución si está disponible (asignación flexible)
                maquina_a_usar = tarea_prog.get('maquina', tarea_original['maquina'])
                
                # Obtener tiempos absolutos del optimizador
                inicio_min = tarea_prog["inicio"]
                fin_min = tarea_prog["fin"]
                
                # Usar DIRECTAMENTE el día del optimizador
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                
                # El optimizador devuelve el día directamente
                if 'dia' in tarea_prog and tarea_prog['dia'] != 'N/A':
                    dia_asignado = tarea_prog['dia']
                    dia_num = dias_orden.get(dia_asignado, 0)
                else:
                    # Si no hay día del optimizador, calcular basándose en tiempo consecutivo
                    # El optimizador usa días consecutivos de 16 horas cada uno
                    dia_consecutivo = inicio_min // (16 * 60)  # 16 horas por día laboral
                    
                    # Obtener días laborales de la sesión
                    dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
                    
                    if dia_consecutivo < len(dias_laborales):
                        dia_asignado = dias_laborales[dia_consecutivo]
                        dia_num = dias_orden.get(dia_asignado, 0)
                    else:
                        dia_asignado = "Lunes"  # Fallback
                
                # Calcular hora dentro del día laboral (horas efectivas configuradas)
                horas_por_dia_laboral = horas_efectivas
                minutos_por_dia_laboral = int(horas_por_dia_laboral * 60)
                
                # Calcular posición dentro del día específico
                # El optimizador devuelve tiempo absoluto desde el inicio de la semana
                # dia_asignado es un NÚMERO (0-6) que representa el día de la semana completa
                
                dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
                horas_por_dia_laboral = horas_efectivas
                minutos_por_dia_laboral = int(horas_por_dia_laboral * 60)
                
                # CLAVE: El optimizador usa tiempo CONSECUTIVO por días laborales
                # Día laboral 0: 0-960 min, Día laboral 1: 960-1920 min, etc.
                
                # 1. Calcular qué día laboral consecutivo corresponde al tiempo
                dia_laboral_consecutivo = inicio_min // minutos_por_dia_laboral
                
                # 2. Obtener el día real de la semana de ese día laboral
                if dia_laboral_consecutivo < len(dias_laborales):
                    dia_nombre = dias_laborales[dia_laboral_consecutivo]
                    # USAR el número del día en la semana completa (0-6) para mostrar días vacíos
                    dia_num_semana = dias_semana_completa.index(dia_nombre)
                else:
                    # Fallback
                    dia_nombre = 'Lunes'
                    dia_num_semana = 0
                
                # 3. Calcular tiempo relativo dentro del día laboral (en minutos)
                inicio_min_dia = inicio_min % minutos_por_dia_laboral
                duracion_minutos = fin_min - inicio_min
                
                # VERIFICAR si la tarea excede las horas del día
                tiempo_restante_dia = minutos_por_dia_laboral - inicio_min_dia
                if duracion_minutos > tiempo_restante_dia:
                    # La tarea se extiende más allá del día - DIVIDIR EN DOS PARTES
                    # Parte 1: del inicio hasta el final del día actual
                    duracion_parte1 = tiempo_restante_dia
                    duracion_parte2 = duracion_minutos - tiempo_restante_dia
                    
                    # Añadir primera parte
                    inicio_hora_dia = inicio_min_dia / 60.0
                    duracion_horas_parte1 = duracion_parte1 / 60.0
                    inicio_semanal_parte1 = dia_num_semana * horas_por_dia_laboral + inicio_hora_dia
                    fin_semanal_parte1 = inicio_semanal_parte1 + duracion_horas_parte1
                    
                    gantt_data.append({
                        'Tarea': f"{tarea_original['id']} - {tarea_original['nombre']} (Parte 1)",
                        'Trabajo': tarea_original.get('trabajo', 'Sin trabajo'),
                        'Máquina': maquina_a_usar,
                        'Día': dia_nombre,
                        'Inicio': inicio_semanal_parte1,
                        'Fin': fin_semanal_parte1,
                        'Duración': duracion_parte1 + (tarea_original['tiempo_setup'] if duracion_parte1 == duracion_minutos else 0)
                    })
                    
                    # Buscar el siguiente día laboral
                    siguiente_dia_laboral_idx = dia_laboral_consecutivo + 1
                    if siguiente_dia_laboral_idx < len(dias_laborales):
                        siguiente_dia_nombre = dias_laborales[siguiente_dia_laboral_idx]
                        siguiente_dia_num_semana = dias_semana_completa.index(siguiente_dia_nombre)
                        
                        # Añadir segunda parte al inicio del siguiente día laboral
                        duracion_horas_parte2 = duracion_parte2 / 60.0
                        inicio_semanal_parte2 = siguiente_dia_num_semana * horas_por_dia_laboral
                        fin_semanal_parte2 = inicio_semanal_parte2 + duracion_horas_parte2
                        
                        gantt_data.append({
                            'Tarea': f"{tarea_original['id']} - {tarea_original['nombre']} (Parte 2)",
                            'Trabajo': tarea_original.get('trabajo', 'Sin trabajo'),
                            'Máquina': maquina_a_usar,
                            'Día': siguiente_dia_nombre,
                            'Inicio': inicio_semanal_parte2,
                            'Fin': fin_semanal_parte2,
                            'Duración': duracion_parte2
                        })
                    
                    # Continuar con la siguiente tarea (no añadir esta tarea completa)
                    continue
                
                # Si la tarea NO excede el día, procesarla normalmente
                inicio_hora_dia = inicio_min_dia / 60.0
                duracion_horas = duracion_minutos / 60.0
                
                # USAR el día REAL de la semana (0-6) para el posicionamiento
                # Esto hace que los días no laborales aparezcan vacíos
                inicio_semanal = dia_num_semana * horas_por_dia_laboral + inicio_hora_dia
                fin_semanal = inicio_semanal + duracion_horas
                
                gantt_data.append({
                    'Tarea': f"{tarea_original['id']} - {tarea_original['nombre']}",
                    'Trabajo': tarea_original.get('trabajo', 'Sin trabajo'),
                    'Máquina': maquina_a_usar,
                    'Día': dia_nombre,
                    'Inicio': inicio_semanal,
                    'Fin': fin_semanal,
                    'Duración': tarea_original['duracion'] + tarea_original['tiempo_setup']
                })
    else:
        # Simulación para vista previa sin optimización - distribución secuencial
        tiempo_acumulado_por_maquina = {}
        dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
        dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        horas_por_dia_laboral = horas_efectivas
        
        for i, tarea in tareas_df.iterrows():
            maquina = tarea['maquina']
            
            # Inicializar tiempo por máquina si no existe
            if maquina not in tiempo_acumulado_por_maquina:
                tiempo_acumulado_por_maquina[maquina] = 0  # Empezar al inicio del primer día laboral
            
            # Calcular día laboral y hora de inicio
            tiempo_acumulado = tiempo_acumulado_por_maquina[maquina]
            dia_num_laboral = int(tiempo_acumulado // horas_por_dia_laboral)
            hora_en_dia = tiempo_acumulado % horas_por_dia_laboral
            
            # Si se pasa de los días laborales, empezar de nuevo
            if dia_num_laboral >= len(dias_laborales):
                dia_num_laboral = dia_num_laboral % len(dias_laborales)
            
            # Obtener el día laboral asignado
            dia_asignado = dias_laborales[dia_num_laboral]
            # Obtener número del día en la semana completa (para mostrar días vacíos)
            dia_num_semana = dias_semana_completa.index(dia_asignado)
            
            # Trabajar en MINUTOS para precisión
            hora_en_dia_min = hora_en_dia * 60  # Convertir horas a minutos
            duracion_minutos = tarea['duracion']
            
            # USAR el día REAL de la semana (0-6) para el posicionamiento
            inicio_semanal_min = dia_num_semana * (horas_por_dia_laboral * 60) + hora_en_dia_min
            fin_semanal_min = inicio_semanal_min + duracion_minutos
            
            # Convertir a horas para el gráfico
            inicio_semanal = inicio_semanal_min / 60.0
            fin_semanal = fin_semanal_min / 60.0
            duracion_horas = duracion_minutos / 60.0
            
            gantt_data.append({
                'Tarea': f"{tarea['id']} - {tarea['nombre']}",
                'Trabajo': tarea.get('trabajo', 'Sin trabajo'),
                'Máquina': tarea['maquina'],
                'Día': dia_asignado,
                'Inicio': inicio_semanal,
                'Fin': fin_semanal,
                'Duración': tarea['duracion']
            })
            
            # Actualizar tiempo acumulado para la máquina
            tiempo_acumulado_por_maquina[maquina] = tiempo_acumulado + duracion_horas + 0.5  # 30 min de buffer
    
    return gantt_data

def mostrar_gantt_por_maquina(tareas_df, resultado, horas_efectivas=10):
    """Mostrar diagrama de Gantt separado por máquina"""
    st.subheader("⚙️ Diagrama de Gantt por Máquina - Distribución de Carga")
    
    # Crear datos del Gantt
    gantt_data = crear_gantt_semanal(tareas_df, resultado, horas_efectivas)
    
    if not gantt_data:
        st.info("ℹ️ No hay datos para mostrar")
        return
    
    # Agrupar por máquina
    maquinas = {}
    for row in gantt_data:
        maquina = row['Máquina']
        if maquina not in maquinas:
            maquinas[maquina] = []
        maquinas[maquina].append(row)
    
    # Colores por trabajo
    colores_trabajo = px.colors.qualitative.Set3
    trabajos_unicos = list(set([item['Trabajo'] for item in gantt_data]))
    color_map = {trabajo: colores_trabajo[i % len(colores_trabajo)] for i, trabajo in enumerate(trabajos_unicos)}
    
    # Ordenar tareas por inicio en cada máquina
    for maquina in maquinas:
        maquinas[maquina].sort(key=lambda x: x['Inicio'])
    
    # Crear el gráfico principal con todas las máquinas en un solo gráfico
    fig = go.Figure()
    
    maquinas_ordenadas = sorted(maquinas.keys())
    
    # Para cada máquina, agregar segmentos de barra continua
    for maquina in maquinas_ordenadas:
        tareas_maquina = maquinas[maquina]
        
        for row in tareas_maquina:
            trabajo = row['Trabajo']
            color = color_map.get(trabajo, '#1f77b4')
            duracion = row['Fin'] - row['Inicio']
            
            fig.add_trace(go.Bar(
                name=trabajo,
                x=[duracion],
                y=[maquina],
                base=[row['Inicio']],
                orientation='h',
                marker_color=color,
                marker_line_color='white',
                marker_line_width=0.5,
                text=f"{row['Duración']} min",
                textposition='inside',
                hovertemplate=f"<b>{row['Tarea']}</b><br>" +
                             f"Trabajo: {trabajo}<br>" +
                             f"Máquina: {maquina}<br>" +
                             f"Día: {row['Día']}<br>" +
                             f"Duración: {row['Duración']} min<br>" +
                             f"<extra></extra>",
                showlegend=trabajo not in [trace.name for trace in fig.data]
            ))
    
    # Configurar layout
    fig.update_layout(
        title="📅 Gantt por Máquina - Distribución de Carga",
        xaxis_title="Tiempo (Horas)",
        yaxis_title="Máquinas",
        yaxis=dict(
            categoryorder='array',
            categoryarray=maquinas_ordenadas
        ),
        height=max(400, len(maquinas_ordenadas) * 80),
        barmode='stack',
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=80, r=150, t=50, b=50)
    )
    
    # Configurar el eje X para mostrar TODA LA SEMANA (7 días) - igual que el otro Gantt
    dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
    horas_por_dia_laboral = horas_efectivas
    
    # Calcular ticks para TODOS los días de la semana (7 días)
    tickvals = [i * horas_por_dia_laboral + horas_por_dia_laboral/2 for i in range(7)]
    
    # Preparar etiquetas: días laborales en negrita, no laborales en cursiva
    ticktext = []
    for dia in dias_semana_completa:
        if dia in dias_laborales:
            ticktext.append(f"<b>{dia}</b>")  # Días laborales en negrita
        else:
            ticktext.append(f"<i>{dia}</i>")  # Días no laborales en cursiva
    
    # Mostrar toda la semana
    fig.update_xaxes(
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext,
        range=[0, 7 * horas_por_dia_laboral]  # Toda la semana
    )
    
    # Agregar líneas verticales para separar los días
    for i in range(1, 7):
        # Líneas más marcadas para separadores entre días laborales, más tenues para días no laborales
        dia_actual = dias_semana_completa[i]
        dia_anterior = dias_semana_completa[i-1]
        if dia_actual in dias_laborales or dia_anterior in dias_laborales:
            fig.add_vline(x=i * horas_por_dia_laboral, line_dash="dash", line_color="gray", opacity=0.5)
        else:
            fig.add_vline(x=i * horas_por_dia_laboral, line_dash="dot", line_color="lightgray", opacity=0.2)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Resumen de carga por máquina
    st.markdown("### Resumen por Máquina")
    for maquina in maquinas_ordenadas:
        tareas_maquina = maquinas[maquina]
        total_minutos = sum([row['Duración'] for row in tareas_maquina])
        total_horas = total_minutos / 60
        st.caption(f"**{maquina}:** {total_horas:.1f} horas ({total_minutos} min) en {len(tareas_maquina)} tareas")

def mostrar_diagrama_gantt(tareas_df, resultado, key_suffix="", horas_efectivas=10):
    """Mostrar diagrama de Gantt semanal de la programación"""
    st.subheader("📅 Diagrama de Gantt Semanal - Programación de Producción")
    
    # Crear datos del Gantt semanal
    gantt_data = crear_gantt_semanal(tareas_df, resultado, horas_efectivas)
    
    if not gantt_data:
        st.info("ℹ️ No hay datos para mostrar en el diagrama de Gantt")
        return
    
    # Crear el gráfico de Gantt
    fig = go.Figure()
    
    # Colores por trabajo
    colores_trabajo = px.colors.qualitative.Set3
    trabajos_unicos = list(set([item['Trabajo'] for item in gantt_data]))
    color_map = {trabajo: colores_trabajo[i % len(colores_trabajo)] for i, trabajo in enumerate(trabajos_unicos)}
    
    # Agregar barras para cada tarea
    for i, row in enumerate(gantt_data):
        trabajo = row['Trabajo']
        color = color_map.get(trabajo, '#1f77b4')
        
        # Calcular duración para la barra
        duracion = row['Fin'] - row['Inicio']
        
        fig.add_trace(go.Bar(
            name=trabajo,
            x=[duracion],
            y=[f"{row['Máquina']} - {row['Tarea']}"],
            base=[row['Inicio']],
            orientation='h',
            marker_color=color,
            text=f"{row['Día']}<br>{row['Duración']} min",
            textposition='inside',
            hovertemplate=f"<b>{row['Tarea']}</b><br>" +
                         f"Trabajo: {trabajo}<br>" +
                         f"Máquina: {row['Máquina']}<br>" +
                         f"Día: {row['Día']}<br>" +
                         f"Duración: {row['Duración']} min<br>" +
                         f"<extra></extra>",
            showlegend=trabajo not in [trace.name for trace in fig.data]  # Evitar duplicados en leyenda
        ))
    
    # Configurar el layout del gráfico
    fig.update_layout(
        title="📅 Programación Semanal de Producción",
        xaxis_title="Tiempo (Horas de la Semana)",
        yaxis_title="Máquina - Tarea",
        height=max(400, len(gantt_data) * 30),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        margin=dict(l=200, r=120, t=50, b=50)
    )
    
    # Configurar el eje X para mostrar TODA LA SEMANA (7 días)
    dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
    horas_por_dia_laboral = horas_efectivas
    
    # Calcular ticks para TODOS los días de la semana (7 días)
    tickvals = [i * horas_por_dia_laboral + horas_por_dia_laboral/2 for i in range(7)]
    
    # Preparar etiquetas: días laborales en negrita, no laborales en cursiva
    ticktext = []
    for dia in dias_semana_completa:
        if dia in dias_laborales:
            ticktext.append(f"<b>{dia}</b>")  # Días laborales en negrita
        else:
            ticktext.append(f"<i>{dia}</i>")  # Días no laborales en cursiva
    
    # Mostrar toda la semana
    fig.update_xaxes(
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext,
        range=[0, 7 * horas_por_dia_laboral]  # Toda la semana
    )
    
    # Agregar líneas verticales para separar los días
    for i in range(1, 7):
        # Líneas más marcadas para separadores entre días laborales, más tenues para días no laborales
        dia_actual = dias_semana_completa[i]
        dia_anterior = dias_semana_completa[i-1]
        if dia_actual in dias_laborales or dia_anterior in dias_laborales:
            fig.add_vline(x=i * horas_por_dia_laboral, line_dash="dash", line_color="gray", opacity=0.5)
        else:
            fig.add_vline(x=i * horas_por_dia_laboral, line_dash="dot", line_color="lightgray", opacity=0.2)
    
    st.plotly_chart(fig, use_container_width=True, key=f"gantt_semanal_chart{key_suffix}")
    
    # Información adicional
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total de Tareas", len(gantt_data))
    with col2:
        trabajos_count = len(trabajos_unicos)
        st.metric("🔧 Trabajos", trabajos_count)
    with col3:
        maquinas_count = len(set([item['Máquina'] for item in gantt_data]))
        st.metric("⚙️ Máquinas", maquinas_count)
    

def descargar_reporte(resultado, tareas_df):
    """Generar y descargar reporte de optimización"""
    reporte = f"""
    REPORTE DE OPTIMIZACIÓN DE PRODUCCIÓN
    =====================================
    
    Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    RESULTADOS:
    - Estado: {resultado.get('status', 'N/A')}
    - Tiempo de resolución: {resultado.get('tiempo_resolucion', 0):.2f} segundos
    - Tiempo total de producción: {resultado.get('valor_objetivo', 0)} minutos
    
    TAREAS ORIGINALES:
    {tareas_df.to_string(index=False)}
    
    """
    
    # Agregar programación detallada si está disponible
    if resultado.get('solucion') and resultado['solucion'].get('programacion'):
        reporte += "\nPROGRAMACIÓN OPTIMIZADA:\n"
        for tarea_prog in resultado['solucion']['programacion']:
            reporte += f"- {tarea_prog}\n"
    
    # Convertir a bytes para descarga
    reporte_bytes = reporte.encode('utf-8')
    
    # Botón de descarga
    st.download_button(
        label="📥 Descargar Reporte TXT",
        data=reporte_bytes,
        file_name=f"reporte_optimizacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )

def guardar_configuracion(hora_inicio, hora_fin, dias_laborales, almuerzo_inicio, almuerzo_fin, 
                          num_maquinas, num_operadores, tiempo_maximo, objetivo, 
                          considerar_setup):
    """Guardar configuración en un archivo JSON"""
    config = {
        "horario_trabajo": {
            "inicio": hora_inicio.strftime("%H:%M"),
            "fin": hora_fin.strftime("%H:%M"),
            "dias_laborales": dias_laborales,
            "descanso_almuerzo": {
                "inicio": almuerzo_inicio.strftime("%H:%M"),
                "fin": almuerzo_fin.strftime("%H:%M")
            }
        },
        "recursos": {
            "num_maquinas": num_maquinas,
            "num_operadores": num_operadores
        },
        "parametros_optimizacion": {
            "tiempo_maximo_resolucion": tiempo_maximo,
            "objetivo": objetivo,
            "restricciones": {
                "considerar_setup": considerar_setup
            }
        }
    }
    
    return json.dumps(config, indent=2, ensure_ascii=False)

def cargar_configuracion_default():
    """Cargar configuración por defecto"""
    return {
        "horario_trabajo": {
            "inicio": "08:00",
            "fin": "18:00",
            "dias_laborales": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
            "descanso_almuerzo": {
                "inicio": "12:00",
                "fin": "13:00"
            }
        },
        "recursos": {
            "num_maquinas": 3,
            "num_operadores": 3
        },
        "parametros_optimizacion": {
            "tiempo_maximo_resolucion": 30,
            "objetivo": "Minimizar tiempo total",
            "restricciones": {
                "considerar_setup": True
            }
        }
    }

# Inicialización de session state para múltiples trabajos
if "trabajos" not in st.session_state:
    st.session_state.trabajos = crear_trabajos_ejemplo()
if 'tareas_df' not in st.session_state:
    st.session_state.tareas_df = crear_datos_ejemplo()
if 'editar_tareas' not in st.session_state:
    st.session_state.editar_tareas = False
if 'resultado_optimizacion' not in st.session_state:
    st.session_state.resultado_optimizacion = None

# Título principal
st.title("🏭 Optimizador de Programación de Producción SEMANAL")
st.markdown("Utiliza Google OR-Tools para optimizar la programación semanal de múltiples trabajos de producción")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Selector de semana
    st.markdown("### 📅 Semana de Producción")
    col_sem1, col_sem2, col_sem3 = st.columns([2, 1, 1])
    
    with col_sem1:
        semana_actual = obtener_semana_actual()
        semana_programar = st.number_input(
            "Semana a programar",
            min_value=1,
            max_value=52,
            value=semana_actual,
            help="Selecciona la semana del año que deseas programar (1-52)"
        )
    
    with col_sem2:
        anio_programar = st.number_input(
            "Año",
            min_value=2024,
            max_value=2030,
            value=datetime.now().year,
            help="Año de la programación"
        )
    
    with col_sem3:
        st.metric("Semana Actual", semana_actual)
    
    st.info(f"📅 Programando: **Semana {semana_programar} del {anio_programar}**")
    st.markdown("---")
    
    # Pestañas de configuración
    tab_config, tab_data, tab_historial, tab_tracking, tab_dashboard = st.tabs(["⚙️ Sistema", "📁 Trabajos", "📚 Historial", "🏭 Tracking", "📊 Dashboard KPIs"])
    
    with tab_config:
        st.subheader("🏭 Parámetros del Sistema")
        
        # Horario de trabajo
        st.write("**🕐 Horario de Trabajo**")
        hora_inicio = st.time_input(
            "Hora de inicio", 
            value=datetime.strptime("08:00", "%H:%M").time(),
            help="Hora de inicio de la jornada laboral"
        )
        hora_fin = st.time_input(
            "Hora de fin", 
            value=datetime.strptime("18:00", "%H:%M").time(),
            help="Hora de fin de la jornada laboral"
        )
        
        # Días laborales
        st.write("**📅 Días Laborales**")
        dias_laborales = st.multiselect(
            "Seleccionar días laborales",
            ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
            default=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
            help="Días de la semana en que se trabaja"
        )
        
        # Mostrar orden final de días laborales
        if dias_laborales:
            # Ordenar días laborales cronológicamente
            dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            dias_ordenados = sorted(dias_laborales, key=lambda dia: dias_semana_completa.index(dia))
            
            # Crear cartel con el orden final
            dias_texto = " → ".join(dias_ordenados)
            st.info(f"📋 **Orden final de días laborales:** {dias_texto}")
            st.caption("💡 Los días se ordenan automáticamente cronológicamente para evitar programación 'torcida'")
        else:
            st.warning("⚠️ Selecciona al menos un día laboral para continuar")
        
        # Descanso para almuerzo
        st.write("**🍽️ Descanso Almuerzo**")
        almuerzo_inicio = st.time_input(
            "Inicio almuerzo",
            value=datetime.strptime("12:00", "%H:%M").time(),
            help="Hora de inicio del descanso para almuerzo"
        )
        almuerzo_fin = st.time_input(
            "Fin almuerzo",
            value=datetime.strptime("13:00", "%H:%M").time(),
            help="Hora de fin del descanso para almuerzo"
        )
        
        st.markdown("---")
        
        # Recursos disponibles
        st.write("**🔧 Recursos Disponibles**")
        num_maquinas = st.number_input(
            "Número de máquinas", 
            min_value=1, 
            max_value=20, 
            value=3,
            help="Cantidad total de máquinas disponibles"
        )
        num_operadores = st.number_input(
            "Número de operadores", 
            min_value=1, 
            max_value=20, 
            value=3,
            help="Cantidad total de operadores disponibles"
        )
        
        st.markdown("---")
        
        # Parámetros de optimización
        st.write("**🎯 Parámetros de Optimización**")
        tiempo_maximo = st.number_input(
            "Tiempo máximo de resolución (segundos)", 
            min_value=10, 
            max_value=300, 
            value=30,
            help="Tiempo límite para resolver el modelo de optimización"
        )
        
        objetivo = st.selectbox(
            "Objetivo de optimización",
            ["Minimizar tiempo total", "Maximizar utilización", "Minimizar costos", "Balanceado"],
            help="Criterio principal para la optimización"
        )
        
        # Restricciones adicionales
        st.write("**🔒 Restricciones**")
        considerar_setup = st.checkbox(
            "Considerar tiempo de setup", 
            value=True,
            help="Incluir tiempo de preparación entre tareas"
        )
        
        st.markdown("---")
        
        # Guardar y cargar configuración
        st.write("**💾 Gestión de Configuración**")
        
        # Botón para descargar configuración actual
        config_json = guardar_configuracion(
            hora_inicio, hora_fin, dias_laborales, almuerzo_inicio, almuerzo_fin,
            num_maquinas, num_operadores, tiempo_maximo, objetivo,
            considerar_setup
        )
        
        st.download_button(
            label="📥 Descargar Configuración",
            data=config_json,
            file_name=f"configuracion_produccion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
        
        # Botón para cargar configuración
        config_file = st.file_uploader(
            "Cargar configuración",
            type=['json'],
            help="Cargar archivo de configuración guardado previamente"
        )
        
        if config_file is not None:
            try:
                config_cargada = json.load(config_file)
                st.success("✅ Configuración cargada exitosamente!")
                st.info("ℹ️ Recarga la página para aplicar la nueva configuración")
            except Exception as e:
                st.error(f"❌ Error al cargar configuración: {e}")
    
    with tab_data:
        st.subheader("📁 Gestión de Trabajos")
        
        # Mostrar trabajos actuales
        st.write("**📋 Trabajos Actuales**")
        for trabajo_nombre, tareas in st.session_state.trabajos.items():
            titulo = f"🔧 {trabajo_nombre} ({len(tareas)} tareas)"
                
            with st.expander(titulo):
                if tareas:
                    df_trabajo = pd.DataFrame(tareas)
                    # Mostrar columnas relevantes
                    columnas_disponibles = ["id", "nombre", "duracion", "maquina"]
                    columnas_mostrar = [col for col in columnas_disponibles if col in df_trabajo.columns]
                    st.dataframe(df_trabajo[columnas_mostrar], use_container_width=True)
                    
                    # Botones para editar trabajo
                    col_edit1, col_edit2 = st.columns(2)
                    with col_edit1:
                        if st.button(f"✏️ Editar Tareas de {trabajo_nombre}", key=f"edit_{trabajo_nombre}"):
                            st.session_state[f"editing_{trabajo_nombre}"] = True
                            st.rerun()
                    
                    with col_edit2:
                        if st.button(f"🗑️ Eliminar {trabajo_nombre}", key=f"delete_{trabajo_nombre}"):
                            del st.session_state.trabajos[trabajo_nombre]
                            st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                            st.success(f"✅ Trabajo '{trabajo_nombre}' eliminado!")
                            st.rerun()
                    
                    # Mostrar editor de tareas si está activado
                    if st.session_state.get(f"editing_{trabajo_nombre}", False):
                        st.write("**✏️ Editar Tareas:**")
                        
                        # Mostrar cada tarea para editar
                        for i, tarea in enumerate(tareas):
                            st.write(f"**Tarea {i+1}: {tarea['id']} - {tarea['nombre']}**")
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                nuevo_nombre = st.text_input(
                                    "Nombre", 
                                    value=tarea['nombre'], 
                                    key=f"edit_nombre_{trabajo_nombre}_{i}"
                                )
                                nueva_duracion = st.number_input(
                                    "Duración (min)", 
                                    min_value=1, 
                                    value=int(tarea['duracion']), 
                                    key=f"edit_duracion_{trabajo_nombre}_{i}"
                                )
                            
                            with col2:
                                nuevo_setup = st.number_input(
                                    "Setup (min)", 
                                    min_value=0, 
                                    value=int(tarea.get('tiempo_setup', 0)), 
                                    key=f"edit_setup_{trabajo_nombre}_{i}",
                                    help="Tiempo de preparación"
                                )
                            
                            with col3:
                                ml_options = [f"M{j+1}" for j in range(num_maquinas)]
                                
                                # Detectar tipo de asignación actual
                                maquina_actual = tarea.get('maquina', 'M1')
                                if ',' in maquina_actual:
                                    tipo_actual = "Máquinas alternativas"
                                    maquinas_actuales = [m.strip() for m in maquina_actual.split(',')]
                                elif maquina_actual in ['M?', 'CUALQUIERA', '?']:
                                    tipo_actual = "Cualquier máquina"
                                    maquinas_actuales = []
                                else:
                                    tipo_actual = "Máquina específica"
                                    maquinas_actuales = [maquina_actual]
                                
                                edit_tipo_maquina = st.radio(
                                    "Asignación",
                                    ["Específica", "Alternativas", "Cualquiera"],
                                    index=0 if tipo_actual == "Máquina específica" else 1 if tipo_actual == "Máquinas alternativas" else 2,
                                    key=f"edit_tipo_{trabajo_nombre}_{i}",
                                    horizontal=True
                                )
                                
                                if edit_tipo_maquina == "Específica":
                                    try:
                                        idx = ml_options.index(maquinas_actuales[0]) if maquinas_actuales else 0
                                    except:
                                        idx = 0
                                    nueva_maquina = st.selectbox("Máquina", ml_options, index=idx, key=f"edit_machine_{trabajo_nombre}_{i}")
                                elif edit_tipo_maquina == "Alternativas":
                                    nuevas_maq = st.multiselect(
                                        "Máquinas",
                                        ml_options,
                                        default=maquinas_actuales if maquinas_actuales else [],
                                        key=f"edit_multimachine_{trabajo_nombre}_{i}"
                                    )
                                    nueva_maquina = ",".join(nuevas_maq) if nuevas_maq else (maquinas_actuales[0] if maquinas_actuales else "M1")
                                else:
                                    nueva_maquina = "M?"
                                
                                if st.button(f"💾 Guardar", key=f"save_task_{trabajo_nombre}_{i}"):
                                    # Actualizar tarea (compatible con nuevo formato)
                                    tarea_actualizada = {
                                        "id": tarea['id'],  # Mantener el ID original
                                        "nombre": nuevo_nombre,
                                        "duracion": nueva_duracion,
                                        "tiempo_setup": nuevo_setup,
                                        "maquina": nueva_maquina
                                    }
                                    
                                    # Actualizar en el formato correcto
                                    if isinstance(st.session_state.trabajos[trabajo_nombre], dict):
                                        st.session_state.trabajos[trabajo_nombre]['tareas'][i] = tarea_actualizada
                                    else:
                                        st.session_state.trabajos[trabajo_nombre][i] = tarea_actualizada
                                    
                                    st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                                    st.success(f"✅ Tarea {tarea['id']} actualizada!")
                                    st.rerun()
                                
                                if st.button(f"🗑️ Eliminar", key=f"delete_task_{trabajo_nombre}_{i}"):
                                    # Eliminar tarea (compatible con nuevo formato)
                                    if isinstance(st.session_state.trabajos[trabajo_nombre], dict):
                                        st.session_state.trabajos[trabajo_nombre]['tareas'].pop(i)
                                    else:
                                        st.session_state.trabajos[trabajo_nombre].pop(i)
                                    st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                                    st.success(f"✅ Tarea {tarea['id']} eliminada!")
                                    st.rerun()
                            
                            st.markdown("---")
                        
                        # Botón para finalizar edición
                        if st.button(f"✅ Finalizar Edición", key=f"finish_edit_{trabajo_nombre}"):
                            st.session_state[f"editing_{trabajo_nombre}"] = False
                            st.rerun()
                
                else:
                    st.info("ℹ️ Este trabajo no tiene tareas asignadas")
                    
                    # Botón para eliminar trabajo vacío
                    if st.button(f"🗑️ Eliminar {trabajo_nombre}", key=f"delete_empty_{trabajo_nombre}"):
                        del st.session_state.trabajos[trabajo_nombre]
                        st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                        st.success(f"✅ Trabajo '{trabajo_nombre}' eliminado!")
                        st.rerun()
        
        st.markdown("---")
        
        # Crear nuevo trabajo
        st.write("**➕ Crear Nuevo Trabajo**")
        with st.expander("Agregar nuevo trabajo"):
            nuevo_trabajo_nombre = st.text_input("Nombre del trabajo", value="", key="nuevo_trabajo_nombre")
            
            if st.button("➕ Crear Trabajo Vacío", key="crear_trabajo_btn"):
                if nuevo_trabajo_nombre:
                    st.session_state.trabajos[nuevo_trabajo_nombre] = []
                    st.success(f"✅ Trabajo '{nuevo_trabajo_nombre}' creado!")
                    st.rerun()
                else:
                    st.error("❌ Ingresa un nombre para el trabajo")
        
        st.markdown("---")
        
        # Agregar tarea a trabajo existente
        st.write("**✏️ Agregar Tarea a Trabajo**")
        if st.session_state.trabajos:
            trabajo_seleccionado = st.selectbox(
                "Seleccionar trabajo",
                list(st.session_state.trabajos.keys()),
                help="Trabajo al que agregar la nueva tarea",
                key="trabajo_seleccionado"
            )
            
            with st.expander("Agregar nueva tarea"):
                nueva_tarea_id = st.text_input("ID de la tarea", value="", key="nueva_tarea_id")
                nueva_tarea_nombre = st.text_input("Nombre de la tarea", value="", key="nueva_tarea_nombre")
                
                col_dur1, col_dur2 = st.columns(2)
                with col_dur1:
                    nueva_tarea_duracion = st.number_input("Duración (minutos)", min_value=1, value=60, key="nueva_tarea_duracion")
                with col_dur2:
                    nueva_tarea_setup = st.number_input("Setup (minutos)", min_value=0, value=0, key="nueva_tarea_setup", help="Tiempo de preparación/cambio")
                
                # Generar opciones de máquinas dinámicamente basándose en el número configurado
                opciones_maquinas = [f"M{i+1}" for i in range(num_maquinas)]
                opciones_maquinas.extend(["M?", "CUALQUIERA"])  # Agregar opciones flexibles
                
                nueva_tarea_maquina_tipo = st.radio(
                    "Asignación de máquina",
                    ["Máquina específica", "Máquinas alternativas", "Cualquier máquina"],
                    key="nueva_tarea_maquina_tipo",
                    help="Selecciona cómo asignar la máquina para esta tarea"
                )
                
                if nueva_tarea_maquina_tipo == "Máquina específica":
                    nueva_tarea_maquina = st.selectbox("Máquina", opciones_maquinas[:num_maquinas], key="nueva_tarea_maquina")
                elif nueva_tarea_maquina_tipo == "Máquinas alternativas":
                    nuevas_maquinas_permisibles = st.multiselect(
                        "Máquinas permitidas (puede usar cualquiera)",
                        opciones_maquinas[:num_maquinas],
                        key="nuevas_maquinas_permisibles",
                        help="Selecciona todas las máquinas que pueden ejecutar esta tarea"
                    )
                    if nuevas_maquinas_permisibles:
                        nueva_tarea_maquina = ",".join(nuevas_maquinas_permisibles)
                    else:
                        nueva_tarea_maquina = "M?"
                        st.warning("Selecciona al menos una máquina o cambiarás a 'Cualquier máquina'")
                else:  # Cualquier máquina
                    nueva_tarea_maquina = "M?"
                
                
                if st.button("➕ Agregar Tarea", key="agregar_tarea_btn"):
                    if nueva_tarea_nombre and nueva_tarea_id:
                        nueva_tarea = {
                            "id": nueva_tarea_id,
                            "nombre": nueva_tarea_nombre,
                            "duracion": nueva_tarea_duracion,
                            "tiempo_setup": nueva_tarea_setup,
                            "maquina": nueva_tarea_maquina
                        }
                        
                        # Validar la tarea (sin días laborales)
                        es_valida, mensaje = validar_tarea(nueva_tarea)
                        
                        if es_valida:
                            st.session_state.trabajos[trabajo_seleccionado].append(nueva_tarea)
                            # Actualizar también el DataFrame de tareas para compatibilidad
                            st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                            st.success("✅ Tarea agregada exitosamente!")
                            st.rerun()
                        else:
                            st.error(f"❌ Error en la tarea: {mensaje}")
                    else:
                        st.error("❌ Completa todos los campos")
        else:
            st.info("ℹ️ Primero crea un trabajo para poder agregar tareas")
        
        st.markdown("---")
        
        # Limpiar todos los trabajos
        col_clear1, col_clear2 = st.columns(2)
        with col_clear1:
            if st.button("🗑️ Limpiar Todos", key="limpiar_trabajos_btn"):
                st.session_state.trabajos = {}
                st.session_state.tareas_df = pd.DataFrame()
                # Limpiar también los estados de edición
                keys_to_remove = [key for key in st.session_state.keys() if key.startswith("editing_")]
                for key in keys_to_remove:
                    del st.session_state[key]
                st.success("✅ Todos los trabajos han sido eliminados!")
                st.rerun()
        
        with col_clear2:
            if st.button("🔄 Resetear a Ejemplos", key="reset_ejemplos_btn"):
                st.session_state.trabajos = crear_trabajos_ejemplo(num_maquinas)
                st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                # Limpiar estados de edición
                keys_to_remove = [key for key in st.session_state.keys() if key.startswith("editing_")]
                for key in keys_to_remove:
                    del st.session_state[key]
                st.success("✅ Trabajos reseteados a ejemplos originales!")
                st.rerun()
        
        st.markdown("---")
        
        # Importar/Exportar trabajos desde Excel
        st.write("**📊 Importar/Exportar Excel**")
        
        # Botón para descargar plantilla
        col_excel1, col_excel2 = st.columns(2)
        with col_excel1:
            plantilla_excel = crear_plantilla_excel()
            st.download_button(
                label="📥 Descargar Plantilla Excel",
                data=plantilla_excel,
                file_name=f"plantilla_trabajos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Descarga una plantilla Excel con ejemplos para completar tus trabajos",
                key="download_plantilla_btn"
            )
        
        with col_excel2:
            # Exportar trabajos actuales
            if st.session_state.trabajos:
                trabajos_excel = exportar_trabajos_a_excel(st.session_state.trabajos)
                if trabajos_excel:
                    st.download_button(
                        label="📤 Exportar Trabajos Actuales",
                        data=trabajos_excel,
                        file_name=f"trabajos_actuales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Exporta todos los trabajos actuales a Excel",
                        key="export_trabajos_btn"
                    )
        
        # Importar trabajos desde Excel
        st.write("**📂 Importar Trabajos desde Excel**")
        archivo_excel = st.file_uploader(
            "Selecciona archivo Excel",
            type=['xlsx', 'xls'],
            help="Carga un archivo Excel con la estructura de trabajos",
            key="upload_excel_trabajos"
        )
        
        if archivo_excel is not None:
            trabajos_importados, mensaje = importar_trabajos_desde_excel(archivo_excel)
            
            if trabajos_importados:
                st.info(mensaje)
                
                # Mostrar vista previa
                st.write("**Vista previa de trabajos importados:**")
                for trabajo_nombre, tareas in trabajos_importados.items():
                    st.write(f"- **{trabajo_nombre}**: {len(tareas)} tareas")
                
                # Opciones de importación
                col_import1, col_import2 = st.columns(2)
                with col_import1:
                    if st.button("✅ Reemplazar Trabajos Actuales", key="import_replace_btn"):
                        st.session_state.trabajos = trabajos_importados
                        st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                        st.success(f"✅ Trabajos reemplazados exitosamente!")
                        st.rerun()
                
                with col_import2:
                    if st.button("➕ Agregar a Trabajos Existentes", key="import_add_btn"):
                        # Combinar trabajos existentes con importados
                        contador = 1
                        for trabajo_nombre, tareas in trabajos_importados.items():
                            # Evitar duplicados agregando sufijo si ya existe
                            nombre_final = trabajo_nombre
                            while nombre_final in st.session_state.trabajos:
                                nombre_final = f"{trabajo_nombre} ({contador})"
                                contador += 1
                            st.session_state.trabajos[nombre_final] = tareas
                        
                        st.session_state.tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
                        st.success(f"✅ Trabajos agregados exitosamente!")
                        st.rerun()
            else:
                st.error(mensaje)
    
    # Tab Historial
    with tab_historial:
        st.subheader("📚 Historial de Programaciones")
        st.caption("💡 Ver y comparar todas las simulaciones y programaciones guardadas")
        
        try:
            historial_df = obtener_historial_programaciones(limit=20)
            
            if not historial_df.empty:
                # Opción de comparación
                st.markdown("#### 🔍 Comparar Programaciones")
                prog_ids_disponibles = historial_df['ID'].tolist()
                prog_seleccionadas = st.multiselect(
                    "Seleccionar programaciones para comparar (máx 4):",
                    prog_ids_disponibles,
                    max_selections=4
                )
                
                if len(prog_seleccionadas) >= 2:
                    comparacion_df = comparar_programaciones(prog_seleccionadas)
                    st.dataframe(comparacion_df, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 📋 Todas las Programaciones")
                
                # Mostrar tabla con emojis de estado
                for idx, row in historial_df.iterrows():
                    emoji = convertir_estado_a_emoji(row['Estado'])
                    
                    with st.expander(f"{emoji} {row['ID']} - Semana {row['Semana']} ({row['Estado'].upper()})"):
                        col_h1, col_h2 = st.columns(2)
                        
                        with col_h1:
                            st.write(f"**Estado:** {row['Estado']}")
                            st.write(f"**Objetivo:** {row['Objetivo']}")
                            st.write(f"**Makespan:** {row['Makespan (min)']} min")
                            st.write(f"**Tiempo Resolución:** {row['Num Tareas']}s" if 'Tiempo Resolución' in row else "")
                        
                        with col_h2:
                            st.write(f"**Trabajos:** {row['Num Trabajos']}")
                            st.write(f"**Tareas:** {row['Num Tareas']}")
                            st.write(f"**Creada:** {row['Fecha Creación']}")
                            st.write(f"**Usuario:** {row['Usuario']}")
                        
                        # Información de estado y botones de acción
                        if row['Estado'] == 'simulacion':
                            st.info("🧪 Simulación - No se ejecutó en producción")
                            
                            # Validación para aprobar simulación a producción
                            from modelos.database import obtener_programaciones, EstadoProgramacion
                            
                            programaciones_planificadas = obtener_programaciones(estado=EstadoProgramacion.PLANIFICADA)
                            programaciones_en_ejecucion = obtener_programaciones(estado=EstadoProgramacion.EN_EJECUCION)
                            programaciones_completadas = obtener_programaciones(estado=EstadoProgramacion.COMPLETADA)
                            
                            # Verificar si ya hay una programación activa O completada para la MISMA semana
                            semana_simulacion = row['Semana']
                            anio_simulacion = row.get('Año', 2025)  # Usar año por defecto si no está disponible
                            
                            ya_hay_activa_semana = any(prog['semana_produccion'] == semana_simulacion and prog['anio'] == anio_simulacion 
                                                      for prog in programaciones_planificadas + programaciones_en_ejecucion)
                            ya_hay_completada_semana = any(prog['semana_produccion'] == semana_simulacion and prog['anio'] == anio_simulacion 
                                                          for prog in programaciones_completadas)
                            
                            col_btn1, col_btn2 = st.columns(2)
                            
                            with col_btn1:
                                if ya_hay_activa_semana:
                                    st.button(f"✅ Aprobar para Producción", key=f"aprobar_{row['ID']}", type="primary", disabled=True)
                                    st.caption("⚠️ Ya hay una programación activa para esta semana")
                                elif ya_hay_completada_semana:
                                    st.button(f"✅ Aprobar para Producción", key=f"aprobar_{row['ID']}", type="primary", disabled=True)
                                    st.caption("⚠️ Ya hay una programación completada para esta semana")
                                else:
                                    if st.button(f"✅ Aprobar para Producción", key=f"aprobar_{row['ID']}", type="primary"):
                                        try:
                                            from utils.db_helpers import aprobar_programacion_actual
                                            if aprobar_programacion_actual(row['ID'], "Usuario App"):
                                                st.success(f"✅ Simulación {row['ID']} aprobada para producción (Semana {semana_simulacion})")
                                                st.rerun()
                                            else:
                                                st.error("Error al aprobar simulación")
                                        except Exception as e:
                                            st.error(f"Error: {e}")
                            
                            with col_btn2:
                                # Botón de eliminar para simulaciones
                                if st.button(f"🗑️ Eliminar Simulación", key=f"eliminar_{row['ID']}", type="secondary"):
                                    exito, mensaje = eliminar_programacion_guardada(row['ID'])
                                    if exito:
                                        st.success(mensaje)
                                        st.rerun()
                                    else:
                                        st.error(mensaje)
                        
                        # Botones de exportación para todas las programaciones
                        st.markdown("---")
                        st.markdown("#### 📤 Exportar Programación")
                        
                        col_exp1, col_exp2, col_exp3 = st.columns(3)
                        
                        with col_exp1:
                            if st.button(f"📋 Órdenes de Trabajo", key=f"export_ordenes_{row['ID']}", type="primary"):
                                try:
                                    from utils.gestor_exportacion import GestorExportacion
                                    from modelos.database import obtener_tareas_planificadas
                                    
                                    gestor = GestorExportacion()
                                    
                                    # Obtener datos de la programación
                                    programacion_data = {
                                        'id': row['ID'],
                                        'semana_produccion': row['Semana'],
                                        'anio': row.get('Año', 2025),
                                        'estado': row['Estado'],
                                        'objetivo_usado': row['Objetivo'],
                                        'makespan_planificado': row['Makespan (min)'],
                                        'fecha_creacion': row['Fecha Creación'],
                                        'aprobada_por': row.get('Aprobada Por', ''),
                                        'fecha_aprobacion': None
                                    }
                                    
                                    # Obtener tareas de la programación
                                    tareas_raw = obtener_tareas_planificadas(row['ID'])
                                    
                                    if tareas_raw:
                                        # Procesar datos RAW para formato PDF
                                        tareas_procesadas = procesar_tareas_desde_bd(tareas_raw)
                                        archivo_ordenes = gestor.exportar_ordenes_completas(programacion_data, tareas_procesadas)
                                        if archivo_ordenes:
                                            st.session_state[f'ordenes_file_{row["ID"]}'] = archivo_ordenes
                                            st.session_state[f'ordenes_filename_{row["ID"]}'] = f"Ordenes_Semana_{row['Semana']}_{row['ID']}.pdf"
                                        else:
                                            st.error("No se pudo generar el archivo de órdenes")
                                    else:
                                        st.error("No se encontraron tareas para esta programación")
                                        
                                except Exception as e:
                                    st.error(f"Error exportando órdenes: {e}")
                            
                            # Mostrar botón de descarga si existe el archivo
                            if f'ordenes_file_{row["ID"]}' in st.session_state:
                                with open(st.session_state[f'ordenes_file_{row["ID"]}'], 'rb') as f:
                                    st.download_button(
                                        label="📥 Descargar Órdenes",
                                        data=f.read(),
                                        file_name=st.session_state[f'ordenes_filename_{row["ID"]}'],
                                        mime="application/pdf",
                                        key=f"download_ordenes_{row['ID']}"
                                    )
                        
                        with col_exp2:
                            if st.button(f"📊 Planilla Excel", key=f"export_excel_{row['ID']}", type="secondary"):
                                try:
                                    from utils.gestor_exportacion import GestorExportacion
                                    from modelos.database import obtener_tareas_planificadas
                                    
                                    gestor = GestorExportacion()
                                    
                                    # Obtener datos de la programación
                                    programacion_data = {
                                        'id': row['ID'],
                                        'semana_produccion': row['Semana'],
                                        'anio': row.get('Año', 2025),
                                        'estado': row['Estado'],
                                        'objetivo_usado': row['Objetivo'],
                                        'makespan_planificado': row['Makespan (min)'],
                                        'fecha_creacion': row['Fecha Creación'],
                                        'aprobada_por': row.get('Aprobada Por', ''),
                                        'fecha_aprobacion': None
                                    }
                                    
                                    # Obtener tareas de la programación
                                    tareas_raw = obtener_tareas_planificadas(row['ID'])
                                    
                                    # Obtener configuración de la programación
                                    from modelos.database import obtener_programacion
                                    import json
                                    prog_data = obtener_programacion(row['ID'])
                                    configuracion = None
                                    if prog_data and prog_data.get('configuracion_json'):
                                        try:
                                            configuracion = json.loads(prog_data['configuracion_json'])
                                        except:
                                            configuracion = None
                                    
                                    if tareas_raw:
                                        # Procesar datos RAW para formato Excel
                                        tareas_procesadas = procesar_tareas_desde_bd(tareas_raw, configuracion)
                                        archivo_excel = gestor.exportar_excel_simple(programacion_data, tareas_procesadas)
                                        if archivo_excel:
                                            st.session_state[f'excel_file_{row["ID"]}'] = archivo_excel
                                            st.session_state[f'excel_filename_{row["ID"]}'] = f"Planilla_Semana_{row['Semana']}_{row['ID']}.xlsx"
                                    else:
                                        st.error("No se encontraron tareas para esta programación")
                                        
                                except Exception as e:
                                    st.error(f"Error exportando Excel: {e}")
                            
                            # Mostrar botón de descarga si existe el archivo
                            if f'excel_file_{row["ID"]}' in st.session_state:
                                with open(st.session_state[f'excel_file_{row["ID"]}'], 'rb') as f:
                                    st.download_button(
                                        label="📥 Descargar Planilla Excel",
                                        data=f.read(),
                                        file_name=st.session_state[f'excel_filename_{row["ID"]}'],
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"download_excel_{row['ID']}"
                                    )
                        
                        with col_exp3:
                            if st.button(f"📋 Datos CSV", key=f"export_csv_{row['ID']}", type="secondary"):
                                try:
                                    from utils.gestor_exportacion import GestorExportacion
                                    from modelos.database import obtener_tareas_planificadas
                                    
                                    gestor = GestorExportacion()
                                    
                                    # Obtener datos de la programación
                                    programacion_data = {
                                        'id': row['ID'],
                                        'semana_produccion': row['Semana'],
                                        'anio': row.get('Año', 2025),
                                        'estado': row['Estado'],
                                        'objetivo_usado': row['Objetivo'],
                                        'makespan_planificado': row['Makespan (min)'],
                                        'fecha_creacion': row['Fecha Creación'],
                                        'aprobada_por': row.get('Aprobada Por', ''),
                                        'fecha_aprobacion': None
                                    }
                                    
                                    # Obtener tareas de la programación
                                    tareas_raw = obtener_tareas_planificadas(row['ID'])
                                    
                                    # Obtener configuración de la programación
                                    from modelos.database import obtener_programacion
                                    import json
                                    prog_data = obtener_programacion(row['ID'])
                                    configuracion = None
                                    if prog_data and prog_data.get('configuracion_json'):
                                        try:
                                            configuracion = json.loads(prog_data['configuracion_json'])
                                        except:
                                            configuracion = None
                                    
                                    if tareas_raw:
                                        # Procesar datos RAW para formato CSV
                                        tareas_procesadas = procesar_tareas_desde_bd(tareas_raw, configuracion)
                                        archivo_csv = gestor.exportar_csv_simple(programacion_data, tareas_procesadas)
                                        if archivo_csv:
                                            st.session_state[f'csv_file_{row["ID"]}'] = archivo_csv
                                            st.session_state[f'csv_filename_{row["ID"]}'] = f"Datos_Semana_{row['Semana']}_{row['ID']}.csv"
                                    else:
                                        st.error("No se encontraron tareas para esta programación")
                                        
                                except Exception as e:
                                    st.error(f"Error exportando CSV: {e}")
                            
                            # Mostrar botón de descarga si existe el archivo
                            if f'csv_file_{row["ID"]}' in st.session_state:
                                with open(st.session_state[f'csv_file_{row["ID"]}'], 'rb') as f:
                                    st.download_button(
                                        label="📥 Descargar Datos CSV",
                                        data=f.read(),
                                        file_name=st.session_state[f'csv_filename_{row["ID"]}'],
                                        mime="text/csv",
                                        key=f"download_csv_{row['ID']}"
                                    )
                        
                        if row['Estado'] == 'planificada':
                            st.success(f"✅ Aprobada por: {row['Aprobada Por']}")
                            
                            # Checkbox de confirmación para eliminar planificadas
                            confirmar = st.checkbox(
                                f"Confirmar eliminación (⚠️ es programación oficial)",
                                key=f"confirmar_{row['ID']}"
                            )
                            
                            if confirmar:
                                if st.button(f"🗑️ Eliminar Programación", key=f"eliminar_{row['ID']}", type="primary"):
                                    from modelos.database import eliminar_programacion
                                    # Forzar eliminación de planificada
                                    exito, mensaje = eliminar_programacion(row['ID'], forzar=True)
                                    if exito:
                                        st.warning(mensaje)
                                        st.rerun()
                                    else:
                                        st.error(mensaje)
                        
                        if row['Estado'] == 'en_ejecucion':
                            st.warning("🏭 En Ejecución - NO se puede eliminar")
                            st.error("⛔ Esta programación se está ejecutando actualmente en producción")
                        
                        if row['Estado'] == 'completada':
                            st.success("✔️ Completada - Datos reales disponibles")
                            st.warning("⛔ No se puede eliminar programación completada (datos históricos)")
                        
                        if row['Estado'] == 'cancelada':
                            st.warning("❌ Cancelada")
                            
                            # Botón de eliminar para canceladas
                            if st.button(f"🗑️ Eliminar", key=f"eliminar_{row['ID']}", type="secondary"):
                                exito, mensaje = eliminar_programacion_guardada(row['ID'])
                                if exito:
                                    st.success(mensaje)
                                    st.rerun()
                                else:
                                    st.error(mensaje)
                        
                        # Mostrar tareas planificadas
                        st.markdown("**📋 Tareas Planificadas:**")
                        tareas_df = obtener_asignaciones_como_dataframe(row['ID'])
                        
                        if not tareas_df.empty:
                            # Mostrar tabla compacta
                            columnas_mostrar = ['ID Tarea', 'Nombre', 'Máquina', 'Día', 'Inicio (min)', 'Fin (min)', 'Duración (min)']
                            st.dataframe(
                                tareas_df[columnas_mostrar] if all(col in tareas_df.columns for col in columnas_mostrar) else tareas_df,
                                use_container_width=True,
                                height=min(200, len(tareas_df) * 35 + 38)
                            )
                            
                            # Resumen
                            st.caption(f"Total: {len(tareas_df)} tareas planificadas")
                        else:
                            st.warning("⚠️ No se encontraron tareas planificadas")
            else:
                st.info("ℹ️ No hay programaciones guardadas aún. Ejecuta una optimización y guárdala.")
        
        except Exception as e:
            st.error(f"Error cargando historial: {e}")
            import traceback
            st.code(traceback.format_exc())

# Contenido principal
# Convertir trabajos a DataFrame (hacer esto ANTES de las columnas para que esté disponible en ambas)
# Siempre recalcular desde st.session_state.trabajos para asegurar que esté actualizado
tareas_df = convertir_trabajos_a_dataframe(st.session_state.trabajos)
# Actualizar también el session_state para mantener sincronización
st.session_state.tareas_df = tareas_df

col1, col2 = st.columns([2, 1])

with col1:
    st.header("📋 Gestión de Trabajos Semanales")
    
    # Mostrar configuración actual
    with st.expander("⚙️ Configuración Actual", expanded=False):
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            st.write("**🕐 Horario de Trabajo**")
            st.write(f"• Inicio: {hora_inicio.strftime('%H:%M')}")
            st.write(f"• Fin: {hora_fin.strftime('%H:%M')}")
            st.write(f"• Días: {', '.join(dias_laborales)}")
            st.write(f"• Almuerzo: {almuerzo_inicio.strftime('%H:%M')} - {almuerzo_fin.strftime('%H:%M')}")
        
        with col_config2:
            st.write("**🔧 Recursos**")
            st.write(f"• Máquinas: {num_maquinas}")
            st.write(f"• Operadores: {num_operadores}")
            st.write(f"• Objetivo: {objetivo}")
            st.write(f"• Tiempo límite: {tiempo_maximo}s")
    
    if not tareas_df.empty:
        st.subheader("📊 Resumen de Trabajos")
        
        # Estadísticas por trabajo
        trabajos_stats = tareas_df.groupby("trabajo").agg({
            "duracion": ["count", "sum", "mean"]
        }).round(1)
        trabajos_stats.columns = ["Número de Tareas", "Duración Total (min)", "Duración Promedio (min)"]
        st.dataframe(trabajos_stats, use_container_width=True)
        
        # Mostrar todas las tareas
        st.subheader("📋 Tareas para Optimización")
        columnas_tareas = ["trabajo", "id", "nombre", "duracion", "maquina"]
        st.dataframe(tareas_df[columnas_tareas], use_container_width=True)
        
    else:
        st.info("ℹ️ No hay trabajos definidos. Usa el sidebar para crear trabajos y agregar tareas.")
    
    # Botón de optimización
    if not tareas_df.empty:
        if st.button("🚀 Ejecutar Optimización Semanal", type="primary"):
            with st.spinner("Optimizando programación semanal de producción..."):
                try:
                    # Validar que haya tareas
                    if tareas_df.empty:
                        st.error("❌ No hay tareas para optimizar. Agrega tareas primero.")
                    else:
                        # Crear optimizador
                        optimizador = OptimizadorProduccion()
                        
                        # Calcular horas efectivas de trabajo
                        from datetime import datetime, timedelta
                        hora_inicio_dt = datetime.combine(datetime.today(), hora_inicio)
                        hora_fin_dt = datetime.combine(datetime.today(), hora_fin)
                        almuerzo_inicio_dt = datetime.combine(datetime.today(), almuerzo_inicio)
                        almuerzo_fin_dt = datetime.combine(datetime.today(), almuerzo_fin)
                        
                        # Total de horas del día
                        total_horas = (hora_fin_dt - hora_inicio_dt).total_seconds() / 3600
                        
                        # Horas de almuerzo
                        horas_almuerzo = (almuerzo_fin_dt - almuerzo_inicio_dt).total_seconds() / 3600
                        minutos_almuerzo = int(horas_almuerzo * 60)
                        
                        # Horas efectivas (sin almuerzo)
                        horas_efectivas = total_horas - horas_almuerzo
                        
                        # Crear y resolver modelo con configuración de días laborales y horarios
                        # Nota: Las máquinas siempre operan sin paralelismo (una tarea a la vez)
                        
                        # Ordenar días laborales cronológicamente para evitar programación "torcida"
                        dias_semana_completa = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                        dias_laborales_ordenados = sorted(dias_laborales, key=lambda dia: dias_semana_completa.index(dia))
                        
                        optimizador.crear_modelo(tareas_df, num_operadores, dias_laborales_ordenados, objetivo, horas_efectivas, minutos_almuerzo)
                        resultado = optimizador.resolver()
                        
                        # Guardar resultado en session state
                        st.session_state.resultado_optimizacion = resultado
                        st.session_state.optimizador = optimizador
                        st.session_state.dias_laborales = dias_laborales_ordenados
                        st.session_state.horas_efectivas = horas_efectivas  # Guardar horas efectivas para el Gantt
                        st.session_state.minutos_por_dia_laboral = horas_efectivas * 60  # Guardar minutos por día laboral (540)
                        # Guardar horarios para uso en conversión de minutos a hora
                        st.session_state.hora_inicio = hora_inicio
                        st.session_state.hora_fin = hora_fin
                        
                        st.success("✅ ¡Optimización semanal completada exitosamente!")
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error en la optimización: {e}")
                    st.write("**Posibles causas:**")
                    st.write("- Datos de tareas incompletos o inválidos")
                    st.write("- Problemas con el modelo de optimización")
                    st.write("- Configuración incorrecta")
                    st.write("- Tareas asignadas a días no laborales")

# Mostrar resultados de optimización FUERA de las columnas (ocupa todo el ancho)
if 'resultado_optimizacion' in st.session_state and st.session_state.resultado_optimizacion is not None:
    # Línea divisoria prominente antes de los resultados
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.header("📈 Resultados de la Optimización")
    
    resultado = st.session_state.resultado_optimizacion
    
    # Métricas principales en columnas
    col_res1, col_res2, col_res3 = st.columns(3)
    
    with col_res1:
        st.metric("Estado", resultado.get('status', 'N/A'))
    
    with col_res2:
        st.metric("Tiempo de Resolución", f"{resultado.get('tiempo_resolucion', 0):.2f} s")
    
    with col_res3:
        st.metric("Tiempo Total de Producción", f"{resultado.get('valor_objetivo', 0)} min")
    
    # Botones de acción
    st.markdown("### 🎯 Acciones de Programación")
    
    # Validación de programaciones existentes para la misma semana
    from modelos.database import obtener_programaciones, EstadoProgramacion
    
    programaciones_planificadas = obtener_programaciones(estado=EstadoProgramacion.PLANIFICADA)
    programaciones_en_ejecucion = obtener_programaciones(estado=EstadoProgramacion.EN_EJECUCION)
    programaciones_completadas = obtener_programaciones(estado=EstadoProgramacion.COMPLETADA)
    
    # Verificar si ya hay una programación activa O completada para la MISMA semana
    ya_hay_activa_semana = any(prog['semana_produccion'] == semana_programar and prog['anio'] == anio_programar 
                              for prog in programaciones_planificadas + programaciones_en_ejecucion)
    ya_hay_completada_semana = any(prog['semana_produccion'] == semana_programar and prog['anio'] == anio_programar 
                                  for prog in programaciones_completadas)
    
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    
    with col_btn1:
        if ya_hay_activa_semana:
            st.button("✅ Aprobar para Producción", help="Marcar como programación oficial para ejecutar", use_container_width=True, disabled=True)
            st.caption("⚠️ Ya hay una programación aprobada o en ejecución para esta semana. Ve al Historial para cancelarla primero.")
        elif ya_hay_completada_semana:
            st.button("✅ Aprobar para Producción", help="Marcar como programación oficial para ejecutar", use_container_width=True, disabled=True)
            st.caption("⚠️ Ya hay una programación completada para esta semana. No se puede aprobar otra.")
        else:
            if st.button("✅ Aprobar para Producción", help="Marcar como programación oficial para ejecutar", use_container_width=True):
                try:
                    # Obtener programación detallada procesada
                    programacion_detallada = st.session_state.get('programacion_detallada', [])
                    
                    # Primero guardar la programación
                    prog_id = guardar_programacion_desde_resultado(
                        resultado=resultado,
                        trabajos=st.session_state.trabajos,
                        configuracion={
                            'objetivo': objetivo,
                            'semana': semana_programar,
                            'anio': anio_programar,
                            'num_maquinas': num_maquinas,
                            'num_operadores': num_operadores,
                            'dias_laborales': st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']),
                            'minutos_por_dia_laboral': st.session_state.get('minutos_por_dia_laboral', 540)
                        },
                        semana=semana_programar,
                        anio=anio_programar,
                        usuario="Usuario App",
                        programacion_detallada=programacion_detallada  # Pasar datos procesados
                    )
                    
                    # Luego aprobarla
                    if aprobar_programacion_actual(prog_id, "Usuario App"):
                        st.success(f"✅ Programación {prog_id} aprobada para producción (Semana {semana_programar}/{anio_programar})")
                        st.rerun()
                    else:
                        st.error("Error al aprobar programación")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    with col_btn2:
        if st.button("🧪 Guardar como Simulación", help="Guardar sin aprobar (solo para referencia)", use_container_width=True):
            try:
                # Obtener programación detallada procesada
                programacion_detallada = st.session_state.get('programacion_detallada', [])
                
                prog_id = guardar_simulacion_con_tareas_divididas(
                    resultado=resultado,
                    trabajos=st.session_state.trabajos,
                    configuracion={
                        'objetivo': objetivo,
                        'semana': semana_programar,
                        'anio': anio_programar,
                        'num_maquinas': num_maquinas,
                        'num_operadores': num_operadores,
                        'dias_laborales': st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']),
                        'minutos_por_dia_laboral': st.session_state.get('minutos_por_dia_laboral', 540)
                    },
                    semana=semana_programar,
                    anio=anio_programar,
                    usuario="Usuario App",
                    programacion_detallada=programacion_detallada  # Pasar datos procesados
                )
                st.success(f"🧪 Simulación {prog_id} guardada para Semana {semana_programar}/{anio_programar} (ver en Historial)")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col_btn3:
        if st.button("💾 Descargar Reporte", help="Exportar resultados a archivo", use_container_width=True):
            reporte_contenido = descargar_reporte(resultado, st.session_state.tareas_df)
            if reporte_contenido:
                pass  # Ya se descarga automáticamente
    
    with col_btn4:
        if st.button("❌ Descartar", help="Limpiar resultados sin guardar", use_container_width=True):
            st.session_state.resultado_optimizacion = None
            st.rerun()
    
    st.markdown("---")
    
    # Mostrar programación detallada
    if resultado and resultado.get('solucion') and resultado['solucion'].get('programacion'):
        st.subheader("📋 Programación Detallada")
        
        # Crear DataFrame con la programación usando datos del resultado de optimización
        programacion_data = []
        # Usar los días laborales seleccionados por el usuario
        dias_laborales = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
        
        # Usar los datos del resultado de optimización y dividir tareas automáticamente
        for tarea_prog in resultado['solucion']['programacion']:
            tarea_id = tarea_prog['tarea_id']
            tarea_indice = tarea_prog.get('tarea_indice', 0)
            
            # Log de depuración temporal
            # st.write(f"🔍 DEBUG: Procesando {tarea_id} (índice {tarea_indice})")
            
            if tarea_indice < len(st.session_state.tareas_df):
                tarea_original = st.session_state.tareas_df.iloc[tarea_indice]
                
                # Obtener la máquina asignada (flexible o fija)
                maquina_a_usar = tarea_prog.get('maquina', None)
                if maquina_a_usar is None:
                    maquina_a_usar = tarea_original['maquina']
                
                # Obtener duración total de la tarea original
                duracion_total_original = tarea_original['duracion']
                inicio_min = tarea_prog['inicio']
                fin_min = tarea_prog['fin']
                duracion_asignada = fin_min - inicio_min
                
                # Log de depuración temporal (DESHABILITADO TEMPORALMENTE)
                # st.write(f"🔍 DEBUG: {tarea_id} - Original: {duracion_total_original}min, Asignada: {duracion_asignada}min, Inicio: {inicio_min}, Fin: {fin_min}")
                
                # Verificar si la tarea necesita ser dividida
                minutos_por_dia = st.session_state.get('minutos_por_dia_laboral', 540)  # Usar minutos reales de la configuración
                # st.write(f"🔍 DEBUG: minutos_por_dia = {minutos_por_dia} (debería ser 540)")
                
                # Calcular en qué día empieza y termina la tarea
                dia_inicio = int(inicio_min // minutos_por_dia)
                dia_fin = int(fin_min // minutos_por_dia)
                
                # Log de depuración temporal (DESHABILITADO TEMPORALMENTE)
                # st.write(f"🔍 DEBUG: {tarea_id} - Día inicio: {dia_inicio}, Día fin: {dia_fin}")
                
                # Una tarea debe dividirse SOLO si cruza el límite del día laboral
                # (empieza y termina en días diferentes)
                debe_dividirse = (dia_inicio != dia_fin)
                
                # Log de depuración temporal (DESHABILITADO TEMPORALMENTE)
                # st.write(f"🔍 DEBUG: {tarea_id} - Debe dividirse: {debe_dividirse}")
                
                if debe_dividirse:
                    # Dividir la tarea en partes
                    partes = []
                    tiempo_restante = duracion_asignada
                    tiempo_actual = inicio_min
                    parte_num = 1
                    
                    while tiempo_restante > 0:
                        # Calcular cuánto tiempo queda en el día actual
                        dia_actual = tiempo_actual // minutos_por_dia
                        inicio_dia = tiempo_actual % minutos_por_dia
                        tiempo_disponible_dia = minutos_por_dia - inicio_dia
                        
                        # Determinar duración de esta parte
                        duracion_parte = min(tiempo_restante, tiempo_disponible_dia)
                        fin_parte = tiempo_actual + duracion_parte
                        
                        # Calcular día y hora real
                        dia_numero = int(tiempo_actual // minutos_por_dia)
                        dia_nombre = dias_laborales[dia_numero] if dia_numero < len(dias_laborales) else 'N/A'
                        
                        # Convertir minutos acumulativos a hora real del día
                        inicio_real = minutos_a_hora_dia(tiempo_actual, minutos_por_dia)
                        
                        # CASO ESPECIAL: Si fin_parte es exactamente el inicio del día siguiente,
                        # significa que la tarea termina al final del día actual (18:00)
                        from datetime import time as dt_time
                        print(f"DEBUG TABLE: {tarea_id}.P{parte_num} - fin_parte={fin_parte}, minutos_por_dia={minutos_por_dia}, modulo={fin_parte % minutos_por_dia}")
                        if fin_parte > 0 and fin_parte % minutos_por_dia == 0:
                            fin_real = dt_time(18, 0)  # 18:00 del día actual
                            print(f"DEBUG TABLE: {tarea_id}.P{parte_num} - Usando 18:00")
                        else:
                            fin_real = minutos_a_hora_dia(fin_parte, minutos_por_dia)
                            print(f"DEBUG TABLE: {tarea_id}.P{parte_num} - Usando minutos_a_hora_dia: {fin_real}")
                        
                        # Crear ID con parte
                        id_tarea = f"{tarea_id}.P{parte_num}"
                        nombre_tarea = f"{tarea_original['nombre']} (P{parte_num})"
                        
                        partes.append({
                            'ID': id_tarea,
                            'Tarea': nombre_tarea,
                            'Máquina': maquina_a_usar,
                            'Día': dia_nombre,
                            'Inicio': inicio_real.strftime('%H:%M'),
                            'Fin': fin_real.strftime('%H:%M'),
                            'Duración (min)': duracion_parte,
                            # Datos adicionales para PDF/Excel/CSV
                            'trabajo_id': tarea_original['trabajo'].replace('Trabajo ', '') if isinstance(tarea_original['trabajo'], str) else tarea_original['trabajo'],
                            'tarea_id': id_tarea,
                            'dia': dia_nombre[:3],  # Abreviado
                            'maquina_id': maquina_a_usar if isinstance(maquina_a_usar, str) and maquina_a_usar.startswith('M') else f"M01",
                            'operador_id': f"Op{int(str(tarea_prog.get('operador', 1)).replace('OP', '')):02d}",
                            'inicio_planificado': inicio_real.strftime('%H:%M'),
                            'fin_planificado': fin_real.strftime('%H:%M'),
                            'duracion_planificada': duracion_parte
                        })
                        
                        # Actualizar para la siguiente parte
                        tiempo_restante -= duracion_parte
                        tiempo_actual = fin_parte
                        parte_num += 1
                    
                    # Agregar todas las partes
                    programacion_data.extend(partes)
                    
                else:
                    # Tarea que cabe en un solo día
                    dia_numero = int(inicio_min // minutos_por_dia)
                    dia_nombre = dias_laborales[dia_numero] if dia_numero < len(dias_laborales) else 'N/A'
                    
                    # Convertir minutos acumulativos a hora real del día
                    inicio_real = minutos_a_hora_dia(inicio_min, minutos_por_dia)
                    fin_real = minutos_a_hora_dia(fin_min, minutos_por_dia)
                    
                    programacion_data.append({
                        'ID': tarea_id,
                        'Tarea': tarea_original['nombre'],
                        'Máquina': maquina_a_usar,
                        'Día': dia_nombre,
                        'Inicio': inicio_real.strftime('%H:%M'),
                        'Fin': fin_real.strftime('%H:%M'),
                        'Duración (min)': duracion_asignada,
                        # Datos adicionales para PDF/Excel/CSV
                        'trabajo_id': tarea_original['trabajo'].replace('Trabajo ', '') if isinstance(tarea_original['trabajo'], str) else tarea_original['trabajo'],
                        'tarea_id': tarea_id,
                        'dia': dia_nombre[:3],  # Abreviado
                        'maquina_id': maquina_a_usar if isinstance(maquina_a_usar, str) and maquina_a_usar.startswith('M') else f"M01",
                        'operador_id': f"Op{int(str(tarea_prog.get('operador', 1)).replace('OP', '')):02d}",
                        'inicio_planificado': inicio_real.strftime('%H:%M'),
                        'fin_planificado': fin_real.strftime('%H:%M'),
                        'duracion_planificada': duracion_asignada
                    })
        
        if programacion_data:
            # Guardar programacion_data en session_state para usar en PDF/Excel/CSV
            st.session_state.programacion_detallada = programacion_data
            
            # Crear DataFrame solo para visualización (sin datos internos)
            columnas_visualizacion = ['ID', 'Tarea', 'Máquina', 'Día', 'Inicio', 'Fin', 'Duración (min)']
            df_programacion = pd.DataFrame(programacion_data)
            df_visual = df_programacion[columnas_visualizacion]
            st.dataframe(df_visual, use_container_width=True)
            
            # El diagrama de Gantt se muestra más abajo en la sección principal
    
    # Botones de acción
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📥 Descargar Reporte", key="btn_download_main"):
            descargar_reporte(resultado, st.session_state.tareas_df)
    
    with col_btn2:
        if st.button("🗑️ Limpiar Resultados", key="btn_clear_main"):
            st.session_state.resultado_optimizacion = None
            st.rerun()
    
    # Diagrama de Gantt INMEDIATAMENTE después de los resultados
    st.markdown("---")
    st.header("📅 Diagrama de Gantt Semanal")
    horas_para_gantt = st.session_state.get('horas_efectivas', 10)  # Usar 10 horas (8:00-18:00 con almuerzo)
    mostrar_diagrama_gantt(st.session_state.tareas_df, resultado, "_main", horas_para_gantt)
    
    # Gantt por máquina
    st.markdown("---")
    st.header("⚙️ Diagrama de Gantt por Máquina")
    st.caption("📌 Máquinas en eje Y - Ver carga por recurso")
    mostrar_gantt_por_maquina(st.session_state.tareas_df, resultado, horas_para_gantt)
    
    # Información adicional sobre la programación semanal
    with st.expander("ℹ️ Información sobre la Programación Semanal"):
        dias_info = st.session_state.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
        horas_info = st.session_state.get('horas_efectivas', 16)
        st.markdown(f"""
        **🎯 Cómo interpretar el diagrama:**
        - **Eje X (horizontal)**: Tiempo en horas a lo largo de TODA LA SEMANA (Lunes a Domingo)
        - **Eje Y (vertical)**: Combinación de máquina y tarea
        - **Colores**: Cada color representa un trabajo diferente
        - **Líneas verticales**: Separadores entre días de la semana
        - **Días laborales** (en negrita): {', '.join(dias_info)}
        - **Días no laborales** (en cursiva): Aparecen vacíos sin tareas
        - **Horas disponibles por día**: {horas_info:.1f} horas
        
        **📊 División de tareas:**
        - Si una tarea excede las horas disponibles del día, **se divide automáticamente en partes**
        - La primera parte se muestra hasta el final del día actual
        - La segunda parte se muestra al inicio del siguiente día laboral
        - Cada parte se identifica con "(Parte 1)" y "(Parte 2)" en el nombre
        
        **📈 Funcionalidades:**
        - Pasa el cursor sobre las barras para ver detalles de cada tarea o parte
        - La programación muestra los tiempos reales calculados por el optimizador
        - Los días no laborales se muestran vacíos para visualizar el calendario completo
        - Las tareas se posicionan en su día real de la semana y horario exacto
        """)

with col2:
    st.header("📊 Estadísticas Semanales")
    
    if not tareas_df.empty:
        # Estadísticas básicas de tareas - más compactas
        st.subheader("📋 Resumen General")
        
        # Métricas en columnas para ahorrar espacio vertical
        col_met1, col_met2 = st.columns(2)
        with col_met1:
            st.metric("Total de Trabajos", len(st.session_state.trabajos))
            st.metric("Duración Total", f"{tareas_df['duracion'].sum()} min")
        with col_met2:
            st.metric("Total de Tareas", len(tareas_df))
            st.metric("Máquinas Únicas", tareas_df["maquina"].nunique())
        
        # Duración promedio en una línea separada
        st.metric("Duración Promedio", f"{tareas_df['duracion'].mean():.1f} min")
        
        # Gráfico de duración por trabajo
        st.subheader("📊 Duración por Trabajo")
        fig_trabajos = px.bar(
            tareas_df.groupby("trabajo")["duracion"].sum().reset_index(),
            x="trabajo",
            y="duracion",
            title="Duración Total por Trabajo",
            labels={"duracion": "Duración (min)", "trabajo": "Trabajo"}
        )
        fig_trabajos.update_xaxes(tickangle=45)
        fig_trabajos.update_layout(height=250)
        st.plotly_chart(fig_trabajos, use_container_width=True, key="chart_trabajos")
        
        # Gráfico de distribución por máquina (torta)
        st.subheader("⚙️ Distribución por Máquina")
        # Crear datos para el gráfico de torta - usar TIEMPO TOTAL
        maquina_duracion = tareas_df.groupby('maquina')['duracion'].sum().reset_index(name='duracion_total')
        
        if not maquina_duracion.empty:
            fig_maquina = px.pie(
                maquina_duracion,
                values='duracion_total',
                names='maquina',
                title="Distribución de Tiempo por Máquina"
            )
            # Mostrar solo porcentajes en el gráfico
            fig_maquina.update_traces(
                texttemplate='%{label}<br>%{percent}',
                textposition='inside',
                hovertemplate='<b>%{label}</b><br>Tiempo: %{value} min<br>Porcentaje: %{percent}<extra></extra>'
            )
            fig_maquina.update_layout(height=250)
            st.plotly_chart(fig_maquina, use_container_width=True, key="chart_maquinas")
            
            # Mostrar tabla con detalles en desplegable
            with st.expander("📋 Detalles por Máquina"):
                # Agregar estadísticas completas
                maquina_stats = tareas_df.groupby('maquina').agg({
                    'duracion': ['sum', 'count', 'mean']
                }).round(1)
                maquina_stats.columns = ['Tiempo Total (min)', 'Número de Tareas', 'Tiempo Promedio (min)']
                st.dataframe(maquina_stats, use_container_width=True)
        else:
            st.info("ℹ️ No hay datos de máquinas para mostrar")

    # Tab Tracking
    with tab_tracking:
        st.subheader("🏭 Tracking de Producción")
        st.caption("💡 Registra los tiempos reales de ejecución de tareas en producción")
        
        try:
            # Obtener todas las programaciones activas (PLANIFICADA y EN_EJECUCION)
            from modelos.database import obtener_programaciones_activas, obtener_tareas_sin_ejecucion_real, obtener_ejecuciones_reales_programacion, verificar_programacion_completa
            
            programaciones_activas = obtener_programaciones_activas()
            
            if programaciones_activas:
                st.success(f"📋 **Programaciones Activas:** {len(programaciones_activas)}")
                
                # Mostrar cada programación activa
                for prog in programaciones_activas:
                    with st.expander(f"📅 Semana {prog['semana_produccion']}/{prog['anio']} - {prog['estado'].value}", expanded=True):
                        st.info(f"**ID:** {prog['id']} | **Estado:** {prog['estado'].value}")
                        
                        # Verificar estado de completitud
                        esta_completa, total_tareas, tareas_registradas = verificar_programacion_completa(prog['id'])
                        
                        # Métricas de progreso
                        col_prog1, col_prog2, col_prog3 = st.columns(3)
                        with col_prog1:
                            st.metric("Tareas Totales", total_tareas)
                        with col_prog2:
                            st.metric("Tareas Registradas", tareas_registradas)
                        with col_prog3:
                            porcentaje = (tareas_registradas / total_tareas * 100) if total_tareas > 0 else 0
                            st.metric("Progreso", f"{porcentaje:.1f}%")
                        
                        # Barra de progreso
                        if total_tareas > 0:
                            st.progress(tareas_registradas / total_tareas)
                        
                        st.markdown("---")
                        
                        # Botón para iniciar ejecución (solo si está PLANIFICADA)
                        if prog['estado'].value == 'planificada':
                            if st.button(f"🚀 Iniciar Ejecución - Semana {prog['semana_produccion']}", 
                                       key=f"iniciar_{prog['id']}", 
                                       type="primary", 
                                       use_container_width=True):
                                from modelos.database import cambiar_estado_programacion
                                from modelos.database_models import EstadoProgramacion
                                exito, mensaje = cambiar_estado_programacion(prog['id'], EstadoProgramacion.EN_EJECUCION, "Usuario App")
                                if exito:
                                    st.success(mensaje)
                                    st.rerun()
                                else:
                                    st.error(mensaje)
                        
                        # Sección de registro de tareas (solo si está EN_EJECUCION)
                        if prog['estado'].value == 'en_ejecucion':
                            st.subheader("📝 Registrar Ejecución Real")
                            
                            # Obtener tareas pendientes
                            tareas_pendientes = obtener_tareas_sin_ejecucion_real(prog['id'])
                            
                            if tareas_pendientes:
                                st.write(f"**Tareas pendientes de registro:** {len(tareas_pendientes)}")
                                
                                # Seleccionar tarea para registrar - Formato: ID_Tarea_Nombre
                                tarea_options = {}
                                for t in tareas_pendientes:
                                    # Formato: A2.P1 - Soldadura (P1) - M1
                                    tarea_key = f"{t['tarea_id']} - {t['tarea_nombre']} - M{t['maquina_planificada']}"
                                    tarea_options[tarea_key] = t
                                
                                tarea_seleccionada_str = st.selectbox(
                                    "Selecciona una tarea para registrar:",
                                    options=list(tarea_options.keys()),
                                    key=f"tarea_select_{prog['id']}"
                                )
                                
                                if tarea_seleccionada_str:
                                    tarea = tarea_options[tarea_seleccionada_str]
                                    
                                    # Formulario para registrar tarea - usando un key más estable
                                    form_key = f"form_registrar_{prog['id']}"
                                    with st.form(form_key):
                                        st.write("**Registrar ejecución real:**")
                                        
                                        col_t1, col_t2 = st.columns(2)
                                        with col_t1:
                                            st.write(f"**Tarea:** {tarea['tarea_nombre']}")
                                            st.write(f"**Máquina Planificada:** {tarea['maquina_planificada']}")
                                            st.write(f"**Duración Planificada:** {tarea['duracion_planificada']} min")
                                        
                                        with col_t2:
                                            # Usar los datos ya calculados de la BD (formato HH:MM)
                                            inicio_str = tarea.get('inicio_hora', 'N/A')
                                            fin_str = tarea.get('fin_hora', 'N/A')
                                            
                                            st.write(f"**Inicio Planificado:** {inicio_str}")
                                            st.write(f"**Fin Planificado:** {fin_str}")
                                            if tarea.get('dia_nombre'):
                                                st.write(f"**Día:** {tarea['dia_nombre']}")
                                        
                                        # Usar los tiempos planificados de la BD como valores por defecto
                                        from datetime import time as dt_time, datetime
                                        
                                        # Convertir inicio_hora y fin_hora (HH:MM) a objetos time
                                        inicio_default = dt_time(8, 0)  # Fallback por defecto
                                        fin_default = dt_time(9, 0)  # Fallback por defecto
                                        
                                        # Convertir inicio_hora de "HH:MM" a objeto time
                                        if tarea.get('inicio_hora'):
                                            try:
                                                hora, minuto = map(int, tarea['inicio_hora'].split(':'))
                                                inicio_default = dt_time(hora, minuto)
                                            except:
                                                pass
                                        
                                        # Convertir fin_hora de "HH:MM" a objeto time
                                        if tarea.get('fin_hora'):
                                            try:
                                                hora, minuto = map(int, tarea['fin_hora'].split(':'))
                                                fin_default = dt_time(hora, minuto)
                                            except:
                                                pass
                                        
                                        # Campos de registro
                                        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                                        dia_planificado = tarea.get('dia_nombre', 'Lun')
                                        # Buscar el índice del día planificado (Lun -> Lunes, etc.)
                                        dia_idx_default = 0
                                        for i, dia in enumerate(dias_semana):
                                            if dia_planificado in dia[:3]:
                                                dia_idx_default = i
                                                break
                                        
                                        # Usar ID de tarea en los keys para que cada tarea tenga su propio formulario
                                        tarea_id = tarea['tarea_planificada_id']
                                        
                                        col_r1, col_r2 = st.columns(2)
                                        with col_r1:
                                            # Día de la semana de inicio
                                            dia_inicio_idx = st.selectbox(
                                                "Día de inicio:",
                                                range(len(dias_semana)),
                                                format_func=lambda i: dias_semana[i],
                                                index=dia_idx_default,
                                                key=f"dia_inicio_{prog['id']}_{tarea_id}"
                                            )
                                            inicio_real = st.time_input("Hora de inicio real:", value=inicio_default, key=f"inicio_real_{prog['id']}_{tarea_id}")
                                            maquina_usada = st.text_input("Máquina utilizada:", value=tarea['maquina_planificada'], key=f"maquina_usada_{prog['id']}_{tarea_id}")
                                            operador = st.text_input("Operador:", value=tarea.get('operador_planificado', 'Operador 1'), key=f"operador_{prog['id']}_{tarea_id}")
                                        
                                        with col_r2:
                                            # Día de la semana de fin
                                            dia_fin_idx = st.selectbox(
                                                "Día de fin:",
                                                range(len(dias_semana)),
                                                format_func=lambda i: dias_semana[i],
                                                index=dia_idx_default,
                                                key=f"dia_fin_{prog['id']}_{tarea_id}"
                                            )
                                            fin_real = st.time_input("Hora de fin real:", value=fin_default, key=f"fin_real_{prog['id']}_{tarea_id}")
                                            problemas = st.text_area("Problemas encontrados:", key=f"problemas_{prog['id']}_{tarea_id}")
                                            tiempo_paradas = st.number_input("Tiempo de paradas (min):", min_value=0, value=0, key=f"paradas_{prog['id']}_{tarea_id}")
                                        
                                        # Botón de registro
                                        if st.form_submit_button("✅ Registrar Ejecución", type="primary"):
                                            if inicio_real and fin_real:
                                                # Calcular fecha real basada en semana y año de la programación
                                                from datetime import datetime, timedelta
                                                
                                                # Calcular la fecha del lunes de esa semana usando isocalendar
                                                anio_semana = prog['anio']
                                                num_semana = prog['semana_produccion']
                                                
                                                # Crear una fecha cualquiera del año y ajustar a la semana
                                                primer_dia = datetime(anio_semana, 1, 1)
                                                # Ajustar al lunes de esa semana
                                                dias_para_lunes = (7 - primer_dia.weekday()) % 7
                                                primer_lunes = primer_dia + timedelta(days=dias_para_lunes)
                                                
                                                # Calcular el lunes de la semana solicitada
                                                lunes_semana = primer_lunes + timedelta(weeks=num_semana-1)
                                                
                                                # Calcular fecha de inicio y fin
                                                fecha_inicio = lunes_semana + timedelta(days=dia_inicio_idx)
                                                fecha_fin = lunes_semana + timedelta(days=dia_fin_idx)
                                                
                                                # Crear datetime con fecha y hora
                                                inicio_datetime = datetime.combine(fecha_inicio, inicio_real)
                                                fin_datetime = datetime.combine(fecha_fin, fin_real)
                                                
                                                from modelos.database import registrar_ejecucion_real
                                                try:
                                                    ejecucion_id = registrar_ejecucion_real(
                                                        tarea_planificada_id=tarea['tarea_planificada_id'],
                                                        inicio_real=inicio_datetime,
                                                        fin_real=fin_datetime,
                                                        maquina_usada=maquina_usada,
                                                        operador_ejecutor=operador,
                                                        problemas=problemas,
                                                        tiempo_paradas=tiempo_paradas,
                                                        registrado_por="Usuario App"
                                                    )
                                                    
                                                    # Limpiar los campos del formulario después del registro exitoso
                                                    keys_to_clear = [
                                                        f"dia_inicio_{prog['id']}_{tarea_id}",
                                                        f"inicio_real_{prog['id']}_{tarea_id}",
                                                        f"maquina_usada_{prog['id']}_{tarea_id}",
                                                        f"operador_{prog['id']}_{tarea_id}",
                                                        f"dia_fin_{prog['id']}_{tarea_id}",
                                                        f"fin_real_{prog['id']}_{tarea_id}",
                                                        f"problemas_{prog['id']}_{tarea_id}",
                                                        f"paradas_{prog['id']}_{tarea_id}"
                                                    ]
                                                    for key in keys_to_clear:
                                                        if key in st.session_state:
                                                            del st.session_state[key]
                                                    
                                                    st.success(f"✅ Ejecución registrada exitosamente (ID: {ejecucion_id})")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error al registrar: {str(e)}")
                                            else:
                                                st.error("Por favor completa todos los campos obligatorios")
                            else:
                                st.success("🎉 ¡Todas las tareas han sido registradas!")
                            
                            # Mostrar tareas ya registradas
                            ejecuciones_registradas = obtener_ejecuciones_reales_programacion(prog['id'])
                            if ejecuciones_registradas:
                                st.subheader("📊 Tareas Registradas")
                                
                                for ejecucion in ejecuciones_registradas:
                                    with st.expander(f"✅ {ejecucion['tarea_nombre']} - M{ejecucion['maquina_usada']}"):
                                        col_e1, col_e2 = st.columns(2)
                                        with col_e1:
                                            st.write(f"**Operador:** {ejecucion['operador_ejecutor']}")
                                            st.write(f"**Inicio Real:** {ejecucion['inicio_real'].strftime('%H:%M')}")
                                            st.write(f"**Fin Real:** {ejecucion['fin_real'].strftime('%H:%M')}")
                                        with col_e2:
                                            st.write(f"**Máquina:** {ejecucion['maquina_usada']}")
                                            st.write(f"**Tiempo Paradas:** {ejecucion['tiempo_paradas']} min")
                                            if ejecucion['problemas_encontrados']:
                                                st.write(f"**Problemas:** {ejecucion['problemas_encontrados']}")
                            
                            # Botón para marcar como completada (solo si está completa)
                            if esta_completa:
                                st.subheader("🏁 Finalizar Programación")
                                
                                # Checkbox de confirmación
                                confirmar_key = f"confirmar_completar_tracking_{prog['id']}"
                                if confirmar_key not in st.session_state:
                                    st.session_state[confirmar_key] = False
                                
                                confirmar_completar = st.checkbox(
                                    "Confirmar que se registraron todos los datos reales",
                                    key=confirmar_key,
                                    value=st.session_state[confirmar_key]
                                )
                                
                                
                                st.markdown("---")
                                
                                # Botón solo activo si está confirmado
                                if st.button(f"✅ Marcar Semana {prog['semana_produccion']} como Completada", 
                                           key=f"completar_{prog['id']}",
                                           type="primary", 
                                           use_container_width=True,
                                           disabled=not confirmar_completar):
                                    from modelos.database import cambiar_estado_programacion
                                    from modelos.database_models import EstadoProgramacion
                                    
                                    exito, mensaje = cambiar_estado_programacion(
                                        prog['id'], 
                                        EstadoProgramacion.COMPLETADA, 
                                        "Usuario App"
                                    )
                                    if exito:
                                        st.success(f"{mensaje} 🎉")
                                        st.rerun()
                                    else:
                                        st.error(mensaje)
            else:
                st.info("📭 No hay programaciones activas para tracking")
                st.caption("💡 Ve al tab 'Historial' para aprobar una programación o crear una nueva")
        
        except Exception as e:
            st.error(f"Error en tracking: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # ========================================================================
    # TAB: DASHBOARD KPIS
    # ========================================================================
    with tab_dashboard:
        try:
            st.subheader("📊 Dashboard de KPIs - Análisis de Producción")
            st.caption("Métricas industriales y análisis de desempeño")
            
            # Obtener programaciones completadas
            historial_df = obtener_historial_programaciones(limit=50)
            
            # Filtrar solo completadas (el estado viene en minúscula desde la BD)
            if not historial_df.empty:
                programaciones_completadas = historial_df[
                    historial_df['Estado'].str.lower() == 'completada'
                ].to_dict('records')
            else:
                programaciones_completadas = []
            
            if not programaciones_completadas:
                st.info("📭 No hay programaciones completadas para analizar")
                st.caption("💡 Completa una programación en el tab 'Tracking' para ver métricas")
            
            else:
                # Selector de programación
                st.write("**Selecciona programación a analizar:**")
                opciones_prog = [
                    f"Semana {p['Semana']}/{p['Año']} - {p.get('Num Tareas', 0)} tareas"
                    for p in programaciones_completadas
                ]
                
                prog_seleccionada_idx = st.selectbox(
                    "Programación",
                    range(len(programaciones_completadas)),
                    format_func=lambda i: opciones_prog[i] if i < len(opciones_prog) else "",
                    key="prog_dashboard_select"
                )
                
                prog_seleccionada = programaciones_completadas[prog_seleccionada_idx]
                
                # Obtener ejecuciones reales
                from modelos.database import obtener_ejecuciones_reales_programacion, obtener_programacion
                prog_id = prog_seleccionada.get('ID', '')
                
                try:
                    ejecuciones = obtener_ejecuciones_reales_programacion(prog_id)
                    st.caption(f"🔍 ID: '{prog_id}' | Ejecuciones: {len(ejecuciones) if ejecuciones else 0}")
                except Exception as e:
                    st.error(f"Error al obtener ejecuciones: {e}")
                    ejecuciones = []
                
                # Si no hay ejecuciones reales, mostrar métricas básicas
                if not ejecuciones:
                    st.info("💡 Esta programación no tiene datos de tracking registrados. Mostrando métricas básicas de la planificación.")
                    
                    # Obtener datos planificados
                    prog_detallada = obtener_programacion(prog_seleccionada.get('ID', ''))
                    
                    if prog_detallada:
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Tiempo Planificado", f"{prog_detallada.get('makespan_planificado', 0)} min")
                        
                        with col2:
                            st.metric("Trabajos", prog_detallada.get('num_trabajos', 0))
                        
                        with col3:
                            st.metric("Tareas", prog_detallada.get('num_tareas', 0))
                        
                        with col4:
                            st.metric("Estado", prog_detallada.get('estado', 'N/A'))
                        
                        st.warning("⚠️ Para ver KPIs completos (OEE, OTIF, desviaciones), registra tiempos reales en 'Tracking'")
                    else:
                        st.info("📭 No hay datos disponibles para esta programación")
                
                elif ejecuciones:
                    prog_id = prog_seleccionada.get('ID', '')
                    
                    # Obtener métricas desde BD
                    from modelos.database import obtener_metricas, calcular_y_guardar_metricas
                    metricas_bd = obtener_metricas(prog_id)
                    
                    # Si no existen métricas, calcularlas y guardarlas
                    if not metricas_bd:
                        with st.spinner("🔄 Calculando KPIs y guardando en BD..."):
                            calcular_y_guardar_metricas(prog_id)
                            metricas_bd = obtener_metricas(prog_id)
                    
                    if metricas_bd:
                        # Mostrar fecha de último cálculo
                        if metricas_bd.get('fecha_calculo'):
                            fecha_calc = metricas_bd['fecha_calculo']
                            if isinstance(fecha_calc, str):
                                st.caption(f"📅 Último cálculo: {fecha_calc}")
                            else:
                                st.caption(f"📅 Último cálculo: {fecha_calc.strftime('%Y-%m-%d %H:%M:%S') if hasattr(fecha_calc, 'strftime') else fecha_calc}")
                        
                        # Convertir métricas de BD al formato esperado para la UI
                        metricas = {
                            'oee_global': metricas_bd.get('oee_global', 0.0),
                            'disponibilidad_oee': metricas_bd.get('disponibilidad_oee', 0.0),
                            'rendimiento_oee': metricas_bd.get('rendimiento_oee', 0.0),
                            'calidad_oee': metricas_bd.get('calidad_oee', 0.0),
                            'throughput_semanal': metricas_bd.get('throughput_semanal', 0),
                            'otif_porcentaje': metricas_bd.get('otif_porcentaje', 0.0),
                            'tareas_a_tiempo': metricas_bd.get('tareas_a_tiempo', 0),
                            'tareas_retrasadas': metricas_bd.get('tareas_retrasadas', 0),
                            'tareas_adelantadas': metricas_bd.get('tareas_adelantadas', 0),
                            'desviacion_promedio': metricas_bd.get('desviacion_promedio', 0.0),
                            'desviacion_maxima': metricas_bd.get('desviacion_maxima', 0.0),
                            'lead_time_promedio': metricas_bd.get('lead_time_promedio', 0.0),  # Utilización global promedio ponderada
                            'cuello_botella': metricas_bd.get('cuello_botella_identificado'),
                            'total_tareas': len(ejecuciones),
                            # Incluir ejecuciones reales para las planillas desplegables
                            'ejecuciones': ejecuciones,
                            # Reconstruir utilizacion_maquinas desde BD
                            'utilizacion_maquinas': {
                                'M1': {
                                    'utilizacion_total': metricas_bd.get('utilizacion_m1', 0.0),
                                    'tiempo_productivo': metricas_bd.get('tiempo_productivo_m1', 0),
                                    'tiempo_ocioso': metricas_bd.get('tiempo_ocioso_m1', 0),
                                    'tiempo_setup': metricas_bd.get('tiempo_setup_m1', 0),
                                    'num_tareas': sum(1 for e in ejecuciones if e.get('maquina_usada') == 'M1')
                                },
                                'M2': {
                                    'utilizacion_total': metricas_bd.get('utilizacion_m2', 0.0),
                                    'tiempo_productivo': metricas_bd.get('tiempo_productivo_m2', 0),
                                    'tiempo_ocioso': metricas_bd.get('tiempo_ocioso_m2', 0),
                                    'tiempo_setup': metricas_bd.get('tiempo_setup_m2', 0),
                                    'num_tareas': sum(1 for e in ejecuciones if e.get('maquina_usada') == 'M2')
                                },
                                'M3': {
                                    'utilizacion_total': metricas_bd.get('utilizacion_m3', 0.0),
                                    'tiempo_productivo': metricas_bd.get('tiempo_productivo_m3', 0),
                                    'tiempo_ocioso': metricas_bd.get('tiempo_ocioso_m3', 0),
                                    'tiempo_setup': metricas_bd.get('tiempo_setup_m3', 0),
                                    'num_tareas': sum(1 for e in ejecuciones if e.get('maquina_usada') == 'M3')
                                }
                            }
                        }
                    else:
                        st.error("❌ No se pudieron cargar las métricas desde BD")
                        # Inicializar metricas vacío pero con ejecuciones para que las planillas funcionen
                        metricas = {
                            'ejecuciones': ejecuciones,
                            'total_tareas': len(ejecuciones),
                            'oee_global': 0.0,
                            'disponibilidad_oee': 0.0,
                            'rendimiento_oee': 0.0,
                            'calidad_oee': 0.0,
                            'throughput_semanal': len(ejecuciones),
                            'otif_porcentaje': 0.0,
                            'tareas_a_tiempo': 0,
                            'tareas_retrasadas': 0,
                            'tareas_adelantadas': 0,
                            'desviacion_promedio': 0.0,
                            'desviacion_maxima': 0.0,
                            'utilizacion_maquinas': {}
                        }
                    
                    # Mostrar KPIs principales (7 KPIs en 2 filas: 4 + 3)
                    # Primera fila: 4 KPIs principales
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "🎯 OEE Global",
                            f"{metricas['oee_global']:.1f}%",
                            help="Overall Equipment Effectiveness"
                        )
                    
                    with col2:
                        st.metric(
                            "✅ Cumplimiento (OTIF)",
                            f"{metricas['otif_porcentaje']:.1f}%",
                            delta=f"{metricas['tareas_a_tiempo']}/{metricas['total_tareas']} tareas"
                        )
                    
                    with col3:
                        st.metric(
                            "⏱️ Desviación Promedio",
                            f"{metricas['desviacion_promedio']:.0f} min",
                            delta=f"Max: {metricas['desviacion_maxima']:.0f} min"
                        )
                    
                    with col4:
                        # Utilización Global de Máquinas (promedio ponderado)
                        utilizacion_global = metricas.get('lead_time_promedio', 0.0)  # Reutilizamos este campo
                        st.metric(
                            "⚙️ Utilización Global",
                            f"{utilizacion_global:.1f}%",
                            help="Promedio ponderado por tiempo productivo"
                        )
                    
                    # Segunda fila: 3 Componentes del OEE
                    col5, col6, col7 = st.columns(3)
                    
                    with col5:
                        disponibilidad = metricas.get('disponibilidad_oee', 0.0)
                        st.metric(
                            "📊 Disponibilidad",
                            f"{disponibilidad:.1f}%",
                            help="% de tiempo de operación vs tiempo planificado"
                        )
                    
                    with col6:
                        rendimiento = metricas.get('rendimiento_oee', 0.0)
                        st.metric(
                            "⚡ Rendimiento",
                            f"{rendimiento:.1f}%",
                            help="% de velocidad real vs planificada (tiempo total)"
                        )
                    
                    with col7:
                        calidad = metricas.get('calidad_oee', 0.0)
                        st.metric(
                            "✨ Calidad",
                            f"{calidad:.1f}%",
                            help="% de tareas sin problemas/rechazos"
                        )
                    
                    st.markdown("---")
                    
                    # Utilización por máquina
                    st.subheader("⚙️ Utilización de Máquinas")
                    
                    if metricas.get('utilizacion_maquinas'):
                        maquinas_data = []
                        for maq, data in metricas['utilizacion_maquinas'].items():
                            maquinas_data.append({
                                'Máquina': maq,
                                'Utilización Total': f"{data['utilizacion_total']:.1f}%",
                                'Tiempo Productivo': f"{data['tiempo_productivo']:.0f} min",
                                'Tiempo Ocioso': f"{data['tiempo_ocioso']:.0f} min",
                                'Tareas': data['num_tareas']
                            })
                        
                        df_utilizacion = pd.DataFrame(maquinas_data)
                        st.dataframe(df_utilizacion, use_container_width=True, hide_index=True)
                        
                        # Gráfico de barras
                        fig_barras = px.bar(
                            df_utilizacion,
                            x='Máquina',
                            y='Utilización Total',
                            color='Máquina',
                            text='Utilización Total',
                            title='Utilización por Máquina',
                            color_discrete_map={'M1': '#1f77b4', 'M2': '#ff7f0e', 'M3': '#2ca02c'}
                        )
                        fig_barras.update_layout(showlegend=False, height=400)
                        fig_barras.update_traces(texttemplate='%{text}', textposition='outside')
                        st.plotly_chart(fig_barras, use_container_width=True)
                        
                        # Alerta de cuello de botella
                        cuello = metricas.get('cuello_botella')
                        if cuello:
                            st.warning(f"⚠️ Cuello de botella identificado: **{cuello}** - Considera redistribuir carga")
                    
                    st.markdown("---")
                    
                    # Análisis de cumplimiento
                    st.subheader("🎯 Análisis de Cumplimiento")
                    
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        st.metric("A Tiempo", metricas['tareas_a_tiempo'], 
                                delta=f"{metricas['tareas_a_tiempo']/metricas['total_tareas']*100:.0f}%")
                    
                    with col_b:
                        st.metric("Retrasadas", metricas['tareas_retrasadas'],
                                delta=f"-{metricas['tareas_retrasadas']/metricas['total_tareas']*100:.0f}%")
                    
                    with col_c:
                        adelantadas = metricas.get('tareas_adelantadas', 0)
                        st.metric("Adelantadas", adelantadas)
                    
                    # Comparativa planificado vs real (diagnóstico)
                    with st.expander("🕒 Comparativa Planificado vs Real (diagnóstico)", expanded=False):
                        ejecuciones_data = metricas.get('ejecuciones', [])
                        if ejecuciones_data:
                            from datetime import datetime
                            from utils.kpi_calculator import KPIExporter
                            
                            # Obtener semana y año para construir datetimes planificados
                            prog_info = obtener_programacion(prog_id)
                            semana_prod = prog_info.get('semana_produccion') if prog_info else None
                            anio_prod = prog_seleccionada.get('Año') if prog_seleccionada else None
                            
                            calc = KPIExporter()
                            
                            filas = []
                            for e in ejecuciones_data:
                                tarea = e.get('tarea_nombre', 'N/A')
                                
                                # Usar horas planificadas (HH:MM) en lugar de minutos lineales
                                inicio_hora = e.get('inicio_hora')  # String HH:MM
                                fin_hora = e.get('fin_hora')  # String HH:MM
                                dia_nombre = e.get('dia_nombre')  # Ej: "Lun"
                                dia_semana = e.get('dia_semana')  # 0=Lunes, etc
                                
                                # Construir datetime planificado desde hora, día, semana, año
                                inicio_plan_dt = None
                                fin_plan_dt = None
                                if inicio_hora and fin_hora and dia_semana is not None and semana_prod and anio_prod:
                                    try:
                                        inicio_plan_dt = calc._construir_datetime_planificado(
                                            inicio_hora, dia_semana, semana_prod, anio_prod
                                        )
                                        fin_plan_dt = calc._construir_datetime_planificado(
                                            fin_hora, dia_semana, semana_prod, anio_prod
                                        )
                                    except Exception:
                                        pass
                                
                                # Calcular duración planificada REAL desde los datetimes
                                dur_plan_calculada = None
                                if inicio_plan_dt and fin_plan_dt:
                                    dur_plan_calculada = int((fin_plan_dt - inicio_plan_dt).total_seconds() / 60)
                                
                                # Horas reales
                                ini_real = e.get('inicio_real')
                                fin_real = e.get('fin_real')
                                
                                # Calcular duración real desde datetimes si están disponibles
                                dur_real_calculada = None
                                if ini_real and fin_real:
                                    try:
                                        if isinstance(ini_real, str):
                                            ini_real_dt = datetime.fromisoformat(ini_real.replace('Z', '+00:00'))
                                        else:
                                            ini_real_dt = ini_real
                                        
                                        if isinstance(fin_real, str):
                                            fin_real_dt = datetime.fromisoformat(fin_real.replace('Z', '+00:00'))
                                        else:
                                            fin_real_dt = fin_real
                                        
                                        if isinstance(ini_real_dt, datetime) and isinstance(fin_real_dt, datetime):
                                            dur_real_calculada = int((fin_real_dt - ini_real_dt).total_seconds() / 60)
                                    except Exception:
                                        pass
                                
                                # IMPORTANTE: Calcular duración planificada desde inicio_hora y fin_hora
                                # porque duracion_planificada de BD es la duración efectiva de trabajo (sin almuerzo)
                                # pero inicio_hora/fin_hora reflejan el tiempo transcurrido TOTAL (puede incluir almuerzo si cruza)
                                
                                # Prioridad 1: Calcular desde datetime (más preciso, considera fechas completas)
                                if dur_plan_calculada is None and inicio_hora and fin_hora:
                                    # Prioridad 2: Calcular directamente desde HH:MM (mismo día)
                                    try:
                                        h_ini, m_ini = map(int, inicio_hora.split(':'))
                                        h_fin, m_fin = map(int, fin_hora.split(':'))
                                        minutos_inicio = h_ini * 60 + m_ini
                                        minutos_fin = h_fin * 60 + m_fin
                                        # Si cruza medianoche, ajustar (aunque no debería pasar en mismo día)
                                        if minutos_fin < minutos_inicio:
                                            minutos_fin += 24 * 60
                                        dur_plan_calculada = minutos_fin - minutos_inicio
                                    except Exception:
                                        pass
                                
                                # SIEMPRE usar cálculo desde horas cuando esté disponible
                                # Esto garantiza que duración planificada = diferencia entre fin_hora e inicio_hora
                                if dur_plan_calculada is not None:
                                    dur_plan = dur_plan_calculada
                                elif inicio_hora and fin_hora and ':' in inicio_hora and ':' in fin_hora:
                                    # Calcular directamente desde horas (fallback si datetime no funcionó)
                                    try:
                                        h_ini, m_ini = map(int, inicio_hora.split(':'))
                                        h_fin, m_fin = map(int, fin_hora.split(':'))
                                        dur_plan = (h_fin * 60 + m_fin) - (h_ini * 60 + m_ini)
                                        if dur_plan < 0:
                                            dur_plan += 24 * 60  # Ajuste si cruza medianoche
                                    except:
                                        dur_plan = e.get('duracion_planificada', 0)
                                else:
                                    # Último recurso: usar duracion_planificada de BD
                                    dur_plan = e.get('duracion_planificada', 0)
                                dur_real = dur_real_calculada if dur_real_calculada is not None else e.get('duracion_real', 0)
                                
                                desv_bd = e.get('desviacion_duracion')
                                tiempo_paradas = e.get('tiempo_paradas', 0) or 0
                                
                                # Calcular desviación desde duraciones calculadas
                                # NOTA: La desviación se calcula comparando duración real vs planificada
                                # PERO la desviación de BD compara contra duración original de tabla 'tareas'
                                # Para esta tabla de diagnóstico, comparamos duraciones de inicio/fin
                                desv_calculada = None
                                if dur_real > 0 and dur_plan is not None:
                                    dur_real_sin_paradas = max(0, dur_real - tiempo_paradas)
                                    desv_calculada = dur_real_sin_paradas - dur_plan
                                
                                # Usar desviación calculada para esta tabla
                                desv_final = desv_calculada if desv_calculada is not None else desv_bd
                                
                                # Formatear fechas/horas si existen
                                def fmt(dt):
                                    try:
                                        if isinstance(dt, str):
                                            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                                        return dt.strftime('%Y-%m-%d %H:%M') if dt else ''
                                    except Exception:
                                        return str(dt) if dt else ''
                                
                                # Formatear hora planificada (mostrar día + fecha completa)
                                def fmt_plan(dt, dia_nom):
                                    if dt:
                                        return f"{dia_nom if dia_nom else ''} {fmt(dt)}".strip()
                                    elif inicio_hora and dia_nom:
                                        return f"{dia_nom} {inicio_hora}"
                                    return ''
                                
                                # Mostrar hora planificada usando inicio_hora y fin_hora (HH:MM)
                                inicio_plan_str = fmt_plan(inicio_plan_dt, dia_nombre) if inicio_plan_dt else (f"{dia_nombre} {inicio_hora}" if inicio_hora and dia_nombre else '')
                                fin_plan_str = fmt_plan(fin_plan_dt, dia_nombre) if fin_plan_dt else (f"{dia_nombre} {fin_hora}" if fin_hora and dia_nombre else '')
                                
                                # Obtener operador ejecutor
                                operador_ejecutor = e.get('operador_ejecutor', 'N/A')
                                
                                filas.append({
                                    'Tarea': tarea,
                                    'Día': dia_nombre or '',
                                    'Inicio Plan.': inicio_plan_str,
                                    'Fin Plan.': fin_plan_str,
                                    'Duración Plan. (min)': dur_plan if dur_plan is not None else '',
                                    'Inicio Real': fmt(ini_real),
                                    'Fin Real': fmt(fin_real),
                                    'Duración Real (min)': dur_real if dur_real is not None else '',
                                    'Operador': operador_ejecutor if operador_ejecutor else 'N/A',
                                    'Tiempo Paradas (min)': tiempo_paradas,
                                    'Desv. Duración (min)': round(desv_final, 1) if desv_final is not None else '',
                                })
                            
                            if filas:
                                df_comp = pd.DataFrame(filas)
                                st.dataframe(df_comp, use_container_width=True, hide_index=True)
                                
                                # Mostrar resumen estadístico
                                st.caption("📊 **Resumen:**")
                                col_res1, col_res2, col_res3 = st.columns(3)
                                
                                with col_res1:
                                    desv_mean = df_comp['Desv. Duración (min)'].dropna().mean() if 'Desv. Duración (min)' in df_comp else None
                                    if desv_mean is not None and not df_comp['Desv. Duración (min)'].dropna().empty:
                                        st.metric("Desv. Promedio", f"{desv_mean:.1f} min")
                                    else:
                                        st.metric("Desv. Promedio", "N/A")
                                
                                with col_res2:
                                    desv_max = df_comp['Desv. Duración (min)'].dropna().abs().max() if 'Desv. Duración (min)' in df_comp else None
                                    if desv_max is not None and not df_comp['Desv. Duración (min)'].dropna().empty:
                                        st.metric("Desv. Máxima", f"{desv_max:.1f} min")
                                    else:
                                        st.metric("Desv. Máxima", "N/A")
                                
                                with col_res3:
                                    fuera_tolerancia = (df_comp['Desv. Duración (min)'].dropna().abs() > 5).sum() if 'Desv. Duración (min)' in df_comp else 0
                                    st.metric("Fuera Tolerancia (±5min)", fuera_tolerancia)
                                
                                st.info("ℹ️ **Horas Planificadas:** Se usan las horas optimizadas (formato HH:MM) de la tabla TareaPlanificada, "
                                       "no minutos lineales. Las desviaciones se calculan usando la duración de la tabla 'Tareas' original.")
                            else:
                                st.info("No hay ejecuciones para comparar.")
                        else:
                            st.info("No hay datos de ejecuciones disponibles")
                    
                else:
                    st.info("📭 No hay datos de ejecución real para esta programación")
                    st.caption("💡 Registra tiempos reales en el tab 'Tracking' para ver métricas")
        
        except Exception as e:
            st.error(f"Error en dashboard: {e}")
            import traceback
            st.code(traceback.format_exc())


# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        <p>🏭 Optimizador de Programación de Producción SEMANAL | Desarrollado con OR-Tools y Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True
) 