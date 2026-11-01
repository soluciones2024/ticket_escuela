import sqlite3
from datetime import datetime

class SoporteEscuelaModel:
    def __init__(self, db_name="soporte_escuela.db"):
        self.db_name = db_name
        self.conectar_bd()

    def conectar_bd(self):
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            
            # 1. Tabla de Usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    nombre_completo TEXT NOT NULL,
                    sala_asignada TEXT DEFAULT 'Sala 1',
                    permisos TEXT DEFAULT 'Tickets'
                )
            """)

            # 2. Tabla de Salas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS salas (
                    nombre_sala TEXT PRIMARY KEY,
                    pabellon TEXT NOT NULL,
                    capacidad_alumnos INTEGER
                )
            """)

            # 3. Historial de Auditoría de Salas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bitacora_salas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_sala TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    fecha_accion TEXT NOT NULL,
                    operario TEXT NOT NULL
                )
            """)

            # 4. Catálogo de Equipamiento Real por Sala
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventario_sala (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sala TEXT NOT NULL,
                    nombre_equipo TEXT NOT NULL,
                    codigo_inventario TEXT UNIQUE,
                    marca TEXT,
                    modelo TEXT,
                    serie TEXT
                )
            """)

            # 5. Historial de Auditoría / Movimientos de Inventario
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bitacora_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo_inventario TEXT NOT NULL,
                    sala_origen TEXT,
                    sala_destino TEXT,
                    accion TEXT NOT NULL,
                    fecha_movimiento TEXT NOT NULL,
                    operario TEXT NOT NULL
                )
            """)

            # 6. Tabla de Tickets Escolares (Se añaden campos de resolución e informático)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    solicitante TEXT NOT NULL,
                    sala TEXT NOT NULL,
                    tipo_equipo TEXT NOT NULL,
                    codigo_inventario TEXT,
                    descripcion_falla TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    fecha_reporte TEXT NOT NULL,
                    prioridad TEXT DEFAULT 'Media',
                    fecha_solucion TEXT,
                    tipo_solucion TEXT,        -- 'Reparación en Sitio', 'Cambio Componente', 'Garantía'
                    comentario_tecnico TEXT,
                    fecha_planificada TEXT,     -- Calendario de planificación técnica
                    FOREIGN KEY(solicitante) REFERENCES usuarios(username)
                )
            """)
            
            # 7. Bitácora de Reparación / Hoja de Vida Atómica del Dispositivo
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bitacora_reparaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    codigo_inventario TEXT,     -- Amarre directo para la Hoja de Vida
                    tecnico TEXT NOT NULL,
                    fecha_accion TEXT NOT NULL,
                    componente_cambiado TEXT,
                    detalles_tecnicos TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
                )
            """)

            # 8. Tabla para Planificación de Mantenimientos Preventivos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mantenimientos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sala TEXT NOT NULL,
                    tarea_programada TEXT NOT NULL,
                    fecha_programada TEXT NOT NULL,
                    estado TEXT DEFAULT 'Agendado'
                )
            """)

            # 9. Tabla para Control y Préstamo de Carritos Móviles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prestamos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    carrito_nombre TEXT NOT NULL,
                    docente TEXT NOT NULL,
                    sala_destino TEXT NOT NULL,
                    bloque_horario TEXT NOT NULL,
                    fecha_prestamo TEXT NOT NULL,
                    estado TEXT DEFAULT 'Reservado',
                    observaciones TEXT
                )
            """)
            conexion.commit()
        self._inyectar_datos_demo()

    def _inyectar_datos_demo(self):
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT OR IGNORE INTO salas VALUES ('Sala 1', 'Pabellón Central', 35)")
            cursor.execute("INSERT OR IGNORE INTO salas VALUES ('Laboratorio Computación', 'Bloque Tecnológico', 40)")
            cursor.execute("INSERT OR IGNORE INTO salas VALUES ('Biblioteca', 'Bloque Tecnológico', 50)")
            cursor.execute("INSERT OR IGNORE INTO salas VALUES ('Oficina TI', 'Bloque Tecnológico', 5)")
            
            cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol, nombre_completo, sala_asignada, permisos) VALUES ('profesor1', 'profe123', 'Profesor', 'Carlos Mendoza', 'Laboratorio Computación', 'Tickets')")
            cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol, nombre_completo, sala_asignada, permisos) VALUES ('admin_soporte', 'tec123', 'Informático', 'Soporte TI Escuela', 'Oficina TI', 'Tickets,Bitacora,Carritos,Usuarios,Inventario,Salas,Actas')")
            
            cursor.execute("INSERT OR IGNORE INTO inventario_sala (sala, nombre_equipo, codigo_inventario, marca, modelo, serie) VALUES ('Laboratorio Computación', 'Proyector Epson Techo', 'PRY-LAB-01', 'Epson', 'PowerLite X41', 'X41-998877')")
            cursor.execute("INSERT OR IGNORE INTO inventario_sala (sala, nombre_equipo, codigo_inventario, marca, modelo, serie) VALUES ('Laboratorio Computación', 'PC Alumno Torre/Escritorio', 'PC-LAB-A01', 'HP', 'ProDesk 400', 'G6-554433')")
            conexion.commit()

    def registrar_accion_sala(self, nombre_sala, accion, operario):
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO bitacora_salas (nombre_sala, accion, fecha_accion, operario) VALUES (?, ?, ?, ?)", (nombre_sala, accion, ahora, operario))
            conexion.commit()

    def registrar_movimiento_inventario(self, codigo, origen, destino, accion, operario):
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO bitacora_inventario (codigo_inventario, sala_origen, sala_destino, accion, fecha_movimiento, operario) VALUES (?, ?, ?, ?, ?, ?)", (codigo, origen, destino, accion, ahora, operario))
            conexion.commit()

    def crear_ticket_escuela(self, solicitante, sala, tipo_equipo, codigo, descripcion, prioridad='Media'):
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO tickets (solicitante, sala, tipo_equipo, codigo_inventario, descripcion_falla, estado, fecha_reporte, prioridad) VALUES (?, ?, ?, ?, ?, 'Abierto', ?, ?)", (solicitante, sala, tipo_equipo, codigo, descripcion, ahora, prioridad))
            conexion.commit()

    def registrar_en_bitacora(self, ticket_id, codigo_inv, tecnico, componente, detalles):
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO bitacora_reparaciones (ticket_id, codigo_inventario, tecnico, fecha_accion, componente_cambiado, detalles_tecnicos) VALUES (?, ?, ?, ?, ?, ?)", (ticket_id, codigo_inv, tecnico, ahora, componente, detalles))
            conexion.commit()

    def agendar_mantenimiento(self, sala, tarea, fecha):
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO mantenimientos (sala, tarea_programada, fecha_programada) VALUES (?, ?, ?)", (sala, tarea, fecha))
            conexion.commit()

    def registrar_prestamo(self, carrito, docente, sala, bloque, fecha):
        with sqlite3.connect(self.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("INSERT INTO prestamos (carrito_nombre, docente, sala_destino, bloque_horario, fecha_prestamo) VALUES (?, ?, ?, ?, ?)", (carrito, docente, sala, bloque, fecha))
            conexion.commit()
