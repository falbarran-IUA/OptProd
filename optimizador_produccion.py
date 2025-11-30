#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimizador de Programación de Producción
Utiliza Google OR-Tools para optimizar los horarios de producción
"""

import pandas as pd
import numpy as np
from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import json
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OptimizadorProduccion:
    """
    Clase principal para optimizar la programación de producción
    """
    
    def __init__(self, config_file='datos/configuracion.json'):
        """
        Inicializar el optimizador con configuración
        
        Args:
            config_file (str): Ruta al archivo de configuración
        """
        self.config = self._cargar_configuracion(config_file)
        self.model = None
        self.solver = None
        self.resultado = None
        
    def _cargar_configuracion(self, config_file):
        """Cargar configuración desde archivo JSON"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración {config_file} no encontrado. Usando configuración por defecto.")
            return self._configuracion_por_defecto()
    
    def _configuracion_por_defecto(self):
        """Configuración por defecto del sistema"""
        return {
            "horario_trabajo": {
                "inicio": "08:00",
                "fin": "18:00",
                "dias_laborales": [0, 1, 2, 3, 4]  # Lunes a Viernes
            },
            "recursos": {
                "maquinas": ["M1", "M2", "M3"],
                "operadores": ["OP1", "OP2", "OP3"]
            },
            "parametros_optimizacion": {
                "tiempo_maximo_resolucion": 30,  # segundos
                "objetivo": "minimizar_tiempo_total"
            }
        }
    
    def cargar_datos_tareas(self, archivo_tareas):
        """
        Cargar datos de tareas desde archivo Excel
        
        Args:
            archivo_tareas (str): Ruta al archivo Excel con las tareas
            
        Returns:
            pd.DataFrame: DataFrame con las tareas
        """
        try:
            df = pd.read_excel(archivo_tareas)
            # Asegurar que la duración sea entera
            if 'duracion' in df.columns:
                df['duracion'] = df['duracion'].astype(int)
            logger.info(f"Datos cargados: {len(df)} tareas")
            return df
        except Exception as e:
            logger.error(f"Error al cargar datos: {e}")
            return self._generar_datos_ejemplo()
    
    def _generar_datos_ejemplo(self):
        """Generar datos de ejemplo para demostración"""
        tareas = [
            {"id": "T1", "nombre": "Corte de Material", "duracion": 120, "tiempo_setup": 15, "maquina": "M1"},
            {"id": "T2", "nombre": "Soldadura", "duracion": 180, "tiempo_setup": 20, "maquina": "M2"},
            {"id": "T3", "nombre": "Pintura", "duracion": 90, "tiempo_setup": 10, "maquina": "M3"},
            {"id": "T4", "nombre": "Ensamblaje", "duracion": 150, "tiempo_setup": 25, "maquina": "M1"},
            {"id": "T5", "nombre": "Control Calidad", "duracion": 60, "tiempo_setup": 5, "maquina": "M2"},
        ]
        df = pd.DataFrame(tareas)
        # Asegurar que la duración sea entera
        df['duracion'] = df['duracion'].astype(int)
        df['tiempo_setup'] = df['tiempo_setup'].astype(int)
        return df
    
    def crear_modelo(self, tareas_df, num_operadores=None, dias_laborales=None, objetivo="Minimizar tiempo total", horas_por_dia=16, minutos_almuerzo=60):
        """Crea el modelo de optimización con OR-Tools"""
        logger.info("Creando modelo...")
        if dias_laborales:
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dias_laborales_num = [dias_semana.index(dia) for dia in dias_laborales if dia in dias_semana]
        
        # Crear modelo CP-SAT
        self.model = cp_model.CpModel()
        
        # Crear variables de decisión
        num_tareas = len(tareas_df)
        
        # Configuración semanal - NUEVA ESTRATEGIA
        if dias_laborales:
            # Mapeo de días a números
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dias_laborales_num = [dias_semana.index(dia) for dia in dias_laborales if dia in dias_semana]
            
            # NUEVA ESTRATEGIA: OR-Tools trabaja con minutos efectivos puros
            # Sin restricciones de días - optimiza libremente en el tiempo total
            minutos_por_dia_laboral = int(horas_por_dia * 60)  # Minutos efectivos por día
            dias_disponibles = len(dias_laborales_num)
            
            # Horizonte: tiempo total disponible (días × minutos efectivos por día)
            horizon = dias_disponibles * minutos_por_dia_laboral
            self.minutos_por_dia_laboral = minutos_por_dia_laboral  # Guardar para división posterior
            self.dias_laborales_num = dias_laborales_num  # Guardar para división posterior
        else:
            # Calcular un horizonte apropiado basado en la duración total de las tareas
            duracion_total = sum(int(tareas_df.iloc[i]['duracion']) for i in range(num_tareas))
            horizon = max(int(24 * 60), duracion_total * 2)  # Al menos 24 horas o 2x la duración total
            dias_laborales_num = list(range(7))  # Todos los días
        
        start_time = {}
        end_time = {}
        operator_assignment = {}
        machine_assignment = {}  # Nueva: asignación flexible de máquinas
        maquinas_permitidas_por_tarea = {}  # Lista de máquinas permitidas para cada tarea
        
        # Detectar todas las máquinas disponibles del DataFrame
        maquinas_disponibles = sorted(tareas_df['maquina'].unique().tolist())
        
        # Extraer todas las máquinas mencionadas (pueden estar en listas como "M1,M2")
        todas_las_maquinas = set()
        for maq in maquinas_disponibles:
            if maq in ['M?', 'CUALQUIERA', '?']:
                continue
            # Si contiene comas, es una lista
            if ',' in str(maq):
                todas_las_maquinas.update([m.strip() for m in str(maq).split(',')])
            else:
                todas_las_maquinas.add(str(maq))
        
        # Si no hay máquinas específicas, usar M1, M2, M3 como default
        if not todas_las_maquinas:
            todas_las_maquinas = {'M1', 'M2', 'M3'}
        
        maquinas_fijas = sorted(list(todas_las_maquinas))
        logger.info(f"Máquinas: {maquinas_fijas}")
        
        # Procesar máquinas permitidas para cada tarea
        for i in range(num_tareas):
            maquina_spec = tareas_df.iloc[i]['maquina']
            
            if maquina_spec in ['M?', 'CUALQUIERA', '?']:
                # Puede usar cualquier máquina
                maquinas_permitidas = list(range(len(maquinas_fijas)))
            elif ',' in str(maquina_spec):
                # Es una lista de máquinas permitidas (ej: "M1,M2,M3")
                maqs = [m.strip() for m in str(maquina_spec).split(',')]
                maquinas_permitidas = [maquinas_fijas.index(m) for m in maqs if m in maquinas_fijas]
                if not maquinas_permitidas:
                    logger.warning(f"Tarea {i} especifica máquinas que no existen: {maquina_spec}")
                    maquinas_permitidas = list(range(len(maquinas_fijas)))  # Fallback: todas
            else:
                # Máquina específica fija
                if maquina_spec in maquinas_fijas:
                    maquinas_permitidas = [maquinas_fijas.index(maquina_spec)]
                else:
                    logger.warning(f"Tarea {i} especifica máquina que no existe: {maquina_spec}")
                    maquinas_permitidas = list(range(len(maquinas_fijas)))  # Fallback: todas
            
            maquinas_permitidas_por_tarea[i] = maquinas_permitidas
            # Tarea puede usar: {[maquinas_fijas[m] for m in maquinas_permitidas]}
        
        for i in range(num_tareas):
            start_time[i] = self.model.NewIntVar(0, horizon, f'start_time_{i}')
            end_time[i] = self.model.NewIntVar(0, horizon, f'end_time_{i}')
            if num_operadores:
                operator_assignment[i] = self.model.NewIntVar(0, num_operadores - 1, f'operator_{i}')
            
            # Asignación flexible de máquina restringida a las permitidas
            if len(maquinas_permitidas_por_tarea[i]) == 1:
                # Solo una máquina permitida - fijar el valor
                machine_assignment[i] = maquinas_permitidas_por_tarea[i][0]
            else:
                # Múltiples máquinas permitidas - variable
                min_maq = min(maquinas_permitidas_por_tarea[i])
                max_maq = max(maquinas_permitidas_por_tarea[i])
                machine_assignment[i] = self.model.NewIntVar(min_maq, max_maq, f'machine_{i}')
                # Agregar restricción: solo valores permitidos
                self.model.AddAllowedAssignments([machine_assignment[i]], [(m,) for m in maquinas_permitidas_por_tarea[i]])
        
        # Restricciones básicas
        for i in range(num_tareas):
            duracion = int(tareas_df.iloc[i]['duracion'])  # Asegurar que sea entero
            tiempo_setup = int(tareas_df.iloc[i].get('tiempo_setup', 0))  # Tiempo de preparación
            duracion_total = duracion + tiempo_setup  # Duración total incluye setup
            # Restricción: tiempo de fin = tiempo de inicio + duración total
            self.model.Add(end_time[i] == start_time[i] + duracion_total)
            
            # NUEVA ESTRATEGIA: Sin restricciones de días
            # OR-Tools optimiza libremente en el tiempo total disponible
            # La división en días se hace después en el post-procesamiento
        
        # No superposición en máquinas
        logger.info("Restricciones de máquinas...")
        
        for i in range(num_tareas):
            for j in range(i + 1, num_tareas):
                # Crear variable: ¿están en la misma máquina?
                same_machine = self.model.NewBoolVar(f'same_machine_{i}_{j}')
                
                # Verificar máquinas especificadas en Excel
                maquina_i_especificada = tareas_df.iloc[i]['maquina']
                maquina_j_especificada = tareas_df.iloc[j]['maquina']
                
                # Determinar si ambas tienen máquina fija y es la misma
                # NO considerar flexibles las que tienen comas (ej: M1,M2)
                maquina_i_es_flexible = maquina_i_especificada in ['M?', 'CUALQUIERA', '?'] or ',' in str(maquina_i_especificada)
                maquina_j_es_flexible = maquina_j_especificada in ['M?', 'CUALQUIERA', '?'] or ',' in str(maquina_j_especificada)
                
                ambas_misma_fija = (maquina_i_especificada == maquina_j_especificada and 
                                   not maquina_i_es_flexible and not maquina_j_es_flexible)
                
                # Si ambas están en la misma máquina FIJA, forzar same_machine = 1
                if ambas_misma_fija:
                    self.model.Add(same_machine == 1)
                    pass
                else:
                    self.model.Add(machine_assignment[i] == machine_assignment[j]).OnlyEnforceIf(same_machine)
                    self.model.Add(machine_assignment[i] != machine_assignment[j]).OnlyEnforceIf(same_machine.Not())
                
                # Si están en la misma máquina, una debe ir antes que la otra
                task_i_before_j = self.model.NewBoolVar(f'task_{i}_before_{j}')
                task_j_before_i = self.model.NewBoolVar(f'task_{j}_before_{i}')
                
                # Solo una puede ir antes que la otra, y solo si están en la misma máquina
                self.model.Add(task_i_before_j + task_j_before_i == 1).OnlyEnforceIf(same_machine)
                
                # Si NO están en la misma máquina, no hay restricción de orden
                self.model.Add(task_i_before_j == 0).OnlyEnforceIf(same_machine.Not())
                self.model.Add(task_j_before_i == 0).OnlyEnforceIf(same_machine.Not())
                
                # Restricciones temporales
                self.model.Add(end_time[i] <= start_time[j]).OnlyEnforceIf(task_i_before_j)
                self.model.Add(end_time[j] <= start_time[i]).OnlyEnforceIf(task_j_before_i)
        
        # Restricción: no superposición para operadores (si se especifican)
        if num_operadores:
            for i in range(num_tareas):
                for j in range(i + 1, num_tareas):
                    # Variable booleana: ¿mismo operador?
                    same_operator = self.model.NewBoolVar(f'same_op_{i}_{j}')
                    self.model.Add(operator_assignment[i] == operator_assignment[j]).OnlyEnforceIf(same_operator)
                    self.model.Add(operator_assignment[i] != operator_assignment[j]).OnlyEnforceIf(same_operator.Not())

                    # Si están en el mismo operador, una debe ir antes que la otra
                    before = self.model.NewBoolVar(f'before_{i}_{j}')
                    after = self.model.NewBoolVar(f'after_{i}_{j}')
                    self.model.Add(end_time[i] <= start_time[j]).OnlyEnforceIf(before)
                    self.model.Add(end_time[j] <= start_time[i]).OnlyEnforceIf(after)
                    # Solo una puede ir antes que la otra si están en el mismo operador
                    self.model.Add(before + after == same_operator)
        
        # Restricciones de precedencia: respetar orden lógico de tareas del mismo trabajo
        logger.info("Restricciones de precedencia...")
        
        # Agrupar tareas por trabajo
        trabajos = {}
        for i in range(num_tareas):
            tarea = tareas_df.iloc[i]
            # Extraer el trabajo del campo 'trabajo' del DataFrame
            # Si no existe, intentar extraer del ID (ej: "A1" -> "A")
            if 'trabajo' in tarea and pd.notna(tarea['trabajo']):
                trabajo_id = str(tarea['trabajo'])
            else:
                trabajo_id = tarea['id'][0] if len(tarea['id']) > 0 else None
            
            if trabajo_id:
                if trabajo_id not in trabajos:
                    trabajos[trabajo_id] = []
                trabajos[trabajo_id].append((i, tarea))
        
        # Para cada trabajo, ordenar por subíndice numérico y agregar restricciones de precedencia
        for trabajo_id, tareas_trabajo in trabajos.items():
            if len(tareas_trabajo) > 1:
                # Ordenar por subíndice numérico (ej: A1, A2, T1-1, T1-2)
                def extraer_subindice(tarea_tuple):
                    tarea_id = tarea_tuple[1]['id']
                    # Manejar IDs con guión (ej: "T1-1", "T1-2") o sin guión (ej: "A1", "A2")
                    if '-' in tarea_id:
                        # Extraer último número después del guión
                        match = re.search(r'-(\d+)$', tarea_id)
                        return int(match.group(1)) if match else 0
                    else:
                        # Extraer el número del final del ID
                        match = re.search(r'\d+', tarea_id)
                        return int(match.group()) if match else 0
                
                tareas_ordenadas = sorted(tareas_trabajo, key=extraer_subindice)
                # Trabajo {trabajo_id}: {[t[1]['id'] for t in tareas_ordenadas]}
                
                # Agregar restricción: cada tarea debe terminar antes de que comience la siguiente
                for k in range(len(tareas_ordenadas) - 1):
                    tarea_actual_idx = tareas_ordenadas[k][0]
                    tarea_siguiente_idx = tareas_ordenadas[k + 1][0]
                    
                    tarea_actual = tareas_ordenadas[k][1]
                    tarea_siguiente = tareas_ordenadas[k + 1][1]
                    
                    # La tarea actual debe terminar antes de que comience la siguiente
                    self.model.Add(end_time[tarea_actual_idx] <= start_time[tarea_siguiente_idx])
                    pass
        
        logger.info(f"Objetivo: {objetivo}")
        
        if objetivo == "Minimizar tiempo total":
            makespan = self.model.NewIntVar(0, horizon, 'makespan')
            for i in range(num_tareas):
                self.model.Add(makespan >= end_time[i])
            self.model.Minimize(makespan)
            self.objetivo_tipo = "makespan"
            
        elif objetivo == "Maximizar utilización":
            makespan = self.model.NewIntVar(0, horizon, 'makespan')
            for i in range(num_tareas):
                self.model.Add(makespan >= end_time[i])
            
            num_maquinas = len(maquinas_fijas)
            
            if num_maquinas > 1:
                tiempos_maquinas = []
                
                # Crear variable de tiempo para cada máquina REAL
                for idx_maquina in range(num_maquinas):
                    tiempo_maquina = self.model.NewIntVar(0, horizon, f'tiempo_maq_{idx_maquina}')
                    
                    # Para cada tarea, si se asigna a esta máquina, agregar su tiempo final
                    for i in range(num_tareas):
                        # Variable: ¿la tarea i se asigna a esta máquina?
                        en_esta_maquina = self.model.NewBoolVar(f'en_maq_{idx_maquina}_{i}')
                        self.model.Add(machine_assignment[i] == idx_maquina).OnlyEnforceIf(en_esta_maquina)
                        
                        # Si está en esta máquina, su tiempo contribuye al tiempo total de la máquina
                        self.model.Add(tiempo_maquina >= end_time[i]).OnlyEnforceIf(en_esta_maquina)
                    
                    tiempos_maquinas.append(tiempo_maquina)
                
                # Minimizar el máximo desbalance entre máquinas
                tiempo_max = self.model.NewIntVar(0, horizon, 'tiempo_max')
                tiempo_min = self.model.NewIntVar(0, horizon, 'tiempo_min')
                for tm in tiempos_maquinas:
                    self.model.Add(tiempo_max >= tm)
                    self.model.Add(tiempo_min <= tm)
                
                # Objetivo: minimizar desbalance + makespan
                objetivo_utilizacion = self.model.NewIntVar(0, horizon * 100, 'obj_util')
                self.model.Add(objetivo_utilizacion == makespan * 5 + (tiempo_max - tiempo_min) * 10)
                self.model.Minimize(objetivo_utilizacion)
            else:
                self.model.Minimize(makespan)
            self.objetivo_tipo = "utilizacion"
            
        elif objetivo == "Minimizar costos":
            makespan = self.model.NewIntVar(0, horizon, 'makespan')
            for i in range(num_tareas):
                self.model.Add(makespan >= end_time[i])
            
            tiempo_total_ocupacion = self.model.NewIntVar(0, horizon * 1000, 'tiempo_total_ocupacion')
            suma_tiempos = []
            
            maquinas = tareas_df['maquina'].unique()
            for maquina in maquinas:
                tareas_maquina = tareas_df[tareas_df['maquina'] == maquina].index.tolist()
                if tareas_maquina:
                    tiempo_ocupacion_maquina = self.model.NewIntVar(0, horizon, f'tiempo_maq_{maquina}')
                    for i in tareas_maquina:
                        self.model.Add(tiempo_ocupacion_maquina >= end_time[i])
                    suma_tiempos.append(tiempo_ocupacion_maquina)
            
            if suma_tiempos:
                self.model.Add(tiempo_total_ocupacion == sum(suma_tiempos))
                self.model.Minimize(tiempo_total_ocupacion)
            else:
                self.model.Minimize(makespan)
            self.objetivo_tipo = "costos"
            
        elif objetivo == "Balanceado":
            makespan = self.model.NewIntVar(0, horizon, 'makespan')
            for i in range(num_tareas):
                self.model.Add(makespan >= end_time[i])
            
            tiempo_ocioso_total = self.model.NewIntVar(0, horizon * num_tareas, 'tiempo_ocioso_total')
            suma_tiempo_ocioso = []
            
            maquinas = tareas_df['maquina'].unique()
            for maquina in maquinas:
                tareas_maquina = tareas_df[tareas_df['maquina'] == maquina].index.tolist()
                if len(tareas_maquina) > 1:
                    tiempo_trabajo_maquina = sum(tareas_df.iloc[i]['duracion'] for i in tareas_maquina)
                    tiempo_total_maquina = self.model.NewIntVar(0, horizon, f'tiempo_total_{maquina}')
                    
                    for i in tareas_maquina:
                        self.model.Add(tiempo_total_maquina >= end_time[i])
                    
                    tiempo_ocioso_maquina = self.model.NewIntVar(0, horizon, f'tiempo_ocioso_{maquina}')
                    self.model.Add(tiempo_ocioso_maquina == tiempo_total_maquina - tiempo_trabajo_maquina)
                    suma_tiempo_ocioso.append(tiempo_ocioso_maquina)
            
            if suma_tiempo_ocioso:
                self.model.Add(tiempo_ocioso_total == sum(suma_tiempo_ocioso))
                objetivo_balanceado = self.model.NewIntVar(0, horizon * 1000, 'objetivo_balanceado')
                self.model.Add(objetivo_balanceado == makespan * 7 + tiempo_ocioso_total * 3)
                self.model.Minimize(objetivo_balanceado)
            else:
                self.model.Minimize(makespan)
            self.objetivo_tipo = "balanceado"
            
        else:
            # Fallback a makespan
            makespan = self.model.NewIntVar(0, horizon, 'makespan')
            for i in range(num_tareas):
                self.model.Add(makespan >= end_time[i])
            self.model.Minimize(makespan)
            self.objetivo_tipo = "makespan"
        
        # Guardar referencias a las variables para uso posterior
        self.start_time = start_time
        self.end_time = end_time
        self.makespan = makespan
        self.operator_assignment = operator_assignment if num_operadores else None
        self.machine_assignment = machine_assignment  # Asignación flexible de máquinas
        self.maquinas_fijas = maquinas_fijas  # Lista de máquinas disponibles
        self.day_assignment = None  # Ya no usamos asignación de días en el optimizador
        self.dias_laborales = dias_laborales
        self.num_tareas = num_tareas
        self.horizon = horizon
        
        # Crear mapeo de índices a IDs reales de tareas
        self.tarea_ids = {}
        for i in range(num_tareas):
            self.tarea_ids[i] = tareas_df.iloc[i]['id']
        
        logger.info("Modelo creado")
    
    def resolver(self):
        """
        Resolver el modelo de optimización
        
        Returns:
            dict: Resultado de la optimización
        """
        logger.info("Resolviendo...")
        
        # Crear solver
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.config["parametros_optimizacion"]["tiempo_maximo_resolucion"]
        
        # Configurar estrategia de búsqueda según el objetivo
        if self.objetivo_tipo == "utilizacion":
            # Para balance de carga, usar estrategia diferente
            self.solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        elif self.objetivo_tipo == "costos":
            # Para costos, enfocarse en decisiones de secuenciación
            self.solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        
        # Resolver
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"Solución encontrada en {self.solver.WallTime():.2f}s")
            
            # Extraer resultados
            solucion_detallada = self._extraer_solucion()
            
            # Calcular el makespan real desde la programación extraída
            # Esto es el tiempo de la última tarea que termina
            makespan_real = solucion_detallada.get('tiempo_total', 0)
            
            self.resultado = {
                'status': 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
                'tiempo_resolucion': self.solver.WallTime(),
                'valor_objetivo': makespan_real,  # Usar makespan real calculado desde la programación
                'solucion': solucion_detallada
            }
            
            return self.resultado
        else:
            logger.error("No se encontró solución")
            return {'status': 'INFEASIBLE', 'error': 'No se encontró solución factible'}
    
    def _extraer_solucion(self):
        """Extraer la solución del modelo resuelto"""
        # Validaciones mínimas sin depender de self.resultado
        if not hasattr(self, 'start_time') or not hasattr(self, 'end_time'):
            return {'tiempo_total': self.solver.ObjectiveValue() if hasattr(self, 'solver') else 0.0, 'programacion': []}
        
        try:
            # Extraer tiempos de inicio y fin para cada tarea
            programacion = []
            for i in range(len(self.start_time)):
                start_val = self.solver.Value(self.start_time[i])
                end_val = self.solver.Value(self.end_time[i])
                
                # Obtener el ID real de la tarea
                tarea_id_real = self.tarea_ids.get(i, f"T{i}")
                
                # Calcular el día basándose en los minutos efectivos (POST-PROCESAMIENTO)
                dia_calculado = 0
                if hasattr(self, 'minutos_por_dia_laboral') and self.minutos_por_dia_laboral > 0:
                    dia_calculado = start_val // self.minutos_por_dia_laboral
                
                # Obtener máquina asignada
                maquina_asignada = "N/A"
                if hasattr(self, 'machine_assignment') and i in self.machine_assignment:
                    try:
                        machine_val = self.solver.Value(self.machine_assignment[i])
                        if hasattr(self, 'maquinas_fijas') and machine_val < len(self.maquinas_fijas):
                            maquina_asignada = self.maquinas_fijas[machine_val]
                    except Exception as e:
                        logger.warning(f"No se pudo obtener máquina para tarea {i}: {e}")
                
                tarea_info = {
                    'tarea_id': tarea_id_real,
                    'tarea_indice': i,
                    'inicio': start_val,
                    'fin': end_val,
                    'duracion': end_val - start_val,
                    'dia': dia_calculado,
                    'maquina': maquina_asignada
                }
                
                # Agregar información del operador si está disponible
                if hasattr(self, 'operator_assignment') and self.operator_assignment and i in self.operator_assignment:
                    try:
                        operator_val = self.solver.Value(self.operator_assignment[i])
                        tarea_info['operador'] = f"OP{operator_val + 1}"
                    except Exception as e:
                        logger.warning(f"No se pudo obtener operador para tarea {i}: {e}")
                        tarea_info['operador'] = "N/A"
                else:
                    tarea_info['operador'] = "N/A"
                
                # El día ya se calculó arriba en el post-procesamiento
                # Tarea {tarea_id_real}: día {dia_calculado}, tiempo {start_val}-{end_val}
                
                programacion.append(tarea_info)
            
            # Calcular el makespan real de la solución (el tiempo de la última tarea)
            if programacion:
                makespan_real = max(t['fin'] for t in programacion)
            else:
                makespan_real = 0
            
            return {
                'tiempo_total': makespan_real,  # Usar makespan real, no valor artificial
                'programacion': programacion
            }
        except Exception as e:
            logger.warning(f"No se pudo extraer solución detallada: {e}")
            # Calcular makespan real si está disponible
            if hasattr(self, 'makespan'):
                makespan_real = self.solver.Value(self.makespan) if hasattr(self, 'solver') else 0
            else:
                makespan_real = self.solver.ObjectiveValue() if hasattr(self, 'solver') else 0
            return {
                'tiempo_total': makespan_real,
                'programacion': []
            }
    
    def generar_reporte(self, archivo_salida=None):
        """
        Generar reporte de la optimización
        
        Args:
            archivo_salida (str): Ruta del archivo de salida (opcional)
        """
        if not self.resultado:
            logger.warning("No hay resultados para generar reporte")
            return
        
        reporte = f"""
        ========================================
        REPORTE DE OPTIMIZACIÓN DE PRODUCCIÓN
        ========================================
        
        Estado: {self.resultado['status']}
        Tiempo de resolución: {self.resultado['tiempo_resolucion']:.2f} segundos
        Tiempo total de producción: {self.resultado['valor_objetivo']} minutos
        
        Detalles de la programación:
        """
        
        if self.resultado['solucion'] and self.resultado['solucion']['programacion']:
            for tarea in self.resultado['solucion']['programacion']:
                reporte += f"\nTarea {tarea['tarea_id']}: "
                reporte += f"Inicio: {tarea['inicio']} min, "
                reporte += f"Fin: {tarea['fin']} min, "
                reporte += f"Duración: {tarea['duracion']} min"
                if 'operador' in tarea:
                    reporte += f", Operador: {tarea['operador']}"
        
        reporte += "\n\n========================================"
        
        print(reporte)
        
        if archivo_salida:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                f.write(reporte)
            logger.info(f"Reporte guardado en {archivo_salida}")


def main():
    """Función principal para ejecutar la optimización"""
    print("🚀 Iniciando Optimizador de Programación de Producción")
    print("=" * 60)
    
    # Crear optimizador
    optimizador = OptimizadorProduccion()
    
    # Cargar datos (usar datos de ejemplo si no hay archivo)
    try:
        tareas = optimizador.cargar_datos_tareas('datos/tareas_ejemplo.xlsx')
    except:
        tareas = optimizador._generar_datos_ejemplo()
    
    print(f"📋 Tareas cargadas: {len(tareas)}")
    print(tareas)
    print()
    
    # Crear y resolver modelo
    optimizador.crear_modelo(tareas, num_operadores=3)  # Usar 3 operadores por defecto
    resultado = optimizador.resolver()
    
    # Generar reporte
    optimizador.generar_reporte()
    
    print("✅ Optimización completada!")


if __name__ == "__main__":
    main() 