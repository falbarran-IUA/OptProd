#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Migración: JSON → SQLite
Optimizador de Producción v1.3

Migra la configuración desde JSON y session_state a la base de datos SQLite
"""

import json
import os
import sys
from datetime import datetime

# Fix encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from modelos.database import (
    db_manager, crear_maquina, crear_operador,
    inicializar_datos_default, obtener_estadisticas_generales
)

def migrar_configuracion_json():
    """Migrar configuración desde JSON a BD"""
    
    config_path = 'datos/configuracion.json'
    
    if not os.path.exists(config_path):
        print(f"⚠️ No se encontró {config_path}")
        print("   Usando configuración por defecto...")
        inicializar_datos_default()
        return
    
    print(f"📂 Leyendo configuración desde {config_path}...")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Migrar máquinas
    if 'recursos' in config and 'maquinas' in config['recursos']:
        print("\n🔧 Migrando máquinas...")
        for maq in config['recursos']['maquinas']:
            try:
                crear_maquina(
                    id=maq['id'],
                    nombre=maq['nombre'],
                    capacidad=maq.get('capacidad', 1),
                    tiempo_setup=maq.get('tiempo_setup', 0),
                    costo_por_hora=config.get('costos', {}).get('costo_por_hora_maquina', {}).get(maq['id'], 50.0)
                )
                print(f"  ✅ {maq['id']}: {maq['nombre']}")
            except Exception as e:
                print(f"  ⚠️ {maq['id']} ya existe o error: {e}")
    
    # Migrar operadores
    if 'recursos' in config and 'operadores' in config['recursos']:
        print("\n👷 Migrando operadores...")
        for op in config['recursos']['operadores']:
            try:
                crear_operador(
                    id=op['id'],
                    nombre=op['nombre'],
                    habilidades=op.get('habilidades', []),
                    costo_por_hora=config.get('costos', {}).get('costo_por_hora_operador', 25.0)
                )
                print(f"  ✅ {op['id']}: {op['nombre']}")
            except Exception as e:
                print(f"  ⚠️ {op['id']} ya existe o error: {e}")
    
    print("\n✅ Migración de configuración completada")


def verificar_migracion():
    """Verificar que la migración fue exitosa"""
    
    print("\n" + "="*60)
    print("📊 VERIFICACIÓN DE MIGRACIÓN")
    print("="*60)
    
    stats = obtener_estadisticas_generales()
    
    print("\nEstadísticas del sistema:")
    print(f"  • Máquinas: {stats['total_maquinas']}")
    print(f"  • Operadores: {stats['total_operadores']}")
    print(f"  • Trabajos: {stats['total_trabajos']}")
    print(f"  • Programaciones: {stats['total_programaciones']}")
    
    if stats['total_maquinas'] >= 3 and stats['total_operadores'] >= 3:
        print("\n✅ Migración exitosa - Base de datos lista para usar")
        return True
    else:
        print("\n⚠️ Advertencia: Faltan datos básicos")
        return False


def main():
    """Proceso principal de migración"""
    
    print("="*60)
    print("🔄 MIGRACIÓN DE DATOS: JSON → SQLite")
    print("   Optimizador de Producción v1.3")
    print("="*60)
    
    # 1. Crear tablas
    print("\n1️⃣ Creando estructura de base de datos...")
    db_manager.crear_tablas()
    print("   ✅ Tablas creadas")
    
    # 2. Migrar configuración
    print("\n2️⃣ Migrando configuración desde JSON...")
    migrar_configuracion_json()
    
    # 3. Verificar
    print("\n3️⃣ Verificando migración...")
    exito = verificar_migracion()
    
    if exito:
        print("\n" + "="*60)
        print("🎉 ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!")
        print("="*60)
        print("\n📝 Próximos pasos:")
        print("   1. La aplicación ahora usará la base de datos SQLite")
        print("   2. Archivo de BD: datos/produccion.db")
        print("   3. Los archivos JSON se mantienen como backup")
        print("   4. Ejecuta: streamlit run app_semanal.py")
    else:
        print("\n⚠️ Migración completada con advertencias")
        print("   Revisa los mensajes anteriores")
    
    print()


if __name__ == "__main__":
    main()

