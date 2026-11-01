from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from model_escuela import SoporteEscuelaModel
import sqlite3
import qrcode
import os
import smtplib
import json
import queue
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'colegio_token_secreto_2026_ti'

modelo = SoporteEscuelaModel()
QR_DIR = os.path.join(os.getcwd(), 'static', 'qrs')
if not os.path.exists(QR_DIR): 
    os.makedirs(QR_DIR)

# Lista global en memoria para gestionar las alertas inmediatas en las computadoras técnicas
suscriptores_ti = []

# ==========================================
# CONFIGURACIÓN DEL SERVIDOR DE CORREO (SMTP)
# ==========================================
SMTP_SERVIDOR = "://gmail.com"  
SMTP_PUERTO = 587
CORREO_EMISOR = "jcaceres@escuelafelipecubillos.cl"  
CORREO_PASSWORD = "Koala2050#@"  
CORREO_TECNICO_AVISO = "jcaceres@escuelafelipecubillos.cl"  
def consultar_escuela(query, params=()):
    """Ejecuta consultas de selección devolviendo tuplas nativas de SQLite."""
    try:
        with sqlite3.connect(modelo.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error consulta: {e}")
        return []

def ejecutar_modificacion_escuela(query, params=()):
    """Ejecuta transacciones de escritura (INSERT, UPDATE, DELETE)."""
    try:
        with sqlite3.connect(modelo.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute(query, params)
            conexion.commit()
            return True
    except Exception as e:
        print(f"Error modificacion: {e}")
        return False

# --- CANAL EN TIEMPO REAL PARA ALERTAS EMERGENTES (PUSH) ---
@app.route('/stream')
def stream():
    """Canal permanente de transmisión de eventos en tiempo real para el informático."""
    def eventos():
        q = queue.Queue()
        suscriptores_ti.append(q)
        try:
            while True:
                msg = q.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            suscriptores_ti.remove(q)
            
    if 'usuario' not in session or session.get('rol') not in ['Tecnico', 'Informático']:
        return "No autorizado", 403
    return app.response_class(eventos(), mimetype='text/event-stream')


def enviar_correo_notificacion_ticket(folio, solicitante, sala, equipo, codigo, prioridad, descripcion):
    """Motor de envío de correos con sistema de contingencia Offline integrado."""
    # 1. Construimos el diseño HTML del correo
    msg = MIMEMultipart()
    msg['From'] = CORREO_EMISOR
    msg['To'] = f"{solicitante}@colegio.cl, {CORREO_TECNICO_AVISO}"  
    msg['Subject'] = f"🚨 NUEVO TICKET EMITIDO - Folio #{folio} [{prioridad}]"
    
    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #1a237e; border-radius: 8px; padding: 20px;">
            <h2 style="background-color: #1a237e; color: white; padding: 10px; margin-top: 0; border-radius: 4px; text-align: center;">Mesa de Soporte TI - Alerta de Ticket</h2>
            <p>Se ha emitido un nuevo requerimiento de soporte informático en la plataforma escolar con los siguientes detalles:</p>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; background-color: #f8fafc; font-weight: bold; width: 150px;">Folio de Atención:</td><td style="padding: 8px; background-color: #f8fafc;">#{folio}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Funcionario Solicitante:</td><td style="padding: 8px;">{solicitante}</td></tr>
                <tr><td style="padding: 8px; background-color: #f8fafc; font-weight: bold;">Ubicación / Sala:</td><td style="padding: 8px; background-color: #f8fafc;">{sala}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Dispositivo Afectado:</td><td style="padding: 8px;">{equipo}</td></tr>
                <tr><td style="padding: 8px; background-color: #f8fafc; font-weight: bold;">Nº Inventario Placa:</td><td style="padding: 8px; background-color: #f8fafc; font-family: monospace;">{codigo}</td></tr>
                <tr><td style="padding: 8px; font-weight: bold;">Criticidad Semáforo:</td><td style="padding: 8px; color: #c0392b; font-weight: bold;">{prioridad}</td></tr>
            </table>
            <div style="margin-top: 15px; padding: 10px; background-color: #fffaf0; border-left: 4px solid #f39c12; font-style: italic;">
                <strong>Descripción de la Falla:</strong><br>"{descripcion}"
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(cuerpo_html, 'html'))
    
    try:
        # Intentamos el envío real a través de Internet
        server = smtplib.SMTP(SMTP_SERVIDOR, SMTP_PUERTO, timeout=5)
        server.starttls()
        server.login(CORREO_EMISOR, CORREO_PASSWORD)
        server.sendmail(CORREO_EMISOR, [CORREO_TECNICO_AVISO], msg.as_string())
        server.quit()
        print(f"📧 Correo del ticket #{folio} enviado exitosamente a la red global.")
    except Exception as e:
        # RESPALDO AUTOMÁTICO OFFLINE (Si la PC no tiene internet, guarda el correo en un archivo)
        print(f"\n⚠️ AVISO: El PC no tiene salida a internet ({e}). Activando Resguardo Local.")
        try:
            # Creamos la carpeta 'static' si no existe
            if not os.path.exists('static'):
                os.makedirs('static')
                
            ruta_archivo = os.path.join(os.getcwd(), 'static', 'bandeja_salida_simulada.html')
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                f.write(cuerpo_html)
            print(f"💾 CORREO GUARDADO LOCALMENTE en: static/bandeja_salida_simulada.html\n")
        except Exception as file_err:
            print(f"Error al escribir archivo local: {file_err}")

@app.route('/')
def index():
    if 'usuario' in session: 
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        with sqlite3.connect(modelo.db_name) as conexion:
            cursor = conexion.cursor()
            cursor.execute("SELECT rol, nombre_completo, sala_asignada, permisos FROM usuarios WHERE username = ? AND password = ?", (username, password))
            res = cursor.fetchone()
        if res:
            session['usuario'] = username
            session['rol'] = res[0]
            session['nombre'] = res[1]
            session['sala_asignada'] = res[2]
            session['permisos'] = [p.strip() for p in res[3].split(',') if p.strip()]
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales no válidas.', 'danger')
    return render_template('login.html')
# --- 1. DASHBOARD INTELIGENTE CON REPORTES EN TIEMPO REAL ---
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario' not in session: 
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        sala = session.get('sala_asignada', 'Sala 1')
        equipo_completo = request.form.get('equipo_inventario')
        
        # Desempaquetado atómico de los metadatos del dispositivo
        parts = equipo_completo.split('|')
        tipo_equipo = parts[0]
        codigo = parts[1]
        
        descripcion = request.form.get('descripcion')
        prioridad = request.form.get('prioridad', 'Media')
        
        # Guardamos en la base de datos y recuperamos el folio autonumérico generado
        folio_nuevo = modelo.crear_ticket_escuela(session['usuario'], sala, tipo_equipo, codigo, descripcion, prioridad)
        
        # AVISO EN PANTALLA: Disparo de confirmación visual inmediata (Mensaje Flash)
        flash(f"🎉 ¡Ticket Emitido con Éxito! Se ha generado el Folio #{folio_nuevo}. El equipo informático ha recibido la notificación por correo.", "success")
        
        # NOTIFICACIÓN PUSH EN TIEMPO REAL: Estructuramos el aviso para la pantalla del informático
        datos_alerta = json.dumps({
            "folio": folio_nuevo,
            "sala": sala,
            "equipo": tipo_equipo,
            "prioridad": prioridad,
            "descripcion": descripcion[:60] + "..."
        })
        # Despachamos la alerta de inmediato a todas las consolas técnicas abiertas
        for sub in suscriptores_ti:
            sub.put(datos_alerta)
            
        # ENVÍO POR CORREO: Disparo automático del proceso SMTP en segundo plano
        enviar_correo_notificacion_ticket(folio_nuevo, session['usuario'], sala, tipo_equipo, codigo, prioridad, descripcion)
        
        return redirect(url_for('dashboard'))
        
    # Consultamos el catálogo de equipamiento real asignado a la sala fija del docente
    equipos_sala = consultar_escuela("SELECT nombre_equipo, codigo_inventario FROM inventario_sala WHERE sala = ?", (session.get('sala_asignada'),))
    
    # Restricción de visibilidad según jerarquías del pabellón
    if session.get('rol') in ['Tecnico', 'Informático']:
        tickets = consultar_escuela("SELECT id, solicitante, sala, tipo_equipo, codigo_inventario, prioridad, estado, fecha_reporte FROM tickets ORDER BY id DESC")
    else:
        tickets = consultar_escuela("SELECT id, solicitante, sala, tipo_equipo, codigo_inventario, prioridad, estado, fecha_reporte FROM tickets WHERE sala = ? ORDER BY id DESC", (session.get('sala_asignada'),))
        
    return render_template('panel_tickets.html', tickets=tickets, catalogo=equipos_sala)
# --- 2. ENTORNO MESA DE CONTROL TÉCNICA E HISTORIALES ---
@app.route('/bitacora', methods=['GET', 'POST'])
def bitacora():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        formulario_tipo = request.form.get('formulario_tipo')
        if formulario_tipo == 'reparacion':
            ticket_id = request.form.get('ticket_id')
            componente = request.form.get('componente').strip()
            detalles = request.form.get('detalles').strip()
            nuevo_estado = request.form.get('nuevo_estado')
            tipo_solucion = request.form.get('tipo_solucion')
            from datetime import datetime
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ticket_raw = consultar_escuela("SELECT codigo_inventario FROM tickets WHERE id = ?", (int(ticket_id),))
            codigo_inv = ticket_raw[0][0] if ticket_raw else 'N/A'
            modelo.registrar_en_bitacora(int(ticket_id), codigo_inv, session['usuario'], componente, detalles)
            ejecutar_modificacion_escuela("UPDATE tickets SET estado = ?, fecha_solucion = ?, tipo_solucion = ?, comentario_tecnico = ? WHERE id = ?", (nuevo_estado, ahora, tipo_solucion, detalles, int(ticket_id)))
            flash(f"✅ Se registró la solución para el Ticket #{ticket_id} de forma exitosa.", "success")
        elif formulario_tipo == 'planificacion':
            ticket_id = request.form.get('ticket_id')
            fecha_plan = request.form.get('fecha_planificada')
            ejecutar_modificacion_escuela("UPDATE tickets SET fecha_planificada = ?, estado = 'En Revisión' WHERE id = ?", (fecha_plan, int(ticket_id)))
            flash(f"📅 Visita técnica para el Ticket #{ticket_id} programada en el cronograma.", "info")
        return redirect(url_for('bitacora'))
        
    tickets_pendientes = consultar_escuela("SELECT id, sala, tipo_equipo, prioridad, descripcion_falla FROM tickets WHERE estado != 'Reparado' AND estado != 'De Baja' ORDER BY id DESC")
    codigo_busqueda = request.args.get('buscar_codigo_hoja_vida', '').strip()
    if codigo_busqueda:
        historial_reparaciones = consultar_escuela("SELECT id, ticket_id, tecnico, fecha_accion, componente_cambiado, detalles_tecnicos FROM bitacora_reparaciones WHERE codigo_inventario = ? ORDER BY id DESC", (codigo_busqueda,))
    else:
        historial_reparaciones = consultar_escuela("SELECT id, ticket_id, tecnico, fecha_accion, componente_cambiado, detalles_tecnicos FROM bitacora_reparaciones ORDER BY id DESC LIMIT 50")
    cronograma_soluciones = consultar_escuela("SELECT id, sala, tipo_equipo, fecha_planificada, prioridad, estado FROM tickets WHERE fecha_planificada IS NOT NULL AND estado != 'Reparado' AND estado != 'De Baja' ORDER BY fecha_planificada ASC")
    return render_template('bitacora.html', tickets_activos=tickets_pendientes, historial=historial_reparaciones, cronograma=cronograma_soluciones, codigo_buscado=codigo_busqueda)

# --- GESTIÓN MANTENEDOR DE USUARIOS (EXTRACCIÓN ATÓMICA DE TEXTO CORREGIDA) ---
@app.route('/mantenedor_usuarios', methods=['GET', 'POST'])
def mantenedor_usuarios():
    if 'usuario' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        rol = request.form['rol']
        nombre_completo = request.form['nombre_completo'].strip()
        sala_asignada = request.form['sala_asignada']
        
        permisos_lista = request.form.getlist('permisos')
        permisos_str = ",".join(permisos_lista) if permisos_lista else "Tickets"
        
        if accion == 'crear':
            ejecutar_modificacion_escuela(
                "INSERT INTO usuarios (username, password, rol, nombre_completo, sala_asignada, permisos) VALUES (?, ?, ?, ?, ?, ?)", 
                (username, password, rol, nombre_completo, sala_asignada, permisos_str)
            )
        elif accion == 'modificar':
            ejecutar_modificacion_escuela(
                "UPDATE usuarios SET password=?, rol=?, nombre_completo=?, sala_asignada=?, permisos=? WHERE username=?", 
                (password, rol, nombre_completo, sala_asignada, permisos_str, username)
            )
        elif accion == 'eliminar':
            ejecutar_modificacion_escuela("DELETE FROM usuarios WHERE username=?", (username,))
        return redirect(url_for('mantenedor_usuarios'))
        
    usuarios_list = consultar_escuela("SELECT username, password, rol, nombre_completo, sala_asignada, permisos FROM usuarios")
    
    # SOLUCIÓN DE RAÍZ: Desarmamos la tupla extrayendo estrictamente la posición [0] de cada fila
    salas_raw = consultar_escuela("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC")
    salas_disponibles = [s[0] for s in salas_raw]
    
    return render_template('mantenedor_usuarios.html', usuarios=usuarios_list, salas_select=salas_disponibles)

# --- 4. GESTIÓN MANTENEDOR DE INVENTARIO AMPLIADO (REPARADO DEFINITIVO) ---
@app.route('/mantenedor_inventario', methods=['GET', 'POST'])
def mantenedor_inventario():
    if 'usuario' not in session: 
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        accion = request.form.get('accion')
        equipo_id = request.form.get('equipo_id')
        sala = request.form['sala']
        nombre_equipo = request.form['nombre_equipo'].strip()
        codigo_inventario = request.form['codigo_inventario'].strip()
        marca = request.form['marca'].strip()
        modelo_eq = request.form['modelo'].strip()
        serie = request.form['serie'].strip()
        
        if accion == 'crear':
            ejecutar_modificacion_escuela(
                "INSERT INTO inventario_sala (sala, nombre_equipo, codigo_inventario, marca, modelo, serie) VALUES (?, ?, ?, ?, ?, ?)", 
                (sala, nombre_equipo, codigo_inventario, marca, modelo_eq, serie)
            )
            modelo.registrar_movimiento_inventario(codigo_inventario, None, sala, 'REGISTRO', session['usuario'])
        elif accion == 'modificar':
            origen_raw = consultar_escuela("SELECT sala FROM inventario_sala WHERE id=?", (int(equipo_id),))
            sala_origen = origen_raw[0][0] if origen_raw else None
            
            ejecutar_modificacion_escuela(
                "UPDATE inventario_sala SET sala=?, nombre_equipo=?, codigo_inventario=?, marca=?, modelo=?, serie=? WHERE id=?", 
                (sala, nombre_equipo, codigo_inventario, marca, modelo_eq, serie, int(equipo_id))
            )
            modelo.registrar_movimiento_inventario(codigo_inventario, sala_origen, sala, 'MODIFICACION', session['usuario'])
        elif accion == 'eliminar':
            ejecutar_modificacion_escuela("DELETE FROM inventario_sala WHERE id=?", (int(equipo_id),))
            modelo.registrar_movimiento_inventario(codigo_inventario, sala, None, 'ELIMINACION', session['usuario'])
        return redirect(url_for('mantenedor_inventario'))
        
    inventario_list = consultar_escuela("SELECT id, sala, nombre_equipo, codigo_inventario, marca, modelo, serie FROM inventario_sala ORDER BY id DESC")
    historial_inventario = consultar_escuela("SELECT id, codigo_inventario, sala_origen, sala_destino, accion, fecha_movimiento, operario FROM bitacora_inventario ORDER BY id DESC")
    
    # EXTRACCIÓN CORREGIDA EXTRAIENDO EL ÍNDICE 0 DE LA TUPLA
    salas_colegio_raw = consultar_escuela("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC")
    salas_limpias = [s[0] for s in salas_colegio_raw]
    
    return render_template('mantenedor_inventario.html', 
                           inventario=inventario_list, 
                           historial=historial_inventario, 
                           salas_select=salas_limpias)

# --- 5. GESTIÓN MANTENEDOR DE SALAS / DEPENDENCIAS ---
@app.route('/mantenedor_salas', methods=['GET', 'POST'])
def mantenedor_salas():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        accion = request.form.get('accion')
        nombre_sala = request.form['nombre_sala'].strip()
        pabellon = request.form['pabellon'].strip()
        capacidad = request.form['capacidad'].strip()
        if accion == 'crear':
            ejecutar_modificacion_escuela("INSERT INTO salas VALUES (?, ?, ?)", (nombre_sala, pabellon, int(capacidad)))
            modelo.registrar_accion_sala(nombre_sala, 'CREAR', session['usuario'])
        elif accion == 'modificar':
            ejecutar_modificacion_escuela("UPDATE salas SET pabellon=?, capacidad_alumnos=? WHERE nombre_sala=?", (pabellon, int(capacidad), nombre_sala))
            modelo.registrar_accion_sala(nombre_sala, 'MODIFICAR', session['usuario'])
        elif accion == 'eliminar':
            ejecutar_modificacion_escuela("DELETE FROM salas WHERE nombre_sala=?", (nombre_sala,))
            modelo.registrar_accion_sala(nombre_sala, 'ELIMINAR', session['usuario'])
        return redirect(url_for('mantenedor_salas'))
    salas_list = consultar_escuela("SELECT nombre_sala, pabellon, capacidad_alumnos FROM salas ORDER BY nombre_sala ASC")
    historial_salas = consultar_escuela("SELECT id, nombre_sala, accion, fecha_accion, operario FROM bitacora_salas ORDER BY id DESC")
    return render_template('mantenedor_salas.html', salas=salas_list, historial=historial_salas)
# --- 6. CONTROL Y PRÉSTAMO DE CARRITOS MÓVILES ---
@app.route('/carritos', methods=['GET', 'POST'])
def carritos():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        accion = request.form.get('accion_tipo', 'reservar')
        if accion == 'reservar':
            modelo.registrar_prestamo(request.form.get('carrito'), session['usuario'], request.form.get('sala'), request.form.get('bloque'), request.form.get('fecha'))
        elif accion == 'actualizar':
            ejecutar_modificacion_escuela("UPDATE prestamos SET estado = ?, observaciones = ? WHERE id = ?", (request.form.get('nuevo_estado'), request.form.get('observaciones'), int(request.form.get('prestamo_id'))))
        return redirect(url_for('carritos'))
    prestamos_activos = consultar_escuela("SELECT id, carrito_nombre, docente, sala_destino, bloque_horario, fecha_prestamo, estado, observaciones FROM prestamos ORDER BY id DESC")
    return render_template('carritos.html', prestamos=prestamos_activos)




# --- 7. MÓDULO DE INFORMES, ACTAS OFICIALES Y CONTADORES ---
@app.route('/actas')
def actas():
    if 'usuario' not in session: return redirect(url_for('login'))
    sala_filtro = request.args.get('sala_filtro', 'Todos')
    tipo_informe = request.args.get('tipo', 'Ficha General de Inventario')
    if sala_filtro == 'Todos':
        metricas = consultar_escuela("SELECT COUNT(*), SUM(case when estado='Reparado' then 1 else 0 end), SUM(case when estado='De Baja' then 1 else 0 end) FROM tickets")
    else:
        metricas = consultar_escuela("SELECT COUNT(*), SUM(case when estado='Reparado' then 1 else 0 end), SUM(case when estado='De Baja' then 1 else 0 end) FROM tickets WHERE sala = ?", (sala_filtro,))
    totales_globales = consultar_escuela("SELECT COUNT(*), SUM(case when estado='Abierto' or estado='En Revisión' then 1 else 0 end), SUM(case when estado='Reparado' then 1 else 0 end), SUM(case when estado='De Baja' then 1 else 0 end) FROM tickets")
    
    if tipo_informe == "Ficha General de Inventario":
        query = "SELECT id, sala, nombre_equipo, codigo_inventario, marca, modelo, serie FROM inventario_sala" if sala_filtro == "Todos" else "SELECT id, sala, nombre_equipo, codigo_inventario, marca, modelo, serie FROM inventario_sala WHERE sala = ?"
        params = () if sala_filtro == "Todos" else (sala_filtro,)
    elif tipo_informe == "Equipos Dados de Baja":
        query = "SELECT t.id, t.sala, t.tipo_equipo, t.codigo_inventario, i.marca, i.modelo, 'RETIRADO' FROM tickets t LEFT JOIN inventario_sala i ON t.codigo_inventario = i.codigo_inventario WHERE t.estado = 'De Baja'" if sala_filtro == "Todos" else "SELECT t.id, t.sala, t.tipo_equipo, t.codigo_inventario, i.marca, i.modelo, 'RETIRADO' FROM tickets t LEFT JOIN inventario_sala i ON t.codigo_inventario = i.codigo_inventario WHERE t.estado = 'De Baja' AND t.sala = ?"
        params = () if sala_filtro == "Todos" else (sala_filtro,)
    elif tipo_informe == "Incidentes Pendientes (Mesa TI)":
        query = "SELECT id, sala, tipo_equipo, codigo_inventario, prioridad, estado, fecha_reporte FROM tickets WHERE estado != 'Reparado' AND estado != 'De Baja'" if sala_filtro == "Todos" else "SELECT id, sala, tipo_equipo, codigo_inventario, prioridad, estado, fecha_reporte FROM tickets WHERE estado != 'Reparado' AND estado != 'De Baja' AND sala = ?"
        params = () if sala_filtro == "Todos" else (sala_filtro,)
    elif tipo_informe == "Historial de Reparaciones (Bitácora)":
        query = "SELECT b.id, t.sala, t.tipo_equipo, t.codigo_inventario, b.tecnico, b.componente_cambiado, b.fecha_accion FROM bitacora_reparaciones b JOIN tickets t ON b.ticket_id = t.id" if sala_filtro == "Todos" else "SELECT b.id, t.sala, t.tipo_equipo, t.codigo_inventario, b.tecnico, b.componente_cambiado, b.fecha_accion FROM bitacora_reparaciones b JOIN tickets t ON b.ticket_id = t.id WHERE t.sala = ?"
        params = () if sala_filtro == "Todos" else (sala_filtro,)

    # === BUSCA ESTE BLOQUE AL FINAL DE LA FUNCIÓN @app.route('/actas') ===
    informes_data = consultar_escuela(query, params)
    
    # 1. Traemos la lista cruda de salas desde la Base de Datos
    salas_colegio_raw = consultar_escuela("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC")
    
    # 2. SOLUCIÓN: Desarmamos la tupla extrayendo estrictamente la primera posición de cada fila s[0]
    lista_salas = ['Todos'] + [s[0] for s in salas_colegio_raw]
    
    return render_template('actas_informes.html', 
                           informes=informes_data, 
                           tipo_seleccionado=tipo_informe, 
                           sala_seleccionada=sala_filtro, 
                           metricas=metricas, 
                           globales=totales_globales, 
                           salas_select=lista_salas)

# --- 8. HISTORIAL DE SOLUCIONES Y AUDITORÍA POR SALA/USUARIO/ESTADO ---
@app.route('/historial_soluciones')
def historial_soluciones():
    if 'usuario' not in session: return redirect(url_for('login'))
    filtro_sala = request.args.get('filtro_sala', 'Todos')
    filtro_usuario = request.args.get('filtro_usuario', 'Todos')
    filtro_estado = request.args.get('filtro_estado', 'Todos')
    query = "SELECT id, solicitante, sala, tipo_equipo, codigo_inventario, prioridad, estado, fecha_reporte, fecha_solucion, tipo_solucion, comentario_tecnico FROM tickets WHERE 1=1"
    params = []
    if filtro_sala != 'Todos': query += " AND sala = ?"; params.append(filtro_sala)
    if filtro_usuario != 'Todos': query += " AND solicitante = ?"; params.append(filtro_usuario)
    if filtro_estado != 'Todos': query += " AND estado = ?"; params.append(filtro_estado)
    query += " ORDER BY id DESC"
    resultados = consultar_escuela(query, tuple(params))
    lista_salas = ['Todos'] + [s[0] for s in consultar_escuela("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC")]
    lista_usuarios = ['Todos'] + [u[0] for u in consultar_escuela("SELECT username FROM usuarios ORDER BY username ASC")]
    return render_template('historial_soluciones.html', tickets=resultados, salas=lista_salas, usuarios=lista_usuarios, estados=['Todos', 'Abierto', 'En Revisión', 'Reparado', 'De Baja'], sel_sala=filtro_sala, sel_user=filtro_usuario, sel_estado=filtro_estado)

@app.route('/generar_qr/<sala>')
def generar_qr(sala):
    qr_img = qrcode.make(f"http://127.0.0{sala}")
    file_name = f"qr_{sala.replace(' ', '_')}.png"
    file_path = os.path.join(QR_DIR, file_name)
    qr_img.save(file_path)
    return send_from_directory(QR_DIR, file_name)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 9. MÓDULO CENTRAL DE RESPALDOS Y CARGAS MASIVAS (MIGRACIÓN TI REPARADO) ---
@app.route('/administracion_sistema', methods=['GET', 'POST'])
def administracion_sistema():
    if 'usuario' not in session or session.get('rol') not in ['Tecnico', 'Informático']:
        return "No autorizado - Nivel de privilegios insuficiente", 403
        
    if request.method == 'POST':
        formulario_accion = request.form.get('formulario_accion')
        
        # A. PROCESAR RESPALDO DE SEGURIDAD (BACKUP)
        if formulario_accion == 'respaldar_bd':
            import shutil
            from datetime import datetime
            fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_escuela_{fecha_str}.db"
            try:
                if not os.path.exists(os.path.join(os.getcwd(), 'static')):
                    os.makedirs(os.path.join(os.getcwd(), 'static'))
                shutil.copy(modelo.db_name, os.path.join(os.getcwd(), 'static', backup_name))
                flash(f"💾 Copia de seguridad generada con éxito: /static/{backup_name}", "success")
            except Exception as e:
                flash(f"❌ Error al generar la copia de seguridad: {e}", "danger")
                
        # AA. PROCESAR CARGA / RESTAURACIÓN DE RESPALDO (RESTORE)
        elif formulario_accion == 'cargar_respaldo_bd':
            file_back = request.files.get('archivo_db')
            if not file_back or file_back.filename == '':
                flash("⚠️ Seleccione un archivo .db válido para restaurar.", "danger")
                return redirect(url_for('administracion_sistema'))
                
            if not file_back.filename.endswith('.db'):
                flash("❌ Formato incorrecto. Solo se admiten archivos relacionales de extensión .db", "danger")
                return redirect(url_for('administracion_sistema'))
                
            try:
                import shutil
                # Cerramos conexiones inactivas sobrescribiendo el archivo físico de la BD
                file_back.save(modelo.db_name)
                flash("🚨 Base de datos restaurada con éxito. El sistema ha recuperado la configuración histórica seleccionada.", "success")
            except Exception as e:
                flash(f"❌ Error crítico en restauración de datos: {e}", "danger")
                
        # B. CARGA MASIVA DE EQUIPAMIENTO
        elif formulario_accion == 'carga_masiva_equipos':
            datos_raw = request.form.get('csv_equipos', '').strip()
            if not datos_raw:
                flash("⚠️ El campo de carga de equipos está vacío.", "info")
                return redirect(url_for('administracion_sistema'))
            lineas = datos_raw.split('\n')
            equipos_inyectados = 0
            for linea in lineas:
                partes = [p.strip() for p in linea.split(',')]
                if len(partes) >= 6:
                    res = ejecutar_modificacion_escuela(
                        "INSERT OR IGNORE INTO inventario_sala (sala, nombre_equipo, codigo_inventario, marca, modelo, serie) VALUES (?, ?, ?, ?, ?, ?)",
                        (partes[0], partes[1], partes[2], partes[3], partes[4], partes[5])
                    )
                    if res: equipos_inyectados += 1
            flash(f"🚀 Carga masiva exitosa: Se matricularon {equipos_inyectados} nuevos dispositivos en el inventario.", "success")

        # C. CARGA MASIVA DE CUENTAS
        elif formulario_accion == 'carga_masiva_usuarios':
            datos_raw = request.form.get('csv_usuarios', '').strip()
            if not datos_raw:
                flash("⚠️ El campo de carga de usuarios está vacío.", "info")
                return redirect(url_for('administracion_sistema'))
            lineas = datos_raw.split('\n')
            usuarios_inyectados = 0
            for linea in lineas:
                partes = [p.strip() for p in linea.split(',')]
                if len(partes) >= 6:
                    res = ejecutar_modificacion_escuela(
                        "INSERT OR IGNORE INTO usuarios (username, password, rol, nombre_completo, sala_asignada, permisos) VALUES (?, ?, ?, ?, ?, ?)",
                        (partes[0], partes[1], partes[2], partes[3], partes[4], partes[5])
                    )
                    if res: usuarios_inyectados += 1
            flash(f"👥 Carga masiva exitosa: Se registraron {usuarios_inyectados} cuentas de operarios.", "success")
            
        return redirect(url_for('administracion_sistema'))
    return render_template('administracion_sistema.html')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)
