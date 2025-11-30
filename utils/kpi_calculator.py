#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculadora de KPIs Industriales
Calcula métricas de eficiencia, utilización, cumplimiento, etc.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class KPIExporter:
    """Calculadora de KPIs industriales para producción"""
    
    def __init__(self, dias_laborales=5, minutos_por_dia=600, num_maquinas=3):
        """
        Inicializar calculadora de KPIs ERP
        
        Args:
            dias_laborales: Días laborales por semana (default: 5)
            minutos_por_dia: Minutos productivos por día (default: 600 = 10h)
            num_maquinas: Número de máquinas disponibles
        """
        self.dias_laborales = dias_laborales
        self.minutos_por_dia = minutos_por_dia
        self.num_maquinas = num_maquinas
        self.capacidad_semanal_total = dias_laborales * minutos_por_dia * num_maquinas
        
    def calcular_utilizacion_maquina(self, tiempo_productivo: int, 
                                    tiempo_ocioso: int = None,
                                    tiempo_setup: int = 0) -> Dict[str, float]:
        """
        Calcular utilización de una máquina
        
        Args:
            tiempo_productivo: Minutos productivos (real)
            tiempo_ocioso: Minutos ociosos (opcional)
            tiempo_setup: Minutos de setup
        
        Returns:
            Dict con utilización total y por tipo
        """
        if tiempo_ocioso is None:
            # Calcular desde tiempo disponible
            tiempo_total_disponible = self.dias_laborales * self.minutos_por_dia
            tiempo_ocioso = tiempo_total_disponible - tiempo_productivo - tiempo_setup
        
        tiempo_total = tiempo_productivo + tiempo_ocioso + tiempo_setup
        
        if tiempo_total == 0:
            return {
                'utilizacion_total': 0.0,
                'utilizacion_productiva': 0.0,
                'utilizacion_setup': 0.0,
                'utilizacion_ociosa': 100.0,
                'tiempo_total': 0
            }
        
        return {
            'utilizacion_total': (tiempo_productivo + tiempo_setup) / tiempo_total * 100,
            'utilizacion_productiva': tiempo_productivo / tiempo_total * 100,
            'utilizacion_setup': tiempo_setup / tiempo_total * 100,
            'utilizacion_ociosa': tiempo_ocioso / tiempo_total * 100,
            'tiempo_total': tiempo_total,
            'tiempo_productivo': tiempo_productivo,
            'tiempo_ocioso': tiempo_ocioso,
            'tiempo_setup': tiempo_setup
        }
    
    def calcular_oee(self, disponibilidad: float, rendimiento: float, 
                     calidad: float) -> float:
        """
        Calcular OEE (Overall Equipment Effectiveness)
        
        Args:
            disponibilidad: % de tiempo disponible (0-100)
            rendimiento: % de rendimiento vs teórico (0-100)
            calidad: % de calidad/firts pass (0-100)
        
        Returns:
            OEE total (0-100)
        """
        return disponibilidad * rendimiento * calidad / 10000
    
    def calcular_desviaciones(self, ejecuciones: List[Dict], semana_produccion: int = None, 
                             anio: int = None) -> Dict:
        """
        Calcular estadísticas de desviaciones usando la misma lógica que Rendimiento
        
        Compara duraciones TOTALES (ambas incluyen almuerzo si cruza mediodía)
        
        Args:
            ejecuciones: Lista de ejecuciones con inicio_hora, fin_hora, dia_semana
            semana_produccion: Semana ISO para construir datetime planificado
            anio: Año para construir datetime planificado
        
        Returns:
            Dict con estadísticas de desviaciones
        """
        if not ejecuciones:
            return {
                'desviacion_promedio': 0.0,
                'desviacion_mediana': 0.0,
                'desviacion_maxima': 0.0,
                'desviacion_minima': 0.0,
                'desviaciones_positivas': 0,
                'desviaciones_negativas': 0,
                'desviaciones_cero': 0,
                'desviacion_std': 0.0
            }
        
        # Calcular desviaciones usando la misma lógica que calcular_cumplimiento_plazos
        # Comparar duraciones TOTALES (ambas incluyen almuerzo si cruza mediodía)
        desviaciones_list = []
        for e in ejecuciones:
            desv = None
            
            # Obtener datos necesarios (misma lógica que calcular_cumplimiento_plazos)
            inicio_hora = e.get('inicio_hora')  # HH:MM planificado
            fin_hora = e.get('fin_hora')        # HH:MM planificado
            dia_semana = e.get('dia_semana')     # 0=Lunes, 1=Martes, etc.
            dur_real_bd = e.get('duracion_real')  # Duración total real (incluye almuerzo)
            tiempo_paradas = e.get('tiempo_paradas', 0) or 0
            
            # PRIORIDAD 1: Calcular duración planificada TOTAL desde inicio_hora y fin_hora
            # Esto incluye almuerzo si la tarea cruza mediodía, igual que duracion_real del usuario
            if inicio_hora and fin_hora and dia_semana is not None and semana_produccion and anio:
                try:
                    inicio_plan_dt = self._construir_datetime_planificado(
                        inicio_hora, dia_semana, semana_produccion, anio
                    )
                    fin_plan_dt = self._construir_datetime_planificado(
                        fin_hora, dia_semana, semana_produccion, anio
                    )
                    
                    if inicio_plan_dt and fin_plan_dt:
                        # Duración planificada TOTAL (incluye almuerzo si cruza mediodía)
                        dur_plan_total = (fin_plan_dt - inicio_plan_dt).total_seconds() / 60
                        
                        # Usar duracion_real de BD (ya incluye almuerzo)
                        if dur_real_bd is not None:
                            dur_real_total = dur_real_bd
                            # Comparar: duración real total (sin paradas) vs duración planificada total
                            # Ambas incluyen almuerzo si cruza mediodía
                            dur_real_sin_paradas = max(0, dur_real_total - tiempo_paradas)
                            desv = dur_real_sin_paradas - dur_plan_total
                except Exception:
                    desv = None
            
            # PRIORIDAD 2: Fallback si no hay datos de horas
            if desv is None:
                # Usar desviacion_duracion de BD si está disponible (ya calculada correctamente)
                desv = e.get('desviacion_duracion')
                if desv is None:
                    # Último fallback: comparar efectivas (no ideal, pero mejor que nada)
                    dur_plan_efectiva = e.get('duracion_planificada')
                    if dur_plan_efectiva is not None and dur_real_bd is not None:
                        dur_real_sin_paradas = max(0, dur_real_bd - tiempo_paradas)
                        desv = dur_real_sin_paradas - dur_plan_efectiva
                    else:
                        desv = 0  # Si no hay datos, asumir 0
            
            desviaciones_list.append(desv)
        
        if not desviaciones_list:
            return self._desviaciones_vacias()
        
        import statistics
        
        return {
            'desviacion_promedio': statistics.mean(desviaciones_list),
            'desviacion_mediana': statistics.median(desviaciones_list),
            'desviacion_maxima': max(desviaciones_list),
            'desviacion_minima': min(desviaciones_list),
            'desviaciones_positivas': len([d for d in desviaciones_list if d > 0]),
            'desviaciones_negativas': len([d for d in desviaciones_list if d < 0]),
            'desviaciones_cero': len([d for d in desviaciones_list if d == 0]),
            'desviacion_std': statistics.stdev(desviaciones_list) if len(desviaciones_list) > 1 else 0.0,
            'total_desviaciones': len(desviaciones_list)
        }
    
    def _desviaciones_vacias(self) -> Dict:
        """Retornar desviaciones vacías"""
        return {
            'desviacion_promedio': 0.0,
            'desviacion_mediana': 0.0,
            'desviacion_maxima': 0.0,
            'desviacion_minima': 0.0,
            'desviaciones_positivas': 0,
            'desviaciones_negativas': 0,
            'desviaciones_cero': 0,
            'desviacion_std': 0.0,
            'total_desviaciones': 0
        }
    
    def _construir_datetime_planificado(self, inicio_hora: str, dia_semana: int, 
                                       semana_produccion: int, anio: int) -> Optional[datetime]:
        """
        Construir datetime planificado desde hora HH:MM, día de semana y semana de producción
        
        Args:
            inicio_hora: Hora en formato HH:MM (ej: "08:00", "14:15")
            dia_semana: Día de semana (0=Lunes, 1=Martes, ..., 6=Domingo)
            semana_produccion: Número de semana ISO (1-53)
            anio: Año de producción
        
        Returns:
            datetime con la fecha y hora planificada, o None si hay error
        """
        if not inicio_hora or not isinstance(inicio_hora, str) or ':' not in inicio_hora:
            return None
        
        try:
            # Parsear hora
            h, m = map(int, inicio_hora.split(':'))
            
            # Calcular lunes de la semana ISO
            # ISO week: lunes de la semana es el día que contiene el 4 de enero de ese año
            # Calcular el primer día del año
            primer_dia = datetime(anio, 1, 1)
            
            # Día de la semana del 1 de enero (0=Lunes, 6=Domingo)
            dia_1_enero = primer_dia.weekday()
            
            # Calcular el lunes de la semana 1
            # Si el 1 de enero es lunes (0), el lunes de semana 1 es el 1 de enero
            # Si el 1 de enero es martes (1), el lunes de semana 1 es el 31 de diciembre del año anterior
            # ISO week: semana 1 contiene el 4 de enero
            # Calcular lunes de la semana que contiene el 4 de enero
            fecha_semana_1 = datetime(anio, 1, 4)
            lunes_semana_1 = fecha_semana_1 - timedelta(days=fecha_semana_1.weekday())
            
            # Calcular lunes de la semana de producción
            semanas_desde_semana_1 = semana_produccion - 1
            lunes_semana_produccion = lunes_semana_1 + timedelta(weeks=semanas_desde_semana_1)
            
            # Agregar días hasta el día de la semana deseado
            fecha_completa = lunes_semana_produccion + timedelta(days=dia_semana)
            
            # Construir datetime final con la hora
            return datetime.combine(fecha_completa.date(), datetime.min.time().replace(hour=h, minute=m))
            
        except Exception as e:
            logger.warning(f"Error construyendo datetime planificado: {e}")
            return None
    
    def calcular_cumplimiento_plazos(self, ejecuciones: List[Dict], tolerancia_minutos: int = 5,
                                     semana_produccion: int = None, anio: int = None) -> Dict:
        """
        Calcular cumplimiento de plazos (OTIF - On Time In Full)
        
        Compara horas planificadas (datetime) vs horas reales (datetime) usando
        los campos ya calculados: inicio_hora, fin_hora, dia_semana
        
        Args:
            ejecuciones: Lista de ejecuciones con inicio_hora, fin_hora, dia_semana, inicio_real, fin_real
            tolerancia_minutos: Tolerancia en minutos para considerar "a tiempo" (default: 5)
            semana_produccion: Semana de producción ISO (opcional, se puede obtener de ejecuciones)
            anio: Año de producción (opcional, se puede obtener de ejecuciones)
        
        Returns:
            Dict con métricas de cumplimiento
        """
        if not ejecuciones:
            return {
                'otif_porcentaje': 0.0,
                'tareas_a_tiempo': 0,
                'tareas_retrasadas': 0,
                'tareas_adelantadas': 0,
                'total_tareas': 0,
                'tolerancia_usada': tolerancia_minutos
            }
        
        total = len(ejecuciones)
        a_tiempo = 0
        retrasadas = 0
        adelantadas = 0
        
        # Si no se proporciona semana/año, intentar obtenerla de las ejecuciones
        # (típicamente todas las ejecuciones pertenecen a la misma programación)
        if semana_produccion is None or anio is None:
            # Buscar en alguna ejecución si tiene información de programación
            # Por ahora usar valores por defecto si no están disponibles
            pass
        
        for ejec in ejecuciones:
            # Calcular desviación comparando duraciones TOTALES (ambas incluyen almuerzo si cruza mediodía)
            # duracion_real del usuario YA incluye almuerzo, entonces debemos comparar con duración planificada TOTAL
            
            desv = None
            
            # Obtener datos necesarios
            inicio_hora = ejec.get('inicio_hora')  # HH:MM planificado
            fin_hora = ejec.get('fin_hora')        # HH:MM planificado
            dia_semana = ejec.get('dia_semana')     # 0=Lunes, 1=Martes, etc.
            inicio_real = ejec.get('inicio_real')   # datetime real
            fin_real = ejec.get('fin_real')        # datetime real
            dur_real_bd = ejec.get('duracion_real')  # Duración total real (incluye almuerzo)
            tiempo_paradas = ejec.get('tiempo_paradas', 0) or 0
            
            # PRIORIDAD 1: Calcular duración planificada TOTAL desde inicio_hora y fin_hora
            # Esto incluye almuerzo si la tarea cruza mediodía, igual que duracion_real del usuario
            if inicio_hora and fin_hora and dia_semana is not None and semana_produccion and anio:
                try:
                    inicio_plan_dt = self._construir_datetime_planificado(
                        inicio_hora, dia_semana, semana_produccion, anio
                    )
                    fin_plan_dt = self._construir_datetime_planificado(
                        fin_hora, dia_semana, semana_produccion, anio
                    )
                    
                    if inicio_plan_dt and fin_plan_dt:
                        # Duración planificada TOTAL (incluye almuerzo si cruza mediodía)
                        dur_plan_total = (fin_plan_dt - inicio_plan_dt).total_seconds() / 60
                        
                        # Si tenemos duracion_real de BD, usarla (ya incluye almuerzo)
                        # Si no, calcular desde datetime real
                        if dur_real_bd is not None:
                            dur_real_total = dur_real_bd
                        elif inicio_real and fin_real:
                            # Convertir a datetime si son strings
                            if isinstance(inicio_real, str):
                                inicio_real_dt = datetime.fromisoformat(inicio_real.replace('Z', '+00:00'))
                            else:
                                inicio_real_dt = inicio_real
                            
                            if isinstance(fin_real, str):
                                fin_real_dt = datetime.fromisoformat(fin_real.replace('Z', '+00:00'))
                            else:
                                fin_real_dt = fin_real
                            
                            if isinstance(inicio_real_dt, datetime) and isinstance(fin_real_dt, datetime):
                                dur_real_total = (fin_real_dt - inicio_real_dt).total_seconds() / 60
                            else:
                                dur_real_total = None
                        else:
                            dur_real_total = None
                        
                        if dur_real_total is not None:
                            # Comparar: duración real total (sin paradas) vs duración planificada total
                            # Ambas incluyen almuerzo si cruza mediodía
                            dur_real_sin_paradas = max(0, dur_real_total - tiempo_paradas)
                            desv = dur_real_sin_paradas - dur_plan_total
                            
                            # DEBUG: Log para verificar cálculo
                            if abs(desv) > tolerancia_minutos:
                                logger.debug(f"Tarea {ejec.get('tarea_nombre', 'N/A')}: "
                                            f"dur_real_total={dur_real_total}, paradas={tiempo_paradas}, "
                                            f"dur_sin_paradas={dur_real_sin_paradas}, "
                                            f"dur_plan_total={dur_plan_total}, desv={desv}")
                except Exception as e:
                    logger.warning(f"Error calculando desviación desde horas: {e}")
                    desv = None
            
            # PRIORIDAD 2: Fallback a usar duraciones de BD (si no hay inicio_hora/fin_hora)
            if desv is None:
                dur_plan_bd = ejec.get('duracion_planificada')  # Efectiva sin almuerzo
                
                if dur_plan_bd is not None and dur_real_bd is not None:
                    # Comparar efectivas: real sin paradas vs planificada efectiva
                    dur_real_sin_paradas = max(0, dur_real_bd - tiempo_paradas)
                    desv = dur_real_sin_paradas - dur_plan_bd
                    
                    # DEBUG
                    if abs(desv) > tolerancia_minutos:
                        logger.debug(f"Tarea {ejec.get('tarea_nombre', 'N/A')}: "
                                    f"FALLBACK - dur_real={dur_real_bd}, dur_plan_efectiva={dur_plan_bd}, "
                                    f"desv={desv}")
            
            # Si después de todos los intentos no tenemos desviación, considerar a tiempo
            if desv is None:
                desv = 0  # Si no hay datos, considerar a tiempo
            
            if desv == 0 or abs(desv) <= tolerancia_minutos:
                a_tiempo += 1
            elif desv > tolerancia_minutos:
                retrasadas += 1
            else:  # desv < -tolerancia_minutos
                adelantadas += 1
        
        return {
            'otif_porcentaje': (a_tiempo / total * 100) if total > 0 else 0.0,
            'tareas_a_tiempo': a_tiempo,
            'tareas_retrasadas': retrasadas,
            'tareas_adelantadas': adelantadas,
            'total_tareas': total,
            'tolerancia_usada': tolerancia_minutos
        }
    
    def calcular_eficiencia_machines(self, ejecuciones: List[Dict]) -> Dict[str, Dict]:
        """
        Calcular eficiencia por máquina
        
        Args:
            ejecuciones: Lista de ejecuciones con maquina_usada y duraciones
        
        Returns:
            Dict con métricas por máquina
        """
        if not ejecuciones:
            return {}
        
        maquinas = {}
        
        # Calcular makespan real desde fechas de ejecución
        tiempos_inicio = []
        tiempos_fin = []
        for ejec in ejecuciones:
            inicio = ejec.get('inicio_real')
            fin = ejec.get('fin_real')
            
            # Convertir a datetime si es string o otro tipo
            if inicio:
                if isinstance(inicio, str):
                    try:
                        inicio = datetime.fromisoformat(inicio.replace('Z', '+00:00'))
                    except:
                        inicio = None
                if isinstance(inicio, datetime):
                    tiempos_inicio.append(inicio)
            
            if fin:
                if isinstance(fin, str):
                    try:
                        fin = datetime.fromisoformat(fin.replace('Z', '+00:00'))
                    except:
                        fin = None
                if isinstance(fin, datetime):
                    tiempos_fin.append(fin)
        
        # Acumular tiempos por máquina
        for ejec in ejecuciones:
            maq = ejec.get('maquina_usada') or ejec.get('maquina_planificada')
            if not maq:
                continue
            
            if maq not in maquinas:
                maquinas[maq] = {
                    'tiempo_productivo': 0,
                    'tiempo_planificado': 0,
                    'tiempo_setup': 0,
                    'num_tareas': 0
                }
            
            dur_real = ejec.get('duracion_real', 0)
            dur_plan = ejec.get('duracion_planificada', 0)
            
            maquinas[maq]['tiempo_productivo'] += dur_real
            maquinas[maq]['tiempo_planificado'] += dur_plan
            maquinas[maq]['tiempo_setup'] += ejec.get('tiempo_paradas', 0)  # Usar paradas como proxy de setup
            maquinas[maq]['num_tareas'] += 1
        
        # Calcular utilización para cada máquina usando CAPACIDAD TEÓRICA CONFIGURADA
        # Tiempo disponible = días laborales * minutos por día (efectivos, sin almuerzo)
        tiempo_disponible_maq = self.dias_laborales * self.minutos_por_dia
        
        for maq, data in maquinas.items():
            # Eficiencia = planificado / real
            data['eficiencia'] = (
                data['tiempo_planificado'] / data['tiempo_productivo'] * 100
                if data['tiempo_productivo'] > 0 else 100.0
            )
            
            # Calcular tiempo ocioso: capacidad teórica - tiempo usado
            tiempo_ocioso = max(0, tiempo_disponible_maq - data['tiempo_productivo'] - data['tiempo_setup'])
            
            data['tiempo_ocioso'] = tiempo_ocioso
            data['tiempo_total'] = tiempo_disponible_maq
            
            if tiempo_disponible_maq > 0:
                data['utilizacion_total'] = (
                    (data['tiempo_productivo'] + data['tiempo_setup']) / tiempo_disponible_maq * 100
                )
                data['utilizacion_productiva'] = (
                    data['tiempo_productivo'] / tiempo_disponible_maq * 100
                )
                data['utilizacion_setup'] = (
                    data['tiempo_setup'] / tiempo_disponible_maq * 100
                )
                data['utilizacion_ociosa'] = (
                    tiempo_ocioso / tiempo_disponible_maq * 100
                )
            else:
                data['utilizacion_total'] = 0.0
                data['utilizacion_productiva'] = 0.0
                data['utilizacion_setup'] = 0.0
                data['utilizacion_ociosa'] = 100.0
        
        return maquinas
    
    def _calcular_disponibilidad(self, ejecuciones: List[Dict]) -> float:
        """
        Calcular disponibilidad desde datos reales
        
        Disponibilidad = (Tiempo Real de Producción / Tiempo Planificado) × 100
        
        Mide el tiempo de producción real frente al tiempo de producción planificado.
        Se ve afectado por averías, paradas planificadas y cambios.
        
        Donde:
        - Tiempo Planificado = Suma de todas las duraciones planificadas
        - Tiempo Real de Producción = Tiempo Planificado - Tiempo de Paradas
        
        Args:
            ejecuciones: Lista de ejecuciones reales
            
        Returns:
            Disponibilidad en porcentaje (0-100)
        """
        if not ejecuciones:
            return 0.0
        
        # Calcular tiempo planificado total
        tiempo_planificado_total = sum(
            e.get('duracion_planificada', 0) 
            for e in ejecuciones 
            if e.get('duracion_planificada') is not None
        )
        
        # Calcular tiempo de paradas total (averías, paradas planificadas, cambios)
        tiempo_paradas_total = sum(
            e.get('tiempo_paradas', 0) 
            for e in ejecuciones 
            if e.get('tiempo_paradas') is not None
        )
        
        # Tiempo real de producción = tiempo planificado - paradas
        tiempo_produccion_real = max(0, tiempo_planificado_total - tiempo_paradas_total)
        
        # Disponibilidad = (Tiempo Real de Producción / Tiempo Planificado) × 100
        if tiempo_planificado_total > 0:
            disponibilidad = (tiempo_produccion_real / tiempo_planificado_total) * 100
            return min(100.0, max(0.0, disponibilidad))  # Asegurar rango 0-100
        else:
            # Fallback: asumir 100% si no hay tiempo planificado (caso ideal)
            return 100.0
    
    def _calcular_rendimiento(self, ejecuciones: List[Dict], semana_produccion: int = None, 
                              anio: int = None) -> float:
        """
        Calcular rendimiento desde datos reales
        
        ENFOQUE 2 (PYME): Comparar tiempos TOTALES (ambos incluyen almuerzo si cruza)
        
        Rendimiento = (Tiempo Planificado TOTAL / Tiempo Real TOTAL) × 100
        
        Args:
            ejecuciones: Lista de ejecuciones reales con inicio_hora, fin_hora, dia_semana
            semana_produccion: Semana ISO para construir datetime planificado
            anio: Año para construir datetime planificado
            
        Returns:
            Rendimiento en porcentaje (puede ser >100 si fue más rápido)
        """
        if not ejecuciones:
            return 0.0
        
        # PRIORIDAD: Calcular tiempo planificado TOTAL desde inicio_hora y fin_hora
        tiempo_planificado_total = 0
        tiempo_real_total = sum(
            e.get('duracion_real', 0) 
            for e in ejecuciones 
            if e.get('duracion_real') is not None
        )
        
        if semana_produccion and anio:
            # Calcular desde inicio_hora/fin_hora (incluye almuerzo si cruza)
            for ejec in ejecuciones:
                inicio_hora = ejec.get('inicio_hora')
                fin_hora = ejec.get('fin_hora')
                dia_semana = ejec.get('dia_semana')
                
                if inicio_hora and fin_hora and dia_semana is not None:
                    try:
                        inicio_plan_dt = self._construir_datetime_planificado(
                            inicio_hora, dia_semana, semana_produccion, anio
                        )
                        fin_plan_dt = self._construir_datetime_planificado(
                            fin_hora, dia_semana, semana_produccion, anio
                        )
                        
                        if inicio_plan_dt and fin_plan_dt:
                            # Duración planificada TOTAL (incluye almuerzo si cruza)
                            dur_plan_total = (fin_plan_dt - inicio_plan_dt).total_seconds() / 60
                            tiempo_planificado_total += dur_plan_total
                            continue
                    except Exception:
                        pass
        
        # FALLBACK: Si no se pudo calcular desde horas, usar duracion_planificada efectiva
        if tiempo_planificado_total == 0:
            tiempo_planificado_total = sum(
                e.get('duracion_planificada', 0) 
                for e in ejecuciones 
                if e.get('duracion_planificada') is not None
            )
        
        if tiempo_real_total > 0:
            # Rendimiento = qué tan cerca estuvo del planificado
            # Si real < planificado → rendimiento > 100%
            return (tiempo_planificado_total / tiempo_real_total) * 100
        else:
            return 100.0
    
    def _calcular_calidad(self, ejecuciones: List[Dict]) -> float:
        """
        Calcular calidad desde datos reales
        
        Calidad = (Tareas Sin Problemas / Total Tareas) × 100
        
        Args:
            ejecuciones: Lista de ejecuciones reales
            
        Returns:
            Calidad en porcentaje (0-100)
        """
        if not ejecuciones:
            return 0.0
        
        total = len(ejecuciones)
        tareas_sin_problemas = sum(
            1 for e in ejecuciones 
            if not e.get('problemas_encontrados') or 
               (isinstance(e.get('problemas_encontrados'), str) and 
                len(e.get('problemas_encontrados', '').strip()) == 0)
        )
        
        if total > 0:
            return (tareas_sin_problemas / total) * 100
        else:
            return 100.0
    
    def identificar_cuellos_botella(self, ejecuciones: List[Dict]) -> Optional[str]:
        """
        Identificar cuello de botella (máquina más utilizada)
        
        Args:
            ejecuciones: Lista de ejecuciones
        
        Returns:
            ID de la máquina con mayor utilización o None
        """
        maquinas = self.calcular_eficiencia_machines(ejecuciones)
        
        if not maquinas:
            return None
        
        # Encontrar máquina con mayor tiempo productivo
        max_tiempo = max(
            (data['tiempo_productivo'] for data in maquinas.values()),
            default=0
        )
        
        # Si hay alto uso (>85%), identificar cuello
        cuello = None
        for maq, data in maquinas.items():
            if data['utilizacion_total'] > 85 and data['tiempo_productivo'] == max_tiempo:
                cuello = maq
                break
        
        return cuello
    
    def calcular_metricas_completas(self, ejecuciones: List[Dict],
                                   programacion_id: str, semana_produccion: int = None,
                                   anio: int = None) -> Dict:
        """
        Calcular todas las métricas para una programación
        
        Args:
            ejecuciones: Lista de ejecuciones reales
            programacion_id: ID de la programación
            semana_produccion: Semana ISO (para cálculo correcto de rendimiento)
            anio: Año (para cálculo correcto de rendimiento)
        
        Returns:
            Dict completo con todas las métricas
        """
        # Desviaciones (usar misma lógica que Rendimiento)
        desviaciones = self.calcular_desviaciones(ejecuciones, semana_produccion=semana_produccion, anio=anio)
        
        # Cumplimiento (usar tolerancia de 5 min por defecto, pero configurable)
        cumplimiento = self.calcular_cumplimiento_plazos(ejecuciones, tolerancia_minutos=5,
                                                        semana_produccion=semana_produccion, anio=anio)
        
        # Eficiencia por máquina
        eficiencia_maquinas = self.calcular_eficiencia_machines(ejecuciones)
        
        # Cuello de botella
        cuello_botella = self.identificar_cuellos_botella(ejecuciones)
        
        # Calcular OEE desde datos reales
        disponibilidad = self._calcular_disponibilidad(ejecuciones)
        rendimiento = self._calcular_rendimiento(ejecuciones, semana_produccion=semana_produccion, anio=anio)
        calidad = self._calcular_calidad(ejecuciones)
        
        oee = self.calcular_oee(
            disponibilidad=disponibilidad,
            rendimiento=rendimiento,
            calidad=calidad
        )
        
        return {
            'programacion_id': programacion_id,
            'fecha_calculo': datetime.now(),
            'oee_global': round(oee, 2),
            'disponibilidad_oee': round(disponibilidad, 2),
            'rendimiento_oee': round(rendimiento, 2),
            'calidad_oee': round(calidad, 2),
            'throughput_semanal': len(ejecuciones),
            'lead_time_promedio': 0.0,  # Reutilizado para utilización global
            
            'utilizacion_maquinas': eficiencia_maquinas,
            'cuello_botella': cuello_botella,
            
            'otif_porcentaje': cumplimiento['otif_porcentaje'],
            'tareas_a_tiempo': cumplimiento['tareas_a_tiempo'],
            'tareas_retrasadas': cumplimiento['tareas_retrasadas'],
            
            'desviacion_promedio': desviaciones['desviacion_promedio'],
            'desviacion_maxima': desviaciones['desviacion_maxima'],
            
            'ejecuciones': ejecuciones,
            'total_tareas': len(ejecuciones)
        }
    
def main():
    """Test de la calculadora de KPIs"""
    calc = KPIExporter()
    
    # Datos de prueba
    ejecuciones = [
        {'maquina_usada': 'M1', 'duracion_real': 120, 'duracion_planificada': 100, 'desviacion_duracion': 20},
        {'maquina_usada': 'M1', 'duracion_real': 90, 'duracion_planificada': 95, 'desviacion_duracion': -5},
        {'maquina_usada': 'M2', 'duracion_real': 200, 'duracion_planificada': 180, 'desviacion_duracion': 20},
    ]
    
    metricas = calc.calcular_metricas_completas(ejecuciones, 'PROG001')
    print("Métricas calculadas:")
    print(f"OEE: {metricas['oee_global']}%")
    print(f"OTIF: {metricas['otif_porcentaje']}%")
    print(f"Desviación promedio: {metricas['desviacion_promedio']} min")
    print(f"Cuello de botella: {metricas['cuello_botella']}")


if __name__ == "__main__":
    main()



