#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelos de Base de Datos - Optimizador de Producción v1.3
SQLAlchemy ORM Models para gestión de programaciones y tracking
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class EstadoProgramacion(enum.Enum):
    """Estados del ciclo de vida de una programación"""
    SIMULACION = "simulacion"
    PLANIFICADA = "planificada"
    EN_EJECUCION = "en_ejecucion"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class EstadoTarea(enum.Enum):
    """Estados de ejecución de una tarea"""
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    RETRASADA = "retrasada"
    CANCELADA = "cancelada"


# ============================================================================
# RECURSOS
# ============================================================================

class Maquina(Base):
    """Máquinas disponibles en la planta"""
    __tablename__ = 'maquinas'
    
    id = Column(String(10), primary_key=True)  # M1, M2, M3
    nombre = Column(String(100), nullable=False)
    capacidad = Column(Integer, default=1)
    tiempo_setup_default = Column(Integer, default=0)  # minutos
    disponible = Column(Boolean, default=True)
    costo_por_hora = Column(Float, default=0.0)
    
    # Metadata
    fecha_creacion = Column(DateTime, default=datetime.now)
    fecha_modificacion = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relaciones
    tareas_planificadas = relationship("TareaPlanificada", back_populates="maquina")
    
    def __repr__(self):
        return f"<Maquina(id={self.id}, nombre={self.nombre})>"


class Operador(Base):
    """Operadores disponibles"""
    __tablename__ = 'operadores'
    
    id = Column(String(10), primary_key=True)  # OP1, OP2, OP3
    nombre = Column(String(100), nullable=False)
    habilidades = Column(Text)  # JSON string con lista de máquinas: ["M1", "M2"]
    disponible = Column(Boolean, default=True)
    costo_por_hora = Column(Float, default=25.0)
    
    # Metadata
    fecha_creacion = Column(DateTime, default=datetime.now)
    fecha_modificacion = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relaciones
    tareas_planificadas = relationship("TareaPlanificada", back_populates="operador")
    
    def __repr__(self):
        return f"<Operador(id={self.id}, nombre={self.nombre})>"


# ============================================================================
# TRABAJOS Y TAREAS BASE
# ============================================================================

class Trabajo(Base):
    """Trabajos (conjunto de tareas relacionadas)"""
    __tablename__ = 'trabajos'
    
    id = Column(String(10), primary_key=True)  # A, B, C
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    cliente = Column(String(100))
    fecha_creacion = Column(DateTime, default=datetime.now)
    fecha_entrega_deseada = Column(DateTime)
    
    # Relaciones
    tareas = relationship("Tarea", back_populates="trabajo", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Trabajo(id={self.id}, nombre={self.nombre})>"


class Tarea(Base):
    """Tareas individuales (plantilla)"""
    __tablename__ = 'tareas'
    
    id = Column(String(20), primary_key=True)  # A1, A2, A3
    trabajo_id = Column(String(10), ForeignKey('trabajos.id'), nullable=False)
    nombre = Column(String(200), nullable=False)
    duracion = Column(Integer, nullable=False)  # minutos
    maquina_requerida = Column(String(10), ForeignKey('maquinas.id'))
    tiempo_setup = Column(Integer, default=0)  # minutos
    orden = Column(Integer)  # Para precedencias
    
    # Relaciones
    trabajo = relationship("Trabajo", back_populates="tareas")
    
    def __repr__(self):
        return f"<Tarea(id={self.id}, nombre={self.nombre}, duracion={self.duracion})>"


# ============================================================================
# PROGRAMACIONES (OPTIMIZACIONES)
# ============================================================================

class Programacion(Base):
    """Programación/Optimización generada"""
    __tablename__ = 'programaciones'
    
    id = Column(String(50), primary_key=True)  # PROG-2025-W41-001
    
    # Información temporal
    semana_produccion = Column(Integer, nullable=False)  # 41, 42, etc
    anio = Column(Integer, nullable=False)  # 2025
    fecha_creacion = Column(DateTime, default=datetime.now)
    
    # Estado
    estado = Column(Enum(EstadoProgramacion), default=EstadoProgramacion.SIMULACION)
    
    # Parámetros de optimización usados
    objetivo_usado = Column(String(50))  # 'minimizar_tiempo', 'maximizar_utilizacion', etc
    tiempo_resolucion = Column(Float)  # segundos
    
    # Resultados planificados
    makespan_planificado = Column(Integer)  # minutos
    num_trabajos = Column(Integer)
    num_tareas = Column(Integer)
    costo_estimado = Column(Float)
    
    # Aprobación
    usuario_creador = Column(String(100))
    aprobada_por = Column(String(100))
    fecha_aprobacion = Column(DateTime)
    
    # Notas
    notas = Column(Text)
    configuracion_json = Column(Text)  # JSON con toda la config usada
    
    # Relaciones
    tareas_planificadas = relationship("TareaPlanificada", back_populates="programacion", cascade="all, delete-orphan")
    metricas = relationship("MetricaCalculada", back_populates="programacion", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Programacion(id={self.id}, semana={self.semana_produccion}, estado={self.estado.value})>"


class TareaPlanificada(Base):
    """Tareas planificadas en una programación específica"""
    __tablename__ = 'tareas_planificadas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relaciones
    programacion_id = Column(String(50), ForeignKey('programaciones.id'), nullable=False)
    tarea_id = Column(String(20))  # Referencia a la tarea original
    trabajo_id = Column(String(10))
    
    # Información de la tarea
    nombre = Column(String(200), nullable=False)
    duracion_planificada = Column(Integer, nullable=False)  # minutos
    tiempo_setup = Column(Integer, default=0)
    
    # Asignación
    maquina_id = Column(String(10), ForeignKey('maquinas.id'), nullable=False)
    operador_id = Column(String(10), ForeignKey('operadores.id'))
    
    # Tiempos planificados (en minutos desde inicio de semana)
    inicio_planificado = Column(Integer, nullable=False)
    fin_planificado = Column(Integer, nullable=False)
    
    # Información procesada (formato UI)
    inicio_hora = Column(String(10))  # Formato HH:MM (ej: 08:00, 18:00)
    fin_hora = Column(String(10))  # Formato HH:MM (ej: 14:15, 18:00)
    dia_nombre = Column(String(10))  # Día en formato texto (ej: Lun, Mar, Mié)
    
    # Información adicional
    dia_semana = Column(Integer)  # 0=Lunes, 1=Martes, etc
    es_dividida = Column(Boolean, default=False)
    parte_numero = Column(Integer, default=1)  # 1, 2 si está dividida
    
    # Relaciones
    programacion = relationship("Programacion", back_populates="tareas_planificadas")
    maquina = relationship("Maquina", back_populates="tareas_planificadas")
    operador = relationship("Operador", back_populates="tareas_planificadas")
    ejecucion_real = relationship("EjecucionReal", back_populates="tarea_planificada", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TareaPlanificada(id={self.id}, tarea={self.tarea_id}, maquina={self.maquina_id})>"


# ============================================================================
# EJECUCIÓN REAL (TRACKING)
# ============================================================================

class EjecucionReal(Base):
    """Registro de ejecución real de tareas en producción"""
    __tablename__ = 'ejecucion_real'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relación con tarea planificada
    tarea_planificada_id = Column(Integer, ForeignKey('tareas_planificadas.id'), nullable=False)
    
    # Tiempos reales
    inicio_real = Column(DateTime)
    fin_real = Column(DateTime)
    duracion_real = Column(Integer)  # minutos
    
    # Recursos reales usados
    maquina_usada = Column(String(10), ForeignKey('maquinas.id'))
    operador_ejecutor = Column(String(10), ForeignKey('operadores.id'))
    
    # Estado y desviaciones
    estado = Column(Enum(EstadoTarea), default=EstadoTarea.PENDIENTE)
    desviacion_inicio = Column(Integer)  # minutos (+ = retraso, - = adelanto)
    desviacion_fin = Column(Integer)
    desviacion_duracion = Column(Integer)
    
    # Problemas e incidencias
    problemas_encontrados = Column(Text)
    tiempo_paradas = Column(Integer, default=0)  # minutos
    notas_operador = Column(Text)
    
    # Metadata
    registrado_por = Column(String(100))
    fecha_registro = Column(DateTime, default=datetime.now)
    
    # Relaciones
    tarea_planificada = relationship("TareaPlanificada", back_populates="ejecucion_real")
    
    def __repr__(self):
        return f"<EjecucionReal(id={self.id}, estado={self.estado.value})>"


# ============================================================================
# MÉTRICAS Y KPIs
# ============================================================================

class MetricaCalculada(Base):
    """KPIs calculados para cada programación completada"""
    __tablename__ = 'metricas_calculadas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relación con programación
    programacion_id = Column(String(50), ForeignKey('programaciones.id'), unique=True, nullable=False)
    
    # Metadata
    fecha_calculo = Column(DateTime, default=datetime.now)
    
    # KPIs Globales
    oee_global = Column(Float)  # Overall Equipment Effectiveness (%)
    disponibilidad_oee = Column(Float)  # Disponibilidad componente del OEE (%)
    rendimiento_oee = Column(Float)  # Rendimiento componente del OEE (%)
    calidad_oee = Column(Float)  # Calidad componente del OEE (%)
    throughput_semanal = Column(Integer)  # Trabajos completados
    lead_time_promedio = Column(Float)  # Días promedio (reutilizado para utilización global)
    
    # Utilización por máquina (%)
    utilizacion_m1 = Column(Float)
    utilizacion_m2 = Column(Float)
    utilizacion_m3 = Column(Float)
    
    # Tiempos por máquina
    tiempo_productivo_m1 = Column(Integer)  # minutos
    tiempo_productivo_m2 = Column(Integer)
    tiempo_productivo_m3 = Column(Integer)
    tiempo_ocioso_m1 = Column(Integer)
    tiempo_ocioso_m2 = Column(Integer)
    tiempo_ocioso_m3 = Column(Integer)
    tiempo_setup_m1 = Column(Integer)
    tiempo_setup_m2 = Column(Integer)
    tiempo_setup_m3 = Column(Integer)
    
    # Cumplimiento
    otif_porcentaje = Column(Float)  # On-Time In-Full (%)
    tareas_a_tiempo = Column(Integer)
    tareas_retrasadas = Column(Integer)
    tareas_adelantadas = Column(Integer)  # Tareas completadas antes de lo planificado
    
    # Desviaciones
    desviacion_promedio = Column(Float)  # minutos
    desviacion_maxima = Column(Float)
    
    # Costos
    costo_real = Column(Float)
    costo_maquinas = Column(Float)
    costo_operadores = Column(Float)
    costo_penalizaciones = Column(Float)
    costo_setup = Column(Float)
    
    # Análisis
    cuello_botella_identificado = Column(String(10))  # ID de máquina
    makespan_real = Column(Integer)  # minutos
    diferencia_makespan = Column(Integer)  # real - planificado
    
    # Relaciones
    programacion = relationship("Programacion", back_populates="metricas")
    
    def __repr__(self):
        return f"<MetricaCalculada(programacion_id={self.programacion_id}, oee={self.oee_global})>"


# ============================================================================
# CONFIGURACIÓN DEL SISTEMA
# ============================================================================

class ConfiguracionSistema(Base):
    """Configuración global del sistema"""
    __tablename__ = 'configuracion_sistema'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    clave = Column(String(50), unique=True, nullable=False)
    valor = Column(Text)
    tipo = Column(String(20))  # 'string', 'int', 'float', 'boolean', 'json'
    descripcion = Column(Text)
    fecha_modificacion = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ConfiguracionSistema(clave={self.clave}, valor={self.valor})>"


# ============================================================================
# UTILIDADES
# ============================================================================

def crear_todas_las_tablas(engine):
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(engine)
    print("✅ Todas las tablas creadas exitosamente")


def eliminar_todas_las_tablas(engine):
    """CUIDADO: Elimina todas las tablas"""
    Base.metadata.drop_all(engine)
    print("⚠️ Todas las tablas eliminadas")


if __name__ == "__main__":
    # Ejemplo de uso
    from sqlalchemy import create_engine
    
    # Crear engine SQLite
    engine = create_engine('sqlite:///produccion.db', echo=True)
    
    # Crear todas las tablas
    crear_todas_las_tablas(engine)
    
    print("\n✅ Base de datos inicializada correctamente")
    print("\nTablas creadas:")
    for tabla in Base.metadata.tables.keys():
        print(f"  - {tabla}")

