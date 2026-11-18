from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
import os

app = FastAPI(title="DEMONION MVP - Enterprise Cyber Core", version="5.1.0")
active_sessions = {}

DATA_DIR = "/data" if os.path.exists("/data") and os.access("/data", os.W_OK) else "."
DB_NAME = os.path.join(DATA_DIR, "ventas.db")

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            token_persistente TEXT
        );
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            marca TEXT,
            modelo TEXT,
            anio TEXT,
            km_actual REAL DEFAULT 0.0,
            ultimo_servicio REAL DEFAULT 0.0,
            peso_piloto REAL DEFAULT 0.0,
            altura_piloto REAL DEFAULT 0.0,
            nombre_meta TEXT DEFAULT 'Mantenimiento General',
            monto_meta REAL DEFAULT 2000.0,
            ahorro_acumulado REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS tanque_usuario (
            usuario TEXT PRIMARY KEY,
            litros_tanque REAL DEFAULT 0.0,
            gasto_gasolina_real REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS estadisticas_rutas (
            usuario TEXT PRIMARY KEY,
            km_totales_acumulados REAL DEFAULT 0.0,
            gasto_total_acumulado REAL DEFAULT 0.0,
            tiempo_total_acumulado_min REAL DEFAULT 0.0,
            presupuesto_total_acumulado REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS bitacora_rutas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            nombre_ruta TEXT,
            km_recorridos REAL DEFAULT 0.0,
            costo_viaje REAL DEFAULT 0.0,
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
        );
        CREATE TABLE IF NOT EXISTS combustible (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            km_recorridos REAL DEFAULT 0.0,
            litros_consumidos REAL DEFAULT 0.0,
            rendimiento REAL DEFAULT 30.0
        );
        CREATE TABLE IF NOT EXISTS mantenimiento_componentes (
            usuario TEXT,
            componente TEXT,
            km_acumulados REAL DEFAULT 0.0,
            km_desde_ultimo_aviso REAL DEFAULT 0.0,
            PRIMARY KEY (usuario, componente)
        );
        CREATE TABLE IF NOT EXISTS bitacora_servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            componente TEXT,
            km_realizado REAL DEFAULT 0.0,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS radar_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            nombre TEXT,
            brand TEXT,
            lat REAL,
            lon REAL,
            fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()

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
    token = authorization.split(" ")[1].strip()
    if token in active_sessions:
        return active_sessions[token]
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE token_persistente = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        active_sessions[token] = row[0]
        return row[0]
    raise HTTPException(status_code=401, detail="Sesión expirada")

@app.get("/health")
def health():
    return {"status": "ok", "db": os.path.exists(DB_NAME)}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DEMONION MVP - Enterprise Cyber Core</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-main: #060911;
                --bg-card: rgba(17, 24, 39, 0.9);
                --border-color: #1e293b;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --accent-cyan: #06b6d4;
                --accent-green: #10b981;
                --accent-amber: #f59e0b;
                --accent-red: #ef4444;
                --accent-purple: #8b5cf6;
            }
            body { font-family: 'Outfit', sans-serif; margin: 0; padding: 12px; background: radial-gradient(circle at top right, #0f172a, #060911 60%); color: var(--text-main); min-height: 100vh; }
            .card { background: var(--bg-card); backdrop-filter: blur(10px); padding: 16px; margin-bottom: 12px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5); }
            .hud-bar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
            .hud-metric { background: linear-gradient(145deg, #0f172a, #090d16); border: 1px solid #1e293b; border-top: 2px solid var(--accent-cyan); border-radius: 10px; padding: 10px 8px; text-align: center; }
            .hud-label { font-size: 10px; text-transform: uppercase; color: var(--text-muted); display: block; margin-bottom: 3px; }
            .hud-value { font-size: 15px; font-weight: 700; color: #f8fafc; }
            .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); margin-right: 6px; }
            .auth-status { font-size: 12px; margin-top: 8px; padding: 8px; border-radius: 6px; display: none; }
            h3 { margin-top: 0; color: #38bdf8; font-size: 18px; font-weight: 600; }
            hr { border: 0; border-top: 1px solid var(--border-color); margin: 14px 0; }
            input, select, button { padding: 10px; margin: 4px 0; width: 100%; box-sizing: border-box; border-radius: 8px; border: 1px solid var(--border-color); font-size: 13px; font-family: 'Outfit', sans-serif; background: #0b1120; color: var(--text-main); }
            button { background: linear-gradient(135deg, #0284c7, #0369a1); color: white; border: none; font-weight: 600; cursor: pointer; }
            button:disabled { opacity: 0.5; cursor: wait; }
            .btn-voice { background: var(--accent-purple); width: auto; padding: 6px 10px; font-size: 11px; margin: 0; }
            .btn-share { background: #059669; font-weight: 600; margin-top: 10px; }
            .btn-backup { background: #334155; font-weight: 600; margin-top: 5px; }
            .btn-mantenimiento { background: #d97706; font-weight: 600; font-size: 11px; padding: 6px; margin-top: 6px; width: 48%; }
            .btn-chequeo { background: #0284c7; font-weight: 600; font-size: 11px; padding: 6px; margin-top: 6px; width: 48%; }
            .btn-reset-tanque { background: #dc2626; font-weight: 600; font-size: 12px; padding: 10px; width: 30%; }
            .btn-main-carga { width: 68%; }
            .btn-leido { background: var(--accent-green); font-weight: 600; margin-top: 10px; }
            .btn-accion-carpeta { background: #334155; width: auto; padding: 4px 8px; font-size: 10px; margin: 0; }
            #auth { display: block; max-width: 420px; margin: 40px auto; }
            #app { display: none; max-width: 720px; margin: 0 auto; }
            .flex-row { display: flex; gap: 6px; align-items: center; }
            .input-voz-group { display: flex; gap: 4px; align-items: center; width: 100%; }
            .input-voz-group input { flex: 1; margin: 0; }
            .telemetria-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #0b1120; padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 8px; }
            .telemetria-item { display: flex; flex-direction: column; gap: 2px; }
            .telemetria-item label { font-size: 11px; font-weight: 600; color: var(--text-muted); }
            .entorno-box { background: rgba(14, 165, 233, 0.06); border: 1px solid rgba(14, 165, 233, 0.25); padding: 10px; border-radius: 8px; font-size: 11px; color: #38bdf8; margin-bottom: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
            .checklist-box { background: rgba(245, 158, 11, 0.06); padding: 12px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.35); margin-top: 10px; margin-bottom: 10px; }
            .check-accordion-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 6px; overflow: hidden; }
            .check-accordion-header { padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: #0b1120; }
            .check-accordion-body { display: none; padding: 10px 12px; border-top: 1px dashed var(--border-color); font-size: 11px; color: var(--text-muted); }
            .bloqueado { background: #334155 !important; cursor: not-allowed !important; opacity: 0.65; }
            .progress-container { background: #1e293b; border-radius: 6px; height: 8px; width: 100%; margin: 4px 0; overflow: hidden; border: 1px solid var(--border-color); }
            .progress-bar { height: 100%; width: 100%; background: var(--accent-green); transition: width 0.3s ease; }
            .componentes-grid { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
            .comp-card { background: #0b1120; border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; }
            .bitacora-box { background: #0b1120; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 10px; font-size: 11px; color: var(--text-muted); }
            .panel-oficial { background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.35); padding: 12px; border-radius: 8px; margin-top: 8px; }
            .alerta-normativa { background: rgba(59, 130, 246, 0.06); border: 1px solid rgba(59, 130, 246, 0.35); padding: 12px; border-radius: 8px; font-size: 12px; color: #93c5fd; margin-top: 10px; }
            .bloque-principal-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; margin-bottom: 12px; overflow: hidden; }
            .bloque-principal-header { padding: 13px 16px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; background: linear-gradient(90deg, #0e1626, #111827); border-bottom: 1px solid var(--border-color); }
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
            <input type="text" id="user" placeholder="Usuario" autocomplete="username">
            <input type="password" id="pass" placeholder="Contraseña" autocomplete="current-password">
            <button id="btn-login" onclick="login()">Iniciar Sesión</button>
            <button id="btn-reg" onclick="register()" style="background:#059669; margin-top:6px;">Registrarse</button>
            <div id="auth-msg" class="auth-status"></div>
        </div>

        <div id="app">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;"><span id="hud-dot" class="status-dot"></span>DEMONION // <span id="current-user" style="color:var(--accent-cyan)"></span></h3>
                <span id="hud-lock-badge" style="font-size:10px; padding:4px 8px; border-radius:6px; background:rgba(245,158,11,0.15); color:var(--accent-amber); font-weight:700;">⚠️ CHECKLIST PENDIENTE</span>
            </div>
            <hr>

            <div class="hud-bar">
                <div class="hud-metric">
                    <span class="hud-label">⛽ Autonomía</span>
                    <span id="hud-autonomia" class="hud-value" style="color:var(--accent-cyan);">0.0 km</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-label">💰 Balance Neto</span>
                    <span id="hud-balance" class="hud-value">$0.00</span>
                </div>
                <div class="hud-metric">
                    <span class="hud-label">🛡️ Salud Mecánica</span>
                    <span id="hud-salud" class="hud-value" style="color:var(--accent-green);">100%</span>
                </div>
            </div>
            
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
                            <input type="text" id="nombre_ruta" placeholder="Nombre de Ruta / Pedido (Opcional)">
                            <button type="button" class="btn-voice" onclick="escucharVoz('nombre_ruta')">🎤 Voz</button>
                        </div>
                    </div>
                    <div class="flex-row" style="margin-top: 4px;">
                        <div class="input-voz-group">
                            <input type="number" id="km_ruta" placeholder="Km a Recorrer" oninput="simularRuta()">
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
                            <input type="number" id="presupuesto_ruta" placeholder="Presupuesto / Pago Recibido" value="0.0" oninput="simularRuta()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('presupuesto_ruta')">🎤 Voz</button>
                        </div>
                    </div>
                    <button id="btn_evaluar" style="background:#059669; margin-top:8px;" onclick="evaluarRuta()">Evaluar Costo, Ruta y Descontar</button>
                    <div id="diagnostico-combustible" style="margin-top: 8px;"></div>
                    <div id="contenedor-acordeon-viajes" class="check-accordion-card" style="display:none; margin-top: 8px;">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-viajes', 'arrow-viajes')">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">📁 Viajes Registrados en la Jornada</span>
                            <span id="arrow-viajes" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-viajes" class="check-accordion-body">
                            <div id="lista-viajes-acordeon" style="display: flex; flex-direction: column; gap: 6px;"></div>
                        </div>
                    </div>
                    <div id="diagnostico-oficial" class="panel-oficial" style="display:none;"></div>
                </div>
            </div>

            <div id="contenedor-inspeccion" class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-2', 'arrow-bloque-2')">
                    <span id="titulo-bloque-2" style="font-size:14px; font-weight:600; color:var(--accent-amber);">⚠️ 2. Mantenimiento Preventivo y Checklist</span>
                    <span id="arrow-bloque-2" style="font-size:12px; font-weight:600; color:var(--accent-amber);">▼</span>
                </div>
                <div id="body-bloque-2" class="bloque-principal-body" style="display: block;">
                    <div id="checklist-contenedor" class="checklist-box">
                        <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: 600; font-size: 12px; color: var(--accent-amber);">⚠️ Inspección preventiva: Confirme los 6 puntos críticos de seguridad.</p>
                        <div class="check-accordion-card">
                            <div class="check-accordion-header" onclick="toggleAcordeon('body-seis-puntos', 'arrow-seis-puntos')">
                                <span style="font-size:12px; font-weight:600; color:var(--accent-amber);">📋 Menú Desplegable: Ver y Confirmar los 6 Puntos Críticos</span>
                                <span id="arrow-seis-puntos" style="font-size:10px; font-weight:600;">▼</span>
                            </div>
                            <div id="body-seis-puntos" class="check-accordion-body" style="display: block;">
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
                        <button class="btn-leido" onclick="confirmarLeidoProtocolo()">✔ Entendido y Confirmado (Desbloquear Bloque 1)</button>
                    </div>

                    <div class="check-accordion-card" style="margin-top: 8px;">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-grid-componentes', 'arrow-grid-componentes')">
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">📊 Vida útil de los componentes</span>
                            <span id="arrow-grid-componentes" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-grid-componentes" class="check-accordion-body" style="display: none;">
                            <div class="componentes-grid">
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛢️ Cambio de Aceite (2,500 km)</div>
                                    <div class="progress-container"><div id="barra-aceite" class="progress-bar"></div></div>
                                    <div id="vida-aceite-txt" style="font-size: 11px; margin-top:2px;">100%</div>
                                    <div style="display: flex; gap: 4px; margin-top:4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Cambio de Aceite')">✔ Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Cambio de Aceite')">🔧 Mant.</button>
                                    </div>
                                </div>
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8;">⛓️ Kit Arrastre (15,000 km)</div>
                                    <div class="progress-container"><div id="barra-arrastre" class="progress-bar"></div></div>
                                    <div id="vida-arrastre-txt" style="font-size: 11px; margin-top:2px;">100%</div>
                                    <div style="display: flex; gap: 4px; margin-top:4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Kit de Arrastre / Piñones')">✔ Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Kit de Arrastre / Piñones')">🔧 Mant.</button>
                                    </div>
                                </div>
                                <div class="comp-card">
                                    <div style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛑 Frenos (5,000 km)</div>
                                    <div class="progress-container"><div id="barra-frenos" class="progress-bar"></div></div>
                                    <div id="vida-frenos-txt" style="font-size: 11px; margin-top:2px;">100%</div>
                                    <div style="display: flex; gap: 4px; margin-top:4px;">
                                        <button class="btn-chequeo" onclick="confirmarChequeoComponente('Pastillas de Freno')">✔ Chequeo</button>
                                        <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Pastillas de Freno')">🔧 Mant.</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-3', 'arrow-bloque-3')">
                    <span style="font-size:14px; font-weight:600; color:#38bdf8;">🌐 3. Telemetría Avanzada y Radar GPS Dual</span>
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
                            <div class="radar-grid">
                                <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('gasolineras')">⛽ Gasolineras</button>
                                <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('taller mecanico')">🔧 Talleres</button>
                                <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('vulcanizadora')">🛞 Vulcanizadoras</button>
                                <button class="btn-radar btn-google-maps" onclick="abrirGoogleMapsExterno('refaccionaria')">🔩 Refaccionarias</button>
                            </div>
                            <div class="flex-row" style="margin-top:8px;">
                                <input type="text" id="input_mis_rutas" placeholder="Buscar en Mis Rutas (SQLite)">
                                <button type="button" style="width: auto; padding: 8px 12px; background: #0284c7; font-size: 11px;" onclick="buscarMisRutas()">Mis Rutas</button>
                            </div>
                            <div id="radar-resultados" class="radar-results-box" style="display: none;"></div>
                        </div>
                    </div>

                    <div class="telemetria-grid">
                        <div class="telemetria-item"><label>Marca</label><input type="text" id="marca" placeholder="Ej. Bajaj"></div>
                        <div class="telemetria-item"><label>Modelo</label><input type="text" id="modelo" placeholder="Ej. Pulsar NS 200"></div>
                        <div class="telemetria-item"><label>Año</label><input type="text" id="anio" placeholder="Ej. 2024"></div>
                        <div class="telemetria-item"><label>Odómetro (km)</label><input type="number" id="km" placeholder="Km Actual"></div>
                        <div class="telemetria-item"><label>Peso Piloto (kg)</label><input type="number" id="peso_piloto" placeholder="Ej. 68"></div>
                        <div class="telemetria-item"><label>Altura Piloto (cm)</label><input type="number" id="altura_piloto" placeholder="Ej. 165"></div>
                        <div class="telemetria-item"><label>🎯 Nombre de la Meta</label><input type="text" id="nombre_meta" placeholder="Ej. Llantas Nuevas"></div>
                        <div class="telemetria-item"><label>💵 Monto Meta ($)</label><input type="number" id="monto_meta" placeholder="Ej. 900"></div>
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
            let sistemaBloqueado = false;
            let litrosActualesTanque = 0.0;
            let gastoGasolinaRealGlobal = 0.0;
            let kmTotalesAcumuladosGlobal = 0.0;
            let gastoTotalAcumuladoGlobal = 0.0;
            let presupuestoTotalAcumuladoGlobal = 0.0;
            let ahorroAcumuladoMetaGlobal = 0.0;
            let protocoloConfirmadoLeido = false;
            let currentLat = null, currentLon = null;
            let kmComponentes = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
            let kmDesdeUltimoChequeo = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
            let viajesJornadaList = [];

            function mostrarMensajeAuth(msg, esError = true) {
                let box = document.getElementById("auth-msg");
                box.style.display = "block";
                box.style.background = esError ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.15)";
                box.style.color = esError ? "#fca5a5" : "#6ee7b7";
                box.innerText = msg;
            }

            async function entrarAlDashboard(username) {
                currentUser = username;
                document.getElementById("current-user").innerText = currentUser;
                document.getElementById("auth").style.display = "none";
                document.getElementById("app").style.display = "block";
                await cargarEstadoVehiculoSegura();
                sincronizarVistaComponente();
                verificarJornadaYDiagnostico();
                actualizarHUD();
            }

            window.addEventListener('DOMContentLoaded', async () => {
                if (authToken && authToken !== "null" && authToken !== "undefined") {
                    try {
                        let res = await fetch(API + "/verify-token", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ token: authToken })
                        });
                        if (res.ok) {
                            let data = await res.json();
                            await entrarAlDashboard(data.username);
                        } else {
                            logout();
                        }
                    } catch(e) {
                        mostrarMensajeAuth("⚠️ Servidor sin conexión. Intenta nuevamente.");
                    }
                }
            });

            async function register() {
                let u = document.getElementById("user").value.trim();
                let p = document.getElementById("pass").value.trim();
                if (!u || !p) { mostrarMensajeAuth("⚠️ Ingresa usuario y contraseña."); return; }
                let res = await fetch(API + "/register", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({username: u, password: p})
                });
                let data = await res.json();
                if (res.ok) mostrarMensajeAuth("✔ Registrado correctamente. Inicia sesión.", false);
                else mostrarMensajeAuth("⚠️ " + (data.detail || "Error al registrar."));
            }

            async function login() {
                let u = document.getElementById("user").value.trim();
                let p = document.getElementById("pass").value.trim();
                if (!u || !p) { mostrarMensajeAuth("⚠️ Ingresa usuario y contraseña."); return; }
                let res = await fetch(API + "/login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({username: u, password: p})
                });
                let data = await res.json();
                if(res.ok) {
                    authToken = data.token;
                    localStorage.setItem("demonion_token", authToken);
                    localStorage.setItem("demonion_user", data.username);
                    await entrarAlDashboard(data.username);
                } else {
                    mostrarMensajeAuth("❌ " + (data.detail || "Credenciales inválidas"));
                }
            }

            function logout() {
                authToken = ""; currentUser = "";
                localStorage.removeItem("demonion_token");
                localStorage.removeItem("demonion_user");
                document.getElementById("auth").style.display = "block";
                document.getElementById("app").style.display = "none";
            }

            async function cargarEstadoVehiculoSegura() {
                const headers = { "Authorization": "Bearer " + authToken };
                try {
                    let res = await fetch(API + "/vehiculo", { headers });
                    if (res.ok) {
                        let data = await res.json();
                        if (data && Object.keys(data).length > 0) {
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
                } catch(e) {}

                try {
                    let resTanque = await fetch(API + "/tanque/estado", { headers });
                    if (resTanque.ok) {
                        let dt = await resTanque.json();
                        litrosActualesTanque = dt.litros_tanque || 0.0;
                        gastoGasolinaRealGlobal = dt.gasto_gasolina_real || 0.0;
                    }
                } catch(e) {}

                try {
                    let resEst = await fetch(API + "/estadisticas/rutas", { headers });
                    if (resEst.ok) {
                        let de = await resEst.json();
                        kmTotalesAcumuladosGlobal = de.km_totales_acumulados || 0.0;
                        gastoTotalAcumuladoGlobal = de.gasto_total_acumulado || 0.0;
                        presupuestoTotalAcumuladoGlobal = de.presupuesto_total_acumulado || 0.0;
                    }
                } catch(e) {}

                try {
                    let resMaint = await fetch(API + "/mantenimiento/estado", { headers });
                    if (resMaint.ok) {
                        let dm = await resMaint.json();
                        dm.forEach(item => {
                            if (kmComponentes.hasOwnProperty(item.componente)) {
                                kmComponentes[item.componente] = item.km_acumulados || 0;
                                kmDesdeUltimoChequeo[item.componente] = item.km_desde_ultimo_aviso ?? item.km_acumulados ?? 0;
                            }
                        });
                    }
                } catch(e) {}

                try {
                    let resBit = await fetch(API + "/bitacora", { headers });
                    if (resBit.ok) {
                        let db = await resBit.json();
                        if (db.length > 0) {
                            viajesJornadaList = db.map(b => ({
                                nombre_ruta: b.nombre_ruta,
                                costo_viaje: b.costo_viaje,
                                presupuesto: b.presupuesto || 0.0,
                                balance_neto: b.balance_neto || 0.0,
                                km_recorridos: b.km_recorridos
                            }));
                            actualizarAcordeonViajes();
                            let bitacoraLocal = db.map(b => `✔ [${b.nombre_ruta}] Neto: $${b.balance_neto || 0.0} | ${b.km_recorridos}km`);
                            document.getElementById("lista-bitacora").innerHTML = bitacoraLocal.join("<br>");
                        }
                    }
                } catch(e) {}
            }

            function actualizarHUD() {
                let autonomia = Number((litrosActualesTanque * 30.0).toFixed(1));
                let balance = Number((presupuestoTotalAcumuladoGlobal - gastoTotalAcumuladoGlobal).toFixed(2));
                let vidaAceite = Math.max(0, 100 - ((kmComponentes["Cambio de Aceite"] || 0) / 2500) * 100);
                let vidaArrastre = Math.max(0, 100 - ((kmComponentes["Kit de Arrastre / Piñones"] || 0) / 15000) * 100);
                let vidaFrenos = Math.max(0, 100 - ((kmComponentes["Pastillas de Freno"] || 0) / 5000) * 100);
                let saludPromedio = Math.round((vidaAceite + vidaArrastre + vidaFrenos) / 3);

                document.getElementById("hud-autonomia").innerText = `${autonomia} km`;
                let balEl = document.getElementById("hud-balance");
                balEl.innerText = `$${balance.toFixed(2)}`;
                balEl.style.color = balance >= 0 ? "var(--accent-green)" : "var(--accent-red)";

                let salEl = document.getElementById("hud-salud");
                salEl.innerText = `${saludPromedio}%`;
                salEl.style.color = saludPromedio > 50 ? "var(--accent-green)" : (saludPromedio > 20 ? "var(--accent-amber)" : "var(--accent-red)");
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

            function bloquearSistema(bloquear, mensaje) {
                sistemaBloqueado = bloquear;
                let div = document.getElementById("diagnostico-anulador");
                let badge = document.getElementById("hud-lock-badge");
                if (div) div.innerHTML = mensaje;
                ["btn_cargar", "btn_reset", "btn_evaluar"].forEach(id => {
                    let el = document.getElementById(id);
                    if (el) bloquear ? el.classList.add("bloqueado") : el.classList.remove("bloqueado");
                });
                if (badge) {
                    badge.style.background = bloquear ? "rgba(245,158,11,0.15)" : "rgba(16,185,129,0.15)";
                    badge.style.color = bloquear ? "var(--accent-amber)" : "var(--accent-green)";
                    badge.innerText = bloquear ? "⚠️ CHECKLIST PENDIENTE" : "🛡️ SISTEMA OPERATIVO";
                }
            }

            function verificarJornadaYDiagnostico() {
                let todosOk = ["anulador_frenos", "anulador_cadena", "anulador_llantas", "anulador_luces", "anulador_epp", "anulador_docs"]
                    .every(id => document.getElementById(id).value === "ok");

                if (!todosOk) {
                    bloquearSistema(true, "⚠️ Confirme los 6 puntos críticos en 'Operativo (OK)'.");
                    document.getElementById("checklist-contenedor").style.display = "block";
                    document.getElementById("protocolo-normativo").style.display = "none";
                } else if (!protocoloConfirmadoLeido) {
                    bloquearSistema(true, "⚠️ Confirme el Protocolo Normativo Vial.");
                    document.getElementById("checklist-contenedor").style.display = "none";
                    document.getElementById("protocolo-normativo").style.display = "block";
                } else {
                    bloquearSistema(false, "✔ Puntos de inspección operativos.");
                    document.getElementById("checklist-contenedor").style.display = "none";
                    document.getElementById("protocolo-normativo").style.display = "block";
                }
            }

            function verificarAnuladores() { verificarJornadaYDiagnostico(); }
            function confirmarLeidoProtocolo() {
                protocoloConfirmadoLeido = true;
                verificarJornadaYDiagnostico();
                document.getElementById("body-bloque-1").style.display = "block";
            }

            function actualizarAcordeonViajes() {
                let contenedor = document.getElementById("contenedor-acordeon-viajes");
                let lista = document.getElementById("lista-viajes-acordeon");
                if (!viajesJornadaList.length) { contenedor.style.display = "none"; return; }
                contenedor.style.display = "block";
                lista.innerHTML = viajesJornadaList.map(v => `<div style="background:#0b1120; padding:6px; border-radius:4px;"><b>${v.nombre_ruta}</b> - Neto: $${v.balance_neto}</div>`).join("");
            }

            function sincronizarVistaComponente() {
                let map = [
                    ["Cambio de Aceite", 2500, "barra-aceite", "vida-aceite-txt"],
                    ["Kit de Arrastre / Piñones", 15000, "barra-arrastre", "vida-arrastre-txt"],
                    ["Pastillas de Freno", 5000, "barra-frenos", "vida-frenos-txt"]
                ];
                map.forEach(([comp, max, bId, tId]) => {
                    let acum = kmComponentes[comp] || 0;
                    let vida = Math.max(0, Math.min(100, 100 - (acum / max) * 100));
                    document.getElementById(bId).style.width = vida + "%";
                    document.getElementById(tId).innerText = `${Math.round(vida)}% (${acum}/${max} km)`;
                });
                actualizarHUD();
            }

            async function confirmarChequeoComponente(comp) {
                kmDesdeUltimoChequeo[comp] = 0;
                sincronizarVistaComponente();
                alert(`✔ Chequeo confirmado para ${comp}.`);
            }

            async function registrarMantenimientoDirecto(comp) {
                let res = await fetch(API + "/mantenimiento/reiniciar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ componente: comp })
                });
                if (res.ok) {
                    kmComponentes[comp] = 0;
                    kmDesdeUltimoChequeo[comp] = 0;
                    sincronizarVistaComponente();
                    alert(`✔ Ciclo de ${comp} reiniciado al 100%.`);
                }
            }

            function escucharVoz(inputId) {
                const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SR) { alert("Sin soporte de voz."); return; }
                const r = new SR(); r.lang = 'es-MX'; r.start();
                r.onresult = e => { document.getElementById(inputId).value = e.results[0][0].transcript; };
            }

            function abrirGoogleMapsExterno(q) {
                let url = (currentLat && currentLon) ? `https://www.google.com/maps/search/${encodeURIComponent(q)}/@${currentLat},${currentLon},14z` : `https://www.google.com/maps/search/${encodeURIComponent(q)}`;
                window.open(url, "_blank");
            }

            async function buscarMisRutas() {
                let t = document.getElementById("input_mis_rutas").value.trim();
                let box = document.getElementById("radar-resultados");
                box.style.display = "block";
                let res = await fetch(`${API}/radar/cache?tipo=${encodeURIComponent(t)}`, { headers: { "Authorization": "Bearer " + authToken } });
                let list = await res.json();
                box.innerHTML = list.length ? list.map(i => `<div class="poi-item"><b>${i.nombre}</b></div>`).join("") : "Sin resultados.";
            }

            async function actualizarKm() {
                let body = {
                    marca: document.getElementById("marca").value,
                    modelo: document.getElementById("modelo").value,
                    anio: document.getElementById("anio").value || "2024",
                    km_actual: parseFloat(document.getElementById("km").value) || 0,
                    peso_piloto: parseFloat(document.getElementById("peso_piloto").value) || 68,
                    altura_piloto: parseFloat(document.getElementById("altura_piloto").value) || 165,
                    nombre_meta: document.getElementById("nombre_meta").value || "Mantenimiento General",
                    monto_meta: parseFloat(document.getElementById("monto_meta").value) || 2000
                };
                let res = await fetch(API + "/vehiculo", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify(body)
                });
                if (res.ok) {
                    let d = await res.json();
                    ahorroAcumuladoMetaGlobal = d.ahorro_acumulado;
                    document.getElementById("diagnostico").innerHTML = `<div class="panel-oficial">✔ Unidad <b>${d.marca} ${d.modelo}</b> sincronizada | Meta: <b>$${d.ahorro_acumulado} / $${d.monto_meta}</b></div>`;
                    actualizarHUD();
                }
            }

            async function cargarCombustible() {
                if (sistemaBloqueado) { alert("⚠️ Completa el Checklist."); return; }
                let litros_cargados = parseFloat(document.getElementById("litros_carga").value);
                let precio_litro = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                if (!litros_cargados || litros_cargados <= 0) return;
                let res = await fetch(API + "/combustible/cargar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify({ litros_cargados, precio_litro })
                });
                if (res.ok) {
                    let d = await res.json();
                    litrosActualesTanque = d.litros_tanque;
                    gastoGasolinaRealGlobal = d.gasto_gasolina_real;
                    document.getElementById("litros_carga").value = "";
                    document.getElementById("diagnostico-combustible").innerHTML = `<p style="color:var(--accent-green);">✔ Tanque: <b>${litrosActualesTanque} L</b></p>`;
                    actualizarHUD();
                }
            }

            async function reiniciarTanqueYTelemetria() {
                if (!confirm("¿Reiniciar tanque y contadores?")) return;
                let res = await fetch(API + "/combustible/reiniciar-telemetria", { method: "POST", headers: { "Authorization": "Bearer " + authToken } });
                if (res.ok) { 
                    litrosActualesTanque = 0.0;
                    gastoGasolinaRealGlobal = 0.0;
                    kmTotalesAcumuladosGlobal = 0.0;
                    gastoTotalAcumuladoGlobal = 0.0;
                    presupuestoTotalAcumuladoGlobal = 0.0;
                    viajesJornadaList = [];
                    actualizarAcordeonViajes();
                    actualizarHUD();
                    alert("✔ Reiniciado con éxito."); 
                }
            }

            async function evaluarRuta() {
                if (sistemaBloqueado) { alert("⚠️ Completa el Checklist."); return; }
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                if (!km_recorridos || km_recorridos <= 0) return;
                let payload = {
                    nombre_ruta: document.getElementById("nombre_ruta").value || "Ruta General",
                    km_recorridos,
                    precio_gasolina: parseFloat(document.getElementById("precio_gas").value) || 24.0,
                    presupuesto: parseFloat(document.getElementById("presupuesto_ruta").value) || 0.0,
                    clima_registro: "Óptimo", hora_registro: "Actual", red_registro: "Online",
                    trafico_registro: "Fluido", ubicacion_registro: "GPS Activo", alerta_operativa: "Ninguna"
                };
                let res = await fetch(API + "/combustible/evaluar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    let d = await res.json();
                    litrosActualesTanque = d.litros_restantes;
                    kmTotalesAcumuladosGlobal = d.km_totales_acumulados;
                    gastoTotalAcumuladoGlobal = d.gasto_total_acumulado;
                    presupuestoTotalAcumuladoGlobal = d.presupuesto_total_acumulado;
                    ahorroAcumuladoMetaGlobal = d.ahorro_acumulado;
                    for (let c in kmComponentes) { kmComponentes[c] += km_recorridos; }
                    sincronizarVistaComponente();
                    viajesJornadaList.unshift({ nombre_ruta: payload.nombre_ruta, balance_neto: d.balance_neto, km_recorridos });
                    actualizarAcordeonViajes();
                    actualizarHUD();
                    alert("✔ Ruta evaluada y registrada correctamente.");
                }
            }

            function compartirReporte() {
                window.open("https://api.whatsapp.com/send?text=" + encodeURIComponent(`Reporte DEMONION: Tanque ${litrosActualesTanque}L`), '_blank');
            }

            function descargarRespaldo() { window.location.href = API + "/backup"; }
        </script>
    </body>
    </html>
    """

@app.post("/register")
def register(user: User):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (user.username.strip(), hash_password(user.password)))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El usuario ya existe.")
    finally:
        conn.close()
    return {"mensaje": "Registrado"}

@app.post("/login")
def login(user: User):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE username = ? AND password = ?", (user.username.strip(), hash_password(user.password)))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = secrets.token_hex(32)
    active_sessions[token] = row[0]
    cursor.execute("UPDATE usuarios SET token_persistente = ? WHERE username = ?", (token, row[0]))
    conn.commit()
    conn.close()
    return {"token": token, "username": row[0]}

@app.post("/verify-token")
def verify_token_endpoint(tk: TokenCheck):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM usuarios WHERE token_persistente = ?", (tk.token.strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        active_sessions[tk.token] = row[0]
        return {"username": row[0]}
    raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/tanque/estado")
def obtener_estado_tanque(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return {"litros_tanque": row[0] if row and row[0] else 0.0, "gasto_gasolina_real": row[1] if row and row[1] else 0.0}

@app.get("/estadisticas/rutas")
def obtener_estadisticas_rutas(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {"km_totales_acumulados": 0.0, "gasto_total_acumulado": 0.0, "presupuesto_total_acumulado": 0.0, "tiempo_total_acumulado_min": 0.0}

@app.post("/combustible/reiniciar-telemetria")
def reiniciar_tanque_y_telemetria(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tanque_usuario SET litros_tanque = 0.0, gasto_gasolina_real = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE estadisticas_rutas SET km_totales_acumulados = 0.0, gasto_total_acumulado = 0.0, presupuesto_total_acumulado = 0.0, tiempo_total_acumulado_min = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("DELETE FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    conn.commit()
    conn.close()
    return {"mensaje": "Reiniciado"}

@app.post("/vehiculo")
def gestionar_vehiculo(v: VehiculoUpdate, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT gasto_total_acumulado FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    gasto_total = est_row[0] if est_row and est_row[0] else 0.0
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
    return {"marca": v.marca, "modelo": v.modelo, "km_actual": v.km_actual, "nombre_meta": v.nombre_meta, "monto_meta": v.monto_meta, "ahorro_acumulado": ahorro_real}

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT marca, modelo, anio, km_actual, ultimo_servicio, peso_piloto, altura_piloto, nombre_meta, monto_meta, ahorro_acumulado FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

@app.get("/mantenimiento/estado")
def obtener_estado_mantenimiento(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT componente, km_acumulados, km_desde_ultimo_aviso FROM mantenimiento_componentes WHERE usuario = ?", (usuario,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/bitacora")
def obtener_bitacora(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje FROM bitacora_rutas WHERE usuario = ? ORDER BY id DESC LIMIT 100", (usuario,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/mantenimiento/reiniciar")
def reiniciar_mantenimiento(m: RegistrarMantenimiento, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados, km_desde_ultimo_aviso) VALUES (?, ?, 0.0, 0.0) ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = 0.0, km_desde_ultimo_aviso = 0.0", (usuario, m.componente))
    conn.commit()
    conn.close()
    return {"mensaje": "Reiniciado"}

@app.post("/combustible/cargar")
def cargar_combustible(c: CargarCombustible, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros = round((row[0] if row and row[0] else 0.0) + c.litros_cargados, 2)
    gasto = round((row[1] if row and row[1] else 0.0) + (c.litros_cargados * c.precio_litro), 2)
    cursor.execute("INSERT INTO tanque_usuario (usuario, litros_tanque, gasto_gasolina_real) VALUES (?, ?, ?) ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?, gasto_gasolina_real = ?", (usuario, litros, gasto, litros, gasto))
    conn.commit()
    conn.close()
    return {"litros_tanque": litros, "gasto_gasolina_real": gasto}

@app.post("/combustible/evaluar")
def evaluar_ruta(e: EvaluarRuta, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    for comp in ["Cambio de Aceite", "Kit de Arrastre / Piñones", "Pastillas de Freno"]:
        cursor.execute("INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados, km_desde_ultimo_aviso) VALUES (?, ?, ?, ?) ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = km_acumulados + ?, km_desde_ultimo_aviso = km_desde_ultimo_aviso + ?",
                       (usuario, comp, e.km_recorridos, e.km_recorridos, e.km_recorridos, e.km_recorridos))

    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_tanque = row[0] if row and row[0] else 0.0
    litros_cons = round(e.km_recorridos / 30.0, 2)
    costo = round(litros_cons * e.precio_gasolina, 2)
    balance = round(-costo if e.presupuesto == 0.0 else e.presupuesto - costo, 2)
    litros_restantes = max(0.0, round(litros_tanque - litros_cons, 2))
    minutos = round((e.km_recorridos / 35.0) * 60)
    tiempo_str = f"{minutos} min"

    cursor.execute("INSERT INTO estadisticas_rutas (usuario, km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min) VALUES (?, ?, ?, ?, ?) ON CONFLICT(usuario) DO UPDATE SET km_totales_acumulados = km_totales_acumulados + ?, gasto_total_acumulado = gasto_total_acumulado + ?, presupuesto_total_acumulado = presupuesto_total_acumulado + ?, tiempo_total_acumulado_min = tiempo_total_acumulado_min + ?",
                   (usuario, e.km_recorridos, costo, e.presupuesto, minutos, e.km_recorridos, costo, e.presupuesto, minutos))
    cursor.execute("INSERT INTO bitacora_rutas (usuario, nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (usuario, e.nombre_ruta, e.km_recorridos, costo, e.presupuesto, balance, tiempo_str, e.clima_registro, e.hora_registro, e.red_registro, e.trafico_registro, e.ubicacion_registro, e.alerta_operativa))
    cursor.execute("UPDATE tanque_usuario SET litros_tanque = ? WHERE usuario = ?", (litros_restantes, usuario))

    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est = cursor.fetchone()
    cursor.execute("SELECT monto_meta FROM vehiculos WHERE usuario = ?", (usuario,))
    m_row = cursor.fetchone()
    monto_meta = m_row[0] if m_row and m_row[0] else 2000.0
    ahorro_real = round(monto_meta - est[1], 2)

    conn.commit()
    conn.close()
    return {
        "costo_viaje": costo, "balance_neto": balance, "tiempo_viaje": tiempo_str,
        "litros_restantes": litros_restantes, "km_totales_acumulados": est[0],
        "gasto_total_acumulado": est[1], "presupuesto_total_acumulado": est[2],
        "ahorro_acumulado": ahorro_real
    }

@app.post("/radar/cache")
def guardar_cache_poi(item: CachePOI, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO radar_cache (tipo, nombre, brand, lat, lon) VALUES (?, ?, ?, ?, ?)", (item.tipo.lower(), item.nombre, item.brand, item.lat, item.lon))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/radar/cache")
def obtener_cache_poi(tipo: str, authorization: str = Header(None)):
    verificar_token(authorization)
    conn = get_db()
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
