#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualización de Programaciones Históricas
Funciones para reconstruir y comparar programaciones guardadas
"""

import json
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List
from modelos.database import obtener_programacion, obtener_tareas_planificadas, obtener_metricas


def reconstruir_programacion(prog_id: str) -> Dict:
    """
    Reconstruir toda la información de una programación guardada
    
    Args:
        prog_id: ID de la programación
        
    Returns:
        Dict: Diccionario con toda la información reconstruida
    """
    # Obtener programación (retorna dict)
    prog_dict = obtener_programacion(prog_id)
    
    if not prog_dict:
        return None
    
    # Obtener tareas planificadas (necesitamos modificar para que retorne dicts)
    tareas = obtener_tareas_planificadas(prog_id)
    
    # Reconstruir formato de resultado
    programacion_reconstruida = {
        'id': prog_dict['id'],
        'semana': prog_dict['semana_produccion'],
        'anio': prog_dict['anio'],
        'estado': prog_dict['estado'],
        'objetivo': prog_dict['objetivo_usado'],
        'makespan': prog_dict['makespan_planificado'],
        'num_trabajos': prog_dict['num_trabajos'],
        'num_tareas': prog_dict['num_tareas'],
        'tiempo_resolucion': prog_dict['tiempo_resolucion'],
        'fecha_creacion': prog_dict['fecha_creacion'],
        'aprobada_por': prog_dict['aprobada_por'],
        'tareas_planificadas': tareas
    }
    
    return programacion_reconstruida


def crear_gantt_comparativo(programaciones: List[str], nombres: List[str] = None) -> go.Figure:
    """
    Crear diagrama de Gantt comparativo de múltiples programaciones
    
    Args:
        programaciones: Lista de IDs de programaciones a comparar
        nombres: Nombres para cada programación (opcional)
        
    Returns:
        go.Figure: Figura de Plotly con Gantt comparativo
    """
    if nombres is None:
        nombres = [f"Programación {i+1}" for i in range(len(programaciones))]
    
    fig = go.Figure()
    
    # TODO: Implementar Gantt comparativo
    # Por ahora retornar figura vacía
    
    return fig


def comparar_programaciones(prog_ids: List[str]) -> pd.DataFrame:
    """
    Comparar métricas de múltiples programaciones con datos mejorados
    
    Args:
        prog_ids: Lista de IDs de programaciones
        
    Returns:
        pd.DataFrame: Tabla comparativa con métricas ampliadas
    """
    datos_comparativos = []
    
    for prog_id in prog_ids:
        prog = obtener_programacion(prog_id)
        
        if prog:
            # Extraer configuración si existe
            config_json = prog.get('configuracion_json', '{}')
            config = {}
            try:
                if config_json:
                    config = json.loads(config_json)
                else:
                    config = {}
            except Exception as e:
                config = {}
            
            # Extraer días laborales y configuración
            horario = config.get('horario_trabajo', {})
            recursos = config.get('recursos', {})
            dias_laborales = horario.get('dias_laborales', config.get('dias_laborales', []))
            dias_str = ', '.join([dia[:3] for dia in dias_laborales]) if dias_laborales else 'N/A'
            
            # Calcular minutos por día efectivos
            minutos_por_dia = config.get('minutos_por_dia_laboral', 540)
            try:
                hora_inicio_str = horario.get('inicio', '08:00')
                hora_fin_str = horario.get('fin', '18:00')
                almuerzo_inicio_str = horario.get('descanso_almuerzo', {}).get('inicio', '13:00')
                almuerzo_fin_str = horario.get('descanso_almuerzo', {}).get('fin', '14:00')
                
                h_ini, m_ini = map(int, hora_inicio_str.split(':'))
                h_fin, m_fin = map(int, hora_fin_str.split(':'))
                h_alm_ini, m_alm_ini = map(int, almuerzo_inicio_str.split(':'))
                h_alm_fin, m_alm_fin = map(int, almuerzo_fin_str.split(':'))
                
                minutos_totales = (h_fin * 60 + m_fin) - (h_ini * 60 + m_ini)
                minutos_almuerzo = (h_alm_fin * 60 + m_alm_fin) - (h_alm_ini * 60 + m_alm_ini)
                minutos_por_dia = minutos_totales - minutos_almuerzo
            except:
                pass
            
            num_maquinas = recursos.get('num_maquinas', config.get('num_maquinas', 3))
            num_operadores = recursos.get('num_operadores', config.get('num_operadores', 3))
            
            # Formatear fecha de creación
            fecha_creacion = prog.get('fecha_creacion')
            if fecha_creacion:
                from datetime import datetime
                if isinstance(fecha_creacion, str):
                    fecha_creacion = datetime.fromisoformat(fecha_creacion.replace('Z', '+00:00'))
                fecha_str = fecha_creacion.strftime('%Y-%m-%d %H:%M')
            else:
                fecha_str = 'N/A'
            
            # Obtener métricas reales si la programación está completada
            metricas_bd = obtener_metricas(prog_id) if prog.get('estado', '').lower() == 'completada' else None
            
            # Calcular utilización de máquinas desde planificación
            utilizacion_global = 'N/A'
            utilizacion_m1 = 'N/A'
            utilizacion_m2 = 'N/A'
            utilizacion_m3 = 'N/A'
            balanceo_carga = 'N/A'  # Desviación estándar de utilizaciones
            
            # Si hay métricas de BD (programación completada), usarlas
            if metricas_bd:
                utilizacion_global = f"{metricas_bd.get('lead_time_promedio', 0):.1f}%"
                utilizacion_m1 = f"{metricas_bd.get('utilizacion_m1', 0):.1f}%"
                utilizacion_m2 = f"{metricas_bd.get('utilizacion_m2', 0):.1f}%"
                utilizacion_m3 = f"{metricas_bd.get('utilizacion_m3', 0):.1f}%"
                
                # Calcular balanceo de carga (desviación estándar)
                utilidades = [
                    metricas_bd.get('utilizacion_m1', 0),
                    metricas_bd.get('utilizacion_m2', 0),
                    metricas_bd.get('utilizacion_m3', 0)
                ]
                utilidades_validas = [u for u in utilidades if u > 0]
                if len(utilidades_validas) > 1:
                    import statistics
                    balanceo_carga = f"{statistics.stdev(utilidades_validas):.1f}%"
                elif utilidades_validas:
                    balanceo_carga = "0.0%"  # Solo una máquina activa
            else:
                # Calcular desde tareas planificadas (solo para programaciones activas/simulaciones)
                tareas_planificadas = obtener_tareas_planificadas(prog_id)
                if tareas_planificadas and len(dias_laborales) > 0:
                    try:
                        # Calcular tiempo por máquina
                        tiempo_por_maquina = {}
                        for tarea in tareas_planificadas:
                            maquina = tarea.get('maquina_id', tarea.get('maquina', ''))
                            duracion = tarea.get('duracion_planificada', 0)
                            if maquina:
                                tiempo_por_maquina[maquina] = tiempo_por_maquina.get(maquina, 0) + duracion
                        
                        # Calcular utilización
                        tiempo_disponible = len(dias_laborales) * minutos_por_dia
                        utilidades = []
                        
                        for maq in ['M1', 'M2', 'M3']:
                            tiempo_usado = tiempo_por_maquina.get(maq, 0)
                            if tiempo_disponible > 0:
                                util = (tiempo_usado / tiempo_disponible) * 100
                                utilidades.append(util)
                                if maq == 'M1':
                                    utilizacion_m1 = f"{util:.1f}%"
                                elif maq == 'M2':
                                    utilizacion_m2 = f"{util:.1f}%"
                                elif maq == 'M3':
                                    utilizacion_m3 = f"{util:.1f}%"
                        
                        # Utilización global (promedio simple)
                        if utilidades:
                            utilizacion_global = f"{sum(utilidades) / len(utilidades):.1f}%"
                            
                            # Balanceo de carga
                            if len(utilidades) > 1:
                                import statistics
                                balanceo_carga = f"{statistics.stdev(utilidades):.1f}%"
                            else:
                                balanceo_carga = "0.0%"
                    except Exception as e:
                        pass  # Si hay error, dejar valores por defecto
            
            # Preparar datos comparativos
            datos_prog = {
                'ID': prog['id'],
                'Fecha Creación': fecha_str,
                'Semana': prog['semana_produccion'],
                'Año': prog['anio'],
                'Estado': prog['estado'],
                'Objetivo': prog['objetivo_usado'],
                'Días Laborales': dias_str,
                'Min/Día Efectivos': minutos_por_dia,
                'Máquinas': num_maquinas,
                'Operadores': num_operadores,
                'Num Trabajos': prog['num_trabajos'],
                'Num Tareas': prog['num_tareas'],
                'Makespan (min)': prog['makespan_planificado'],
                'Makespan (h)': f"{prog['makespan_planificado'] / 60:.1f}",
                'Tiempo Resolución (s)': prog['tiempo_resolucion'],
                'Utilización Global': utilizacion_global,
                'Utilización M1': utilizacion_m1,
                'Utilización M2': utilizacion_m2,
                'Utilización M3': utilizacion_m3,
                'Balanceo Carga (std)': balanceo_carga,
            }
            
            # Agregar KPIs reales si están disponibles
            if metricas_bd:
                datos_prog['OEE Global'] = f"{metricas_bd.get('oee_global', 0):.1f}%"
                datos_prog['Disponibilidad'] = f"{metricas_bd.get('disponibilidad_oee', 0):.1f}%"
                datos_prog['Rendimiento'] = f"{metricas_bd.get('rendimiento_oee', 0):.1f}%"
                datos_prog['Calidad'] = f"{metricas_bd.get('calidad_oee', 0):.1f}%"
                datos_prog['Cumplimiento OTIF'] = f"{metricas_bd.get('otif_porcentaje', 0):.1f}%"
                datos_prog['Desviación Promedio'] = f"{metricas_bd.get('desviacion_promedio', 0):.1f} min"
            else:
                # Para programaciones no completadas, dejar campos vacíos
                datos_prog['OEE Global'] = '-'
                datos_prog['Disponibilidad'] = '-'
                datos_prog['Rendimiento'] = '-'
                datos_prog['Calidad'] = '-'
                datos_prog['Cumplimiento OTIF'] = '-'
                datos_prog['Desviación Promedio'] = '-'
            
            datos_comparativos.append(datos_prog)
    
    return pd.DataFrame(datos_comparativos)


def obtener_asignaciones_como_dataframe(prog_id: str) -> pd.DataFrame:
    """
    Obtener asignaciones de una programación en formato DataFrame
    
    Args:
        prog_id: ID de la programación
        
    Returns:
        pd.DataFrame: Asignaciones en formato tabla
    """
    tareas = obtener_tareas_planificadas(prog_id)
    
    if not tareas:
        return pd.DataFrame()
    
    datos = []
    for tarea in tareas:
        # Usar datos procesados (inicio_hora, fin_hora, dia_nombre) si están disponibles
        inicio_display = tarea.get('inicio_hora', tarea.get('inicio_planificado', 0))
        fin_display = tarea.get('fin_hora', tarea.get('fin_planificado', 0))
        dia_display = tarea.get('dia_nombre', _convertir_dia_a_nombre(tarea.get('dia_semana', 0)))
        
        datos.append({
            'ID Tarea': tarea['tarea_id'],
            'Nombre': tarea['nombre'],
            'Máquina': tarea['maquina_id'],
            'Operador': tarea['operador_id'] or '-',
            'Inicio (min)': inicio_display,
            'Fin (min)': fin_display,
            'Duración (min)': tarea['duracion_planificada'],
            'Día': dia_display
        })
    
    return pd.DataFrame(datos)


def _convertir_dia_a_nombre(dia_input) -> str:
    """Convertir número de día o nombre a nombre"""
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Si ya es un string, devolverlo tal como está
    if isinstance(dia_input, str):
        return dia_input
    
    # Si es un número, convertir a nombre
    if isinstance(dia_input, int) and 0 <= dia_input < 7:
        return dias[dia_input]
    
    return 'N/A'


