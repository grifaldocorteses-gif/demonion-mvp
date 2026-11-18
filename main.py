from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
import os

app = FastAPI(title="Proyecto Demonion - Sistema Integral", version="3.5.0")
active_sessions = {}
DB_NAME = "ventas.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            token_persistente TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            marca TEXT,
            modelo TEXT,
            anio TEXT,
            km_actual REAL,
            ultimo_servicio REAL,
            peso_piloto REAL DEFAULT 0.0,
            altura_piloto REAL DEFAULT 0.0,
            nombre_meta TEXT DEFAULT 'Mantenimiento General',
            monto_meta REAL DEFAULT 2000.0,
            ahorro_acumulado REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tanque_usuario (
            usuario TEXT PRIMARY KEY,
            litros_tanque REAL DEFAULT 0.0,
            gasto_gasolina_real REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estadisticas_rutas (
            usuario TEXT PRIMARY KEY,
            km_totales_acumulados REAL DEFAULT 0.0,
            gasto_total_acumulado REAL DEFAULT 0.0,
            tiempo_total_acumulado_min REAL DEFAULT 0.0,
            presupuesto_total_acumulado REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_rutas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            nombre_ruta TEXT,
            km_recorridos REAL,
            costo_viaje REAL,
            presupuesto REAL DEFAULT 0.0,
            balance_neto REAL DEFAULT 0.0,
            tiempo_viaje TEXT,
            clima_registro TEXT,
            hora_registro TEXT,
            red_registro TEXT,
            trafico_registro TEXT,
            ubicacion_registro TEXT,
            alerta_operativa TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS combustible (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            km_recorridos REAL,
            litros_consumidos REAL,
            rendimiento REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mantenimiento_componentes (
            usuario TEXT,
            componente TEXT,
            km_acumulados REAL DEFAULT 0.0,
            km_desde_ultimo_aviso REAL DEFAULT 0.0,
            PRIMARY KEY (usuario, componente)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            componente TEXT,
            km_realizado REAL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radar_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            nombre TEXT,
            brand TEXT,
            lat REAL,
            lon REAL,
            fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE tanque_usuario ADD COLUMN gasto_gasolina_real REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE estadisticas_rutas ADD COLUMN presupuesto_total_acumulado REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN token_persistente TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class User(BaseModel):
    username: str
    password: str

class TokenCheck(BaseModel):
    token: str

class VehiculoUpdate(BaseModel):
    marca: str
    modelo: str
    anio: str
    km_actual: float
    peso_piloto: float = 0.0
    altura_piloto: float = 0.0
    nombre_meta: str = "Mantenimiento General"
    monto_meta: float = 2000.0

class CargarCombustible(BaseModel):
    litros_cargados: float
    precio_litro: float = 24.0

class EvaluarRuta(BaseModel):
    nombre_ruta: str = "Ruta General"
    km_recorridos: float
    precio_gasolina: float
    presupuesto: float = 0.0
    clima_registro: str = "N/D"
    hora_registro: str = "N/D"
    red_registro: str = "N/D"
    trafico_registro: str = "N/D"
    ubicacion_registro: str = "N/D"
    alerta_operativa: str = "N/D"

class RegistrarMantenimiento(BaseModel):
    componente: str

class CachePOI(BaseModel):
    tipo: str
    nombre: str
    brand: str = ""
    lat: float
    lon: float

def verificar_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente o inválido")
    token = authorization.split(" ")[1]
    if token in active_sessions:
        return active_sessions[token]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE token_persistente = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        username = row[0]
        active_sessions[token] = username
        return username

    raise HTTPException(status_code=401, detail="Sesión expirada o inválida")

@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DEMONION MVP - Cyber Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-main: #090d16;
                --bg-card: #111827;
                --border-color: #1f293d;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --accent-cyan: #06b6d4;
                --accent-green: #10b981;
                --accent-amber: #f59e0b;
                --accent-red: #ef4444;
                --accent-purple: #8b5cf6;
            }
            body { font-family: 'Outfit', system-ui, sans-serif; margin: 0; padding: 10px; background: var(--bg-main); color: var(--text-main); }
            .card { background: var(--bg-card); padding: 16px; margin-bottom: 12px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); }
            h3 { margin-top: 0; color: #38bdf8; font-size: 18px; font-weight: 600; }
            hr { border: 0; border-top: 1px solid var(--border-color); margin: 15px 0; }
            input, select, button { padding: 10px; margin: 4px 0; width: 100%; box-sizing: border-box; border-radius: 6px; border: 1px solid var(--border-color); font-size: 13px; font-family: 'Outfit', system-ui, sans-serif; background: #0b1120; color: var(--text-main); }
            button { background: linear-gradient(135deg, #0284c7, #0369a1); color: white; border: none; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
            button:hover { opacity: 0.9; }
            .btn-voice { background: var(--accent-purple); width: auto; padding: 6px 10px; font-size: 11px; margin: 0; }
            .btn-share { background: #059669; font-weight: 600; margin-top: 10px; }
            .btn-backup { background: #334155; font-weight: 600; margin-top: 5px; }
            .btn-mantenimiento { background: #d97706; font-weight: 600; font-size: 11px; padding: 6px; margin-top: 6px; width: 48%; }
            .btn-chequeo { background: #0284c7; font-weight: 600; font-size: 11px; padding: 6px; margin-top: 6px; width: 48%; }
            .btn-reset-tanque { background: #dc2626; font-weight: 600; font-size: 12px; padding: 10px; width: 30%; }
            .btn-main-carga { width: 68%; }
            .btn-leido { background: var(--accent-green); font-weight: 600; margin-top: 10px; }
            .btn-accion-carpeta { background: #334155; width: auto; padding: 4px 8px; font-size: 10px; margin: 0; }
            #auth { display: block; }
            #app { display: none; }
            .flex-row { display: flex; gap: 6px; align-items: center; }
            .input-voz-group { display: flex; gap: 4px; align-items: center; width: 100%; }
            .input-voz-group input { flex: 1; margin: 0; }
            .telemetria-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #0b1120; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 8px; }
            .telemetria-item { display: flex; flex-direction: column; gap: 2px; }
            .telemetria-item label { font-size: 11px; font-weight: 600; color: var(--text-muted); }
            .entorno-box { background: rgba(14, 165, 233, 0.05); border: 1px solid rgba(14, 165, 233, 0.2); padding: 10px; border-radius: 8px; font-size: 11px; color: #38bdf8; margin-bottom: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
            .diagnostico-container { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
            .diag-card { background: #0b1120; border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.2s; }
            .diag-card:hover { border-color: var(--accent-cyan); background: #131d31; }
            .diag-header { display: flex; align-items: center; justify-content: space-between; width: 100%; }
            .diag-header-left { display: flex; align-items: center; gap: 10px; }
            .diag-icon { font-size: 18px; line-height: 1; }
            .diag-title { font-weight: 600; color: var(--text-muted); font-size: 10px; text-transform: uppercase; }
            .diag-subtitle { font-size: 12px; font-weight: 600; }
            .diag-arrow { font-size: 10px; color: var(--text-muted); font-weight: 600; transition: transform 0.2s; }
            .diag-details { display: none; margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--border-color); font-size: 11px; color: var(--text-muted); }
            .checklist-box { background: rgba(245, 158, 11, 0.05); padding: 12px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.3); margin-top: 10px; margin-bottom: 10px; }
            .check-accordion-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 6px; overflow: hidden; }
            .check-accordion-header { padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: #0b1120; }
            .check-accordion-body { display: none; padding: 10px 12px; border-top: 1px dashed var(--border-color); font-size: 11px; color: var(--text-muted); }
            .bloqueado { background: #334155 !important; cursor: not-allowed !important; opacity: 0.7; }
            .progress-container { background: #1e293b; border-radius: 6px; height: 8px; width: 100%; margin: 4px 0; overflow: hidden; border: 1px solid var(--border-color); }
            .progress-bar { height: 100%; width: 100%; background: var(--accent-green); transition: width 0.3s ease; }
            .componentes-grid { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
            .comp-card { background: #0b1120; border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; }
            .bitacora-box { background: #0b1120; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 10px; font-size: 11px; color: var(--text-muted); }
            .panel-oficial { background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.3); padding: 12px; border-radius: 8px; margin-top: 8px; }
            .alerta-normativa { background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.3); padding: 12px; border-radius: 8px; font-size: 12px; color: #93c5fd; margin-top: 10px; }
            .bloque-principal-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; margin-bottom: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); }
            .bloque-principal-header { padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: #0e1626; border-bottom: 1px solid var(--border-color); }
            .bloque-principal-body { display: none; padding: 16px; }
            .radar-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 8px; }
            .btn-radar { background: #1e293b; border: 1px solid var(--border-color); padding: 8px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; color: #38bdf8; display: flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; }
            .btn-google-maps { background: linear-gradient(135deg, #1a73e8, #1557b0); color: white; border: 1px solid #4285f4; }
            .radar-results-box { background: #0b1120; border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; margin-top: 8px; max-height: 220px; overflow-y: auto; font-size: 11px; color: var(--text-muted); }
            .poi-item { padding: 6px 8px; border-bottom: 1px dashed var(--border-color); margin-bottom: 4px; }
        </style>
    </head>
    <body>
        <div id="auth" class="card">
            <h3>🛡️ ACCESO DEMONION MVP</h3>
            <input type="text" id="user" placeholder="Usuario">
            <input type="password" id="pass" placeholder="Contraseña">
            <button onclick="login()">Iniciar Sesión</button>
            <button onclick="register()" style="background:#059669; margin-top:6px;">Registrarse</button>
        </div>

        <div id="app">
            <h3>⚡ PANEL OPERATIVO [<span id="current-user" style="color:var(--accent-cyan)"></span>]</h3>
            <hr>
            
            <!-- BLOQUE 1: Control de Combustible y Autonomía -->
            <div class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-1', 'arrow-bloque-1')">
                    <span style="font-size:14px; font-weight:600; color:#38bdf8;">⚡ 1. Control de Combustible y Autonomía</span>
                    <span id="arrow-bloque-1" style="font-size:12px; font-weight:600; color:#38bdf8;">▼</span>
                </div>
                <div id="body-bloque-1" class="bloque-principal-body">
                    <div class="flex-row">
                        <div class="input-voz-group">
                            <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados" oninput="simularCarga()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('litros_carga')">🎤 Voz</button>
                        </div>
                    </div>
                    
                    <div class="flex-row" style="margin-top: 4px;">
                        <button id="btn_cargar" class="btn-main-carga" onclick="cargarCombustible()">Registrar Carga e Inversión en Tanque</button>
                        <button id="btn_reset" class="btn-reset-tanque" onclick="reiniciarTanqueYTelemetria()">🔄 Reiniciar</button>
                    </div>

                    <div class="flex-row" style="margin-top: 10px;">
                        <div class="input-voz-group">
                            <input type="text" id="nombre_ruta" placeholder="Nombre de Ruta / Pedido (Opcional, ej. Pedido #1)">
                            <button type="button" class="btn-voice" onclick="escucharVoz('nombre_ruta')">🎤 Voz</button>
                        </div>
                    </div>
                    <div class="flex-row" style="margin-top: 4px;">
                        <div class="input-voz-group">
                            <input type="number" id="km_ruta" placeholder="Km a Recorrer (Nueva Ruta)" oninput="simularRuta()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('km_ruta')">🎤 Voz</button>
                        </div>
                    </div>
                    <div class="flex-row">
                        <div class="input-voz-group">
                            <input type="number" id="precio_gas" placeholder="Precio Gasolina ($ / Litro)" value="24.0" oninput="simularRuta()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('precio_gas')">🎤 Voz</button>
                        </div>
                    </div>
                    <div class="flex-row">
                        <div class="input-voz-group">
                            <input type="number" id="presupuesto_ruta" placeholder="Presupuesto / Pago Recibido ($0.0 si es Personal)" value="0.0" oninput="simularRuta()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('presupuesto_ruta')">🎤 Voz</button>
                        </div>
                    </div>
                    <button id="btn_evaluar" style="background:#059669; margin-top:8px;" onclick="evaluarRuta()">Evaluar Costo, Ruta y Descontar (Oficial)</button>
                    
                    <div id="diagnostico-combustible" style="margin-top: 8px;"></div>
                    
                    <div id="contenedor-acordeon-viajes" class="check-accordion-card" style="display:none; margin-top: 8px;">
                        <div class="check-accordion-header">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan); flex:1;" onclick="toggleAcordeon('body-viajes', 'arrow-viajes')">📁 Viajes Registrados en la Jornada</span>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <button type="button" class="btn-accion-carpeta" onclick="alternarVisibilidadConsulta()">Ocultar Consulta</button>
                                <span id="arrow-viajes" style="font-size:10px; font-weight:600;">▼</span>
                            </div>
                        </div>
                        <div id="body-viajes" class="check-accordion-body">
                            <div id="lista-viajes-acordeon" style="display: flex; flex-direction: column; gap: 6px;"></div>
                        </div>
                    </div>

                    <div id="diagnostico-oficial" class="panel-oficial" style="display:none;"></div>
                </div>
            </div>

            <!-- BLOQUE 2: Sello de Seguridad Obligatorio -->
            <div id="contenedor-inspeccion" class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-2', 'arrow-bloque-2')">
                    <span id="titulo-bloque-2" style="font-size:14px; font-weight:600; color:var(--accent-amber);">⚠️ 2. Mantenimiento Preventivo y Checklist (⚠️ Registrar puntos críticos obligatorios antes de usar Bloque 1)</span>
                    <span id="arrow-bloque-2" style="font-size:12px; font-weight:600; color:var(--accent-amber);">▼</span>
                </div>
                <div id="body-bloque-2" class="bloque-principal-body">
                    <div id="checklist-contenedor" class="checklist-box">
                        <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: 600; font-size: 12px; color: var(--accent-amber);">⚠️ Inspección preventiva: Confirme los 6 puntos críticos de seguridad.</p>
                        
                        <div class="check-accordion-card">
                            <div class="check-accordion-header" onclick="toggleAcordeon('body-seis-puntos', 'arrow-seis-puntos')">
                                <span style="font-size:12px; font-weight:600; color:var(--accent-amber);">📋 Menú Desplegable: Ver y Confirmar los 6 Puntos Críticos</span>
                                <span id="arrow-seis-puntos" style="font-size:10px; font-weight:600;">▼</span>
                            </div>
                            <div id="body-seis-puntos" class="check-accordion-body">
                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">🛑 1. Frenos / Suspensión</p>
                                    <select id="anulador_frenos" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">⛓ 2. Kit Arrastre / Piñones</p>
                                    <select id="anulador_cadena" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">🛞 3. Llantas / Presión</p>
                                    <select id="anulador_llantas" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">💡 4. Sistema Eléctrico / Intermitentes</p>
                                    <select id="anulador_luces" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">🪖 5. Casco / Indumentaria (EPP)</p>
                                    <select id="anulador_epp" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                                <div style="margin-bottom: 4px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">📄 6. Licencia / Póliza Vigente</p>
                                    <select id="anulador_docs" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="protocolo-normativo" class="alerta-normativa" style="display:none;">
                        <p style="margin:0 0 4px 0; font-weight:600; color:#60a5fa; font-size:12px;">🛡️ PROTOCOLO DE SEGURIDAD OPERATIVA Y NORMATIVA VIAL</p>
                        <button class="btn-leido" onclick="confirmarLeidoProtocolo()">✔ Entendido y Confirmado (Regresar)</button>
                    </div>

                    <div class="check-accordion-card" style="margin-top: 8px;">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-grid-componentes', 'arrow-grid-componentes')">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">📊 Vida útil y estado simultáneo de los componentes (Aceite, Arrastre, Frenos)</span>
                            <span id="arrow-grid-componentes" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-grid-componentes" class="check-accordion-body" style="display: none;">
                            <div class="componentes-grid">
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8; margin-bottom: 4px;">🛢️ Cambio de Aceite (Ciclo: 2,500 km)</div>
                                    <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                        <span>Progreso de Vida:</span><span id="vida-aceite-txt" style="color:var(--accent-green);">100%</span>
                                    </div>
                                    <div class="progress-container"><div id="barra-aceite" class="progress-bar" style="width: 100%;"></div></div>
                                    <div id="alerta-aceite-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">💡 Sugerencia: Revisar nivel semanalmente.</div>
                                    <div style="display: flex; gap: 4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Cambio de Aceite')">✔ Confirmar Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Cambio de Aceite')">🔧 Registrar Mant.</button>
                                    </div>
                                </div>
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8; margin-bottom: 4px;">⛓️ Kit de Arrastre / Piñones (Ciclo: 15,000 km)</div>
                                    <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                        <span>Progreso de Vida:</span><span id="vida-arrastre-txt" style="color:var(--accent-green);">100%</span>
                                    </div>
                                    <div class="progress-container"><div id="barra-arrastre" class="progress-bar" style="width: 100%;"></div></div>
                                    <div id="alerta-arrastre-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">💡 Sugerencia: Lubricar cadena cada 500 km.</div>
                                    <div style="display: flex; gap: 4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Kit de Arrastre / Piñones')">✔ Confirmar Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Kit de Arrastre / Piñones')">🔧 Registrar Mant.</button>
                                    </div>
                                </div>
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8; margin-bottom: 4px;">🛑 Pastillas de Freno (Ciclo: 5,000 km)</div>
                                    <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                        <span>Progreso de Vida:</span><span id="vida-frenos-txt" style="color:var(--accent-green);">100%</span>
                                    </div>
                                    <div class="progress-container"><div id="barra-frenos" class="progress-bar" style="width: 100%;"></div></div>
                                    <div id="alerta-frenos-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">💡 Sugerencia: Inspeccionar espesor balatas.</div>
                                    <div style="display: flex; gap: 4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Pastillas de Freno')">✔ Confirmar Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Pastillas de Freno')">🔧 Registrar Mant.</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- BLOQUE 3: Telemetría Avanzada y Radar GPS DUAL -->
            <div class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-3', 'arrow-bloque-3')">
                    <span style="font-size:14px; font-weight:600; color:#38bdf8;">🌐 3. Telemetría Avanzada y Radar GPS Dual (Google Maps + Inyección de Coordenadas)</span>
                    <span id="arrow-bloque-3" style="font-size:12px; font-weight:600; color:#38bdf8;">▼</span>
                </div>
                <div id="body-bloque-3" class="bloque-principal-body">
                    <div id="entorno-dispositivo" class="entorno-box">
                        <span id="info-clima">🌤️ Clima: Cargando...</span>
                        <span id="info-bateria">🔋 Batería: --%</span>
                        <span id="info-horario">🕒 Hora: --:--</span>
                        <span id="info-red">📶 Red: Analizando...</span>
                        <span id="info-ubicacion" style="grid-column: span 2;">📍 Ubicación: Obteniendo GPS...</span>
                    </div>

                    <div class="check-accordion-card" style="margin-bottom: 10px;">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-radar-gps', 'arrow-radar-gps')">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">🗺️ Motor Dual de Búsqueda y Almacenamiento Local</span>
                            <span id="arrow-radar-gps" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-radar-gps" class="check-accordion-body" style="display: block;">
                            <div class="check-accordion-card" style="margin-bottom: 8px;">
                                <div class="check-accordion-header" onclick="toggleAcordeon('body-motor-primario', 'arrow-motor-primario')">
                                    <span style="font-size: 11px; font-weight: 700; color: #60a5fa;">🚀 MOTOR PRIMARIO: Google Maps Directo (En línea)</span>
                                    <span id="arrow-motor-primario" style="font-size:10px; font-weight:600;">▼</span>
                                </div>
                                <div id="body-motor-primario" class="check-accordion-body" style="display: none; background: #0b1120;">
                                    <div class="radar-grid">
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('gasolineras')">⛽ Gasolineras</button>
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('taller mecanico')">🔧 Talleres</button>
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('vulcanizadora')">🛞 Vulcanizadoras</button>
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('refaccionaria')">🔩 Refaccionarias</button>
                                    </div>
                                </div>
                            </div>

                            <div class="check-accordion-card" style="margin-bottom: 8px;">
                                <div class="check-accordion-header" onclick="toggleAcordeon('body-repositorio', 'arrow-repositorio')">
                                    <span style="font-size: 11px; font-weight: 700; color: var(--accent-amber);">💾 Repositorio y Marcadores Favoritos (SQLite)</span>
                                    <span id="arrow-repositorio" style="font-size:10px; font-weight:600;">▼</span>
                                </div>
                                <div id="body-repositorio" class="check-accordion-body" style="display: none; background: #0b1120;">
                                    <div class="flex-row">
                                        <div class="input-voz-group">
                                            <input type="text" id="input_mis_rutas" placeholder="Preferencias">
                                            <button type="button" class="btn-voice" onclick="escucharVoz('input_mis_rutas')">🎤</button>
                                        </div>
                                        <button type="button" style="width: auto; padding: 8px 12px; background: #0284c7; font-size: 11px;" onclick="buscarMisRutas()">Mis Rutas</button>
                                    </div>
                                    <div id="radar-resultados" class="radar-results-box" style="display: none;">
                                        <span id="radar-loading">Ingrese un término...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="telemetria-grid">
                        <div class="telemetria-item"><label>Marca</label><input type="text" id="marca" placeholder="Ej. Bajaj" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>Modelo</label><input type="text" id="modelo" placeholder="Ej. Pulsar NS 200" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>Año</label><input type="text" id="anio" placeholder="Ej. 2024" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>Odómetro (km)</label><input type="number" id="km" placeholder="Km Actual" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>Peso Piloto (kg)</label><input type="number" id="peso_piloto" placeholder="Ej. 68" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>Altura Piloto (cm)</label><input type="number" id="altura_piloto" placeholder="Ej. 165" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>🎯 Nombre de la Meta</label><input type="text" id="nombre_meta" placeholder="Ej. Llantas Nuevas" style="padding:6px 8px; font-size:11px;"></div>
                        <div class="telemetria-item"><label>💵 Monto Meta ($)</label><input type="number" id="monto_meta" placeholder="Ej. 900" style="padding:6px 8px; font-size:11px;"></div>
                    </div>

                    <button onclick="actualizarKm()">Sincronizar Odómetro y Auditar Telemetría</button>
                    <div id="diagnostico"></div>

                    <div class="bitacora-box">
                        <p style="margin: 0 0 5px 0; font-weight: 600; font-size: 12px;">📋 AUDITORÍA Y BITÁCORA ANALÍTICA:</p>
                        <div id="lista-bitacora">Sin registros analíticos en esta sesión.</div>
                    </div>

                    <hr>
                    <button class="btn-share" onclick="compartirReporte()">📲 Compartir Reporte (WhatsApp / Local)</button>
                    <button class="btn-backup" onclick="descargarRespaldo()">💾 Descargar Copia de Seguridad (DB)</button>
                </div>
            </div>
            
            <div class="card">
                <button onclick="logout()" style="background:#475569; margin-top: 0;">Cerrar Sesión</button>
            </div>
        </div>

        <script>
            const API = window.location.origin;
            let authToken = localStorage.getItem("demonion_token") || "";
            let currentUser = localStorage.getItem("demonion_user") || "";
            let ultimoDiagnostico = "";
            let sistemaBloqueado = false;
            let litrosActualesTanque = 0.0;
            let gastoGasolinaRealGlobal = 0.0;
            let kmTotalesAcumuladosGlobal = 0.0;
            let gastoTotalAcumuladoGlobal = 0.0;
            let presupuestoTotalAcumuladoGlobal = 0.0;
            let tiempoTotalAcumuladoGlobalMin = 0.0;
            let ahorroAcumuladoMetaGlobal = 0.0;
            let protocoloConfirmadoLeido = false;
            let currentLat = null;
            let currentLon = null;
            let kmComponentes = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
            let kmDesdeUltimoChequeo = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
            let bitacoraLocal = [];
            let viajesJornadaList = [];
            let consultaViajeOculta = false;

            window.addEventListener('DOMContentLoaded', async () => {
                if (authToken) {
                    try {
                        let res = await fetch(API + "/verify-token", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ token: authToken })
                        });
                        if (res.ok) {
                            let data = await res.json();
                            currentUser = data.username;
                            document.getElementById("current-user").innerText = currentUser;
                            document.getElementById("auth").style.display = "none";
                            document.getElementById("app").style.display = "block";
                            await cargarEstadoVehiculo();
                            sincronizarVistaComponente();
                            verificarJornadaYDiagnostico();
                            iniciarTelemetriaNativa();
                        } else { logout(); }
                    } catch(e) { logout(); }
                }
            });

            function iniciarTelemetriaNativa() {
                if (navigator.getBattery) {
                    navigator.getBattery().then(battery => {
                        actualizarBateria(battery);
                        battery.addEventListener('levelchange', () => actualizarBateria(battery));
                    });
                }
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(position => {
                        currentLat = position.coords.latitude;
                        currentLon = position.coords.longitude;
                        fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${currentLat}&lon=${currentLon}&zoom=16`, { headers: { 'Accept-Language': 'es' } })
                        .then(res => res.json())
                        .then(data => {
                            let direccion = data && data.address ? (data.address.road || data.address.suburb || data.address.city || "Zona Exacta GPS") : "Ubicación GPS";
                            document.getElementById("info-ubicacion").innerText = `📍 Ubicación: ${direccion}`;
                        }).catch(() => {});
                    }, () => {}, { enableHighAccuracy: true, timeout: 10000 });
                }
                actualizarRelojSistema();
                setInterval(actualizarRelojSistema, 30000);
            }

            function abrirGoogleMapsExterno(queryBusqueda = "servicios") {
                if (!currentLat || !currentLon) {
                    window.open(`https://www.google.com/maps/search/${encodeURIComponent(queryBusqueda)}`, "_blank");
                    return;
                }
                window.open(`https://www.google.com/maps/search/${encodeURIComponent(queryBusqueda)}/@${currentLat},${currentLon},14z`, "_blank");
            }

            function calcularDistanciaKm(lat1, lon1, lat2, lon2) {
                let R = 6371;
                let dLat = (lat2 - lat1) * Math.PI / 180;
                let dLon = (lon2 - lon1) * Math.PI / 180;
                let a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
                return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
            }

            async function buscarMisRutas() {
                let termino = document.getElementById("input_mis_rutas").value.trim().toLowerCase();
                let resultadosBox = document.getElementById("radar-resultados");
                resultadosBox.style.display = "block";
                resultadosBox.innerHTML = "⏳ Consultando 'Mis Rutas'...";
                try {
                    let res = await fetch(`${API}/radar/cache?tipo=${encodeURIComponent(termino)}`, { headers: { "Authorization": "Bearer " + authToken } });
                    let poisCache = await res.json();
                    if (!poisCache || poisCache.length === 0) {
                        resultadosBox.innerHTML = `⚠️ Sin resultados para '${termino}'.`;
                        return;
                    }
                    let htmlList = `<b style="color:var(--accent-amber);">📁 Resultados de 'Mis Rutas':</b><br><br>`;
                    poisCache.forEach((el, index) => {
                        let mapsUrl = `https://www.google.com/maps/search/?api=1&query=${el.lat},${el.lon}`;
                        htmlList += `<div class="poi-item"><b>${index + 1}. ${el.nombre}</b><br><a href="${mapsUrl}" target="_blank" style="color:#38bdf8;">🌐 Abrir en Google Maps</a></div>`;
                    });
                    resultadosBox.innerHTML = htmlList;
                } catch(e) { resultadosBox.innerHTML = "⚠️ Error al consultar."; }
            }

            function actualizarBateria(battery) {
                document.getElementById("info-bateria").innerText = `🔋 Batería: ${Math.round(battery.level * 100)}%`;
            }

            function actualizarRelojSistema() {
                document.getElementById("info-horario").innerText = `🕒 Hora: ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
            }

            function obtenerPrediccionTrafico() {
                let hora = new Date().getHours();
                return ((hora >= 7 && hora <= 9) || (hora >= 18 && hora <= 20)) ? { nivel: "Alto", multiplicador: 1.35, condicion: "⚠️ Tráfico denso" } : { nivel: "Fluido", multiplicador: 1.0, condicion: "✔ Vías libres" };
            }

            function evaluarAlertasOperativas(kmRutaVal, minutosViaje, litrosConsumidos) {
                return kmRutaVal > 30 ? "🛣️ Ruta larga detectada" : "📍 Trayecto estándar";
            }

            function toggleAcordeon(idBody, idArrow) {
                let body = document.getElementById(idBody);
                let arrow = document.getElementById(idArrow);
                if (body.style.display === "block") {
                    body.style.display = "none";
                    arrow.style.transform = "rotate(0deg)";
                } else {
                    body.style.display = "block";
                    arrow.style.transform = "rotate(180deg)";
                }
            }

            function alternarVisibilidadConsulta() {
                consultaViajeOculta = !consultaViajeOculta;
                let panelOficial = document.getElementById("diagnostico-oficial");
                panelOficial.style.display = consultaViajeOculta ? "none" : "block";
            }

            function actualizarAcordeonViajes() {
                let contenedor = document.getElementById("contenedor-acordeon-viajes");
                let lista = document.getElementById("lista-viajes-acordeon");
                if (!viajesJornadaList.length) { contenedor.style.display = "none"; return; }
                contenedor.style.display = "block";
                lista.innerHTML = viajesJornadaList.map((v, i) => `<div style="background:#0b1120; padding:6px; border-radius:4px;"><b>${v.nombre_ruta}</b> - Neto: $${v.balance_neto}</div>`).join("");
            }

            function limpiarVariablesLocales() {
                litrosActualesTanque = 0.0;
                gastoGasolinaRealGlobal = 0.0;
                kmTotalesAcumuladosGlobal = 0.0;
                gastoTotalAcumuladoGlobal = 0.0;
                presupuestoTotalAcumuladoGlobal = 0.0;
                tiempoTotalAcumuladoGlobalMin = 0.0;
                ahorroAcumuladoMetaGlobal = 0.0;
                bitacoraLocal = [];
                viajesJornadaList = [];
            }

            function bloquearSistema(bloquear, mensaje) {
                sistemaBloqueado = bloquear;
                let div = document.getElementById("diagnostico-anulador");
                if(div) div.innerHTML = mensaje;
            }

            function verificarJornadaYDiagnostico() {
                let f = document.getElementById("anulador_frenos").value;
                let c = document.getElementById("anulador_cadena").value;
                let ll = document.getElementById("anulador_llantas").value;
                let l = document.getElementById("anulador_luces").value;
                let epp = document.getElementById("anulador_epp").value;
                let docs = document.getElementById("anulador_docs").value;
                let todosOk = (f === "ok" && c === "ok" && ll === "ok" && l === "ok" && epp === "ok" && docs === "ok");

                if (!todosOk || !protocoloConfirmadoLeido) {
                    bloquearSistema(true, "⚠️ Verificación de seguridad requerida en Bloque 2.");
                    document.getElementById("checklist-contenedor").style.display = "block";
                    document.getElementById("protocolo-normativo").style.display = "none";
                } else {
                    bloquearSistema(false, "✔ Puntos de inspección operativos.");
                    document.getElementById("checklist-contenedor").style.display = "none";
                    document.getElementById("protocolo-normativo").style.display = "block";
                }
            }

            function verificarAnuladores() { verificarJornadaYDiagnostico(); }
            function confirmarLeidoProtocolo() { protocoloConfirmadoLeido = true; verificarJornadaYDiagnostico(); }

            function simularCarga() {
                let litrosEntrada = parseFloat(document.getElementById("litros_carga").value) || 0;
                let precioGasVal = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                if (litrosEntrada <= 0) return;
                document.getElementById("diagnostico-combustible").innerHTML = `<p><b>Carga sim:</b> ${litrosEntrada} L ($${litrosEntrada * precioGasVal} MXN)</p>`;
            }

            function simularRuta() {
                let kmRutaVal = parseFloat(document.getElementById("km_ruta").value);
                if (!kmRutaVal || kmRutaVal <= 0) return;
                let costo = round((kmRutaVal / 30.0) * 24.0, 2);
                document.getElementById("diagnostico-combustible").innerHTML = `<p><b>Ruta sim:</b> ${kmRutaVal} km | Costo: $${costo} MXN</p>`;
            }

            function round(value, decimals) { return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals); }

            function sincronizarVistaComponente() {
                let ciclos = { "Cambio de Aceite": 2500, "Kit de Arrastre / Piñones": 15000, "Pastillas de Freno": 5000 };
                for (let comp in ciclos) {
                    let vida = Math.max(0, Math.min(100, 100 - ((kmComponentes[comp] || 0) / ciclos[comp]) * 100));
                    if(comp === "Cambio de Aceite") {
                        document.getElementById("barra-aceite").style.width = vida + "%";
                        document.getElementById("vida-aceite-txt").innerText = Math.round(vida) + "%";
                    } else if(comp === "Kit de Arrastre / Piñones") {
                        document.getElementById("barra-arrastre").style.width = vida + "%";
                        document.getElementById("vida-arrastre-txt").innerText = Math.round(vida) + "%";
                    } else if(comp === "Pastillas de Freno") {
                        document.getElementById("barra-frenos").style.width = vida + "%";
                        document.getElementById("vida-frenos-txt").innerText = Math.round(vida) + "%";
                    }
                }
            }

            async function confirmarChequeoComponente(comp) {
                kmDesdeUltimoChequeo[comp] = 0;
                sincronizarVistaComponente();
                alert(`✔ Chequeo confirmado para '${comp}'.`);
            }

            async function registrarMantenimientoDirecto(comp) {
                let res = await fetch(API + "/mantenimiento/reiniciar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ componente: comp })
                });
                if(res.ok) {
                    kmComponentes[comp] = 0;
                    kmDesdeUltimoChequeo[comp] = 0;
                    sincronizarVistaComponente();
                    alert("✔ Mantenimiento registrado con éxito.");
                }
            }

            function escucharVoz(inputId) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) { alert("Navegador sin soporte de voz."); return; }
                const recognition = new SpeechRecognition();
                recognition.lang = 'es-MX';
                recognition.start();
                recognition.onresult = function(event) {
                    document.getElementById(inputId).value = event.results[0][0].transcript.replace(/[^0-9.]/g, '');
                };
            }

            function compartirReporte() {
                if (!ultimoDiagnostico) { alert("Realiza una evaluación primero."); return; }
                window.open("https://api.whatsapp.com/send?text=" + encodeURIComponent(ultimoDiagnostico), '_blank');
            }

            function descargarRespaldo() { window.location.href = API + "/backup"; }

            async function register() {
                let u = document.getElementById("user").value;
                let p = document.getElementById("pass").value;
                let res = await fetch(API + "/register", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({username: u, password: p}) });
                let data = await res.json();
                alert(data.mensaje || data.detail);
            }

            async function login() {
                let u = document.getElementById("user").value;
                let p = document.getElementById("pass").value;
                let res = await fetch(API + "/login", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({username: u, password: p}) });
                if(res.ok) {
                    let data = await res.json();
                    authToken = data.token;
                    currentUser = u;
                    localStorage.setItem("demonion_token", authToken);
                    localStorage.setItem("demonion_user", currentUser);
                    limpiarVariablesLocales();
                    document.getElementById("current-user").innerText = u;
                    document.getElementById("auth").style.display = "none";
                    document.getElementById("app").style.display = "block";
                    await cargarEstadoVehiculo();
                    sincronizarVistaComponente();
                    verificarJornadaYDiagnostico();
                    iniciarTelemetriaNativa();
                } else { alert("Credenciales inválidas"); }
            }

            function logout() {
                authToken = ""; currentUser = "";
                localStorage.removeItem("demonion_token");
                localStorage.removeItem("demonion_user");
                document.getElementById("auth").style.display = "block";
                document.getElementById("app").style.display = "none";
            }

            async function actualizarKm() {
                let marca = document.getElementById("marca").value;
                let modelo = document.getElementById("modelo").value;
                let anio = document.getElementById("anio").value;
                let km_actual = parseFloat(document.getElementById("km").value) || 0;
                let peso_piloto = parseFloat(document.getElementById("peso_piloto").value) || 0;
                let altura_piloto = parseFloat(document.getElementById("altura_piloto").value) || 0;
                let nombre_meta = document.getElementById("nombre_meta").value;
                let monto_meta = parseFloat(document.getElementById("monto_meta").value) || 2000;

                let res = await fetch(API + "/vehiculo", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ marca, modelo, anio, km_actual, peso_piloto, altura_piloto, nombre_meta, monto_meta })
                });
                if(res.ok) { alert("✔ Unidad sincronizada con éxito."); }
            }

            async function cargarCombustible() {
                let litros_cargados = parseFloat(document.getElementById("litros_carga").value);
                let precio_litro = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let res = await fetch(API + "/combustible/cargar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ litros_cargados, precio_litro })
                });
                if(res.ok) { alert("✔ Carga registrada."); actualizarKm(); }
            }

            async function reiniciarTanqueYTelemetria() {
                if (!confirm("¿Reiniciar tanque y contadores?")) return;
                await fetch(API + "/combustible/reiniciar-telemetria", { method: "POST", headers: { "Authorization": "Bearer " + authToken } });
                limpiarVariablesLocales();
                alert("✔ Reiniciado con éxito.");
            }

            async function evaluarRuta() {
                if (sistemaBloqueado) { alert("⚠️ Sistema bloqueado por seguridad en Bloque 2."); return; }
                let nombre_ruta = document.getElementById("nombre_ruta").value || "Ruta General";
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                let precio_gasolina = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let presupuesto = parseFloat(document.getElementById("presupuesto_ruta").value) || 0.0;

                let res = await fetch(API + "/combustible/evaluar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ nombre_ruta, km_recorridos, precio_gasolina, presupuesto })
                });
                if(res.ok) { alert("✔ Ruta evaluada y registrada."); actualizarKm(); }
            }

            async function cargarEstadoVehiculo() {
                let res = await fetch(API + "/vehiculo", { headers: { "Authorization": "Bearer " + authToken } });
                if(res.ok) {
                    let data = await res.json();
                    if(data && Object.keys(data).length > 0) {
                        document.getElementById("marca").value = data.marca || "";
                        document.getElementById("modelo").value = data.modelo || "";
                        document.getElementById("anio").value = data.anio || "";
                        document.getElementById("km").value = data.km_actual || 0;
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/radar/cache")
def guardar_cache_poi(item: CachePOI, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO radar_cache (tipo, nombre, brand, lat, lon) VALUES (?, ?, ?, ?, ?)", (item.tipo.lower(), item.nombre, item.brand, item.lat, item.lon))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/radar/cache")
def obtener_cache_poi(tipo: str, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nombre, brand, lat, lon FROM radar_cache WHERE tipo = ? OR nombre LIKE ? ORDER BY id DESC LIMIT 15", (tipo.lower(), f"%{tipo}%"))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/backup")
def descargar_backup():
    if os.path.exists(DB_NAME):
        return FileResponse(DB_NAME, media_type="application/octet-stream", filename="respaldo_demonion.db")
    raise HTTPException(status_code=404, detail="Base de datos no encontrada")

@app.post("/register")
def register(user: User):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user.username, hash_password(user.password)))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Usuario existente")
    finally:
        conn.close()
    return {"mensaje": "Registrado"}

@app.post("/login")
def login(user: User):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE username = ? AND password = ?", (user.username, hash_password(user.password)))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = secrets.token_hex(32)
    active_sessions[token] = user.username
    cursor.execute("UPDATE usuarios SET token_persistente = ? WHERE username = ?", (token, user.username))
    conn.commit()
    conn.close()
    return {"token": token, "username": user.username}

@app.post("/verify-token")
def verify_token_endpoint(tk: TokenCheck):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE token_persistente = ?", (tk.token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        active_sessions[tk.token] = row[0]
        return {"username": row[0]}
    raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/tanque/estado")
def obtener_estado_tanque(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return {"litros_tanque": row[0] if row and row[0] is not None else 0.0, "gasto_gasolina_real": row[1] if row and row[1] is not None else 0.0}

@app.get("/estadisticas/rutas")
def obtener_estadisticas_rutas(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {"km_totales_acumulados": 0.0, "gasto_total_acumulado": 0.0, "presupuesto_total_acumulado": 0.0, "tiempo_total_acumulado_min": 0.0}

@app.post("/combustible/reiniciar-telemetria")
def reiniciar_tanque_y_telemetria(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tanque_usuario SET litros_tanque = 0.0, gasto_gasolina_real = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE estadisticas_rutas SET km_totales_acumulados = 0.0, gasto_total_acumulado = 0.0, presupuesto_total_acumulado = 0.0, tiempo_total_acumulado_min = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("DELETE FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    conn.commit()
    conn.close()
    return {"mensaje": "Reiniciado con éxito."}

@app.post("/vehiculo")
def gestionar_vehiculo(v: VehiculoUpdate, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT gasto_total_acumulado FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    gasto_total = est_row[0] if est_row and est_row[0] is not None else 0.0
    ahorro_real = round(v.monto_meta - gasto_total, 2)

    cursor.execute("SELECT id FROM vehiculos WHERE usuario = ?", (usuario,))
    if cursor.fetchone():
        cursor.execute("UPDATE vehiculos SET marca=?, modelo=?, anio=?, km_actual=?, peso_piloto=?, altura_piloto=?, nombre_meta=?, monto_meta=?, ahorro_acumulado=? WHERE usuario=?", 
                       (v.marca, v.modelo, v.anio, v.km_actual, v.peso_piloto, v.altura_piloto, v.nombre_meta, v.monto_meta, ahorro_real, usuario))
    else:
        cursor.execute("INSERT INTO vehiculos (usuario, marca, modelo, anio, km_actual, ultimo_servicio, peso_piloto, altura_piloto, nombre_meta, monto_meta, ahorro_acumulado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (usuario, v.marca, v.modelo, v.anio, v.km_actual, v.km_actual, v.peso_piloto, v.altura_piloto, v.nombre_meta, v.monto_meta, ahorro_real))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT marca, modelo, anio, km_actual, ultimo_servicio, peso_piloto, altura_piloto, nombre_meta, monto_meta, ahorro_acumulado FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

@app.get("/mantenimiento/estado")
def obtener_estado_mantenimiento(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT componente, km_acumulados, km_desde_ultimo_aviso FROM mantenimiento_componentes WHERE usuario = ?", (usuario,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/bitacora")
def obtener_bitacora(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje FROM bitacora_rutas WHERE usuario = ? ORDER BY id DESC LIMIT 100", (usuario,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/mantenimiento/reiniciar")
def reiniciar_mantenimiento(m: RegistrarMantenimiento, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT km_actual FROM vehiculos WHERE usuario = ?", (usuario,))
    v_row = cursor.fetchone()
    km_actual = v_row[0] if v_row else 0.0
    cursor.execute("INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados, km_desde_ultimo_aviso) VALUES (?, ?, 0.0, 0.0) ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = 0.0, km_desde_ultimo_aviso = 0.0", (usuario, m.componente))
    conn.commit()
    conn.close()
    return {"mensaje": f"Ciclo de '{m.componente}' reiniciado."}

@app.post("/combustible/cargar")
def cargar_combustible(c: CargarCombustible, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros = (row[0] if row else 0.0) + c.litros_cargados
    gasto = (row[1] if row else 0.0) + (c.litros_cargados * c.precio_litro)
    cursor.execute("INSERT INTO tanque_usuario (usuario, litros_tanque, gasto_gasolina_real) VALUES (?, ?, ?) ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?, gasto_gasolina_real = ?", (usuario, litros, gasto, litros, gasto))
    conn.commit()
    conn.close()
    return {"litros_tanque": litros, "gasto_gasolina_real": gasto}

@app.post("/combustible/evaluar")
def evaluar_ruta(e: EvaluarRuta, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    litros_cons = round(e.km_recorridos / 30.0, 2)
    costo = round(litros_cons * e.precio_gasolina, 2)
    balance = round(-costo if e.presupuesto == 0.0 else e.presupuesto - costo, 2)
    
    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_restantes = max(0.0, (row[0] if row else 0.0) - litros_cons)

    cursor.execute("UPDATE tanque_usuario SET litros_tanque = ? WHERE usuario = ?", (litros_restantes, usuario))
    cursor.execute("INSERT INTO bitacora_rutas (usuario, nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto) VALUES (?, ?, ?, ?, ?, ?)",
                   (usuario, e.nombre_ruta, e.km_recorridos, costo, e.presupuesto, balance))
    conn.commit()
    conn.close()
    return {"status": "ok", "balance_neto": balance, "litros_restantes": litros_restantes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
