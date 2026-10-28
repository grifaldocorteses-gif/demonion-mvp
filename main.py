from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
import os

app = FastAPI()
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

            body { 
                font-family: 'Outfit', system-ui, -apple-system, sans-serif; 
                margin: 0; 
                padding: 10px; 
                background: var(--bg-main); 
                color: var(--text-main); 
            }

            .card { 
                background: var(--bg-card); 
                padding: 16px; 
                margin-bottom: 12px; 
                border-radius: 12px; 
                border: 1px solid var(--border-color);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); 
            }

            h3 { margin-top: 0; color: #38bdf8; font-size: 18px; font-weight: 600; letter-spacing: 0.5px; }
            hr { border: 0; border-top: 1px solid var(--border-color); margin: 15px 0; }

            input, select, button { 
                padding: 10px; 
                margin: 4px 0; 
                width: 100%; 
                box-sizing: border-box; 
                border-radius: 6px; 
                border: 1px solid var(--border-color); 
                font-size: 13px; 
                font-family: 'Outfit', system-ui, -apple-system, sans-serif;
                background: #0b1120;
                color: var(--text-main);
            }

            input:focus, select:focus {
                border-color: var(--accent-cyan);
                outline: none;
                box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2);
            }

            button { 
                background: linear-gradient(135deg, #0284c7, #0369a1); 
                color: white; 
                border: none; 
                font-weight: 600; 
                cursor: pointer; 
                transition: opacity 0.2s;
            }

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
            
            .telemetria-grid { 
                display: grid; 
                grid-template-columns: 1fr 1fr; 
                gap: 8px; 
                background: #0b1120; 
                padding: 10px; 
                border-radius: 8px; 
                border: 1px solid var(--border-color); 
                margin-bottom: 8px; 
            }
            .telemetria-item { display: flex; flex-direction: column; gap: 2px; }
            .telemetria-item label { font-size: 11px; font-weight: 600; color: var(--text-muted); }
            
            .entorno-box { 
                background: rgba(14, 165, 233, 0.05); 
                border: 1px solid rgba(14, 165, 233, 0.2); 
                padding: 10px; 
                border-radius: 8px; 
                font-size: 11px; 
                color: #38bdf8; 
                margin-bottom: 10px; 
                display: grid; 
                grid-template-columns: 1fr 1fr; 
                gap: 6px; 
            }
            
            .diagnostico-container { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
            .diag-card { 
                background: #0b1120; 
                border: 1px solid var(--border-color); 
                border-radius: 8px; 
                padding: 10px 12px; 
                cursor: pointer; 
                transition: all 0.2s; 
            }
            .diag-card:hover { border-color: var(--accent-cyan); background: #131d31; }
            .diag-header { display: flex; align-items: center; justify-content: space-between; width: 100%; }
            .diag-header-left { display: flex; align-items: center; gap: 10px; }
            .diag-icon { font-size: 18px; line-height: 1; }
            .diag-title { font-weight: 600; color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
            .diag-subtitle { font-size: 12px; font-weight: 600; }
            .diag-arrow { font-size: 10px; color: var(--text-muted); font-weight: 600; transition: transform 0.2s; }
            .diag-details { display: none; margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--border-color); font-size: 11px; color: var(--text-muted); }
            .diag-details ul { margin: 4px 0 0 15px; padding: 0; }
            .diag-details li { margin-bottom: 3px; }

            .checklist-box { background: rgba(245, 158, 11, 0.05); padding: 12px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.3); margin-top: 10px; margin-bottom: 10px; }
            .check-accordion-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 6px; overflow: hidden; }
            .check-accordion-header { padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: #0b1120; transition: background 0.2s; }
            .check-accordion-header:hover { background: #131d31; }
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
            .bloque-principal-header { padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: #0e1626; transition: background 0.2s; border-bottom: 1px solid var(--border-color); }
            .bloque-principal-header:hover { background: #131d31; }
            .bloque-principal-body { display: none; padding: 16px; }

            .radar-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 6px;
                margin-top: 8px;
            }
            .btn-radar {
                background: #1e293b;
                border: 1px solid var(--border-color);
                padding: 8px 10px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                color: #38bdf8;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .btn-radar:hover {
                background: #0284c7;
                color: white;
                border-color: var(--accent-cyan);
            }
            .btn-google-maps {
                background: linear-gradient(135deg, #1a73e8, #1557b0);
                color: white;
                border: 1px solid #4285f4;
            }
            .btn-google-maps:hover {
                background: #1557b0;
            }
            .radar-results-box {
                background: #0b1120;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 10px;
                margin-top: 8px;
                max-height: 220px;
                overflow-y: auto;
                font-size: 11px;
                color: var(--text-muted);
            }
            .poi-item {
                padding: 6px 8px;
                border-bottom: 1px dashed var(--border-color);
                margin-bottom: 4px;
            }
            .poi-item:last-child {
                border-bottom: none;
                margin-bottom: 0;
            }
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
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan); cursor:pointer; flex:1;" onclick="toggleAcordeon('body-viajes', 'arrow-viajes')">📁 Viajes Registrados en la Jornada</span>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <button type="button" class="btn-accion-carpeta" onclick="alternarVisibilidadConsulta()">Ocultar Consulta</button>
                                <span id="arrow-viajes" style="font-size:10px; font-weight:600; cursor:pointer;" onclick="toggleAcordeon('body-viajes', 'arrow-viajes')">▼</span>
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
                                    <p style="margin:0 0 2px 0;"><b>Refacciones:</b> Pastillas, líquido DOT 4, retenes. | <b>Costo:</b> $350-$900 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Pérdida de frenado y riesgo de colisión.</p>
                                    <select id="anulador_frenos" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>

                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">⛓ 2. Kit Arrastre / Piñones</p>
                                    <p style="margin:0 0 2px 0;"><b>Refacciones:</b> Cadena, sprocket, piñón. | <b>Costo:</b> $1,200-$2,500 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Ruptura en marcha y bloqueo de rueda.</p>
                                    <select id="anulador_cadena" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>

                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">🛞 3. Llantas / Presión</p>
                                    <p style="margin:0 0 2px 0;"><b>Refacciones:</b> Neumáticos, válvulas, cámaras. | <b>Costo:</b> $800-$2,200 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Pérdida de tracción y pinchazos súbitos.</p>
                                    <select id="anulador_llantas" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>

                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">💡 4. Sistema Eléctrico / Intermitentes</p>
                                    <p style="margin:0 0 2px 0;"><b>Refacciones:</b> Luces LED/halógenas, batería, fusibles. | <b>Costo:</b> $100-$1,200 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Nula visibilidad nocturna y fallo de giro.</p>
                                    <select id="anulador_luces" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>

                                <div style="margin-bottom: 8px; border-bottom: 1px dashed var(--border-color); padding-bottom: 6px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">🪖 5. Casco / Indumentaria (EPP)</p>
                                    <p style="margin:0 0 2px 0;"><b>Refacciones:</b> Mica, guantes, chaleco. | <b>Costo:</b> $400-$3,000 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Lesiones graves en impacto y multas.</p>
                                    <select id="anulador_epp" onchange="verificarAnuladores()">
                                        <option value="revision" selected>Requiere Revisión</option>
                                        <option value="ok">Operativo (OK)</option>
                                    </select>
                                </div>

                                <div style="margin-bottom: 4px;">
                                    <p style="margin:0 0 2px 0; font-weight:600;">📄 6. Licencia / Póliza Vigente</p>
                                    <p style="margin:0 0 2px 0;"><b>Trámites:</b> Licencia tipo A/C, póliza de seguro. | <b>Costo:</b> $800-$3,500 MXN</p>
                                    <p style="margin:0 0 4px 0; color:var(--accent-red);"><b>Omisión:</b> Corralón y desprotección financiera.</p>
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
                        <p style="margin:0 0 4px 0;">Cumple strictly la reglamentación:</p>
                        <p style="margin:0 0 4px 0; font-size:11px;">• <b>Límites:</b> Máx 50 km/h secundarias, 80 km/h acceso controlado, 30 km/h escuelas.</p>
                        <p style="margin:0 0 4px 0; font-size:11px;">• <b>EPP:</b> Casco certificado (DOT/ECE) y chaleco reflejante nocturno.</p>
                        <p style="margin:0 0 6px 0; font-size:11px; color:#fca5a5;">• <b>Prohibiciones:</b> Cero invasión de carriles confinados o banquetas, prohibido conducir cansado o bajo efectos de alcohol.</p>
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
                                    <div class="check-accordion-header" onclick="toggleAcordeon('body-comp-aceite', 'arrow-comp-aceite')" style="background: #111827; padding: 6px 8px; border-radius: 6px; margin-bottom: 4px;">
                                        <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛢️ Cambio de Aceite (Ciclo: 2,500 km)</span>
                                        <span id="arrow-comp-aceite" style="font-size:10px; font-weight:600;">▼</span>
                                    </div>
                                    <div id="body-comp-aceite" class="check-accordion-body" style="padding: 6px 0;">
                                        <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                            <span>Progreso de Vida:</span>
                                            <span id="vida-aceite-txt" style="color:var(--accent-green);">100%</span>
                                        </div>
                                        <div class="progress-container">
                                            <div id="barra-aceite" class="progress-bar" style="width: 100%;"></div>
                                        </div>
                                        <div id="alerta-aceite-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">
                                            💡 <b>Sugerencia:</b> Revisar nivel semanalmente.
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Cambio de Aceite')">✔ Confirmar Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Cambio de Aceite')">🔧 Registrar Mant.</button>
                                    </div>
                                </div>

                                <div class="comp-card">
                                    <div class="check-accordion-header" onclick="toggleAcordeon('body-comp-arrastre', 'arrow-comp-arrastre')" style="background: #111827; padding: 6px 8px; border-radius: 6px; margin-bottom: 4px;">
                                        <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">⛓️ Kit de Arrastre / Piñones (Ciclo: 15,000 km)</span>
                                        <span id="arrow-comp-arrastre" style="font-size:10px; font-weight:600;">▼</span>
                                    </div>
                                    <div id="body-comp-arrastre" class="check-accordion-body" style="padding: 6px 0;">
                                        <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                            <span>Progreso de Vida:</span>
                                            <span id="vida-arrastre-txt" style="color:var(--accent-green);">100%</span>
                                        </div>
                                        <div class="progress-container">
                                            <div id="barra-arrastre" class="progress-bar" style="width: 100%;"></div>
                                        </div>
                                        <div id="alerta-arrastre-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">
                                            💡 <b>Sugerencia:</b> Lubricar cadena cada 500 km.
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Kit de Arrastre / Piñones')">✔ Confirmar Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Kit de Arrastre / Piñones')">🔧 Registrar Mant.</button>
                                    </div>
                                </div>

                                <div class="comp-card">
                                    <div class="check-accordion-header" onclick="toggleAcordeon('body-comp-frenos', 'arrow-comp-frenos')" style="background: #111827; padding: 6px 8px; border-radius: 6px; margin-bottom: 4px;">
                                        <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛑 Pastillas de Freno (Ciclo: 5,000 km)</span>
                                        <span id="arrow-comp-frenos" style="font-size:10px; font-weight:600;">▼</span>
                                    </div>
                                    <div id="body-comp-frenos" class="check-accordion-body" style="padding: 6px 0;">
                                        <div style="font-size: 11px; display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 2px;">
                                            <span>Progreso de Vida:</span>
                                            <span id="vida-frenos-txt" style="color:var(--accent-green);">100%</span>
                                        </div>
                                        <div class="progress-container">
                                            <div id="barra-frenos" class="progress-bar" style="width: 100%;"></div>
                                        </div>
                                        <div id="alerta-frenos-msg" style="font-size: 10px; color: var(--accent-green); margin-top: 3px; font-weight: 600;">
                                            💡 <b>Sugerencia:</b> Inspeccionar espesor de balatas periódicamente.
                                        </div>
                                    </div>
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

            <!-- BLOQUE 3: Telemetría Avanzada y Radar GPS DUAL (Google Maps + Inyección de Coordenadas) -->
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

                    <!-- SISTEMA DUAL DE NAVEGACIÓN Y BÚSQUEDA -->
                    <div class="check-accordion-card" style="margin-bottom: 10px;">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-radar-gps', 'arrow-radar-gps')">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">🗺️ Motor Dual de Búsqueda y Almacenamiento Local</span>
                            <span id="arrow-radar-gps" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-radar-gps" class="check-accordion-body" style="display: block;">
                            
                            <!-- SECCIÓN 1: MOTOR PRIMARIO (GOOGLE MAPS DIRECTO) -->
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
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('hospitales')">🏥 Hospitales</button>
                                        <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('estacion de policia')">🚨 Policía</button>
                                    </div>

                                    <div style="margin-top: 8px; background: rgba(26, 115, 232, 0.1); border: 1px solid rgba(66, 133, 244, 0.3); padding: 8px; border-radius: 6px;">
                                        <label style="font-size: 10px; font-weight: 600; color: #93c5fd; display: block; margin-bottom: 4px;">🔍 Búsqueda Personalizada "Otros" (Google Maps):</label>
                                        <div class="flex-row">
                                            <div class="input-voz-group">
                                                <input type="text" id="input_gmaps_otros" placeholder="Buscar en Google Maps (ej. Farmacia, Comida)...">
                                                <button type="button" class="btn-voice" onclick="escucharVoz('input_gmaps_otros')">🎤</button>
                                            </div>
                                            <button type="button" class="btn-radar btn-google-maps" style="width: auto; padding: 8px 12px; font-size: 11px; margin: 0; white-space: nowrap;" onclick="abrirGoogleMapsOtros()">🧭 Buscar</button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- SECCIÓN 2: REPOSITORIO Y MARCADORES FAVORITOS -->
                            <div class="check-accordion-card" style="margin-bottom: 8px;">
                                <div class="check-accordion-header" onclick="toggleAcordeon('body-repositorio', 'arrow-repositorio')">
                                    <span style="font-size: 11px; font-weight: 700; color: var(--accent-amber);">💾 Repositorio y Marcadores Favoritos (SQLite)</span>
                                    <span id="arrow-repositorio" style="font-size:10px; font-weight:600;">▼</span>
                                </div>
                                <div id="body-repositorio" class="check-accordion-body" style="display: none; background: #0b1120;">
                                    <p style="margin: 0 0 6px 0; color: var(--text-muted); font-size: 10px;">Buscador local prioritario:</p>
                                    
                                    <div class="flex-row">
                                        <div class="input-voz-group">
                                            <input type="text" id="input_mis_rutas" placeholder="Preferencias">
                                            <button type="button" class="btn-voice" onclick="escucharVoz('input_mis_rutas')">🎤</button>
                                        </div>
                                        <button type="button" style="width: auto; padding: 8px 12px; background: #0284c7; font-size: 11px; font-weight: 600;" onclick="buscarMisRutas()">Mis Rutas</button>
                                    </div>

                                    <div id="radar-resultados" class="radar-results-box" style="display: none;">
                                        <span id="radar-loading">Ingrese un término para buscar en "Mis Rutas"...</span>
                                    </div>
                                </div>
                            </div>

                            <!-- SECCIÓN 3: INYECTAR COORDENADAS DE GOOGLE MAPS -->
                            <div class="check-accordion-card" style="margin-bottom: 4px;">
                                <div class="check-accordion-header" onclick="toggleAcordeon('body-inyectar', 'arrow-inyectar')">
                                    <span style="font-size: 11px; font-weight: 600; color: var(--accent-cyan);">📍 Inyectar Coordenadas Copiadas de Google Maps a Base Local</span>
                                    <span id="arrow-inyectar" style="font-size:10px; font-weight:600;">▼</span>
                                </div>
                                <div id="body-inyectar" class="check-accordion-body" style="display: none; background: #0b1120;">
                                    <div style="display:flex; flex-direction:column; gap:4px; margin-top:4px;">
                                        <input type="text" id="gmaps_nombre" placeholder="Nombre del lugar (Ej. Taller Recomendado G. Maps)">
                                        <select id="gmaps_tipo" style="margin:0;">
                                            <option value="taller">Taller</option>
                                            <option value="gasolinera">Gasolinera</option>
                                            <option value="vulcanizadora">Vulcanizadora</option>
                                            <option value="refaccionaria">Refaccionaria</option>
                                            <option value="hospital">Hospital</option>
                                            <option value="policia">Policía</option>
                                            <option value="otros">Otros</option>
                                        </select>
                                        <div class="flex-row">
                                            <input type="text" id="gmaps_coords" placeholder="Lat, Lon (Ej. 19.6543, -99.2014)" style="margin:0;">
                                            <button type="button" style="width:auto; padding:8px 12px; background:#059669; font-size:11px; margin:0;" onclick="guardarCoordenadasGoogleMaps()">Guardar en DB</button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>

                    <!-- Ficha Técnica, Biomecánica y Configuración de Meta de Ahorro -->
                    <div class="telemetria-grid">
                        <div class="telemetria-item">
                            <label>Marca</label>
                            <div class="input-voz-group">
                                <input type="text" id="marca" placeholder="Ej. Bajaj" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('marca')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>Modelo</label>
                            <div class="input-voz-group">
                                <input type="text" id="modelo" placeholder="Ej. Pulsar NS 200" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('modelo')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>Año</label>
                            <div class="input-voz-group">
                                <input type="text" id="anio" placeholder="Ej. 2024" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('anio')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>Odómetro (km)</label>
                            <div class="input-voz-group">
                                <input type="number" id="km" placeholder="Km Actual" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('km')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>Peso Piloto (kg)</label>
                            <div class="input-voz-group">
                                <input type="number" id="peso_piloto" placeholder="Ej. 68" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('peso_piloto')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>Altura Piloto (cm)</label>
                            <div class="input-voz-group">
                                <input type="number" id="altura_piloto" placeholder="Ej. 165" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('altura_piloto')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>🎯 Nombre de la Meta</label>
                            <div class="input-voz-group">
                                <input type="text" id="nombre_meta" placeholder="Ej. Llantas Nuevas / Casco" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('nombre_meta')">🎤</button>
                            </div>
                        </div>
                        <div class="telemetria-item">
                            <label>💵 Monto Meta ($ MXN)</label>
                            <div class="input-voz-group">
                                <input type="number" id="monto_meta" placeholder="Ej. 900" style="padding: 6px 8px; font-size: 11px;">
                                <button type="button" class="btn-voice" onclick="escucharVoz('monto_meta')">🎤</button>
                            </div>
                        </div>
                    </div>

                    <button onclick="actualizarKm()">Sincronizar Odómetro y Auditar Telemetría</button>
                    <div id="diagnostico"></div>

                    <div class="bitacora-box">
                        <p style="margin: 0 0 5px 0; font-weight: 600; font-size: 12px; color: var(--text-main);">📋 AUDITORÍA Y BITÁCORA ANALÍTICA:</p>
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
            let kmComponentes = {
                "Cambio de Aceite": 0,
                "Kit de Arrastre / Piñones": 0,
                "Pastillas de Freno": 0
            };
            let kmDesdeUltimoChequeo = {
                "Cambio de Aceite": 0,
                "Kit de Arrastre / Piñones": 0,
                "Pastillas de Freno": 0
            };
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
                        } else {
                            logout();
                        }
                    } catch(e) {
                        logout();
                    }
                }
            });

            function iniciarTelemetriaNativa() {
                if (navigator.getBattery) {
                    navigator.getBattery().then(battery => {
                        actualizarBateria(battery);
                        battery.addEventListener('levelchange', () => actualizarBateria(battery));
                        battery.addEventListener('chargingchange', () => actualizarBateria(battery));
                    });
                } else {
                    document.getElementById("info-bateria").innerText = "🔋 Batería: N/D";
                }

                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(position => {
                        currentLat = position.coords.latitude;
                        currentLon = position.coords.longitude;
                        
                        fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${currentLat}&lon=${currentLon}&zoom=16`, {
                            headers: { 'Accept-Language': 'es' }
                        })
                        .then(res => res.json())
                        .then(data => {
                            let direccion = data && data.address ? (data.address.road || data.address.suburb || data.address.city || "Zona Exacta GPS") : "Ubicación GPS";
                            document.getElementById("info-ubicacion").innerText = `📍 Ubicación: ${direccion}`;
                        })
                        .catch(() => {
                            document.getElementById("info-ubicacion").innerText = `📍 Coordenadas GPS: ${currentLat.toFixed(4)}, ${currentLon.toFixed(4)}`;
                        });

                        fetch(`https://api.open-meteo.com/v1/forecast?latitude=${currentLat}&longitude=${currentLon}&current_weather=true`)
                            .then(res => res.json())
                            .then(data => {
                                if (data && data.current_weather) {
                                    let temp = data.current_weather.temperature;
                                    let code = data.current_weather.weathercode;
                                    let climaDesc = interpretarClimaWMO(code, temp);
                                    document.getElementById("info-clima").innerText = `🌤️ Clima: ${climaDesc}`;
                                    if (document.getElementById("km_ruta").value > 0) {
                                        simularRuta();
                                    }
                                }
                            })
                            .catch(() => {
                                document.getElementById("info-clima").innerText = "🌤️ Clima: Sin red";
                            });
                    }, () => {
                        document.getElementById("info-ubicacion").innerText = "📍 Ubicación: GPS Denegado / N/D";
                        document.getElementById("info-clima").innerText = "🌤️ Clima: Sin GPS";
                    }, {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    });
                } else {
                    document.getElementById("info-ubicacion").innerText = "📍 Ubicación: No soportada";
                    document.getElementById("info-clima").innerText = "🌤️ Clima: No soportado";
                }

                actualizarRelojSistema();
                setInterval(actualizarRelojSistema, 30000);

                actualizarEstadoRedDetallado();
                if (navigator.connection) {
                    navigator.connection.addEventListener('change', actualizarEstadoRedDetallado);
                }
                window.addEventListener('online', actualizarEstadoRedDetallado);
                window.addEventListener('offline', actualizarEstadoRedDetallado);
            }

            function abrirGoogleMapsExterno(queryBusqueda = "servicios") {
                if (!currentLat || !currentLon) {
                    window.open(`https://www.google.com/maps/search/${encodeURIComponent(queryBusqueda)}`, "_blank");
                    return;
                }
                let url = `https://www.google.com/maps/search/${encodeURIComponent(queryBusqueda)}/@${currentLat},${currentLon},14z`;
                window.open(url, "_blank");
            }

            function abrirGoogleMapsOtros() {
                let termino = document.getElementById("input_gmaps_otros").value.trim();
                if (!termino) {
                    alert("⚠️ Ingrese o dicte una categoría o lugar para buscar en Google Maps.");
                    return;
                }
                abrirGoogleMapsExterno(termino);
            }

            function calcularDistanciaKm(lat1, lon1, lat2, lon2) {
                let R = 6371; 
                let dLat = (lat2 - lat1) * Math.PI / 180;
                let dLon = (lon2 - lon1) * Math.PI / 180;
                let a = 
                    Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
                    Math.sin(dLon/2) * Math.sin(dLon/2);
                let c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
                return R * c;
            }

            async function guardarCoordenadasGoogleMaps() {
                let nombre = document.getElementById("gmaps_nombre").value.trim();
                let tipo = document.getElementById("gmaps_tipo").value;
                let coordsTxt = document.getElementById("gmaps_coords").value.trim();

                if (!nombre || !coordsTxt) {
                    alert("⚠️ Ingrese el nombre del lugar y las coordenadas (Lat, Lon).");
                    return;
                }

                let partes = coordsTxt.split(",");
                if (partes.length !== 2) {
                    alert("⚠️ Formato de coordenadas inválido. Use: latitud, longitud (Ej. 19.6543, -99.2014)");
                    return;
                }

                let lat = parseFloat(partes[0].trim());
                let lon = parseFloat(partes[1].trim());

                if (isNaN(lat) || isNaN(lon)) {
                    alert("⚠️ Las coordenadas ingresadas no son numéricas válidas.");
                    return;
                }

                try {
                    let res = await fetch(API + "/radar/cache", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + authToken
                        },
                        body: JSON.stringify({ tipo, nombre, brand: "Google Maps (Inyectado)", lat, lon })
                    });

                    if (res.ok) {
                        alert("✔ ¡Coordenadas de Google Maps guardadas en 'Mis Rutas' (SQLite)!");
                        document.getElementById("gmaps_nombre").value = "";
                        document.getElementById("gmaps_coords").value = "";
                        document.getElementById("input_mis_rutas").value = nombre;
                        buscarMisRutas();
                    } else {
                        alert("Error al guardar en el servidor.");
                    }
                } catch(e) {
                    alert("Error de conexión al guardar coordenadas.");
                }
            }

            async function buscarMisRutas() {
                let termino = document.getElementById("input_mis_rutas").value.trim().toLowerCase();
                let resultadosBox = document.getElementById("radar-resultados");
                resultadosBox.style.display = "block";
                resultadosBox.innerHTML = "⏳ Consultando 'Mis Rutas' en la base local...";

                try {
                    let res = await fetch(`${API}/radar/cache?tipo=${encodeURIComponent(termino)}`, {
                        headers: { "Authorization": "Bearer " + authToken }
                    });
                    let poisCache = await res.json();

                    if (!poisCache || poisCache.length === 0) {
                        resultadosBox.innerHTML = `⚠️ <b>Sin resultados:</b> No hay coincidencias en 'Mis Rutas' para '${termino}'.`;
                        return;
                    }

                    let elementosConDistancia = poisCache.map(el => {
                        let dist = (el.lat && el.lon && currentLat && currentLon) ? calcularDistanciaKm(currentLat, currentLon, el.lat, el.lon) : 999;
                        return { ...el, distanciaKm: dist };
                    });

                    elementosConDistancia.sort((a, b) => a.distanciaKm - b.distanciaKm);

                    let htmlList = `<b style="color:var(--accent-amber);">📁 Resultados de 'Mis Rutas' [SQLite]:</b><br><br>`;
                    elementosConDistancia.forEach((el, index) => {
                        let brandStr = el.brand ? ` (${el.brand})` : "";
                        let distStr = el.distanciaKm < 999 ? ` (~${el.distanciaKm.toFixed(2)} km)` : "";
                        let mapsUrl = `geo:${el.lat},${el.lon}?q=${el.lat},${el.lon}(${encodeURIComponent(el.nombre)})`;
                        let webUrl = `https://www.google.com/maps/search/?api=1&query=${el.lat},${el.lon}`;
                        let etiquetaPrioridad = index === 0 ? " <span style='color:var(--accent-green); font-weight:600;'>[⭐ Más Cercano]</span>" : "";

                        htmlList += `
                            <div class="poi-item">
                                <b>${index + 1}. ${el.nombre}${brandStr}</b>${etiquetaPrioridad}<br>
                                <span style="color:var(--text-muted); font-size:10px;">Distancia: ${distStr}</span><br>
                                <a href="${mapsUrl}" style="color: #38bdf8; text-decoration: underline;">🧭 App GPS</a> | 
                                <a href="${webUrl}" target="_blank" style="color: #60a5fa; text-decoration: underline;">🌐 Google Maps Web</a>
                            </div>
                        `;
                    });
                    resultadosBox.innerHTML = htmlList;
                } catch(e) {
                    resultadosBox.innerHTML = `⚠️ Error al consultar 'Mis Rutas'.`;
                }
            }

            function interpretarClimaWMO(code, temp) {
                if (code === 0) return `${temp}°C (Óptimo / Soleado)`;
                if (code >= 1 && code <= 3) return `${temp}°C (Nublado / Parcial)`;
                if (code >= 45 && code <= 48) return `${temp}°C (Neblina Densa - Visibilidad Reducida)`;
                if (code >= 51 && code <= 67) return `${temp}°C (Lluvia - Riesgo de Derrape)`;
                if (code >= 71 && code <= 77) return `${temp}°C (Nieve / Aguanieve)`;
                if (code >= 95) return `${temp}°C (Tormenta Severa - Alerta)`;
                return `${temp}°C`;
            }

            function actualizarBateria(battery) {
                let nivel = Math.round(battery.level * 100);
                let estadoCarga = battery.charging ? "⚡" : "";
                document.getElementById("info-bateria").innerText = `🔋 Batería: ${nivel}%${estadoCarga}`;
            }

            function actualizarRelojSistema() {
                let ahora = new Date();
                let horaStr = ahora.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                document.getElementById("info-horario").innerText = `🕒 Hora: ${horaStr}`;
                if (document.getElementById("km_ruta").value > 0) {
                    simularRuta();
                }
            }

            function actualizarEstadoRedDetallado() {
                let elemRed = document.getElementById("info-red");
                if (!navigator.onLine) {
                    elemRed.innerText = "📶 Red: Offline (Modo 'Mis Rutas' Activo)";
                    elemRed.style.color = "var(--accent-red)";
                    return;
                }
                
                let conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
                if (conn) {
                    let tipo = conn.effectiveType || "unknown";
                    let downlink = conn.downlink || 0;
                    let rtt = conn.rtt || 0;

                    if (rtt > 300 || tipo === '2g' || tipo === 'slow-2g') {
                        elemRed.innerText = "📶 Red: Intermitente / Baja";
                        elemRed.style.color = "var(--accent-amber)";
                    } else if (downlink > 5 && (tipo === '4g' || tipo === '5g')) {
                        elemRed.innerText = "📶 Red: Excelente (4G/5G)";
                        elemRed.style.color = "var(--accent-green)";
                    } else {
                        elemRed.innerText = "📶 Red: Buena (" + tipo.toUpperCase() + ")";
                        elemRed.style.color = "var(--accent-cyan)";
                    }
                } else {
                    elemRed.innerText = "📶 Red: Online (Estable)";
                    elemRed.style.color = "var(--accent-green)";
                }
                if (document.getElementById("km_ruta").value > 0) {
                    simularRuta();
                }
            }

            function obtenerPrediccionTrafico() {
                let ahora = new Date();
                let hora = ahora.getHours();
                let dia = ahora.getDay();
                
                if (dia >= 1 && dia <= 5) {
                    if ((hora >= 7 && hora <= 9) || (hora >= 18 && hora <= 20)) {
                        return { nivel: "Alto (Hora Pico / Tráfico Denso)", multiplicador: 1.35, condicion: "⚠️ [Alerta: Zona de alto tráfico / Vías saturadas]" };
                    } else if ((hora >= 10 && hora <= 17)) {
                        return { nivel: "Moderado (Tránsito Medio)", multiplicador: 1.15, condicion: "⚡ [Condición: Tránsito moderado]" };
                    }
                }
                return { nivel: "Fluido / Vías Libres", multiplicador: 1.0, condicion: "✔ [Condición favorable: Vías libres]" };
            }

            function evaluarAlertasOperativas(kmRutaVal, minutosViaje, litrosConsumidos) {
                let climaTexto = document.getElementById("info-clima").innerText;
                let traficoObj = obtenerPrediccionTrafico();
                let alertas = [];

                if (climaTexto.includes("Lluvia") || climaTexto.includes("Tormenta") || climaTexto.includes("Neblina")) {
                    alertas.push("🌧️ [Clima Adverso: Precaución por baja adherencia o visibilidad]");
                } else {
                    alertas.push("🌤️ [Clima Favorable]");
                }

                if (kmRutaVal > 30) {
                    alertas.push("🛣️ [Ruta Larga detectada: Mayor desgaste general / ⚠️ Recomendación: Pausa de descanso]");
                } else {
                    alertas.push("📍 [Trayecto corto / Estándar]");
                }

                if (minutosViaje > 120 || tiempoTotalAcumuladoGlobalMin > 120) {
                    alertas.push("🚨 [Jornada Excesiva / Fatiga Operativa: Descanso obligatorio sugerido]");
                } else if (minutosViaje > 60) {
                    alertas.push("⚠️ [Jornada larga: Monitorear temperatura de motor]");
                } else {
                    alertas.push("✔ [Jornada dentro del rango seguro]");
                }

                alertas.push(traficoObj.condicion);

                if (litrosConsumidos > 2.5) {
                    alertas.push("⛽ [Alto consumo de gasolina por jornada]");
                } else {
                    alertas.push("💧 [Consumo de combustible eficiente]");
                }

                if (kmTotalesAcumuladosGlobal > 150 || minutosViaje > 90) {
                    alertas.push("🔧 [Motor requiere descanso / Enfriamiento preventivo]");
                }

                return alertas.join(" | ");
            }

            function toggleDesplegable(idDetails, idArrow) {
                let details = document.getElementById(idDetails);
                let arrow = document.getElementById(idArrow);
                if (details.style.display === "block") {
                    details.style.display = "none";
                    arrow.style.transform = "rotate(0deg)";
                } else {
                    details.style.display = "block";
                    arrow.style.transform = "rotate(180deg)";
                }
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
                let btnOcultar = event.target;

                if (consultaViajeOculta) {
                    panelOficial.style.display = "none";
                    btnOcultar.innerText = "Mostrar Consulta";
                } else {
                    if (panelOficial.innerHTML.trim() !== "") {
                        panelOficial.style.display = "block";
                    }
                    btnOcultar.innerText = "Ocultar Consulta";
                }
            }

            function actualizarAcordeonViajes() {
                let contenedor = document.getElementById("contenedor-acordeon-viajes");
                let lista = document.getElementById("lista-viajes-acordeon");

                if (!viajesJornadaList || viajesJornadaList.length === 0) {
                    contenedor.style.display = "none";
                    return;
                }

                contenedor.style.display = "block";

                let htmlContent = "";
                viajesJornadaList.forEach((viaje, index) => {
                    let balanceColor = viaje.balance_neto >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                    htmlContent += `
                        <div style="background: #0b1120; border: 1px solid var(--border-color); padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.2s;" onclick="seleccionarViajeAcordeon(${index})">
                            <div style="display: flex; justify-content: space-between; font-weight: 600; color: #38bdf8; font-size: 11px;">
                                <span>📌 ${viaje.nombre_ruta}</span>
                                <span style="color: ${balanceColor};">Neto: $${viaje.balance_neto} MXN</span>
                            </div>
                            <div style="font-size: 10px; color: var(--text-muted); margin-top: 2px;">
                                🕒 ${viaje.hora_registro} | 🛣️ ${viaje.km_recorridos} km | Costo Consumo: $${viaje.costo_viaje}
                            </div>
                        </div>
                    `;
                });
                lista.innerHTML = htmlContent;
            }

            function seleccionarViajeAcordeon(index) {
                let viaje = viajesJornadaList[index];
                if (!viaje) return;

                let panelOficial = document.getElementById("diagnostico-oficial");
                let balanceColor = viaje.balance_neto >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                panelOficial.innerHTML = `
                    <p style="color: var(--accent-cyan); font-weight: 600; margin: 0 0 5px 0;">🔍 [Consulta de Viaje Seleccionado: ${viaje.nombre_ruta}]:</p>
                    <p style="margin:2px 0;"><b>${viaje.ubicacion_registro || 'N/D'}</b></p>
                    <p style="margin:2px 0;"><b>Entorno:</b> ${viaje.hora_registro} | ${viaje.clima_registro}</p>
                    <p style="margin:2px 0;"><b>Señal / Tráfico:</b> ${viaje.red_registro} | Tráfico: ${viaje.trafico_registro}</p>
                    <p style="margin:2px 0;"><b>Presupuesto / Pago Recibido:</b> $${viaje.presupuesto || 0.0} MXN | <b>Costo Consumo:</b> $${viaje.costo_viaje} MXN</p>
                    <p style="margin:2px 0; color: ${balanceColor};"><b>Balance Neto Estimado Viaje:</b> $${viaje.balance_neto} MXN</p>
                    <p style="margin:2px 0;"><b>⏱️ Tiempo del Viaje:</b> ~${viaje.tiempo_viaje}</p>
                    <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${viaje.alerta_operativa || 'N/D'}</p>
                `;

                if (!consultaViajeOculta) {
                    panelOficial.style.display = "block";
                }
            }

            function limpiarVariablesLocales() {
                litrosActualesTanque = 0.0;
                gastoGasolinaRealGlobal = 0.0;
                kmTotalesAcumuladosGlobal = 0.0;
                gastoTotalAcumuladoGlobal = 0.0;
                presupuestoTotalAcumuladoGlobal = 0.0;
                tiempoTotalAcumuladoGlobalMin = 0.0;
                ahorroAcumuladoMetaGlobal = 0.0;
                protocoloConfirmadoLeido = false;
                kmComponentes = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
                kmDesdeUltimoChequeo = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
                bitacoraLocal = [];
                viajesJornadaList = [];
                consultaViajeOculta = false;
                ultimoDiagnostico = "";
                document.getElementById("contenedor-acordeon-viajes").style.display = "none";
                let panelOficial = document.getElementById("diagnostico-oficial");
                panelOficial.innerHTML = "";
                panelOficial.style.display = "none";
            }

            function bloquearSistema(bloquear, mensaje) {
                let btnCargar = document.getElementById("btn_cargar");
                let btnReset = document.getElementById("btn_reset");
                let btnEvaluar = document.getElementById("btn_evaluar");
                let div = document.getElementById("diagnostico-anulador");
                let tituloBloque2 = document.getElementById("titulo-bloque-2");

                sistemaBloqueado = bloquear;
                if(div) div.innerHTML = mensaje;

                if (bloquear) {
                    if(btnCargar) btnCargar.classList.add("bloqueado");
                    if(btnReset) btnReset.classList.add("bloqueado");
                    if(btnEvaluar) btnEvaluar.classList.add("bloqueado");
                    if(tituloBloque2) {
                        tituloBloque2.style.color = "var(--accent-amber)";
                        tituloBloque2.innerText = "⚠️ 2. Mantenimiento Preventivo y Checklist (⚠️ Bloqueo de seguridad: Revise el Bloque 2)";
                    }
                } else {
                    if(btnCargar) btnCargar.classList.remove("bloqueado");
                    if(btnReset) btnReset.classList.remove("bloqueado");
                    if(btnEvaluar) btnEvaluar.classList.remove("bloqueado");
                    if(tituloBloque2) {
                        tituloBloque2.style.color = "#38bdf8";
                        tituloBloque2.innerText = "🛡️ 2. Mantenimiento Preventivo y Checklist (Operativo OK)";
                    }
                }
            }

            function verificarJornadaYDiagnostico() {
                let checklistElem = document.getElementById("checklist-contenedor");
                let protocoloElem = document.getElementById("protocolo-normativo");

                let kmRutaVal = parseFloat(document.getElementById("km_ruta").value) || 0;
                let riesgoComponenteCritico = false;
                let mensajeRiesgo = "";

                let ciclosMaximos = {
                    "Cambio de Aceite": 2500,
                    "Kit de Arrastre / Piñones": 15000,
                    "Pastillas de Freno": 5000
                };

                for (let comp in kmComponentes) {
                    let kmAcum = kmComponentes[comp];
                    let maxCiclo = ciclosMaximos[comp];
                    let kmRestantes = maxCiclo - kmAcum;

                    if (kmRestantes < 100 && kmRutaVal > 10) {
                        riesgoComponenteCritico = true;
                        mensajeRiesgo = `🚨 BLOQUEO DE SEGURIDAD: A '${comp}' le restan solo ${Math.round(kmRestantes)} km de vida y planeas una ruta de ${kmRutaVal} km (>10 km). Realice el mantenimiento o confirme el chequeo en el Bloque 2 para desbloquear.`;
                        break;
                    }
                }

                let alertaGraveActiva = false;
                for (let comp in kmDesdeUltimoChequeo) {
                    let umbralGrave = (comp === "Kit de Arrastre / Piñones") ? 1000 : 2000;
                    if (kmDesdeUltimoChequeo[comp] >= umbralGrave) {
                        alertaGraveActiva = true;
                    }
                }

                let f = document.getElementById("anulador_frenos").value;
                let c = document.getElementById("anulador_cadena").value;
                let ll = document.getElementById("anulador_llantas").value;
                let l = document.getElementById("anulador_luces").value;
                let epp = document.getElementById("anulador_epp").value;
                let docs = document.getElementById("anulador_docs").value;
                let todosOk = (f === "ok" && c === "ok" && ll === "ok" && l === "ok" && epp === "ok" && docs === "ok");

                if (!todosOk || !protocoloConfirmadoLeido || alertaGraveActiva || riesgoComponenteCritico) {
                    if (riesgoComponenteCritico) {
                        bloquearSistema(true, mensajeRiesgo);
                    } else if (alertaGraveActiva) {
                        bloquearSistema(true, "🚨 ALERTA GRAVE: Superados los km sin chequeo obligatorio. Bloque 1 suspendido hasta confirmar chequeo.");
                    } else if (!todosOk) {
                        bloquearSistema(true, "⚠️ Verificación de seguridad requerida: Complete o confirme todos los puntos en 'Operativo (OK)'.");
                    } else {
                        bloquearSistema(false, "✔ Inspección aprobada con éxito.");
                    }

                    if(checklistElem) checklistElem.style.display = "block";
                    if(protocoloElem) protocoloElem.style.display = "none";
                    ultimoDiagnostico = "Estado Operativo: Bloqueado por Seguridad Preventiva";
                } else {
                    bloquearSistema(false, "✔ Puntos de inspección confirmados y operativos.");
                    if(checklistElem) checklistElem.style.display = "none";
                    if(protocoloElem) protocoloElem.style.display = "block";
                }
            }

            function verificarAnuladores() {
                verificarJornadaYDiagnostico();
            }

            function confirmarLeidoProtocolo() {
                protocoloConfirmadoLeido = true;
                verificarJornadaYDiagnostico();
            }

            function simularCarga() {
                let litrosEntrada = parseFloat(document.getElementById("litros_carga").value) || 0;
                let precioGasVal = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let divDiag = document.getElementById("diagnostico-combustible");

                if (litrosEntrada <= 0) {
                    if (document.getElementById("km_ruta").value > 0) {
                        simularRuta();
                    } else {
                        divDiag.innerHTML = "";
                    }
                    return;
                }

                let totalSimulado = round(litrosActualesTanque + litrosEntrada, 2);
                let costoRecargaInversion = round(litrosEntrada * precioGasVal, 2);
                let rendimientoEstandar = 30.0;
                let autonomiaProyectada = round(totalSimulado * rendimientoEstandar, 1);

                divDiag.innerHTML = `
                    <p style="font-size:11px; color:var(--text-muted); margin:0 0 4px 0;"><i>🔍 [Vista previa / Simulación de Carga e Inversión]</i></p>
                    <p style="margin:2px 0;"><b>Carga Actual en Tanque:</b> ${litrosActualesTanque} L</p>
                    <p style="margin:2px 0;"><b>Carga Post-Carga:</b> ${totalSimulado} L (${litrosEntrada} L nuevos)</p>
                    <p style="margin:2px 0; color:var(--accent-amber);"><b>Inversión Monetaria Directa:</b> $${costoRecargaInversion} MXN (${litrosEntrada}L @ $${precioGasVal}/L)</p>
                    <p style="margin:2px 0;"><b>Autonomía Estimada Total:</b> ${autonomiaProyectada} km</p>
                `;
            }

            function simularRuta() {
                let kmRutaVal = parseFloat(document.getElementById("km_ruta").value);
                let precioGasVal = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let presupuestoVal = parseFloat(document.getElementById("presupuesto_ruta").value) || 0.0;
                let divDiag = document.getElementById("diagnostico-combustible");

                verificarJornadaYDiagnostico();

                if (!kmRutaVal || kmRutaVal <= 0) {
                    if (document.getElementById("litros_carga").value > 0) {
                        simularCarga();
                    } else {
                        divDiag.innerHTML = "";
                    }
                    return;
                }

                let rendimientoEstandar = 30.0;
                let litrosConsumidos = round(kmRutaVal / rendimientoEstandar, 2);
                let costoViaje = round(litrosConsumidos * precioGasVal, 2);
                let balanceNetoSim = presupuestoVal === 0 ? round(-costoViaje, 2) : round(presupuestoVal - costoViaje, 2);
                let litrosRestantesSimulados = round(litrosActualesTanque - litrosConsumidos, 2);
                let autonomiaRestanteKm = round(Math.max(0.0, litrosRestantesSimulados) * rendimientoEstandar, 1);
                
                let traficoInfo = obtenerPrediccionTrafico();
                let vel_promedio = 35.0 / traficoInfo.multiplicador; 
                let minutosViaje = round((kmRutaVal / vel_promedio) * 60, 0);
                let h_int = Math.floor(minutosViaje / 60);
                let m_int = Math.round(minutosViaje % 60);
                let tiempoEstimadoSim = h_int > 0 ? `${h_int}h ${m_int}m` : `${m_int} min`;

                let climaActual = document.getElementById("info-clima").innerText.replace("🌤️ Clima: ", "");
                let horaActual = document.getElementById("info-horario").innerText.replace("🕒 Hora: ", "");
                let ubicacionActual = document.getElementById("info-ubicacion").innerText.replace("📍 ", "");
                let alertasSimuladas = evaluarAlertasOperativas(kmRutaVal, minutosViaje, litrosConsumidos);
                let colorBalanceSim = balanceNetoSim >= 0 ? "var(--accent-green)" : "var(--accent-red)";

                divDiag.innerHTML = `
                    <p style="font-size:11px; color:var(--text-muted); margin:0 0 4px 0;"><i>🔍 [Vista previa / Indicadores de Entorno y Ruta]</i></p>
                    <p style="margin:2px 0;"><b>${ubicacionActual}</b></p>
                    <p style="margin:2px 0;"><b>Entorno Actual:</b> ${horaActual} | ${climaActual}</p>
                    <p style="margin:2px 0;"><b>Consumo Teórico / Costo:</b> ${litrosConsumidos} L (<b>$${costoViaje} MXN</b>)</p>
                    <p style="margin:2px 0; color: ${colorBalanceSim};"><b>Balance Neto Simulado:</b> $${balanceNetoSim} MXN (Presupuesto: $${presupuestoVal})</p>
                    <p style="margin:2px 0;"><b>⏱️ Tiempo Estimado:</b> ~${tiempoEstimadoSim}</p>
                    <p style="margin:2px 0;"><b>Autonomía Restante:</b> ${autonomiaRestanteKm} km (${litrosRestantesSimulados} L)</p>
                    <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${alertasSimuladas}</p>
                `;
            }

            function round(value, decimals) {
                return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
            }

            function sincronizarVistaComponente() {
                actualizarBarraComponente("Cambio de Aceite", 2500, "barra-aceite", "vida-aceite-txt", "alerta-aceite-msg", 500);
                actualizarBarraComponente("Kit de Arrastre / Piñones", 15000, "barra-arrastre", "vida-arrastre-txt", "alerta-arrastre-msg", 500);
                actualizarBarraComponente("Pastillas de Freno", 5000, "barra-frenos", "vida-frenos-txt", "alerta-frenos-msg", 1000);
            }

            function actualizarBarraComponente(nombreComp, cicloMax, idBarra, idTxt, idMsg, umbralChequeo) {
                let kmAcumulados = kmComponentes[nombreComp] || 0;
                let kmChequeo = kmDesdeUltimoChequeo[nombreComp] || 0;
                let vidaRestante = Math.max(0, Math.min(100, 100 - (kmAcumulados / cicloMax) * 100));
                
                let barra = document.getElementById(idBarra);
                let txtVida = document.getElementById(idTxt);
                let msgElem = document.getElementById(idMsg);

                if(barra) barra.style.width = vidaRestante + "%";
                if(txtVida) txtVida.innerText = Math.round(vidaRestante) + "% (" + kmAcumulados + "/" + cicloMax + " km)";

                let umbralGrave = (nombreComp === "Kit de Arrastre / Piñones") ? 1000 : 2000;

                if (kmAcumulados >= cicloMax) {
                    if(msgElem) {
                        msgElem.style.color = "var(--accent-red)";
                        msgElem.innerHTML = `🚨 <b>Vida Agotada (${kmAcumulados}/${cicloMax} km):</b> ¡Mantenimiento crítico requerido! Bloque 1 bloqueado para rutas >10 km.`;
                    }
                } else if (kmChequeo >= umbralGrave) {
                    if(msgElem) {
                        msgElem.style.color = "var(--accent-red)";
                        msgElem.innerHTML = `🚨 <b>Alerta Grave (${kmChequeo} km sin chequeo):</b> ¡Requiere inspección obligatoria en el Bloque 2!`;
                    }
                } else if (kmChequeo >= umbralChequeo) {
                    if(msgElem) {
                        msgElem.style.color = "var(--accent-amber)";
                        msgElem.innerHTML = `⚠️ <b>Aviso:</b> Han pasado ${kmChequeo} km desde el último chequeo. Se recomienda inspeccionar / lubricar.`;
                    }
                } else {
                    if(msgElem) {
                        msgElem.style.color = "var(--accent-green)";
                        let sugerenciaTexto = (nombreComp === "Kit de Arrastre / Piñones") ? "Lubricar cadena cada 500 km." : "Revisar nivel periódicamente.";
                        msgElem.innerHTML = `💡 <b>Sugerencia:</b> ${sugerenciaTexto} (${kmChequeo} km desde último chequeo)`;
                    }
                }

                if (vidaRestante > 40) {
                    if(barra) barra.style.background = "var(--accent-green)";
                } else if (vidaRestante > 15) {
                    if(barra) barra.style.background = "var(--accent-amber)";
                } else {
                    if(barra) barra.style.background = "var(--accent-red)";
                }
            }

            async function confirmarChequeoComponente(tipoServicio) {
                kmDesdeUltimoChequeo[tipoServicio] = 0;
                sincronizarVistaComponente();
                verificarJornadaYDiagnostico();
                alert(`✔ Chequeo confirmado para '${tipoServicio}'. Contador de mantenimiento preventivo reiniciado.`);
            }

            async function registrarMantenimientoDirecto(tipoServicio) {
                let res = await fetch(API + "/mantenimiento/reiniciar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ componente: tipoServicio })
                });
                let data = await res.json();
                if(res.ok) {
                    kmComponentes[tipoServicio] = 0;
                    kmDesdeUltimoChequeo[tipoServicio] = 0;
                    sincronizarVistaComponente();
                    verificarJornadaYDiagnostico();
                    
                    let kmActualVal = document.getElementById("km").value || "0";
                    bitacoraLocal.unshift(`✔ [Odómetro: ${kmActualVal} km] Auditoría: ${tipoServicio} auditado y reiniciado al 100%.`);
                    if(bitacoraLocal.length > 5) bitacoraLocal.pop();
                    document.getElementById("lista-bitacora").innerHTML = bitacoraLocal.join("<br>");

                    alert("✔ " + data.mensaje);
                } else {
                    alert(data.detail);
                }
            }

            function escucharVoz(inputId) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) {
                    alert("Tu navegador no soporta entrada por voz.");
                    return;
                }
                const recognition = new SpeechRecognition();
                recognition.lang = 'es-MX';
                recognition.start();

                recognition.onresult = function(event) {
                    let texto = event.results[0][0].transcript;
                    if (inputId === 'km' || inputId === 'litros_carga' || inputId === 'km_ruta' || inputId === 'precio_gas' || inputId === 'presupuesto_ruta' || inputId === 'anio' || inputId === 'peso_piloto' || inputId === 'altura_piloto' || inputId === 'monto_meta') {
                        texto = texto.replace(/[^0-9.]/g, '');
                    }
                    document.getElementById(inputId).value = texto;
                    if (inputId === 'litros_carga') {
                        simularCarga();
                    } else if (inputId === 'km_ruta' || inputId === 'precio_gas' || inputId === 'presupuesto_ruta') {
                        simularRuta();
                    } else if (inputId === 'input_mis_rutas') {
                        buscarMisRutas();
                    } else if (inputId === 'input_gmaps_otros') {
                        abrirGoogleMapsOtros();
                    }
                };

                recognition.onerror = function(event) {
                    alert("Error de voz: " + event.error);
                };
            }

            function compartirReporte() {
                if (!ultimoDiagnostico) {
                    alert("Realiza una evaluación primero.");
                    return;
                }
                const textoReporte = "*REPORTE TELEMETRÍA DEMONION MVP*\\n" + ultimoDiagnostico + "\\n\\nBitácora Reciente:\\n" + (bitacoraLocal.length > 0 ? bitacoraLocal[0] : "Sin registros recientes");

                if (navigator.share) {
                    navigator.share({
                        title: 'Reporte Telemetría',
                        text: textoReporte
                    }).catch(() => {});
                } else {
                    const url = "https://api.whatsapp.com/send?text=" + encodeURIComponent(textoReporte);
                    window.open(url, '_blank');
                }
            }

            function descargarRespaldo() {
                window.location.href = API + "/backup";
            }

            async function register() {
                let u = document.getElementById("user").value;
                let p = document.getElementById("pass").value;
                let res = await fetch(API + "/register", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({username: u, password: p})
                });
                let data = await res.json();
                alert(data.mensaje || data.detail);
            }

            async function login() {
                let u = document.getElementById("user").value;
                let p = document.getElementById("pass").value;
                let res = await fetch(API + "/login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({username: u, password: p})
                });
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
                } else {
                    alert("Credenciales inválidas");
                }
            }

            function logout() {
                authToken = "";
                currentUser = "";
                localStorage.removeItem("demonion_token");
                localStorage.removeItem("demonion_user");
                limpiarVariablesLocales();
                document.getElementById("user").value = "";
                document.getElementById("pass").value = "";
                document.getElementById("auth").style.display = "block";
                document.getElementById("app").style.display = "none";
            }

            async function actualizarKm() {
                let marca = document.getElementById("marca").value;
                let modelo = document.getElementById("modelo").value;
                let anio = parseInt(document.getElementById("anio").value) || 2024;
                let km_actual = parseFloat(document.getElementById("km").value) || 0;
                let peso_piloto = parseFloat(document.getElementById("peso_piloto").value) || 68.0;
                let altura_piloto = parseFloat(document.getElementById("altura_piloto").value) || 165.0;
                let nombre_meta = document.getElementById("nombre_meta").value.trim() || "Mantenimiento General";
                let monto_meta = parseFloat(document.getElementById("monto_meta").value) || 900.0;
                
                let res = await fetch(API + "/vehiculo", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ marca, modelo, anio: anio.toString(), km_actual, peso_piloto, altura_piloto, nombre_meta, monto_meta })
                });
                let data = await res.json();
                if(res.ok) {
                    let anioActual = 2026;
                    let antiguedadAnios = Math.max(0, anioActual - anio);
                    let deprecioAntiguedadPct = antiguedadAnios * 10.0;
                    
                    let estatusKilometraje = "Kilometraje Estándar (Óptimo)";
                    let colorKm = "var(--accent-green)";
                    let recomendacionUso = "Uso personal balanceado. El desgaste mecánico está dentro de los rangos ideales.";

                    if (km_actual > 20000 || (antiguedadAnios > 0 && (km_actual / antiguedadAnios) > 15000)) {
                        estatusKilometraje = "Kilometraje Elevado (>15k-20k km anuales)";
                        colorKm = "var(--accent-red)";
                        recomendacionUso = "Uso intensivo / comercial detectado. Realiza revisiones preventivas de aceite cada 2,000 km.";
                    } else if (km_actual > 10000) {
                        estatusKilometraje = "Kilometraje Moderado / Uso Medio";
                        colorKm = "var(--accent-amber)";
                        recomendacionUso = "Uso continuo. Se recomienda revisar tensión y lubricación de cadena semanalmente.";
                    }

                    let retencionEstimada = Math.max(30, 100 - (18 + deprecioAntiguedadPct));
                    let valorOriginalReferencia = 45000.0;
                    let valorMonetarioEstimado = Math.round(valorOriginalReferencia * (retencionEstimada / 100.0));
                    let montoDepreciacion = valorOriginalReferencia - valorMonetarioEstimado;

                    let mantenimientoProximo = "Ninguno / Óptimo";
                    let minKmRestantes = 999999;
                    let desgloseMantenimientos = "";

                    for (let comp in kmComponentes) {
                        let cicloMax = 2500;
                        if (comp === "Kit de Arrastre / Piñones") cicloMax = 15000;
                        if (comp === "Pastillas de Freno") cicloMax = 5000;

                        let kmUsadosComp = kmComponentes[comp];
                        let kmRestantesComp = Math.max(0, cicloMax - kmUsadosComp);
                        
                        desgloseMantenimientos += `<li><b>${comp}:</b> ${kmRestantesComp} km restantes (Ciclo: ${cicloMax} km)</li>`;

                        if (kmRestantesComp < minKmRestantes) {
                            minKmRestantes = kmRestantesComp;
                            mantenimientoProximo = `${comp} (Faltan ~${kmRestantesComp} km)`;
                        }
                    }

                    let promedioDiario = antiguedadAnios > 0 ? Math.round(km_actual / (antiguedadAnios * 365)) : km_actual;
                    let promedioMensual = antiguedadAnios > 0 ? Math.round(km_actual / (antiguedadAnios * 12)) : km_actual;

                    let imcPiloto = peso_piloto > 0 && altura_piloto > 0 ? (peso_piloto / Math.pow(altura_piloto / 100, 2)).toFixed(1) : "22.0";
                    let precargaSugerida = peso_piloto > 85 ? "Aumentar 2 puntos de precarga en monoshock trasero" : (peso_piloto < 60 ? "Reducir 1 punto de precarga para mayor suavidad" : "Precarga estándar de fábrica recomendada");
                    let fatigaPostural = altura_piloto > 180 ? "Postura alta: Sugiere elevadores de manillar para prevenir tensión lumbar en trayectos >60 min" : (altura_piloto < 165 ? "Postura baja: Alcance óptimo al piso, vigilar ángulo de flexión en rodillas" : "Ergonomía neutral óptima para la geometría del asiento");

                    let pctMeta = Math.min(100, Math.max(0, Math.round((ahorroAcumuladoMetaGlobal / monto_meta) * 100)));
                    let restanteMeta = Math.max(0, monto_meta - ahorroAcumuladoMetaGlobal);
                    
                    let colorBarraMeta = "var(--accent-amber)";
                    if (ahorroAcumuladoMetaGlobal <= 0) {
                        colorBarraMeta = "var(--accent-red)";
                    } else if (ahorroAcumuladoMetaGlobal >= monto_meta) {
                        colorBarraMeta = "var(--accent-green)";
                    }

                    let alertaFelicitacionHtml = "";
                    if (ahorroAcumuladoMetaGlobal > 0 && ahorroAcumuladoMetaGlobal < monto_meta) {
                        alertaFelicitacionHtml = `<p style="margin:4px 0 0 0; color: var(--accent-green); font-weight: 600; font-size: 11px;">🎉 ¡Felicitaciones! Has recuperado tu inversión inicial e iniciado ganancias reales.</p>`;
                    } else if (ahorroAcumuladoMetaGlobal >= monto_meta) {
                        alertaFelicitacionHtml = `<p style="margin:4px 0 0 0; color: var(--accent-green); font-weight: 700; font-size: 11px;">🏆 ¡FELICITACIONES! Has superado la meta establecida de ${nombre_meta}. ¡Capital disponible!</p>`;
                    }

                    let msgMeta = ahorroAcumuladoMetaGlobal <= 0 
                        ? `⚠️ En Negativo / Recuperando Inversión: $${ahorroAcumuladoMetaGlobal.toFixed(2)} MXN.` 
                        : (ahorroAcumuladoMetaGlobal >= monto_meta ? "🏆 ¡Meta Alcanzada! Tienes el capital disponible." : `🚀 Estás al ${pctMeta}% de tu meta. Faltan $${restanteMeta.toFixed(2)} MXN.`);

                    let totalPresupuestoGlobal = presupuestoTotalAcumuladoGlobal || 0.0;
                    let costoGasolinaRealVal = gastoGasolinaRealGlobal || 0.0;
                    let litrosTanqueVal = litrosActualesTanque || 0.0;
                    let balanceNetoTermometro = round(totalPresupuestoGlobal - gastoTotalAcumuladoGlobal, 2);
                    let balanceRealTermometro = ahorroAcumuladoMetaGlobal;

                    document.getElementById("diagnostico").innerHTML = `
                        <div class="diagnostico-container">
                            
                            <div class="diag-card" onclick="toggleDesplegable('details-meta', 'arrow-meta')" style="border-color: var(--accent-cyan);">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">🎯</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">PROPÓSITO DE AHORRO REAL: ${nombre_meta.toUpperCase()}</span>
                                            <span class="diag-subtitle" style="color: ${colorBarraMeta};">$${ahorroAcumuladoMetaGlobal.toFixed(2)} MXN / $${monto_meta.toFixed(2)} MXN (${pctMeta}%)</span>
                                        </div>
                                    </div>
                                    <span id="arrow-meta" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-meta" class="diag-details" style="display: block;">
                                    <div class="progress-container" style="height: 10px; margin-bottom: 6px;">
                                        <div class="progress-bar" style="width: ${ahorroAcumuladoMetaGlobal <= 0 ? 100 : pctMeta}%; background: ${colorBarraMeta};"></div>
                                    </div>
                                    <p style="margin:2px 0; color: var(--text-main);"><b>Estatus:</b> ${msgMeta}</p>
                                    ${alertaFelicitacionHtml}
                                    <p style="margin:6px 0 0 0; color: var(--text-muted); font-size:10px;">📊 <b>Balances Auditados (Termómetro):</b> Inversión: $${costoGasolinaRealVal.toFixed(2)} MXN (${litrosTanqueVal.toFixed(2)} lt gas) vs Balance Neto: $${balanceNetoTermometro.toFixed(2)} MXN | <b>Balance Real:</b> $${balanceRealTermometro.toFixed(2)} MXN</p>
                                </div>
                            </div>

                            <div class="diag-card" onclick="toggleDesplegable('details-valor', 'arrow-valor')">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">💰</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">VALOR COMERCIAL ESTIMADO</span>
                                            <span class="diag-subtitle" style="color: var(--accent-green);">$${valorMonetarioEstimado.toLocaleString()} MXN (~${retencionEstimada}% retención)</span>
                                        </div>
                                    </div>
                                    <span id="arrow-valor" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-valor" class="diag-details">
                                    <p style="margin:0 0 4px 0;"><b>Desglose Financiero de Mercado:</b></p>
                                    <ul>
                                        <li><b>Precio de Referencia (Nuevo):</b> $${valorOriginalReferencia.toLocaleString()} MXN</li>
                                        <li><b>Depreciación Acumulada:</b> -$${montoDepreciacion.toLocaleString()} MXN</li>
                                        <li><b>Precio Sugerido Venta Rápida:</b> $${Math.round(valorMonetarioEstimado * 0.92).toLocaleString()} MXN</li>
                                    </ul>
                                </div>
                            </div>

                            <div class="diag-card" onclick="toggleDesplegable('details-maint', 'arrow-maint')">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">🔧</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">PRÓXIMO MANTENIMIENTO CRÍTICO</span>
                                            <span class="diag-subtitle" style="color: var(--accent-amber);">${mantenimientoProximo}</span>
                                        </div>
                                    </div>
                                    <span id="arrow-maint" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-maint" class="diag-details">
                                    <p style="margin:0 0 4px 0;"><b>Estado Actual de Componentes:</b></p>
                                    <ul>
                                        ${desgloseMantenimientos}
                                    </ul>
                                </div>
                            </div>

                            <div class="diag-card" onclick="toggleDesplegable('details-odometer', 'arrow-odometer')">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">📅</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">ANTIGÜEDAD Y ODÓMETRO SINCRONIZADO</span>
                                            <span class="diag-subtitle">${antiguedadAnios} año(s) | ${data.km_actual} km</span>
                                        </div>
                                    </div>
                                    <span id="arrow-odometer" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-odometer" class="diag-details">
                                    <p style="margin:0 0 4px 0;"><b>Promedios Operativos de Cadencia:</b></p>
                                    <ul>
                                        <li><b>Promedio Diario:</b> ~${promedioDiario} km / día</li>
                                        <li><b>Promedio Mensual:</b> ~${promedioMensual} km / mes</li>
                                        <li><b>Año Modelo Registrado:</b> ${anio}</li>
                                    </ul>
                                </div>
                            </div>

                            <div class="diag-card" onclick="toggleDesplegable('details-km', 'arrow-km')">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">⚠️</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">ANÁLISIS DE KILOMETRAJE</span>
                                            <span class="diag-subtitle" style="color: ${colorKm};">${estatusKilometraje}</span>
                                        </div>
                                    </div>
                                    <span id="arrow-km" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-km" class="diag-details">
                                    <p style="margin:0 0 4px 0;"><b>Diagnóstico Preventivo Operativo:</b></p>
                                    <p style="margin: 2px 0 0 0;">${recomendacionUso}</p>
                                </div>
                            </div>

                            <div class="diag-card" onclick="toggleDesplegable('details-ergo', 'arrow-ergo')">
                                <div class="diag-header">
                                    <div class="diag-header-left">
                                        <span class="diag-icon">🧬</span>
                                        <div style="display:flex; flex-direction:column;">
                                            <span class="diag-title">ERGONOMÍA Y CARGA BIOMÉTRICA</span>
                                            <span class="diag-subtitle" style="color: var(--accent-cyan);">Piloto: ${peso_piloto} kg | ${altura_piloto} cm (IMC: ${imcPiloto})</span>
                                        </div>
                                    </div>
                                    <span id="arrow-ergo" class="diag-arrow">▼</span>
                                </div>
                                <div id="details-ergo" class="diag-details">
                                    <p style="margin:0 0 4px 0;"><b>Ajustes y Confort Recomendados:</b></p>
                                    <ul>
                                        <li><b>Suspensión / Precarga:</b> ${precargaSugerida}</li>
                                        <li><b>Postura y Fatiga:</b> ${fatigaPostural}</li>
                                        <li><b>Distribución de Carga:</b> Óptima para geometría naked deportiva.</li>
                                    </ul>
                                </div>
                            </div>

                        </div>
                    `;
                    ultimoDiagnostico = `Unidad: ${data.marca} ${data.modelo} ${data.anio} | Meta: ${nombre_meta} ($${ahorroAcumuladoMetaGlobal.toFixed(2)}/$${monto_meta})`;
                }
            }

            async function cargarCombustible() {
                let litros_cargados = parseFloat(document.getElementById("litros_carga").value);
                let precio_litro = parseFloat(document.getElementById("precio_gas").value) || 24.0;

                if (!litros_cargados || litros_cargados <= 0) {
                    alert("⚠️ Ingrese una cantidad válida de litros.");
                    return;
                }

                let res = await fetch(API + "/combustible/cargar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ litros_cargados, precio_litro })
                });
                let data = await res.json();
                if(res.ok) {
                    litrosActualesTanque = data.litros_tanque;
                    gastoGasolinaRealGlobal = data.gasto_gasolina_real;
                    ahorroAcumuladoMetaGlobal = data.ahorro_acumulado;

                    let rendimientoEstandar = 30.0;
                    let autonomiaTanque = round(litrosActualesTanque * rendimientoEstandar, 1);
                    let costoRecargaInversion = round(litros_cargados * precio_litro, 2);

                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600; margin:4px 0;">✔ Carga Registrada e Inversión Deduciéndome en Sistema:</p>
                        <p style="margin:2px 0;"><b>Litros Totales en Tanque:</b> ${litrosActualesTanque} L (${litros_cargados} L cargados ahora)</p>
                        <p style="margin:2px 0; color:var(--accent-amber);"><b>Inversión Monetaria Directa:</b> $${costoRecargaInversion} MXN (Acumulada: $${gastoGasolinaRealGlobal.toFixed(2)} MXN)</p>
                        <p style="margin:2px 0;"><b>Autonomía Disponible:</b> ${autonomiaTanque} km</p>
                    `;
                    document.getElementById("litros_carga").value = "";
                    actualizarKm();
                } else {
                    alert(data.detail);
                }
            }

            async function reiniciarTanqueYTelemetria() {
                if (!confirm("¿Estás seguro de reiniciar el tanque a 0 L y borrar los acumulados?")) {
                    return;
                }
                let res = await fetch(API + "/combustible/reiniciar-telemetria", {
                    method: "POST",
                    headers: { "Authorization": "Bearer " + authToken }
                });
                let data = await res.json();
                if(res.ok) {
                    limpiarVariablesLocales();
                    document.getElementById("litros_carga").value = "";
                    document.getElementById("km_ruta").value = "";
                    document.getElementById("nombre_ruta").value = "";
                    document.getElementById("presupuesto_ruta").value = "0.0";
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600;">✔ Acción realizada con éxito.</p>
                    `;
                    verificarJornadaYDiagnostico();
                    actualizarKm();
                } else {
                    alert("Error al reiniciar.");
                }
            }

            async function evaluarRuta() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada: El sistema ha detectado un riesgo crítico para el motor o componentes debido a la ruta planeada. Realice el mantenimiento o confirme el chequeo en el Bloque 2.");
                    return;
                }
                let nombre_ruta = document.getElementById("nombre_ruta").value.trim() || "Ruta General";
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                let precio_gasolina = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let presupuesto = parseFloat(document.getElementById("presupuesto_ruta").value) || 0.0;
                
                let clima_registro = document.getElementById("info-clima").innerText.replace("🌤️ Clima: ", "");
                let hora_registro = document.getElementById("info-horario").innerText.replace("🕒 Hora: ", "");
                let red_registro = document.getElementById("info-red").innerText.replace("📶 Red: ", "");
                let trafico_registro = obtenerPrediccionTrafico().nivel;
                let ubicacion_registro = document.getElementById("info-ubicacion").innerText.replace("📍 ", "");
                
                let rendimientoEstandarEval = 30.0;
                let litrosConsumidosEval = round(km_recorridos / rendimientoEstandarEval, 2);
                let vel_promedio_eval = 35.0 / (obtenerPrediccionTrafico().multiplicador);
                let minutosViajeEval = round((km_recorridos / vel_promedio_eval) * 60);
                let alerta_operativa = evaluarAlertasOperativas(km_recorridos, minutosViajeEval, litrosConsumidosEval);

                let res = await fetch(API + "/combustible/evaluar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ nombre_ruta, km_recorridos, precio_gasolina, presupuesto, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa })
                });
                let data = await res.json();
                if(res.ok) {
                    litrosActualesTanque = data.litros_restantes;
                    gastoGasolinaRealGlobal = data.gasto_gasolina_real;
                    kmTotalesAcumuladosGlobal = data.km_totales_acumulados;
                    gastoTotalAcumuladoGlobal = data.gasto_total_acumulado;
                    presupuestoTotalAcumuladoGlobal = data.presupuesto_total_acumulado;
                    tiempoTotalAcumuladoGlobalMin = data.tiempo_total_acumulado_min;
                    ahorroAcumuladoMetaGlobal = data.ahorro_acumulado;

                    for (let comp in kmComponentes) {
                        kmComponentes[comp] += km_recorridos;
                        kmDesdeUltimoChequeo[comp] += km_recorridos;
                    }
                    sincronizarVistaComponente();

                    if (km_recorridos > 30 || minutosViajeEval > 120 || tiempoTotalAcumuladoGlobalMin > 120) {
                        protocoloConfirmadoLeido = false;
                        document.getElementById("anulador_frenos").value = "revision";
                        document.getElementById("anulador_cadena").value = "revision";
                        document.getElementById("anulador_llantas").value = "revision";
                        document.getElementById("anulador_luces").value = "revision";
                        document.getElementById("anulador_epp").value = "revision";
                        document.getElementById("anulador_docs").value = "revision";
                        alert("⚠️ [Alerta de Seguridad Post-Ruta]: Debido a una ruta larga o jornada extensa, se requiere realizar nuevamente la verificación de los 6 puntos críticos y tomar un descanso preventivo.");
                    }

                    verificarJornadaYDiagnostico();

                    viajesJornadaList.unshift({
                        nombre_ruta: data.nombre_ruta,
                        costo_viaje: data.costo_viaje,
                        presupuesto: data.presupuesto,
                        balance_neto: data.balance_neto,
                        litros_consumidos: data.litros_consumidos,
                        tiempo_viaje: data.tiempo_viaje,
                        km_recorridos: km_recorridos,
                        hora_registro: data.hora_registro,
                        clima_registro: data.clima_registro,
                        red_registro: data.red_registro,
                        trafico_registro: data.trafico_registro,
                        ubicacion_registro: data.ubicacion_registro,
                        alerta_operativa: data.alerta_operativa
                    });
                    actualizarAcordeonViajes();

                    document.getElementById("diagnostico-combustible").innerHTML = "";
                    let panelOficial = document.getElementById("diagnostico-oficial");
                    
                    if (!consultaViajeOculta) {
                        panelOficial.style.display = "block";
                    }

                    let balanceColor = data.balance_neto >= 0 ? "var(--accent-green)" : "var(--accent-red)";

                    panelOficial.innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600; margin: 0 0 5px 0;">✔ Rendimiento Registrado [${data.nombre_ruta}]:</p>
                        <p style="margin:2px 0;"><b>${data.ubicacion_registro}</b></p>
                        <p style="margin:2px 0;"><b>Entorno:</b> ${data.hora_registro} | ${data.clima_registro}</p>
                        <p style="margin:2px 0;"><b>Consumo Teórico / Costo:</b> ${data.litros_consumidos} L (<b>$${data.costo_viaje} MXN</b>)</p>
                        <p style="margin:2px 0;"><b>Presupuesto / Pago Recibido:</b> $${data.presupuesto} MXN</p>
                        <p style="margin:2px 0; color: ${balanceColor};"><b>Balance Neto Estimado Viaje:</b> $${data.balance_neto} MXN</p>
                        <p style="margin:2px 0; color: var(--accent-cyan);"><b>🎯 Ahorro Real acumulado en Bloque 3:</b> $${ahorroAcumuladoMetaGlobal.toFixed(2)} MXN</p>
                        <p style="margin:2px 0;"><b>⏱️ Tiempo del Viaje:</b> ~${data.tiempo_viaje}</p>
                        <p style="margin:2px 0;"><b>Autonomía Restante:</b> ${data.autonomia_restante_km} km (${data.litros_restantes} L)</p>
                        <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${data.alerta_operativa}</p>
                        <hr style="border: 0; border-top: 1px dashed rgba(16, 185, 129, 0.3); margin: 6px 0;">
                        <p style="color: #60a5fa; font-weight: 600; margin:2px 0;">📊 Acumulados Globales:</p>
                        <p style="margin:2px 0;"><b>Km Totales:</b> ${kmTotalesAcumuladosGlobal} km | <b>Gasto Total:</b> $${gastoTotalAcumuladoGlobal.toFixed(2)} MXN</p>
                        <p style="margin:2px 0;"><b>Presupuesto Total:</b> $${presupuestoTotalAcumuladoGlobal.toFixed(2)} MXN | <b>Balance Acumulado:</b> $${round(presupuestoTotalAcumuladoGlobal - gastoTotalAcumuladoGlobal, 2)} MXN</p>
                        <p style="margin:2px 0;"><b>Tiempo Total Acumulado:</b> ${Math.floor(tiempoTotalAcumuladoGlobalMin / 60)}h ${Math.round(tiempoTotalAcumuladoGlobalMin % 60)}m</p>
                    `;

                    actualizarKm();
                } else {
                    alert(data.detail);
                }
            }

            async function cargarEstadoVehiculo() {
                let res = await fetch(API + "/vehiculo", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(res.ok) {
                    let data = await res.json();
                    if(data && Object.keys(data).length > 0) {
                        document.getElementById("marca").value = data.marca || "";
                        document.getElementById("modelo").value = data.modelo || "";
                        document.getElementById("anio").value = data.anio || "";
                        document.getElementById("km").value = data.km_actual || 0;
                        document.getElementById("peso_piloto").value = data.peso_piloto || "";
                        document.getElementById("altura_piloto").value = data.altura_piloto || "";
                        document.getElementById("nombre_meta").value = data.nombre_meta || "Mantenimiento General";
                        document.getElementById("monto_meta").value = data.monto_meta || 900.0;
                        ahorroAcumuladoMetaGlobal = data.ahorro_acumulado || 0.0;
                    }
                }
                
                let resTanque = await fetch(API + "/tanque/estado", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resTanque.ok) {
                    let dataTanque = await resTanque.json();
                    litrosActualesTanque = dataTanque.litros_tanque || 0.0;
                    gastoGasolinaRealGlobal = dataTanque.gasto_gasolina_real || 0.0;
                }

                let resEstadisticas = await fetch(API + "/estadisticas/rutas", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resEstadisticas.ok) {
                    let dataEst = await resEstadisticas.json();
                    kmTotalesAcumuladosGlobal = dataEst.km_totales_acumulados || 0.0;
                    gastoTotalAcumuladoGlobal = dataEst.gasto_total_acumulado || 0.0;
                    presupuestoTotalAcumuladoGlobal = dataEst.presupuesto_total_acumulado || 0.0;
                    tiempoTotalAcumuladoGlobalMin = dataEst.tiempo_total_acumulado_min || 0.0;
                }

                let resMantenimiento = await fetch(API + "/mantenimiento/estado", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resMantenimiento.ok) {
                    let dataMaint = await resMantenimiento.json();
                    dataMaint.forEach(item => {
                        if(kmComponentes.hasOwnProperty(item.componente)) {
                            kmComponentes[item.componente] = item.km_acumulados;
                            kmDesdeUltimoChequeo[item.componente] = item.km_desde_ultimo_aviso !== undefined ? item.km_desde_ultimo_aviso : item.km_acumulados;
                        }
                    });
                }

                let resBitacora = await fetch(API + "/bitacora", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resBitacora.ok) {
                    let dataBit = await resBitacora.json();
                    if(dataBit.length > 0) {
                        viajesJornadaList = dataBit.map(b => ({
                            nombre_ruta: b.nombre_ruta,
                            costo_viaje: b.costo_viaje,
                            presupuesto: b.presupuesto || 0.0,
                            balance_neto: b.balance_neto || 0.0,
                            litros_consumidos: round(b.km_recorridos / 30.0, 2),
                            tiempo_viaje: b.tiempo_viaje,
                            km_recorridos: b.km_recorridos,
                            hora_registro: b.hora_registro,
                            clima_registro: b.clima_registro,
                            red_registro: b.red_registro,
                            trafico_registro: b.trafico_registro,
                            ubicacion_registro: b.ubicacion_registro,
                            alerta_operativa: b.alerta_operativa
                        }));
                        actualizarAcordeonViajes();

                        bitacoraLocal = dataBit.map(b => `✔ [${b.nombre_ruta}] Neto: $${b.balance_neto || 0.0} | ${b.km_recorridos}km`);
                        document.getElementById("lista-bitacora").innerHTML = bitacoraLocal.join("<br>");
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
    cursor.execute("""
        INSERT INTO radar_cache (tipo, nombre, brand, lat, lon)
        VALUES (?, ?, ?, ?, ?)
    """, (item.tipo.lower(), item.nombre, item.brand, item.lat, item.lon))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/radar/cache")
def obtener_cache_poi(tipo: str, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT nombre, brand, lat, lon 
        FROM radar_cache 
        WHERE tipo = ? OR nombre LIKE ? 
        ORDER BY id DESC LIMIT 15
    """, (tipo.lower(), f"%{tipo}%"))
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
    hashed_password = hash_password(user.password)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user.username, hashed_password))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Usuario existente")
    finally:
        conn.close()
    return {"mensaje": "Registrado"}

@app.post("/login")
def login(user: User):
    hashed_password = hash_password(user.password)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE username = ? AND password = ?", (user.username, hashed_password))
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
    return {
        "litros_tanque": row[0] if row and row[0] is not None else 0.0,
        "gasto_gasolina_real": row[1] if row and row[1] is not None else 0.0
    }

@app.get("/estadisticas/rutas")
def obtener_estadisticas_rutas(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"km_totales_acumulados": 0.0, "gasto_total_acumulado": 0.0, "presupuesto_total_acumulado": 0.0, "tiempo_total_acumulado_min": 0.0}

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
    return {"mensaje": "Tanque y contadores de telemetría e historial de ahorro reiniciados con éxito."}

@app.post("/vehiculo")
def gestionar_vehiculo(v: VehiculoUpdate, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # CÁLCULO CORREGIDO: Partir del Balance Neto Acumulado (suma de balances netos de rutas)
    # menos la diferencia entre el gasto real de tanque y el consumo teórico registrado en viajes.
    cursor.execute("SELECT SUM(balance_neto) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    balance_row = cursor.fetchone()
    total_balance_neto = balance_row[0] if balance_row and balance_row[0] is not None else 0.0

    cursor.execute("SELECT gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    tanque_row = cursor.fetchone()
    gasto_gasolina_real = tanque_row[0] if tanque_row and tanque_row[0] is not None else 0.0

    cursor.execute("SELECT SUM(costo_viaje) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    costo_viajes_row = cursor.fetchone()
    total_costo_viajes = costo_viajes_row[0] if costo_viajes_row and costo_viajes_row[0] is not None else 0.0

    ahorro_real_meta = round(total_balance_neto - (gasto_gasolina_real - total_costo_viajes), 2)

    cursor.execute("SELECT id, km_actual, ultimo_servicio FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    
    if row:
        vehiculo_id, km_previo, ultimo_servicio = row
        if ultimo_servicio is None:
            ultimo_servicio = 0.0
        cursor.execute("""
            UPDATE vehiculos 
            SET marca = ?, modelo = ?, anio = ?, km_actual = ?, peso_piloto = ?, altura_piloto = ?, nombre_meta = ?, monto_meta = ?, ahorro_acumulado = ? 
            WHERE id = ?
        """, (v.marca, v.modelo, v.anio, v.km_actual, v.peso_piloto, v.altura_piloto, v.nombre_meta, v.monto_meta, ahorro_real_meta, vehiculo_id))
    else:
        ultimo_servicio = v.km_actual
        cursor.execute("""
            INSERT INTO vehiculos (usuario, marca, modelo, anio, km_actual, ultimo_servicio, peso_piloto, altura_piloto, nombre_meta, monto_meta, ahorro_acumulado) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (usuario, v.marca, v.modelo, v.anio, v.km_actual, ultimo_servicio, v.peso_piloto, v.altura_piloto, v.nombre_meta, v.monto_meta, ahorro_real_meta))
    
    conn.commit()
    conn.close()
    
    km_desde_servicio = max(0.0, v.km_actual - (ultimo_servicio if ultimo_servicio else 0.0))

    return {
        "marca": v.marca,
        "modelo": v.modelo,
        "anio": v.anio,
        "km_actual": v.km_actual,
        "peso_piloto": v.peso_piloto,
        "altura_piloto": v.altura_piloto,
        "nombre_meta": v.nombre_meta,
        "monto_meta": v.monto_meta,
        "ahorro_acumulado": ahorro_real_meta,
        "km_desde_servicio": km_desde_servicio,
        "alerta_color": "green",
        "mensaje_alerta": "Odómetro y metas financieras sincronizadas."
    }

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(balance_neto) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    balance_row = cursor.fetchone()
    total_balance_neto = balance_row[0] if balance_row and balance_row[0] is not None else 0.0

    cursor.execute("SELECT gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    tanque_row = cursor.fetchone()
    gasto_gasolina_real = tanque_row[0] if tanque_row and tanque_row[0] is not None else 0.0

    cursor.execute("SELECT SUM(costo_viaje) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    costo_viajes_row = cursor.fetchone()
    total_costo_viajes = costo_viajes_row[0] if costo_viajes_row and costo_viajes_row[0] is not None else 0.0

    ahorro_real_meta = round(total_balance_neto - (gasto_gasolina_real - total_costo_viajes), 2)

    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = ? WHERE usuario = ?", (ahorro_real_meta, usuario))
    conn.commit()

    cursor.execute("SELECT marca, modelo, anio, km_actual, ultimo_servicio, peso_piloto, altura_piloto, nombre_meta, monto_meta, ahorro_acumulado FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        data = dict(row)
        data["ahorro_acumulado"] = ahorro_real_meta
        data["km_desde_servicio"] = max(0.0, data["km_actual"] - (data["ultimo_servicio"] if data["ultimo_servicio"] else 0.0))
        return data
    return {}

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
    cursor.execute("SELECT nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa FROM bitacora_rutas WHERE usuario = ? ORDER BY id DESC LIMIT 100", (usuario,))
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

    cursor.execute("""
        INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados, km_desde_ultimo_aviso) VALUES (?, ?, 0.0, 0.0)
        ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = 0.0, km_desde_ultimo_aviso = 0.0
    """, (usuario, m.componente))

    cursor.execute("UPDATE vehiculos SET ultimo_servicio = ? WHERE usuario = ?", (km_actual, usuario))

    cursor.execute("INSERT INTO bitacora_servicios (usuario, componente, km_realizado) VALUES (?, ?, ?)",
                   (usuario, m.componente, km_actual))
    
    conn.commit()
    conn.close()
    return {"mensaje": f"Ciclo de '{m.componente}' auditado y reiniciado al 100%."}

@app.post("/combustible/cargar")
def cargar_combustible(c: CargarCombustible, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if c.litros_cargados <= 0:
        raise HTTPException(status_code=400, detail="Los litros deben ser mayores a 0")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_anteriores = row[0] if row and row[0] is not None else 0.0
    gasto_gasolina_anterior = row[1] if row and row[1] is not None else 0.0
    
    nuevo_total_litros = round(litros_anteriores + c.litros_cargados, 2)
    costo_compra_actual = round(c.litros_cargados * c.precio_litro, 2)
    nuevo_gasto_gasolina = round(gasto_gasolina_anterior + costo_compra_actual, 2)
    
    cursor.execute("""
        INSERT INTO tanque_usuario (usuario, litros_tanque, gasto_gasolina_real) VALUES (?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?, gasto_gasolina_real = ?
    """, (usuario, nuevo_total_litros, nuevo_gasto_gasolina, nuevo_total_litros, nuevo_gasto_gasolina))

    cursor.execute("SELECT SUM(balance_neto) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    balance_row = cursor.fetchone()
    total_balance_neto = balance_row[0] if balance_row and balance_row[0] is not None else 0.0

    cursor.execute("SELECT SUM(costo_viaje) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    costo_viajes_row = cursor.fetchone()
    total_costo_viajes = costo_viajes_row[0] if costo_viajes_row and costo_viajes_row[0] is not None else 0.0

    ahorro_real_actualizado = round(total_balance_neto - (nuevo_gasto_gasolina - total_costo_viajes), 2)
    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = ? WHERE usuario = ?", (ahorro_real_actualizado, usuario))

    conn.commit()
    conn.close()
    return {
        "litros_tanque": nuevo_total_litros,
        "gasto_gasolina_real": nuevo_gasto_gasolina,
        "ahorro_acumulado": ahorro_real_actualizado
    }

@app.post("/combustible/evaluar")
def evaluar_ruta(e: EvaluarRuta, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if e.km_recorridos <= 0:
        raise HTTPException(status_code=400, detail="Los kilómetros deben ser mayores a 0")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for comp in ["Cambio de Aceite", "Kit de Arrastre / Piñones", "Pastillas de Freno"]:
        cursor.execute("""
            INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados, km_desde_ultimo_aviso) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(usuario, componente) DO UPDATE SET 
                km_acumulados = km_acumulados + ?,
                km_desde_ultimo_aviso = km_desde_ultimo_aviso + ?
        """, (usuario, comp, e.km_recorridos, e.km_recorridos, e.km_recorridos, e.km_recorridos))

    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_tanque = row[0] if row and row[0] is not None else 0.0
    gasto_gasolina_real = row[1] if row and row[1] is not None else 0.0

    rendimiento_estandar = 30.0
    litros_consumidos = round(e.km_recorridos / rendimiento_estandar, 2)
    costo_viaje = round(litros_consumidos * e.precio_gasolina, 2)
    
    if e.presupuesto == 0.0:
        balance_neto = round(-costo_viaje, 2)
    else:
        balance_neto = round(e.presupuesto - costo_viaje, 2)

    litros_restantes = round(litros_tanque - litros_consumidos, 2)
    
    costo_por_km = round(costo_viaje / e.km_recorridos, 2)
    autonomia_restante_km = round(max(0.0, litros_restantes) * rendimiento_estandar, 1)

    multiplicador_trafico = 1.35 if "Alto" in e.trafico_registro else (1.15 if "Moderado" in e.trafico_registro else 1.0)
    vel_promedio = 35.0 / multiplicador_trafico
    minutos_viaje = round((e.km_recorridos / vel_promedio) * 60)
    
    h_viaje = int(minutos_viaje // 60)
    m_viaje = int(minutos_viaje % 60)
    tiempo_viaje_str = f"{h_viaje}h {m_viaje}m" if h_viaje > 0 else f"{m_viaje} min"

    cursor.execute("""
        INSERT INTO estadisticas_rutas (usuario, km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET 
            km_totales_acumulados = km_totales_acumulados + ?,
            gasto_total_acumulado = gasto_total_acumulado + ?,
            presupuesto_total_acumulado = presupuesto_total_acumulado + ?,
            tiempo_total_acumulado_min = tiempo_total_acumulado_min + ?
    """, (usuario, e.km_recorridos, costo_viaje, e.presupuesto, minutos_viaje, e.km_recorridos, costo_viaje, e.presupuesto, minutos_viaje))

    cursor.execute("""
        INSERT INTO bitacora_rutas (usuario, nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario, e.nombre_ruta, e.km_recorridos, costo_viaje, e.presupuesto, balance_neto, tiempo_viaje_str, e.clima_registro, e.hora_registro, e.red_registro, e.trafico_registro, e.ubicacion_registro, e.alerta_operativa))

    cursor.execute("SELECT SUM(balance_neto) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    balance_row = cursor.fetchone()
    total_balance_neto = balance_row[0] if balance_row and balance_row[0] is not None else 0.0

    cursor.execute("SELECT SUM(costo_viaje) FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    costo_viajes_row = cursor.fetchone()
    total_costo_viajes = costo_viajes_row[0] if costo_viajes_row and costo_viajes_row[0] is not None else 0.0

    ahorro_real_meta = round(total_balance_neto - (gasto_gasolina_real - total_costo_viajes), 2)

    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = ? WHERE usuario = ?", (ahorro_real_meta, usuario))

    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    km_totales_acumulados = est_row[0]
    gasto_total_acumulado = est_row[1]
    presupuesto_total_acumulado = est_row[2]
    tiempo_total_acumulado_min = est_row[3]

    cursor.execute("""
        INSERT INTO tanque_usuario (usuario, litros_tanque, gasto_gasolina_real) VALUES (?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?
    """, (usuario, max(0.0, litros_restantes), gasto_gasolina_real, max(0.0, litros_restantes)))

    cursor.execute("INSERT INTO combustible (usuario, km_recorridos, litros_consumidos, rendimiento) VALUES (?, ?, ?, ?)",
                   (usuario, e.km_recorridos, litros_consumidos, rendimiento_estandar))
    conn.commit()
    conn.close()

    return {
        "nombre_ruta": e.nombre_ruta,
        "litros_consumidos": litros_consumidos,
        "costo_viaje": costo_viaje,
        "presupuesto": e.presupuesto,
        "balance_neto": balance_neto,
        "ahorro_acumulado": ahorro_real_meta,
        "gasto_gasolina_real": gasto_gasolina_real,
        "costo_por_km": costo_por_km,
        "tiempo_viaje": tiempo_viaje_str,
        "autonomia_restante_km": autonomia_restante_km,
        "litros_restantes": max(0.0, litros_restantes),
        "km_totales_acumulados": km_totales_acumulados,
        "gasto_total_acumulado": gasto_total_acumulado,
        "presupuesto_total_acumulado": presupuesto_total_acumulado,
        "tiempo_total_acumulado_min": tiempo_total_acumulado_min,
        "clima_registro": e.clima_registro,
        "hora_registro": e.hora_registro,
        "red_registro": e.red_registro,
        "trafico_registro": e.trafico_registro,
        "ubicacion_registro": e.ubicacion_registro,
        "alerta_operativa": e.alerta_operativa
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
