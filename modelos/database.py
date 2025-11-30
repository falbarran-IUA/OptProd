#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capa de Persistencia - Optimizador de Producción v1.3
Operaciones CRUD y funciones de acceso a datos
"""

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging

from modelos.database_models import (
    Base, Maquina, Operador, Trabajo, Tarea,
    Programacion, TareaPlanificada, EjecucionReal,
    MetricaCalculada, ConfiguracionSistema,
    EstadoProgramacion, EstadoTarea
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================================

class DatabaseManager:
    """Gestor de conexiones a la base de datos"""
    
    def __init__(self, database_url: str = 'sqlite:///datos/produccion.db'):
        """
        Inicializar gestor de BD
        
        Args:
            database_url: URL de conexión (por defecto SQLite)
        """
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def crear_tablas(self):
        """Crear todas las tablas si no existen"""
        Base.metadata.create_all(self.engine)
        logger.info("✅ Tablas creadas/verificadas")
        
    def eliminar_tablas(self):
        """CUIDADO: Eliminar todas las tablas"""
        Base.metadata.drop_all(self.engine)
        logger.warning("⚠️ Todas las tablas eliminadas")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager para obtener sesión de BD"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error en transacción: {e}")
            raise
        finally:
            session.close()


# Instancia global
db_manager = DatabaseManager()


# ============================================================================
# CRUD - MÁQUINAS
# ============================================================================

def crear_maquina(id: str, nombre: str, capacidad: int = 1, 
                  tiempo_setup: int = 0, costo_por_hora: float = 50.0) -> str:
    """Crear nueva máquina"""
    with db_manager.get_session() as session:
        maquina = Maquina(
            id=id,
            nombre=nombre,
            capacidad=capacidad,
            tiempo_setup_default=tiempo_setup,
            costo_por_hora=costo_por_hora
        )
        session.add(maquina)
        session.commit()
        logger.info(f"✅ Máquina creada: {id}")
        return id


def obtener_maquina(id: str) -> Optional[Maquina]:
    """Obtener máquina por ID"""
    with db_manager.get_session() as session:
        return session.query(Maquina).filter(Maquina.id == id).first()


def obtener_todas_maquinas(solo_disponibles: bool = False) -> List[Dict]:
    """Obtener todas las máquinas como diccionarios"""
    with db_manager.get_session() as session:
        query = session.query(Maquina)
        if solo_disponibles:
            query = query.filter(Maquina.disponible == True)
        maquinas = query.all()
        
        return [
            {
                'id': m.id,
                'nombre': m.nombre,
                'capacidad': m.capacidad,
                'tiempo_setup_default': m.tiempo_setup_default,
                'disponible': m.disponible,
                'costo_por_hora': m.costo_por_hora
            }
            for m in maquinas
        ]


def actualizar_maquina(id: str, **kwargs) -> bool:
    """Actualizar datos de máquina"""
    with db_manager.get_session() as session:
        maquina = session.query(Maquina).filter(Maquina.id == id).first()
        if maquina:
            for key, value in kwargs.items():
                if hasattr(maquina, key):
                    setattr(maquina, key, value)
            session.commit()
            logger.info(f"✅ Máquina actualizada: {id}")
            return True
        return False


# ============================================================================
# CRUD - OPERADORES
# ============================================================================

def crear_operador(id: str, nombre: str, habilidades: List[str], 
                   costo_por_hora: float = 25.0) -> str:
    """Crear nuevo operador"""
    with db_manager.get_session() as session:
        operador = Operador(
            id=id,
            nombre=nombre,
            habilidades=json.dumps(habilidades),
            costo_por_hora=costo_por_hora
        )
        session.add(operador)
        session.commit()
        logger.info(f"✅ Operador creado: {id}")
        return id


def obtener_operador(id: str) -> Optional[Operador]:
    """Obtener operador por ID"""
    with db_manager.get_session() as session:
        return session.query(Operador).filter(Operador.id == id).first()


def obtener_todos_operadores(solo_disponibles: bool = False) -> List[Dict]:
    """Obtener todos los operadores como diccionarios"""
    with db_manager.get_session() as session:
        query = session.query(Operador)
        if solo_disponibles:
            query = query.filter(Operador.disponible == True)
        operadores = query.all()
        
        return [
            {
                'id': op.id,
                'nombre': op.nombre,
                'habilidades': op.habilidades,
                'disponible': op.disponible,
                'costo_por_hora': op.costo_por_hora
            }
            for op in operadores
        ]


# ============================================================================
# CRUD - TRABAJOS Y TAREAS
# ============================================================================

def crear_trabajo(id: str, nombre: str, descripcion: str = "", 
                  cliente: str = "", fecha_entrega: datetime = None) -> str:
    """Crear nuevo trabajo"""
    with db_manager.get_session() as session:
        trabajo = Trabajo(
            id=id,
            nombre=nombre,
            descripcion=descripcion,
            cliente=cliente,
            fecha_entrega_deseada=fecha_entrega
        )
        session.add(trabajo)
        session.commit()
        logger.info(f"✅ Trabajo creado: {id}")
        return id


def crear_tarea(id: str, trabajo_id: str, nombre: str, duracion: int,
                maquina_requerida: str, tiempo_setup: int = 0, orden: int = 1) -> str:
    """Crear nueva tarea"""
    with db_manager.get_session() as session:
        tarea = Tarea(
            id=id,
            trabajo_id=trabajo_id,
            nombre=nombre,
            duracion=duracion,
            maquina_requerida=maquina_requerida,
            tiempo_setup=tiempo_setup,
            orden=orden
        )
        session.add(tarea)
        session.commit()
        logger.info(f"✅ Tarea creada: {id}")
        return id


def obtener_trabajo(id: str) -> Optional[Trabajo]:
    """Obtener trabajo por ID con sus tareas"""
    with db_manager.get_session() as session:
        return session.query(Trabajo).filter(Trabajo.id == id).first()


def obtener_todos_trabajos() -> List[Trabajo]:
    """Obtener todos los trabajos"""
    with db_manager.get_session() as session:
        return session.query(Trabajo).all()


def obtener_tareas_trabajo(trabajo_id: str) -> List[Tarea]:
    """Obtener todas las tareas de un trabajo"""
    with db_manager.get_session() as session:
        return session.query(Tarea).filter(
            Tarea.trabajo_id == trabajo_id
        ).order_by(Tarea.orden).all()


# ============================================================================
# CRUD - PROGRAMACIONES
# ============================================================================

def crear_programacion(semana: int, anio: int, objetivo: str,
                      num_trabajos: int, num_tareas: int,
                      makespan: int, tiempo_resolucion: float,
                      configuracion: Dict = None,
                      usuario: str = "Sistema") -> str:
    """
    Crear nueva programación (inicialmente como simulación)
    
    Args:
        semana: Número de semana del año (1-52)
        anio: Año
        objetivo: Objetivo de optimización usado
        num_trabajos: Número de trabajos en la programación
        num_tareas: Número de tareas totales
        makespan: Tiempo total planificado (minutos)
        tiempo_resolucion: Tiempo que tardó el solver (segundos)
        configuracion: Diccionario con configuración completa
        usuario: Usuario que creó la programación
        
    Returns:
        str: ID de la programación creada
    """
    with db_manager.get_session() as session:
        # Generar ID único buscando el máximo número usado
        programaciones_existentes = session.query(Programacion).filter(
            and_(
                Programacion.semana_produccion == semana,
                Programacion.anio == anio
            )
        ).all()
        
        # Extraer números de IDs existentes y encontrar el máximo
        numeros_usados = []
        for p in programaciones_existentes:
            # Formato: PROG-2025-W42-001 → extraer el 001
            try:
                numero = int(p.id.split('-')[-1])
                numeros_usados.append(numero)
            except:
                pass
        
        # Siguiente número disponible
        siguiente_numero = max(numeros_usados) + 1 if numeros_usados else 1
        
        prog_id = f"PROG-{anio}-W{semana:02d}-{siguiente_numero:03d}"
        
        programacion = Programacion(
            id=prog_id,
            semana_produccion=semana,
            anio=anio,
            estado=EstadoProgramacion.SIMULACION,
            objetivo_usado=objetivo,
            tiempo_resolucion=tiempo_resolucion,
            makespan_planificado=makespan,
            num_trabajos=num_trabajos,
            num_tareas=num_tareas,
            usuario_creador=usuario,
            configuracion_json=json.dumps(configuracion) if configuracion else None
        )
        
        session.add(programacion)
        session.commit()
        logger.info(f"✅ Programación creada: {prog_id}")
        return prog_id  # Retornar solo el ID, no el objeto


def aprobar_programacion(prog_id: str, aprobada_por: str) -> bool:
    """
    Aprobar programación para producción
    
    Args:
        prog_id: ID de la programación
        aprobada_por: Usuario que aprueba
        
    Returns:
        bool: True si se aprobó exitosamente
    """
    with db_manager.get_session() as session:
        prog = session.query(Programacion).filter(Programacion.id == prog_id).first()
        
        if prog:
            prog.estado = EstadoProgramacion.PLANIFICADA
            prog.aprobada_por = aprobada_por
            prog.fecha_aprobacion = datetime.now()
            session.commit()
            logger.info(f"✅ Programación aprobada: {prog_id} por {aprobada_por}")
            return True
        return False


def cambiar_estado_programacion(prog_id: str, nuevo_estado: EstadoProgramacion, 
                               usuario: str = None) -> tuple[bool, str]:
    """
    Cambiar estado de programación con validaciones de flujo
    
    Flujo válido:
    - SIMULACION → PLANIFICADA o CANCELADA
    - PLANIFICADA → EN_EJECUCION o CANCELADA
    - EN_EJECUCION → COMPLETADA
    - COMPLETADA → (no se puede cambiar)
    - CANCELADA → (no se puede cambiar)
    
    Args:
        prog_id: ID de la programación
        nuevo_estado: Nuevo estado a asignar
        usuario: Usuario que realiza el cambio (opcional)
        
    Returns:
        tuple: (success: bool, mensaje: str)
    """
    with db_manager.get_session() as session:
        prog = session.query(Programacion).filter(Programacion.id == prog_id).first()
        
        if not prog:
            return False, f"❌ Programación {prog_id} no encontrada"
        
        estado_actual = prog.estado
        
        # Validar transiciones de estado
        transiciones_validas = {
            EstadoProgramacion.SIMULACION: [EstadoProgramacion.PLANIFICADA, EstadoProgramacion.CANCELADA],
            EstadoProgramacion.PLANIFICADA: [EstadoProgramacion.EN_EJECUCION, EstadoProgramacion.CANCELADA],
            EstadoProgramacion.EN_EJECUCION: [EstadoProgramacion.COMPLETADA],
            EstadoProgramacion.COMPLETADA: [],  # No se puede cambiar
            EstadoProgramacion.CANCELADA: []    # No se puede cambiar
        }
        
        if nuevo_estado not in transiciones_validas.get(estado_actual, []):
            estados_validos = ", ".join([e.value for e in transiciones_validas.get(estado_actual, [])])
            if not estados_validos:
                return False, f"⛔ No se puede cambiar el estado de una programación '{estado_actual.value}'"
            return False, f"⚠️ Transición inválida: '{estado_actual.value}' → '{nuevo_estado.value}'. Estados válidos: {estados_validos}"
        
        # Realizar el cambio
        prog.estado = nuevo_estado
        
        # Actualizar campos adicionales según el nuevo estado
        if nuevo_estado == EstadoProgramacion.PLANIFICADA and usuario:
            prog.aprobada_por = usuario
            prog.fecha_aprobacion = datetime.now()
        
        session.commit()
        
        # Si se marca como COMPLETADA, calcular y guardar KPIs automáticamente
        if nuevo_estado == EstadoProgramacion.COMPLETADA:
            try:
                calcular_y_guardar_metricas(prog_id)
                logger.info(f"✅ KPIs calculados automáticamente para {prog_id}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron calcular KPIs automáticamente para {prog_id}: {e}")
                # No fallar el cambio de estado si hay error calculando KPIs
        
        logger.info(f"✅ Estado cambiado: {prog_id} → {nuevo_estado.value} (por {usuario or 'sistema'})")
        return True, f"✅ Estado actualizado: {estado_actual.value} → {nuevo_estado.value}"


def eliminar_programacion(prog_id: str, forzar: bool = False) -> tuple[bool, str]:
    """
    Eliminar una programación de la base de datos
    Por seguridad, SOLO permite eliminar simulaciones y canceladas
    
    Args:
        prog_id: ID de la programación
        forzar: Si True, elimina sin importar el estado (usar con cuidado)
        
    Returns:
        tuple: (success: bool, mensaje: str)
    """
    with db_manager.get_session() as session:
        prog = session.query(Programacion).filter(Programacion.id == prog_id).first()
        
        if not prog:
            return False, f"Programación {prog_id} no encontrada"
        
        # Proteger programaciones importantes (a menos que se fuerce)
        if not forzar and prog.estado in [EstadoProgramacion.PLANIFICADA, 
                                          EstadoProgramacion.EN_EJECUCION, 
                                          EstadoProgramacion.COMPLETADA]:
            return False, f"No se puede eliminar programación con estado '{prog.estado.value}'. Solo simulaciones y canceladas."
        
        # Eliminar (las tareas_planificadas se eliminan automáticamente por CASCADE)
        estado_eliminado = prog.estado.value
        session.delete(prog)
        session.commit()
        logger.info(f"✅ Programación eliminada: {prog_id} (estado: {estado_eliminado})")
        return True, f"Programación {prog_id} eliminada exitosamente"


def obtener_programacion(prog_id: str) -> Optional[Dict]:
    """Obtener programación por ID como diccionario"""
    with db_manager.get_session() as session:
        prog = session.query(Programacion).filter(Programacion.id == prog_id).first()
        
        if not prog:
            return None
        
        return {
            'id': prog.id,
            'semana_produccion': prog.semana_produccion,
            'anio': prog.anio,
            'estado': prog.estado.value if prog.estado else None,
            'objetivo_usado': prog.objetivo_usado,
            'makespan_planificado': prog.makespan_planificado,
            'num_trabajos': prog.num_trabajos,
            'num_tareas': prog.num_tareas,
            'fecha_creacion': prog.fecha_creacion,
            'aprobada_por': prog.aprobada_por,
            'usuario_creador': prog.usuario_creador,
            'tiempo_resolucion': prog.tiempo_resolucion,
            'configuracion_json': prog.configuracion_json,
            'notas': prog.notas
        }


def obtener_programaciones(semana: int = None, anio: int = None,
                          estado: EstadoProgramacion = None,
                          limit: int = 50) -> List[Dict]:
    """
    Obtener programaciones con filtros
    
    Args:
        semana: Filtrar por semana (opcional)
        anio: Filtrar por año (opcional)
        estado: Filtrar por estado (opcional)
        limit: Número máximo de resultados
        
    Returns:
        List[Dict]: Lista de programaciones como diccionarios
    """
    with db_manager.get_session() as session:
        query = session.query(Programacion)
        
        if semana:
            query = query.filter(Programacion.semana_produccion == semana)
        if anio:
            query = query.filter(Programacion.anio == anio)
        if estado:
            query = query.filter(Programacion.estado == estado)
        
        programaciones = query.order_by(Programacion.fecha_creacion.desc()).limit(limit).all()
        
        # Convertir a diccionarios dentro del contexto de sesión
        return [
            {
                'id': p.id,
                'semana_produccion': p.semana_produccion,
                'anio': p.anio,
                'estado': p.estado.value if p.estado else None,
                'objetivo_usado': p.objetivo_usado,
                'makespan_planificado': p.makespan_planificado,
                'num_trabajos': p.num_trabajos,
                'num_tareas': p.num_tareas,
                'fecha_creacion': p.fecha_creacion,
                'aprobada_por': p.aprobada_por,
                'usuario_creador': p.usuario_creador,
                'tiempo_resolucion': p.tiempo_resolucion
            }
            for p in programaciones
        ]


def obtener_programacion_activa() -> Optional[Dict]:
    """Obtener la programación actualmente en ejecución"""
    with db_manager.get_session() as session:
        programacion = session.query(Programacion).filter(
            Programacion.estado == EstadoProgramacion.EN_EJECUCION
        ).first()
        
        if programacion:
            # Convertir a diccionario para evitar problemas de sesión
            return {
                'id': programacion.id,
                'semana_produccion': programacion.semana_produccion,
                'anio': programacion.anio,
                'estado': programacion.estado,
                'objetivo_usado': programacion.objetivo_usado,
                'makespan_planificado': programacion.makespan_planificado,
                'fecha_creacion': programacion.fecha_creacion,
                'aprobada_por': programacion.aprobada_por,
                'fecha_aprobacion': programacion.fecha_aprobacion
            }
        return None


def obtener_programaciones_activas() -> List[Dict]:
    """Obtener todas las programaciones activas (PLANIFICADA y EN_EJECUCION)"""
    with db_manager.get_session() as session:
        programaciones = session.query(Programacion).filter(
            Programacion.estado.in_([EstadoProgramacion.PLANIFICADA, EstadoProgramacion.EN_EJECUCION])
        ).order_by(Programacion.semana_produccion.desc(), Programacion.anio.desc()).all()
        
        return [{
            'id': prog.id,
            'semana_produccion': prog.semana_produccion,
            'anio': prog.anio,
            'estado': prog.estado,
            'objetivo_usado': prog.objetivo_usado,
            'makespan_planificado': prog.makespan_planificado,
            'fecha_creacion': prog.fecha_creacion,
            'aprobada_por': prog.aprobada_por,
            'fecha_aprobacion': prog.fecha_aprobacion
        } for prog in programaciones]


# ============================================================================
# CRUD - TAREAS PLANIFICADAS
# ============================================================================

def crear_tarea_planificada(programacion_id: str, tarea_info: Dict) -> int:
    """
    Crear tarea planificada
    
    Args:
        programacion_id: ID de la programación
        tarea_info: Diccionario con información de la tarea
            - tarea_id, trabajo_id, nombre, duracion_planificada
            - maquina_id, operador_id
            - inicio_planificado, fin_planificado
            - dia_semana, es_dividida, parte_numero, tiempo_setup
    
    Returns:
        int: ID de la tarea planificada creada
    """
    with db_manager.get_session() as session:
        tarea = TareaPlanificada(
            programacion_id=programacion_id,
            **tarea_info
        )
        session.add(tarea)
        session.commit()
        session.refresh(tarea)
        return tarea.id


def obtener_tareas_planificadas(programacion_id: str) -> List[Dict]:
    """Obtener todas las tareas de una programación como diccionarios"""
    with db_manager.get_session() as session:
        tareas = session.query(TareaPlanificada).filter(
            TareaPlanificada.programacion_id == programacion_id
        ).order_by(TareaPlanificada.inicio_planificado).all()
        
        return [
            {
                'id': t.id,
                'programacion_id': t.programacion_id,
                'tarea_id': t.tarea_id,
                'trabajo_id': t.trabajo_id,
                'nombre': t.nombre,
                'duracion_planificada': t.duracion_planificada,
                'tiempo_setup': t.tiempo_setup,
                'maquina_id': t.maquina_id,
                'operador_id': t.operador_id,
                'inicio_planificado': t.inicio_planificado,
                'fin_planificado': t.fin_planificado,
                'dia_semana': t.dia_semana,
                'es_dividida': t.es_dividida,
                'parte_numero': t.parte_numero,
                # Campos procesados del UI
                'inicio_hora': t.inicio_hora if hasattr(t, 'inicio_hora') else None,
                'fin_hora': t.fin_hora if hasattr(t, 'fin_hora') else None,
                'dia_nombre': t.dia_nombre if hasattr(t, 'dia_nombre') else None
            }
            for t in tareas
        ]


def obtener_ejecuciones_reales_programacion(programacion_id: str) -> List[Dict]:
    """
    Obtener todas las ejecuciones reales de una programación

    Args:
        programacion_id: ID de la programación

    Returns:
        List[Dict]: Lista de ejecuciones reales con información de tareas
    """
    with db_manager.get_session() as session:
        # Query con JOIN para obtener información completa
        # Nota: Usar outerjoin porque Tarea y Trabajo pueden no tener datos en la BD
        query = session.query(
            EjecucionReal,
            TareaPlanificada,
            Tarea,
            Trabajo
        ).join(
            TareaPlanificada, EjecucionReal.tarea_planificada_id == TareaPlanificada.id
        ).outerjoin(
            Tarea, TareaPlanificada.tarea_id == Tarea.id
        ).outerjoin(
            Trabajo, Tarea.trabajo_id == Trabajo.id
        ).filter(
            TareaPlanificada.programacion_id == programacion_id
        )
        
        ejecuciones = []
        for ejec_real, tarea_plan, tarea, trabajo in query.all():
            # Manejar casos donde Tarea o Trabajo pueden ser None
            tarea_id = tarea.id if tarea else None
            tarea_nombre = tarea.nombre if tarea else tarea_plan.tarea_id if hasattr(tarea_plan, 'tarea_id') else 'N/A'
            trabajo_id = trabajo.id if trabajo else None
            trabajo_nombre = trabajo.nombre if trabajo else 'N/A'
            
            ejecuciones.append({
                'ejecucion_id': ejec_real.id,
                'tarea_planificada_id': ejec_real.tarea_planificada_id,
                'tarea_id': tarea_id,
                'tarea_nombre': tarea_nombre,
                'trabajo_id': trabajo_id,
                'trabajo_nombre': trabajo_nombre,
                'maquina_planificada': tarea_plan.maquina_id,
                'maquina_usada': ejec_real.maquina_usada,
                'operador_planificado': tarea_plan.operador_id,
                'operador_ejecutor': ejec_real.operador_ejecutor,
                'inicio_planificado': tarea_plan.inicio_planificado,  # Minutos lineales (legacy)
                'fin_planificado': tarea_plan.fin_planificado,  # Minutos lineales (legacy)
                'inicio_hora': tarea_plan.inicio_hora,  # Formato HH:MM ya calculado
                'fin_hora': tarea_plan.fin_hora,  # Formato HH:MM ya calculado
                'dia_nombre': tarea_plan.dia_nombre,  # Ej: "Lun", "Mar"
                'dia_semana': tarea_plan.dia_semana,  # 0=Lunes, 1=Martes, etc
                'inicio_real': ejec_real.inicio_real,
                'fin_real': ejec_real.fin_real,
                'duracion_planificada': tarea_plan.duracion_planificada,
                'duracion_real': ejec_real.duracion_real,
                'desviacion_inicio': ejec_real.desviacion_inicio,
                'desviacion_fin': ejec_real.desviacion_fin,
                'desviacion_duracion': ejec_real.desviacion_duracion,
                'estado': ejec_real.estado.value if ejec_real.estado else None,
                'problemas_encontrados': ejec_real.problemas_encontrados,
                'tiempo_paradas': ejec_real.tiempo_paradas,
                'notas_operador': ejec_real.notas_operador,
                'fecha_registro': ejec_real.fecha_registro
            })
        
        return ejecuciones


def obtener_tareas_sin_ejecucion_real(programacion_id: str) -> List[Dict]:
    """
    Obtener tareas planificadas que NO tienen ejecución real registrada

    Args:
        programacion_id: ID de la programación

    Returns:
        List[Dict]: Lista de tareas pendientes de registro
    """
    with db_manager.get_session() as session:
        # Subquery para tareas que SÍ tienen ejecución real
        tareas_con_ejecucion = session.query(TareaPlanificada.id).join(
            EjecucionReal, TareaPlanificada.id == EjecucionReal.tarea_planificada_id
        ).filter(TareaPlanificada.programacion_id == programacion_id).subquery()
        
        # Query principal para tareas SIN ejecución real
        # Obtener TODAS las tareas planificadas de esta programación que NO tienen ejecución real
        query = session.query(TareaPlanificada).filter(
            TareaPlanificada.programacion_id == programacion_id,
            ~TareaPlanificada.id.in_(tareas_con_ejecucion)
        ).order_by(TareaPlanificada.inicio_planificado)
        
        tareas_pendientes = []
        for tarea_plan in query.all():
            # Extraer información de la tarea
            tarea_id_full = tarea_plan.tarea_id
            tarea_id_base = tarea_id_full.split('.')[0] if '.' in tarea_id_full else tarea_id_full
            trabajo_id = tarea_id_base[0] if len(tarea_id_base) > 0 else 'N/A'
            
            # Intentar obtener nombre de la tarea desde tabla Tarea si existe
            tarea_obj = None
            try:
                tarea_obj = session.query(Tarea).filter(Tarea.id == tarea_id_base).first()
            except:
                pass
            
            tarea_nombre = tarea_plan.nombre if tarea_plan.nombre else tarea_id_full
            if tarea_obj:
                tarea_nombre = tarea_obj.nombre
            
            tareas_pendientes.append({
                'tarea_planificada_id': tarea_plan.id,
                'tarea_id': tarea_plan.tarea_id,  # Usar el ID completo (ej: "A2.P1")
                'tarea_nombre': tarea_nombre,
                'trabajo_id': trabajo_id,
                'trabajo_nombre': f"Trabajo {trabajo_id}",
                'maquina_planificada': tarea_plan.maquina_id,
                'operador_planificado': tarea_plan.operador_id,
                'inicio_planificado': tarea_plan.inicio_planificado,
                'fin_planificado': tarea_plan.fin_planificado,
                'inicio_hora': tarea_plan.inicio_hora,  # Formato HH:MM ya calculado
                'fin_hora': tarea_plan.fin_hora,  # Formato HH:MM ya calculado
                'duracion_planificada': tarea_plan.duracion_planificada,
                'dia_semana': tarea_plan.dia_semana,
                'dia_nombre': tarea_plan.dia_nombre,  # Ej: "Lun", "Mar"
                'es_dividida': tarea_plan.es_dividida,
                'parte_numero': tarea_plan.parte_numero
            })
        
        return tareas_pendientes


def verificar_programacion_completa(programacion_id: str) -> tuple[bool, int, int]:
    """
    Verificar si una programación tiene todas las tareas con ejecución real
    
    Args:
        programacion_id: ID de la programación
        
    Returns:
        tuple: (esta_completa: bool, tareas_totales: int, tareas_registradas: int)
    """
    with db_manager.get_session() as session:
        # Contar tareas planificadas totales
        total_tareas = session.query(TareaPlanificada).filter(
            TareaPlanificada.programacion_id == programacion_id
        ).count()
        
        # Contar tareas con ejecución real
        tareas_registradas = session.query(TareaPlanificada).join(
            EjecucionReal, TareaPlanificada.id == EjecucionReal.tarea_planificada_id
        ).filter(TareaPlanificada.programacion_id == programacion_id).count()
        
        esta_completa = (total_tareas > 0) and (tareas_registradas == total_tareas)
        
        return esta_completa, total_tareas, tareas_registradas


def actualizar_ejecucion_real(ejecucion_id: int, inicio_real: datetime = None,
                            fin_real: datetime = None, maquina_usada: str = None,
                            operador_ejecutor: str = None, problemas: str = None,
                            notas: str = None, tiempo_paradas: int = None) -> bool:
    """
    Actualizar una ejecución real existente
    
    Args:
        ejecucion_id: ID de la ejecución real
        inicio_real, fin_real, maquina_usada, operador_ejecutor: Datos a actualizar
        problemas, notas, tiempo_paradas: Información adicional
        
    Returns:
        bool: True si se actualizó correctamente
    """
    with db_manager.get_session() as session:
        ejecucion = session.query(EjecucionReal).filter(
            EjecucionReal.id == ejecucion_id
        ).first()
        
        if not ejecucion:
            return False
        
        # Actualizar campos proporcionados
        if inicio_real is not None:
            ejecucion.inicio_real = inicio_real
        if fin_real is not None:
            ejecucion.fin_real = fin_real
        if maquina_usada is not None:
            ejecucion.maquina_usada = maquina_usada
        if operador_ejecutor is not None:
            ejecucion.operador_ejecutor = operador_ejecutor
        if problemas is not None:
            ejecucion.problemas_encontrados = problemas
        if notas is not None:
            ejecucion.notas_operador = notas
        if tiempo_paradas is not None:
            ejecucion.tiempo_paradas = tiempo_paradas
        
        # Recalcular desviaciones si se actualizaron tiempos
        if inicio_real is not None or fin_real is not None:
            tarea_plan = session.query(TareaPlanificada).filter(
                TareaPlanificada.id == ejecucion.tarea_planificada_id
            ).first()
            
            if tarea_plan and ejecucion.inicio_real and ejecucion.fin_real:
                # Calcular desviaciones en minutos
                inicio_plan = tarea_plan.inicio_planificado
                fin_plan = tarea_plan.fin_planificado
                
                if inicio_plan:
                    ejecucion.desviacion_inicio = int(
                        (ejecucion.inicio_real - inicio_plan).total_seconds() / 60
                    )
                
                if fin_plan:
                    ejecucion.desviacion_fin = int(
                        (ejecucion.fin_real - fin_plan).total_seconds() / 60
                    )
                
                # Duración real en minutos
                ejecucion.duracion_real = int(
                    (ejecucion.fin_real - ejecucion.inicio_real).total_seconds() / 60
                )
                
                # Desviación: usar duracion ORIGINAL de tabla tareas (no minutos lineales)
                from modelos.database_models import Tarea
                tarea_id_base = tarea_plan.tarea_id.split('.')[0] if '.' in tarea_plan.tarea_id else tarea_plan.tarea_id
                tarea_original = session.query(Tarea).filter(Tarea.id == tarea_id_base).first()
                duracion_original = tarea_original.duracion if tarea_original else tarea_plan.duracion_planificada
                
                tiempo_paradas = ejecucion.tiempo_paradas or 0
                dur_real_sin_setup = max(0, ejecucion.duracion_real - tiempo_paradas)
                ejecucion.desviacion_duracion = dur_real_sin_setup - duracion_original

        session.commit()
        logger.info(f"✅ Ejecución real actualizada: {ejecucion_id}")
        return True


def eliminar_ejecucion_real(ejecucion_id: int) -> bool:
    """
    Eliminar una ejecución real
    
    Args:
        ejecucion_id: ID de la ejecución real
        
    Returns:
        bool: True si se eliminó correctamente
    """
    with db_manager.get_session() as session:
        ejecucion = session.query(EjecucionReal).filter(
            EjecucionReal.id == ejecucion_id
        ).first()
        
        if ejecucion:
            session.delete(ejecucion)
            session.commit()
            logger.info(f"✅ Ejecución real eliminada: {ejecucion_id}")
            return True
        
        return False


# ============================================================================
# CRUD - EJECUCIÓN REAL
# ============================================================================

def registrar_ejecucion_real(tarea_planificada_id: int, inicio_real: datetime,
                            fin_real: datetime, maquina_usada: str,
                            operador_ejecutor: str = None,
                            problemas: str = "", notas: str = "",
                            tiempo_paradas: int = 0,
                            registrado_por: str = "Operador") -> int:
    """
    Registrar ejecución real de una tarea
    
    Args:
        tarea_planificada_id: ID de la tarea planificada
        inicio_real: Hora real de inicio
        fin_real: Hora real de fin
        maquina_usada: Máquina realmente usada
        operador_ejecutor: Operador que ejecutó
        problemas: Descripción de problemas
        notas: Notas del operador
        tiempo_paradas: Tiempo de paradas en minutos
        registrado_por: Quien registra
    """
    with db_manager.get_session() as session:
        # Obtener tarea planificada para calcular desviaciones
        tarea_plan = session.query(TareaPlanificada).filter(
            TareaPlanificada.id == tarea_planificada_id
        ).first()
        
        if not tarea_plan:
            raise ValueError(f"Tarea planificada {tarea_planificada_id} no encontrada")
        
        # Calcular duración real
        duracion_real = int((fin_real - inicio_real).total_seconds() / 60)
        
        # Calcular desviaciones: usar duracion ORIGINAL de tabla tareas (no minutos lineales)
        from modelos.database_models import Tarea
        tarea_id_base = tarea_plan.tarea_id.split('.')[0] if '.' in tarea_plan.tarea_id else tarea_plan.tarea_id
        tarea_original = session.query(Tarea).filter(Tarea.id == tarea_id_base).first()
        duracion_original = tarea_original.duracion if tarea_original else tarea_plan.duracion_planificada
        
        dur_real_sin_setup = max(0, duracion_real - (tiempo_paradas or 0))
        desviacion_duracion = dur_real_sin_setup - duracion_original
        
        # Determinar estado
        if desviacion_duracion > 30:  # Más de 30 min de retraso
            estado = EstadoTarea.RETRASADA
        else:
            estado = EstadoTarea.COMPLETADA
        
        ejecucion = EjecucionReal(
            tarea_planificada_id=tarea_planificada_id,
            inicio_real=inicio_real,
            fin_real=fin_real,
            duracion_real=duracion_real,
            maquina_usada=maquina_usada,
            operador_ejecutor=operador_ejecutor,
            estado=estado,
            desviacion_duracion=desviacion_duracion,
            problemas_encontrados=problemas,
            tiempo_paradas=tiempo_paradas,
            notas_operador=notas,
            registrado_por=registrado_por
        )
        
        session.add(ejecucion)
        session.commit()
        session.refresh(ejecucion)
        logger.info(f"✅ Ejecución real registrada para tarea {tarea_planificada_id}")
        return ejecucion.id


def obtener_ejecucion_real(tarea_planificada_id: int) -> Optional[EjecucionReal]:
    """Obtener ejecución real de una tarea planificada"""
    with db_manager.get_session() as session:
        return session.query(EjecucionReal).filter(
            EjecucionReal.tarea_planificada_id == tarea_planificada_id
        ).first()


# ============================================================================
# CRUD - MÉTRICAS
# ============================================================================

def calcular_y_guardar_metricas(programacion_id: str, semana_produccion: int = None, 
                                 anio: int = None) -> Optional[int]:
    """
    Calcular y guardar métricas/KPIs para una programación
    
    Esta es la función principal que calcula todos los KPIs correctamente
    y los guarda en la BD para uso posterior.
    
    Nota: Una vez que una semana está completada, los valores no cambian,
    por lo que esta función solo calcula si no existen métricas previas.
    
    Args:
        programacion_id: ID de la programación
        semana_produccion: Semana de producción (opcional, se obtiene de BD si no se pasa)
        anio: Año (opcional, se obtiene de BD si no se pasa)
    
    Returns:
        int: ID de la métrica creada/actualizada, o None si hay error
    """
    from utils.kpi_calculator import KPIExporter
    from modelos.database_models import EstadoProgramacion
    
    with db_manager.get_session() as session:
        # Verificar que la programación existe
        prog = session.query(Programacion).filter(Programacion.id == programacion_id).first()
        if not prog:
            logger.error(f"Programación {programacion_id} no encontrada")
            return None
        
        # Obtener semana y año si no se proporcionaron
        if semana_produccion is None:
            semana_produccion = prog.semana_produccion
        if anio is None:
            anio = prog.anio
        
        # Verificar si ya existen métricas (no recalcular si ya existen)
        metrica_existente = session.query(MetricaCalculada).filter(
            MetricaCalculada.programacion_id == programacion_id
        ).first()
        
        if metrica_existente:
            logger.info(f"Métricas ya existen para {programacion_id}")
            return metrica_existente.id
        
        # Obtener ejecuciones reales
        ejecuciones = obtener_ejecuciones_reales_programacion(programacion_id)
        
        if not ejecuciones:
            logger.warning(f"No hay ejecuciones reales para {programacion_id}")
            return None
        
        # Extraer configuración de la programación
        import json
        from datetime import datetime as dt
        
        dias_laborales = 5  # Default
        minutos_por_dia = 600  # Default (10 horas)
        num_maquinas = 3  # Default
        
        if prog.configuracion_json:
            try:
                config = json.loads(prog.configuracion_json)
                
                # Obtener días laborales
                horario = config.get('horario_trabajo', {})
                dias_laborales = horario.get('dias_laborales', 5)
                
                # Calcular minutos por día: (hora_fin - hora_inicio - almuerzo) * 60
                hora_inicio_str = horario.get('inicio', '08:00')
                hora_fin_str = horario.get('fin', '18:00')
                almuerzo_inicio_str = horario.get('descanso_almuerzo', {}).get('inicio', '13:00')
                almuerzo_fin_str = horario.get('descanso_almuerzo', {}).get('fin', '14:00')
                
                # Parsear horas
                try:
                    h_ini, m_ini = map(int, hora_inicio_str.split(':'))
                    h_fin, m_fin = map(int, hora_fin_str.split(':'))
                    h_alm_ini, m_alm_ini = map(int, almuerzo_inicio_str.split(':'))
                    h_alm_fin, m_alm_fin = map(int, almuerzo_fin_str.split(':'))
                    
                    # Calcular minutos totales del día
                    minutos_totales = (h_fin * 60 + m_fin) - (h_ini * 60 + m_ini)
                    
                    # Restar almuerzo
                    minutos_almuerzo = (h_alm_fin * 60 + m_alm_fin) - (h_alm_ini * 60 + m_alm_ini)
                    
                    # Minutos disponibles por día (efectivos, sin almuerzo)
                    minutos_por_dia = minutos_totales - minutos_almuerzo
                except Exception as e:
                    logger.warning(f"Error calculando minutos por día desde configuración: {e}")
                    # Mantener default
                
                # Obtener número de máquinas
                recursos = config.get('recursos', {})
                num_maquinas = recursos.get('num_maquinas', 3)
                
            except Exception as e:
                logger.warning(f"Error parseando configuración JSON: {e}")
                # Usar defaults
        
        # Inicializar calculadora con configuración de la programación
        calc = KPIExporter(
            dias_laborales=dias_laborales,
            minutos_por_dia=int(minutos_por_dia),
            num_maquinas=num_maquinas
        )
        
        # Calcular todas las métricas (pasar semana y año para cálculo correcto de rendimiento)
        metricas_dict = calc.calcular_metricas_completas(ejecuciones, programacion_id,
                                                          semana_produccion=semana_produccion, anio=anio)
        
        # Calcular cumplimiento con tolerancia estándar (5 min)
        cumplimiento = calc.calcular_cumplimiento_plazos(
            ejecuciones,
            tolerancia_minutos=5,
            semana_produccion=semana_produccion,
            anio=anio
        )
        
        # Preparar datos para guardar en BD
        utilizacion_maquinas = metricas_dict.get('utilizacion_maquinas', {})
        
        # Extraer utilización por máquina (M1, M2, M3)
        utilizacion_m1 = utilizacion_maquinas.get('M1', {}).get('utilizacion_total', 0.0) if utilizacion_maquinas.get('M1') else 0.0
        utilizacion_m2 = utilizacion_maquinas.get('M2', {}).get('utilizacion_total', 0.0) if utilizacion_maquinas.get('M2') else 0.0
        utilizacion_m3 = utilizacion_maquinas.get('M3', {}).get('utilizacion_total', 0.0) if utilizacion_maquinas.get('M3') else 0.0
        
        # Tiempos por máquina
        tiempo_productivo_m1 = utilizacion_maquinas.get('M1', {}).get('tiempo_productivo', 0) if utilizacion_maquinas.get('M1') else 0
        tiempo_productivo_m2 = utilizacion_maquinas.get('M2', {}).get('tiempo_productivo', 0) if utilizacion_maquinas.get('M2') else 0
        tiempo_productivo_m3 = utilizacion_maquinas.get('M3', {}).get('tiempo_productivo', 0) if utilizacion_maquinas.get('M3') else 0
        
        tiempo_ocioso_m1 = utilizacion_maquinas.get('M1', {}).get('tiempo_ocioso', 0) if utilizacion_maquinas.get('M1') else 0
        tiempo_ocioso_m2 = utilizacion_maquinas.get('M2', {}).get('tiempo_ocioso', 0) if utilizacion_maquinas.get('M2') else 0
        tiempo_ocioso_m3 = utilizacion_maquinas.get('M3', {}).get('tiempo_ocioso', 0) if utilizacion_maquinas.get('M3') else 0
        
        tiempo_setup_m1 = utilizacion_maquinas.get('M1', {}).get('tiempo_setup', 0) if utilizacion_maquinas.get('M1') else 0
        tiempo_setup_m2 = utilizacion_maquinas.get('M2', {}).get('tiempo_setup', 0) if utilizacion_maquinas.get('M2') else 0
        tiempo_setup_m3 = utilizacion_maquinas.get('M3', {}).get('tiempo_setup', 0) if utilizacion_maquinas.get('M3') else 0
        
        # Calcular utilización global promedio ponderada por tiempo productivo
        total_tiempo_productivo = tiempo_productivo_m1 + tiempo_productivo_m2 + tiempo_productivo_m3
        if total_tiempo_productivo > 0:
            # Promedio ponderado: sum(utilizacion_i * tiempo_productivo_i) / sum(tiempo_productivo_i)
            utilizacion_global_ponderada = (
                utilizacion_m1 * tiempo_productivo_m1 +
                utilizacion_m2 * tiempo_productivo_m2 +
                utilizacion_m3 * tiempo_productivo_m3
            ) / total_tiempo_productivo
        else:
            # Si no hay tiempo productivo, usar promedio simple
            maquinas_con_datos = [u for u in [utilizacion_m1, utilizacion_m2, utilizacion_m3] if u > 0]
            utilizacion_global_ponderada = sum(maquinas_con_datos) / len(maquinas_con_datos) if maquinas_con_datos else 0.0
        
        # Makespan real
        makespan_real = None
        if ejecuciones:
            try:
                tiempos_fin = [e.get('fin_real') for e in ejecuciones if e.get('fin_real')]
                tiempos_inicio = [e.get('inicio_real') for e in ejecuciones if e.get('inicio_real')]
                if tiempos_fin and tiempos_inicio:
                    # Convertir a datetime si son strings
                    from datetime import datetime
                    fin_max = max([
                        datetime.fromisoformat(str(t).replace('Z', '+00:00')) if isinstance(t, str) else t
                        for t in tiempos_fin
                        if t
                    ])
                    inicio_min = min([
                        datetime.fromisoformat(str(t).replace('Z', '+00:00')) if isinstance(t, str) else t
                        for t in tiempos_inicio
                        if t
                    ])
                    makespan_real = int((fin_max - inicio_min).total_seconds() / 60)
            except Exception as e:
                logger.warning(f"Error calculando makespan_real: {e}")
                makespan_real = None
        
        diferencia_makespan = None
        if makespan_real and prog.makespan_planificado:
            diferencia_makespan = makespan_real - prog.makespan_planificado
        
        datos_metricas = {
            'oee_global': metricas_dict.get('oee_global', 0.0),
            'disponibilidad_oee': metricas_dict.get('disponibilidad_oee', 0.0),
            'rendimiento_oee': metricas_dict.get('rendimiento_oee', 0.0),
            'calidad_oee': metricas_dict.get('calidad_oee', 0.0),
            'throughput_semanal': metricas_dict.get('throughput_semanal', 0),
            'lead_time_promedio': round(utilizacion_global_ponderada, 2),  # Usado para almacenar utilización global promedio ponderada
            
            # Utilización por máquina
            'utilizacion_m1': round(utilizacion_m1, 2),
            'utilizacion_m2': round(utilizacion_m2, 2),
            'utilizacion_m3': round(utilizacion_m3, 2),
            
            # Tiempos por máquina
            'tiempo_productivo_m1': tiempo_productivo_m1,
            'tiempo_productivo_m2': tiempo_productivo_m2,
            'tiempo_productivo_m3': tiempo_productivo_m3,
            'tiempo_ocioso_m1': tiempo_ocioso_m1,
            'tiempo_ocioso_m2': tiempo_ocioso_m2,
            'tiempo_ocioso_m3': tiempo_ocioso_m3,
            'tiempo_setup_m1': tiempo_setup_m1,
            'tiempo_setup_m2': tiempo_setup_m2,
            'tiempo_setup_m3': tiempo_setup_m3,
            
            # Cumplimiento
            'otif_porcentaje': round(cumplimiento.get('otif_porcentaje', 0.0), 2),
            'tareas_a_tiempo': cumplimiento.get('tareas_a_tiempo', 0),
            'tareas_retrasadas': cumplimiento.get('tareas_retrasadas', 0),
            'tareas_adelantadas': cumplimiento.get('tareas_adelantadas', 0),
            
            # Desviaciones
            'desviacion_promedio': round(metricas_dict.get('desviacion_promedio', 0.0), 2),
            'desviacion_maxima': round(metricas_dict.get('desviacion_maxima', 0.0), 2),
            
            # Costos (TODO: implementar si es necesario)
            'costo_real': None,
            'costo_maquinas': None,
            'costo_operadores': None,
            'costo_penalizaciones': None,
            'costo_setup': None,
            
            # Análisis
            'cuello_botella_identificado': metricas_dict.get('cuello_botella'),
            'makespan_real': makespan_real,
            'diferencia_makespan': diferencia_makespan
        }
        
        # Crear nueva métrica (ya verificamos que no existe antes)
        metrica = MetricaCalculada(
            programacion_id=programacion_id,
            **datos_metricas
        )
        session.add(metrica)
        session.flush()
        metrica_id = metrica.id
        
        session.commit()
        logger.info(f"✅ Métricas calculadas y guardadas para {programacion_id}")
        return metrica_id


def guardar_metricas(programacion_id: str, metricas: Dict) -> int:
    """
    Guardar métricas calculadas para una programación (DEPRECATED - usar calcular_y_guardar_metricas)
    
    Args:
        programacion_id: ID de la programación
        metricas: Diccionario con todas las métricas
    
    Returns:
        int: ID de la métrica creada
    """
    with db_manager.get_session() as session:
        metrica = MetricaCalculada(
            programacion_id=programacion_id,
            **metricas
        )
        session.add(metrica)
        session.commit()
        session.refresh(metrica)
        logger.info(f"✅ Métricas guardadas para {programacion_id}")
        return metrica.id


def obtener_metricas(programacion_id: str) -> Optional[Dict]:
    """
    Obtener métricas de una programación como diccionario
    
    Args:
        programacion_id: ID de la programación
    
    Returns:
        Dict con todas las métricas o None si no existen
    """
    with db_manager.get_session() as session:
        metrica = session.query(MetricaCalculada).filter(
            MetricaCalculada.programacion_id == programacion_id
        ).first()
        
        if not metrica:
            return None
        
        # Convertir a diccionario con todos los campos
        return {
            'id': metrica.id,
            'programacion_id': metrica.programacion_id,
            'fecha_calculo': metrica.fecha_calculo,
            'oee_global': metrica.oee_global,
            'disponibilidad_oee': getattr(metrica, 'disponibilidad_oee', None),
            'rendimiento_oee': getattr(metrica, 'rendimiento_oee', None),
            'calidad_oee': getattr(metrica, 'calidad_oee', None),
            'throughput_semanal': metrica.throughput_semanal,
            'lead_time_promedio': metrica.lead_time_promedio,
            'utilizacion_m1': metrica.utilizacion_m1,
            'utilizacion_m2': metrica.utilizacion_m2,
            'utilizacion_m3': metrica.utilizacion_m3,
            'tiempo_productivo_m1': metrica.tiempo_productivo_m1,
            'tiempo_productivo_m2': metrica.tiempo_productivo_m2,
            'tiempo_productivo_m3': metrica.tiempo_productivo_m3,
            'tiempo_ocioso_m1': metrica.tiempo_ocioso_m1,
            'tiempo_ocioso_m2': metrica.tiempo_ocioso_m2,
            'tiempo_ocioso_m3': metrica.tiempo_ocioso_m3,
            'tiempo_setup_m1': metrica.tiempo_setup_m1,
            'tiempo_setup_m2': metrica.tiempo_setup_m2,
            'tiempo_setup_m3': metrica.tiempo_setup_m3,
            'otif_porcentaje': metrica.otif_porcentaje,
            'tareas_a_tiempo': metrica.tareas_a_tiempo,
            'tareas_retrasadas': metrica.tareas_retrasadas,
            'tareas_adelantadas': getattr(metrica, 'tareas_adelantadas', 0),
            'desviacion_promedio': metrica.desviacion_promedio,
            'desviacion_maxima': metrica.desviacion_maxima,
            'cuello_botella_identificado': metrica.cuello_botella_identificado,
            'makespan_real': metrica.makespan_real,
            'diferencia_makespan': metrica.diferencia_makespan
        }


def obtener_metricas_historicas(ultimas_n_semanas: int = 4) -> List[MetricaCalculada]:
    """Obtener métricas históricas"""
    with db_manager.get_session() as session:
        return session.query(MetricaCalculada).join(Programacion).filter(
            Programacion.estado == EstadoProgramacion.COMPLETADA
        ).order_by(Programacion.semana_produccion.desc()).limit(ultimas_n_semanas).all()


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def inicializar_datos_default():
    """Inicializar datos por defecto (máquinas y operadores)"""
    
    # Crear máquinas por defecto
    maquinas_default = [
        {"id": "M1", "nombre": "Máquina de Corte", "costo_por_hora": 50.0, "tiempo_setup": 15},
        {"id": "M2", "nombre": "Máquina de Soldadura", "costo_por_hora": 75.0, "tiempo_setup": 20},
        {"id": "M3", "nombre": "Máquina de Pintura", "costo_por_hora": 60.0, "tiempo_setup": 10},
    ]
    
    for maq in maquinas_default:
        if not obtener_maquina(maq["id"]):
            crear_maquina(**maq)
    
    # Crear operadores por defecto
    operadores_default = [
        {"id": "OP1", "nombre": "Operador 1", "habilidades": ["M1", "M2"]},
        {"id": "OP2", "nombre": "Operador 2", "habilidades": ["M2", "M3"]},
        {"id": "OP3", "nombre": "Operador 3", "habilidades": ["M1", "M3"]},
    ]
    
    for op in operadores_default:
        if not obtener_operador(op["id"]):
            crear_operador(**op)
    
    logger.info("✅ Datos por defecto inicializados")


def obtener_estadisticas_generales() -> Dict:
    """Obtener estadísticas generales del sistema"""
    with db_manager.get_session() as session:
        stats = {
            'total_maquinas': session.query(Maquina).count(),
            'total_operadores': session.query(Operador).count(),
            'total_trabajos': session.query(Trabajo).count(),
            'total_programaciones': session.query(Programacion).count(),
            'programaciones_completadas': session.query(Programacion).filter(
                Programacion.estado == EstadoProgramacion.COMPLETADA
            ).count(),
            'programaciones_activas': session.query(Programacion).filter(
                Programacion.estado == EstadoProgramacion.EN_EJECUCION
            ).count(),
        }
        return stats


if __name__ == "__main__":
    # Prueba de inicialización
    db_manager.crear_tablas()
    inicializar_datos_default()
    
    stats = obtener_estadisticas_generales()
    print("\n📊 Estadísticas del sistema:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

