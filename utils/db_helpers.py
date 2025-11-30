#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades de BD para Streamlit App
Funciones helper para integrar la base de datos con app_semanal.py
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import json

from modelos.database import (
    db_manager,
    crear_trabajo, crear_tarea,
    crear_programacion, crear_tarea_planificada,
    aprobar_programacion, cambiar_estado_programacion,
    eliminar_programacion,
    obtener_programacion, obtener_programaciones,
    obtener_todas_maquinas, obtener_todos_operadores,
    EstadoProgramacion
)


def _convertir_dia_a_numero(dia_nombre: str) -> int:
    """Convertir nombre de día a número (0=Lunes, 6=Domingo)"""
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    try:
        return dias.index(dia_nombre)
    except ValueError:
        return 0  # Default a Lunes si no se encuentra

def _calcular_dia_desde_minutos(minutos_acumulativos: int, minutos_por_dia_laboral: int = 600) -> int:
    """Calcular el día de la semana basándose en minutos acumulativos"""
    return minutos_acumulativos // minutos_por_dia_laboral


# Funciones para guardar programaciones

def dividir_tarea_en_partes(tarea_asignacion: Dict, minutos_por_dia_laboral: int = 600) -> List[Dict]:
    """Divide una tarea en partes si excede el día laboral"""
    inicio = tarea_asignacion.get('inicio', 0)
    fin = tarea_asignacion.get('fin', 0)
    duracion_total = fin - inicio
    
    # Calcular día de inicio
    dia_inicio = inicio // minutos_por_dia_laboral
    inicio_dia = inicio % minutos_por_dia_laboral
    
    partes = []
    tiempo_restante = duracion_total
    parte_numero = 1
    
    while tiempo_restante > 0:
        # Calcular cuánto tiempo queda en el día actual
        tiempo_restante_dia = minutos_por_dia_laboral - inicio_dia
        
        if tiempo_restante <= tiempo_restante_dia:
            # La tarea cabe en el día actual
            duracion_parte = tiempo_restante
            fin_parte = inicio + duracion_parte
            
            partes.append({
                'inicio': inicio,
                'fin': fin_parte,
                'duracion': duracion_parte,
                'dia': dia_inicio,
                'parte_numero': parte_numero,
                'es_dividida': len(partes) > 0 or tiempo_restante < duracion_total
            })
            break
        else:
            # La tarea se extiende al siguiente día
            duracion_parte = tiempo_restante_dia
            fin_parte = inicio + duracion_parte
            
            partes.append({
                'inicio': inicio,
                'fin': fin_parte,
                'duracion': duracion_parte,
                'dia': dia_inicio,
                'parte_numero': parte_numero,
                'es_dividida': True
            })
            
            # Preparar para la siguiente parte
            tiempo_restante -= duracion_parte
            parte_numero += 1
            dia_inicio += 1
            inicio = dia_inicio * minutos_por_dia_laboral  # Inicio del siguiente día
            inicio_dia = 0
    
    return partes


def guardar_programacion_desde_resultado(resultado: Dict, trabajos: Dict, 
                                        configuracion: Dict,
                                        semana: int = None,
                                        anio: int = None,
                                        usuario: str = "Usuario",
                                        programacion_detallada: List = None) -> str:
    """Guarda resultado de optimización en la BD como simulación"""
    
    # Calcular semana y año si no se proporcionan
    if semana is None:
        semana = datetime.now().isocalendar()[1]
    
    if anio is None:
        anio = datetime.now().year
    
    # Crear programación (retorna ID directamente)
    # Calcular número de tareas correctamente
    num_tareas = 0
    if 'solucion' in resultado and 'programacion' in resultado['solucion']:
        num_tareas = len(resultado['solucion']['programacion'])
    else:
        num_tareas = resultado.get('tareas_asignadas', 0)
    
    prog_id = crear_programacion(
        semana=semana,
        anio=anio,
        objetivo=configuracion.get('objetivo', 'Minimizar tiempo total'),
        num_trabajos=len(trabajos),
        num_tareas=num_tareas,
        makespan=resultado.get('valor_objetivo', 0),
        tiempo_resolucion=resultado.get('tiempo_resolucion', 0),
        configuracion=configuracion,
        usuario=usuario
    )
    
    # Guardar tareas planificadas
    # Si se proporcionan datos procesados (programacion_detallada), usarlos
    if programacion_detallada:
        print(f"DEBUG: Guardando tareas planificadas PROCESADAS para programación {prog_id}")
        print(f"DEBUG: Usando programacion_detallada con {len(programacion_detallada)} tareas")
        
        # Guardar datos procesados directamente
        for tarea_proc in programacion_detallada:
            # Verificar si tiene los campos necesarios
            if 'inicio_planificado' in tarea_proc and 'fin_planificado' in tarea_proc:
                # Los datos ya vienen procesados con HH:MM
                # Necesitamos convertir HH:MM a minutos acumulativos para guardarlos
                inicio_hora = tarea_proc['inicio_planificado']
                fin_hora = tarea_proc['fin_planificado']
                
                # Parsear HH:MM (ejemplo: "14:15" -> (14, 15))
                try:
                    if isinstance(inicio_hora, str) and ':' in inicio_hora:
                        h_inicio, m_inicio = map(int, inicio_hora.split(':'))
                        minutos_inicio = h_inicio * 60 + m_inicio
                    else:
                        minutos_inicio = 0
                    
                    if isinstance(fin_hora, str) and ':' in fin_hora:
                        h_fin, m_fin = map(int, fin_hora.split(':'))
                        minutos_fin = h_fin * 60 + m_fin
                    else:
                        minutos_fin = 0
                    
                    # Calcular minutos acumulativos (aproximado basado en día)
                    dia_str = tarea_proc.get('dia', 'Lun')
                    # IMPORTANTE: Usar los días laborales de la configuración
                    # NO hardcodear un mapeo fijo
                    dias_laborales = configuracion.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
                    # Crear mapeo basado en días laborales configurados
                    dias_map = {}
                    for i, dia_completo in enumerate(dias_laborales):
                        # Mapear abreviaciones (Lun, Mar, etc.) al índice en días laborales
                        dia_abr = dia_completo[:3]
                        dias_map[dia_abr] = i
                    
                    minutos_por_dia = configuracion.get('minutos_por_dia_laboral', 540)
                    dia_num = dias_map.get(dia_str, 0)
                    
                    inicio_acumulativo = dia_num * minutos_por_dia + minutos_inicio
                    fin_acumulativo = dia_num * minutos_por_dia + minutos_fin
                    
                    tarea_info = {
                        'tarea_id': tarea_proc.get('tarea_id', 'N/A'),
                        'trabajo_id': tarea_proc.get('trabajo_id', 'N/A'),
                        'nombre': tarea_proc.get('Tarea', 'N/A'),
                        'duracion_planificada': tarea_proc.get('duracion_planificada', 0),
                        'tiempo_setup': 0,
                        'maquina_id': tarea_proc.get('maquina_id', 'N/A'),
                        'operador_id': tarea_proc.get('operador_id', 'N/A'),
                        'inicio_planificado': inicio_acumulativo,
                        'fin_planificado': fin_acumulativo,
                        'dia_semana': dia_num,
                        'es_dividida': '.P' in tarea_proc.get('tarea_id', ''),
                        'parte_numero': tarea_proc.get('tarea_id', '').count('.P') + 1,
                        # Guardar datos procesados del UI
                        'inicio_hora': tarea_proc.get('inicio_planificado', ''),
                        'fin_hora': tarea_proc.get('fin_planificado', ''),
                        'dia_nombre': tarea_proc.get('dia', '')
                    }
                    
                    crear_tarea_planificada(prog_id, tarea_info)
                except Exception as e:
                    print(f"ERROR procesando tarea procesada: {e}")
                    continue
    elif resultado.get('solucion') and resultado['solucion'].get('programacion'):
        print(f"DEBUG: Guardando tareas planificadas RAW para programación {prog_id}")
        print(f"DEBUG: Tipo de trabajos: {type(trabajos)}")
        print(f"DEBUG: Contenido de trabajos: {trabajos}")
        
        # PRIMERO: Crear trabajos y tareas base en la BD
        # Manejar tanto diccionario como lista
        if isinstance(trabajos, dict):
            print("DEBUG: Trabajos es diccionario")
            # Verificar si es formato nuevo (dict con tareas) o formato viejo (dict con listas)
            trabajos_dict_normalizado = {}
            for trabajo_id, trabajo_data in trabajos.items():
                if isinstance(trabajo_data, list):
                    # Formato: {'A': [tarea1, tarea2, tarea3]}
                    print(f"DEBUG: Trabajo {trabajo_id} es lista de tareas")
                    trabajos_dict_normalizado[trabajo_id] = {
                        'nombre': f'Trabajo {trabajo_id}',
                        'descripcion': f'Descripción del trabajo {trabajo_id}',
                        'cliente': 'Cliente',
                        'tareas': trabajo_data
                    }
                elif isinstance(trabajo_data, dict) and 'tareas' in trabajo_data:
                    # Formato: {'A': {'nombre': 'Trabajo A', 'tareas': [tarea1, tarea2]}}
                    print(f"DEBUG: Trabajo {trabajo_id} es diccionario con tareas")
                    trabajos_dict_normalizado[trabajo_id] = trabajo_data
                else:
                    print(f"DEBUG: Formato no reconocido para trabajo {trabajo_id}: {type(trabajo_data)}")
                    continue
            
            print(f"DEBUG: Llamando convertir_trabajos_dict_a_bd con {len(trabajos_dict_normalizado)} trabajos")
            convertir_trabajos_dict_a_bd(trabajos_dict_normalizado)
        elif isinstance(trabajos, list):
            print("DEBUG: Trabajos es lista, convirtiendo a diccionario")
            # Convertir lista a diccionario temporal
            trabajos_dict = {}
            for i, trabajo in enumerate(trabajos):
                trabajo_id = trabajo.get('id', f'Trabajo_{i+1}')
                trabajos_dict[trabajo_id] = trabajo
            convertir_trabajos_dict_a_bd(trabajos_dict)
        else:
            print(f"DEBUG: Tipo de trabajos no reconocido: {type(trabajos)}")
        
        # Crear DataFrame de tareas para mapeo
        tareas_df = pd.DataFrame()
        
        # Normalizar trabajos para el DataFrame (usar la misma lógica que arriba)
        if isinstance(trabajos, dict):
            trabajos_dict_df = {}
            for trabajo_id, trabajo_data in trabajos.items():
                if isinstance(trabajo_data, list):
                    # Formato: {'A': [tarea1, tarea2, tarea3]}
                    trabajos_dict_df[trabajo_id] = {
                        'nombre': f'Trabajo {trabajo_id}',
                        'descripcion': f'Descripción del trabajo {trabajo_id}',
                        'cliente': 'Cliente',
                        'tareas': trabajo_data
                    }
                elif isinstance(trabajo_data, dict) and 'tareas' in trabajo_data:
                    # Formato: {'A': {'nombre': 'Trabajo A', 'tareas': [tarea1, tarea2]}}
                    trabajos_dict_df[trabajo_id] = trabajo_data
                else:
                    continue
        elif isinstance(trabajos, list):
            trabajos_dict_df = {}
            for i, trabajo in enumerate(trabajos):
                trabajo_id = trabajo.get('id', f'Trabajo_{i+1}')
                trabajos_dict_df[trabajo_id] = trabajo
        else:
            trabajos_dict_df = trabajos
            
        for trabajo_id, trabajo_data in trabajos_dict_df.items():
            # Manejar ambos formatos: lista directa o diccionario con clave 'tareas'
            if isinstance(trabajo_data, list):
                tareas_lista = trabajo_data
            elif isinstance(trabajo_data, dict) and 'tareas' in trabajo_data:
                tareas_lista = trabajo_data['tareas']
            else:
                continue  # Saltar si no es un formato reconocido
                
            for tarea_data in tareas_lista:
                tareas_df = pd.concat([tareas_df, pd.DataFrame([{
                    'id': tarea_data['id'],
                    'nombre': tarea_data['nombre'],
                    'maquina': tarea_data['maquina'],
                    'duracion': tarea_data['duracion'],
                    'tiempo_setup': tarea_data.get('tiempo_setup', 0),
                    'trabajo': trabajo_id
                }])], ignore_index=True)
        
        for asig in resultado['solucion']['programacion']:
            tarea_id = asig.get('tarea_id', '')
            tarea_indice = asig.get('tarea_indice', 0)
            
            # Obtener información de la tarea original
            tarea_original = None
            if tarea_indice < len(tareas_df):
                tarea_original = tareas_df.iloc[tarea_indice]
            
            # Dividir la tarea en partes si es necesario
            minutos_por_dia = configuracion.get('minutos_por_dia_laboral', 600)
            partes_tarea = dividir_tarea_en_partes(asig, minutos_por_dia)
            
            # Crear una tarea planificada por cada parte
            for parte in partes_tarea:
                # Calcular el día correcto basándose en los minutos de inicio
                dia_calculado = _calcular_dia_desde_minutos(parte['inicio'], minutos_por_dia)
                
                tarea_info = {
                    'tarea_id': tarea_id,
                    'trabajo_id': tarea_id[0] if tarea_id else '',  # Primer carácter
                    'nombre': tarea_original['nombre'] if tarea_original is not None else '',
                    'duracion_planificada': parte['duracion'],
                    'tiempo_setup': tarea_original['tiempo_setup'] if tarea_original is not None else 0,
                    'maquina_id': tarea_original['maquina'] if tarea_original is not None else '',
                    'operador_id': asig.get('operador', 'N/A'),
                    'inicio_planificado': parte['inicio'],
                    'fin_planificado': parte['fin'],
                    'dia_semana': dia_calculado,
                    'es_dividida': parte['es_dividida'],
                    'parte_numero': parte['parte_numero']
            }
            
            crear_tarea_planificada(prog_id, tarea_info)
    
    return prog_id


def convertir_trabajos_dict_a_bd(trabajos_dict: Dict):
    """
    Guardar trabajos del session_state en la BD
    
    Args:
        trabajos_dict: Diccionario de trabajos del formato actual
    """
    for trabajo_id, trabajo_data in trabajos_dict.items():
        # Crear trabajo si no existe
        try:
            trabajo_bd = crear_trabajo(
                id=trabajo_id,
                nombre=trabajo_data.get('nombre', f'Trabajo {trabajo_id}'),
                descripcion=trabajo_data.get('descripcion', ''),
                cliente=trabajo_data.get('cliente', '')
            )
        except:
            pass  # Ya existe
        
        # Crear tareas
        for i, tarea in enumerate(trabajo_data.get('tareas', []), start=1):
            try:
                crear_tarea(
                    id=tarea.get('id', f'{trabajo_id}{i}'),
                    trabajo_id=trabajo_id,
                    nombre=tarea.get('nombre', ''),
                    duracion=tarea.get('duracion', 0),
                    maquina_requerida=tarea.get('maquina', 'M1'),
                    tiempo_setup=tarea.get('tiempo_setup', 0),
                    orden=i
                )
            except:
                pass  # Ya existe


# Funciones para cargar datos

def cargar_maquinas_desde_bd() -> List[Dict]:
    """Cargar máquinas desde BD en formato dict"""
    maquinas = obtener_todas_maquinas(solo_disponibles=True)
    # Ya vienen como diccionarios, solo ajustar nombres de campos
    return [
        {
            'id': m['id'],
            'nombre': m['nombre'],
            'capacidad': m['capacidad'],
            'tiempo_setup': m['tiempo_setup_default'],
            'costo_por_hora': m['costo_por_hora'],
            'disponible': m['disponible']
        }
        for m in maquinas
    ]


def cargar_operadores_desde_bd() -> List[Dict]:
    """Cargar operadores desde BD en formato dict"""
    operadores = obtener_todos_operadores(solo_disponibles=True)
    # Ya vienen como diccionarios
    return [
        {
            'id': op['id'],
            'nombre': op['nombre'],
            'habilidades': json.loads(op['habilidades']) if op['habilidades'] else [],
            'costo_por_hora': op['costo_por_hora'],
            'disponible': op['disponible']
        }
        for op in operadores
    ]


def obtener_historial_programaciones(limit: int = 20) -> pd.DataFrame:
    """
    Obtener historial de programaciones en formato DataFrame
    
    Args:
        limit: Número máximo de programaciones a retornar
        
    Returns:
        pd.DataFrame: Historial de programaciones
    """
    programaciones = obtener_programaciones(limit=limit)
    
    if not programaciones:
        return pd.DataFrame()
    
    datos = []
    for prog in programaciones:
        datos.append({
            'ID': prog['id'],
            'Semana': prog['semana_produccion'],
            'Año': prog['anio'],
            'Estado': prog['estado'],
            'Objetivo': prog['objetivo_usado'],
            'Makespan (min)': prog['makespan_planificado'],
            'Num Trabajos': prog['num_trabajos'],
            'Num Tareas': prog['num_tareas'],
            'Fecha Creación': prog['fecha_creacion'].strftime('%Y-%m-%d %H:%M') if prog['fecha_creacion'] else '-',
            'Aprobada Por': prog['aprobada_por'] or '-',
            'Usuario': prog['usuario_creador']
        })
    
    return pd.DataFrame(datos)


def obtener_semana_actual() -> int:
    """Obtener número de semana actual"""
    return datetime.now().isocalendar()[1]


def obtener_anio_actual() -> int:
    """Obtener año actual"""
    return datetime.now().year


# Funciones de acción

def aprobar_programacion_actual(prog_id: str, usuario: str = "Usuario") -> bool:
    """Aprueba una programación para producción"""
    return aprobar_programacion(prog_id, usuario)


def eliminar_programacion_guardada(prog_id: str) -> tuple[bool, str]:
    """Elimina una programación guardada"""
    return eliminar_programacion(prog_id, forzar=False)


def cancelar_programacion(prog_id: str) -> bool:
    """Cancela una programación"""
    return cambiar_estado_programacion(prog_id, EstadoProgramacion.CANCELADA)


def iniciar_ejecucion_programacion(prog_id: str) -> bool:
    """Inicia ejecución de una programación"""
    return cambiar_estado_programacion(prog_id, EstadoProgramacion.EN_EJECUCION)


def completar_programacion(prog_id: str) -> bool:
    """Marca programación como completada"""
    return cambiar_estado_programacion(prog_id, EstadoProgramacion.COMPLETADA)


# Funciones de formato

def convertir_estado_a_emoji(estado: str) -> str:
    """Convertir estado a emoji para visualización"""
    emojis = {
        'simulacion': '🧪',
        'planificada': '✅',
        'en_ejecucion': '🏭',
        'completada': '✔️',
        'cancelada': '❌'
    }
    return emojis.get(estado, '❓')


def convertir_estado_a_color(estado: str) -> str:
    """Convertir estado a color para visualización"""
    colores = {
        'simulacion': 'blue',
        'planificada': 'green',
        'en_ejecucion': 'orange',
        'completada': 'gray',
        'cancelada': 'red'
    }
    return colores.get(estado, 'black')


# Inicialización

def guardar_simulacion_con_tareas_divididas(resultado: Dict, trabajos: Dict, 
                                           configuracion: Dict,
                                           semana: int = None,
                                           anio: int = None,
                                           usuario: str = "Usuario",
                                           programacion_detallada: List = None) -> str:
    """Guarda resultado de optimización en la BD con tareas divididas"""
    
    # Calcular semana y año si no se proporcionan
    if semana is None or anio is None:
        from datetime import datetime
        hoy = datetime.now()
        if semana is None:
            semana = hoy.isocalendar()[1]
        if anio is None:
            anio = hoy.year
    
    # Crear programación
    programacion_id = crear_programacion(
        semana=semana,
        anio=anio,
        objetivo=configuracion.get('objetivo', 'Minimizar tiempo total'),
        num_trabajos=len(trabajos),
        num_tareas=len(resultado['solucion']['programacion']),
        makespan=resultado['solucion']['tiempo_total'],
        tiempo_resolucion=resultado['tiempo_resolucion'],
        configuracion=configuracion,
        usuario=usuario
    )
    
    # Obtener minutos por día laboral de la configuración
    minutos_por_dia = configuracion.get('minutos_por_dia_laboral', 540)  # Default: 9 horas efectivas
    
    # Si se proporcionan datos procesados, usarlos
    if programacion_detallada:
        print(f"DEBUG: Guardando tareas PROCESADAS en guardar_simulacion")
        for tarea_proc in programacion_detallada:
            if 'inicio_planificado' in tarea_proc and 'fin_planificado' in tarea_proc:
                inicio_hora = tarea_proc['inicio_planificado']
                fin_hora = tarea_proc['fin_planificado']
                
                try:
                    if isinstance(inicio_hora, str) and ':' in inicio_hora:
                        h_inicio, m_inicio = map(int, inicio_hora.split(':'))
                        minutos_inicio = h_inicio * 60 + m_inicio
                    else:
                        minutos_inicio = 0
                    
                    if isinstance(fin_hora, str) and ':' in fin_hora:
                        h_fin, m_fin = map(int, fin_hora.split(':'))
                        minutos_fin = h_fin * 60 + m_fin
                    else:
                        minutos_fin = 0
                    
                    dia_str = tarea_proc.get('dia', 'Lun')
                    # IMPORTANTE: Usar los días laborales de la configuración
                    # NO hardcodear un mapeo fijo
                    dias_laborales = configuracion.get('dias_laborales', ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'])
                    # Crear mapeo basado en días laborales configurados
                    dias_map = {}
                    for i, dia_completo in enumerate(dias_laborales):
                        # Mapear abreviaciones (Lun, Mar, etc.) al índice en días laborales
                        dia_abr = dia_completo[:3]
                        dias_map[dia_abr] = i
                    
                    dia_num = dias_map.get(dia_str, 0)
                    
                    inicio_acumulativo = dia_num * minutos_por_dia + minutos_inicio
                    fin_acumulativo = dia_num * minutos_por_dia + minutos_fin
                    
                    tarea_id = tarea_proc.get('tarea_id', 'N/A')
                    trabajo_id = tarea_proc.get('trabajo_id', 'N/A')
                    
                    crear_tarea_planificada(programacion_id=programacion_id, tarea_info={
                        'tarea_id': tarea_id,
                        'trabajo_id': trabajo_id,
                        'nombre': tarea_proc.get('Tarea', 'N/A'),
                        'maquina_id': tarea_proc.get('maquina_id', 'N/A'),
                        'operador_id': tarea_proc.get('operador_id', 'N/A'),
                        'inicio_planificado': inicio_acumulativo,
                        'fin_planificado': fin_acumulativo,
                        'duracion_planificada': tarea_proc.get('duracion_planificada', 0),
                        'tiempo_setup': 0,
                        'es_dividida': '.P' in str(tarea_id),
                        'parte_numero': tarea_id.count('.P') + 1 if '.P' in str(tarea_id) else None,
                        # Guardar datos procesados del UI
                        'inicio_hora': tarea_proc.get('inicio_planificado', ''),
                        'fin_hora': tarea_proc.get('fin_planificado', ''),
                        'dia_nombre': tarea_proc.get('dia', '')
                    })
                except Exception as e:
                    print(f"ERROR procesando tarea procesada en simulacion: {e}")
                    continue
        return programacion_id
    
    # Procesar cada asignación del resultado (lógica original para datos RAW)
    for asig in resultado['solucion']['programacion']:
        tarea_id = asig.get('tarea_id', '')
        tarea_indice = asig.get('tarea_indice', 0)
        
        # Obtener información de la tarea original
        tarea_original = None
        for trabajo_id, trabajo_data in trabajos.items():
            if isinstance(trabajo_data, dict) and 'tareas' in trabajo_data:
                tareas_lista = trabajo_data['tareas']
            elif isinstance(trabajo_data, list):
                tareas_lista = trabajo_data
            else:
                continue
                
            for tarea_data in tareas_lista:
                if tarea_data['id'] == tarea_id:
                    tarea_original = tarea_data
                    break
            if tarea_original:
                break
        
        if not tarea_original:
            continue
        
        # Dividir la tarea en partes si es necesario
        partes_tarea = dividir_tarea_en_partes(asig, minutos_por_dia)
        
        # Guardar cada parte como una tarea planificada
        for i, parte in enumerate(partes_tarea):
            parte_id = f"{tarea_id}.P{i+1}" if len(partes_tarea) > 1 else tarea_id
            
            crear_tarea_planificada(
                programacion_id=programacion_id,
                tarea_info={
                    'tarea_id': parte_id,
                    'trabajo_id': trabajo_id,
                    'nombre': f"{tarea_original['nombre']} (P{i+1})" if len(partes_tarea) > 1 else tarea_original['nombre'],
                    'maquina_id': tarea_original['maquina'],
                    'operador_id': asig.get('operador', 'Sin asignar'),
                    'inicio_planificado': parte['inicio'],
                    'fin_planificado': parte['fin'],
                    'duracion_planificada': parte['duracion'],
                    'tiempo_setup': tarea_original.get('tiempo_setup', 0),
                    'es_dividida': len(partes_tarea) > 1,
                    'parte_numero': i + 1 if len(partes_tarea) > 1 else None
                }
            )
    
    return programacion_id


def dividir_tarea_en_partes(asig: Dict, minutos_por_dia: int) -> List[Dict]:
    """Divide una tarea en partes si cruza límites de días"""
    inicio_min = asig['inicio']
    fin_min = asig['fin']
    duracion_total = fin_min - inicio_min
    
    # Calcular días de inicio y fin
    dia_inicio = int(inicio_min // minutos_por_dia)
    dia_fin = int(fin_min // minutos_por_dia)
    
    # Si no cruza límites de días, devolver una sola parte
    if dia_inicio == dia_fin:
        return [{
            'inicio': inicio_min,
            'fin': fin_min,
            'duracion': duracion_total,
            'es_dividida': False,
            'parte_numero': 1
        }]
    
    # Si cruza límites, dividir en partes
    partes = []
    tiempo_actual = inicio_min
    parte_numero = 1
    
    while tiempo_actual < fin_min:
        # Calcular el fin de la parte actual
        dia_actual = int(tiempo_actual // minutos_por_dia)
        fin_dia_actual = (dia_actual + 1) * minutos_por_dia
        
        # El fin de la parte es el menor entre el fin del día y el fin total
        fin_parte = min(fin_dia_actual, fin_min)
        
        partes.append({
            'inicio': tiempo_actual,
            'fin': fin_parte,
            'duracion': fin_parte - tiempo_actual,
            'es_dividida': True,
            'parte_numero': parte_numero
        })
        
        tiempo_actual = fin_parte
        parte_numero += 1
    
    return partes


def inicializar_bd_si_necesario():
    """Inicializa BD si no existe, migra desde JSON o crea datos default"""
    try:
        db_manager.crear_tablas()
        
        maquinas = obtener_todas_maquinas()
        if maquinas:
            return False
        
        import os
        config_path = 'datos/configuracion.json'
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if 'recursos' in config and 'maquinas' in config['recursos']:
                    from modelos.database import crear_maquina
                    for maq in config['recursos']['maquinas']:
                        try:
                            crear_maquina(
                                id=maq['id'],
                                nombre=maq['nombre'],
                                capacidad=maq.get('capacidad', 1),
                                tiempo_setup=maq.get('tiempo_setup', 0),
                                costo_por_hora=config.get('costos', {}).get('costo_por_hora_maquina', {}).get(maq['id'], 50.0)
                            )
                        except Exception:
                            pass
                
                if 'recursos' in config and 'operadores' in config['recursos']:
                    from modelos.database import crear_operador
                    for op in config['recursos']['operadores']:
                        try:
                            crear_operador(
                                id=op['id'],
                                nombre=op['nombre'],
                                habilidades=op.get('habilidades', []),
                                costo_por_hora=config.get('costos', {}).get('costo_por_hora_operador', 25.0)
                            )
                        except Exception:
                            pass
                
                maquinas = obtener_todas_maquinas()
                if maquinas:
                    return True
            except Exception:
                pass
        
        from modelos.database import inicializar_datos_default
        inicializar_datos_default()
        return True
        
    except Exception as e:
        print(f"Error inicializando BD: {e}")
        return False

