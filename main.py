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
            password TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
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

    conn.commit()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class User(BaseModel):
    username: str
    password: str

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
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Sesión expirada o inválida")
    return active_sessions[token]

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
                            <input type="text" id="nombre_ruta" placeholder="Nombre de Ruta / Pedido (Ej. Casa / Pedido #1)">
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
                            <input type="number" id="precio_gas" placeholder="Precio Gasolina ($ / Litro)" value="23.7" oninput="simularRuta()">
                            <button type="button" class="btn-voice" onclick="escucharVoz('precio_gas')">🎤 Voz</button>
                        </div>
                    </div>
                    <div class="flex-row">
                        <div class="input-voz-group">
                            <input type="number" id="presupuesto_ruta" placeholder="Presupuesto / Pago Recibido ($0.0 si es Personal)" oninput="simularRuta()">
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

            <!-- BLOQUE 2: Mantenimiento Preventivo y Checklist -->
            <div id="contenedor-inspeccion" class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-2', 'arrow-bloque-2')">
                    <span id="titulo-bloque-2" style="font-size:14px; font-weight:600; color:var(--accent-amber);">⚠️ 2. Mantenimiento Preventivo y Checklist</span>
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
                            <span style="font-size:12px; font-weight:600; color:var(--accent-cyan);">📊 Vida útil y estado simultáneo de los componentes</span>
                            <span id="arrow-grid-componentes" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-grid-componentes" class="check-accordion-body" style="display: none;">
                            <div class="componentes-grid">
                                <div class="comp-card">
                                    <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛢️ Cambio de Aceite</span>
                                    <div class="progress-container"><div id="barra-aceite" class="progress-bar" style="width: 100%;"></div></div>
                                    <button class="btn-chequeo" onclick="confirmarChequeoComponente('Cambio de Aceite')">✔ Confirmar Chequeo</button>
                                    <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Cambio de Aceite')">🔧 Registrar Mant.</button>
                                </div>
                                <div class="comp-card">
                                    <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">⛓️ Kit de Arrastre</span>
                                    <div class="progress-container"><div id="barra-arrastre" class="progress-bar" style="width: 100%;"></div></div>
                                    <button class="btn-chequeo" onclick="confirmarChequeoComponente('Kit de Arrastre / Piñones')">✔ Confirmar Chequeo</button>
                                    <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Kit de Arrastre / Piñones')">🔧 Registrar Mant.</button>
                                </div>
                                <div class="comp-card">
                                    <span style="font-size: 12px; font-weight: 600; color:#38bdf8;">🛑 Pastillas de Freno</span>
                                    <div class="progress-container"><div id="barra-frenos" class="progress-bar" style="width: 100%;"></div></div>
                                    <button class="btn-chequeo" onclick="confirmarChequeoComponente('Pastillas de Freno')">✔ Confirmar Chequeo</button>
                                    <button class="btn-mantenimiento" onclick="registrarMantenimientoDirecto('Pastillas de Freno')">🔧 Registrar Mant.</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- BLOQUE 3: Telemetría Avanzada y Radar GPS Dual -->
            <div class="bloque-principal-card">
                <div class="bloque-principal-header" onclick="toggleAcordeon('body-bloque-3', 'arrow-bloque-3')">
                    <span style="font-size:14px; font-weight:600; color:#38bdf8;">🌐 3. Telemetría Avanzada, Radar GPS y Meta de Ahorro Real</span>
                    <span id="arrow-bloque-3" style="font-size:12px; font-weight:600; color:#38bdf8;">▼</span>
                </div>
                <div id="body-bloque-3" class="bloque-principal-body">
                    <div id="entorno-dispositivo" class="entorno-box">
                        <span id="info-clima">🌤️ Clima: Cargando...</span>
                        <span id="info-bateria">🔋 Batería: --%</span>
                        <span id="info-horario">🕒 Hora: --:--</span>
                        <span id="info-red">📶 Red: Analizando...</span>
                        <span id="info-ubicacion" style="grid-column: span 2;">📍 Ubicación: GPS...</span>
                    </div>

                    <div class="telemetria-grid">
                        <div class="telemetria-item"><label>Marca</label><input type="text" id="marca" placeholder="Bajaj"></div>
                        <div class="telemetria-item"><label>Modelo</label><input type="text" id="modelo" placeholder="Pulsar NS 200"></div>
                        <div class="telemetria-item"><label>Año</label><input type="text" id="anio" placeholder="2024"></div>
                        <div class="telemetria-item"><label>Odómetro (km)</label><input type="number" id="km" placeholder="22863"></div>
                        <div class="telemetria-item"><label>Peso Piloto (kg)</label><input type="number" id="peso_piloto" placeholder="68"></div>
                        <div class="telemetria-item"><label>Altura Piloto (cm)</label><input type="number" id="altura_piloto" placeholder="165"></div>
                        <div class="telemetria-item"><label>🎯 Nombre Meta</label><input type="text" id="nombre_meta" placeholder="Llantas"></div>
                        <div class="telemetria-item"><label>💵 Monto Meta ($)</label><input type="number" id="monto_meta" placeholder="900"></div>
                    </div>

                    <button onclick="actualizarKm()">Sincronizar Odómetro y Auditar Telemetría</button>
                    <div id="diagnostico"></div>

                    <div class="bitacora-box">
                        <p style="margin: 0 0 5px 0; font-weight: 600; font-size: 12px; color: var(--text-main);">📋 AUDITORÍA Y BITÁCORA ANALÍTICA:</p>
                        <div id="lista-bitacora">Sin registros analíticos en esta sesión.</div>
                    </div>

                    <hr>
                    <button class="btn-share" onclick="compartirReporte()">📲 Compartir Reporte</button>
                    <button class="btn-backup" onclick="descargarRespaldo()">💾 Descargar Copia DB</button>
                </div>
            </div>
            
            <div class="card">
                <button onclick="logout()" style="background:#475569; margin-top: 0;">Cerrar Sesión</button>
            </div>
        </div>

        <script>
            const API = window.location.origin;
            let authToken = "";
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

            function formatoTiempoHorasMinutos(minutosTotales) {
                let h = Math.floor(minutosTotales / 60);
                let m = Math.round(minutosTotales % 60);
                return h > 0 ? `${h}h ${m}m` : `${m} min`;
            }

            function round(value, decimals) {
                return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
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

            async function evaluarRuta() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada por seguridad preventiva en Bloque 2.");
                    return;
                }
                let nombre_ruta = document.getElementById("nombre_ruta").value.trim() || "Ruta General";
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                let precio_gasolina = parseFloat(document.getElementById("precio_gas").value) || 23.7;
                let presupuesto = parseFloat(document.getElementById("presupuesto_ruta").value) || 0.0;
                
                let clima_registro = document.getElementById("info-clima") ? document.getElementById("info-clima").innerText.replace("🌤️ Clima: ", "") : "N/D";
                let hora_registro = document.getElementById("info-horario") ? document.getElementById("info-horario").innerText.replace("🕒 Hora: ", "") : "N/D";
                let red_registro = document.getElementById("info-red") ? document.getElementById("info-red").innerText.replace("📶 Red: ", "") : "N/D";
                let trafico_registro = "Fluido";
                let ubicacion_registro = document.getElementById("info-ubicacion") ? document.getElementById("info-ubicacion").innerText.replace("📍 ", "") : "N/D";

                let res = await fetch(API + "/combustible/evaluar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ nombre_ruta, km_recorridos, precio_gasolina, presupuesto, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa: "Ruta Evaluada" })
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

                    viajesJornadaList.unshift({
                        nombre_ruta: data.nombre_ruta,
                        costo_viaje: data.costo_viaje,
                        presupuesto: data.presupuesto,
                        balance_neto: data.balance_neto,
                        litros_consumidos: data.litros_consumidos,
                        tiempo_viaje: data.tiempo_viaje,
                        km_recorridos: km_recorridos,
                        hora_registro: data.hora_registro
                    });
                    actualizarAcordeonViajes();

                    let panelOficial = document.getElementById("diagnostico-oficial");
                    panelOficial.style.display = "block";
                    let balanceColor = data.balance_neto >= 0 ? "var(--accent-green)" : "var(--accent-red)";
                    let tiempoTotalStr = formatoTiempoHorasMinutos(tiempoTotalAcumuladoGlobalMin);

                    panelOficial.innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600; margin: 0 0 5px 0;">✔ Rendimiento Registrado [${data.nombre_ruta}]:</p>
                        <p style="margin:2px 0;"><b>Consumo / Costo Ruta:</b> ${data.litros_consumidos} L (<b>$${data.costo_viaje} MXN</b>)</p>
                        <p style="margin:2px 0;"><b>Presupuesto / Pago Recibido:</b> $${data.presupuesto} MXN</p>
                        <p style="margin:2px 0; color: ${balanceColor};"><b>Balance Neto Viaje:</b> $${data.balance_neto} MXN</p>
                        <p style="margin:2px 0; color: var(--accent-cyan);"><b>🎯 Ahorro Real acumulado en Bloque 3:</b> $${ahorroAcumuladoMetaGlobal.toFixed(2)} MXN</p>
                        <hr style="border: 0; border-top: 1px dashed rgba(16, 185, 129, 0.3); margin: 6px 0;">
                        <p style="color: #60a5fa; font-weight: 600; margin:2px 0;">📊 ACUMULADOS GLOBALES DE LA JORNADA:</p>
                        <p style="margin:2px 0;"><b>⏱️ Tiempo Total Transcurrido:</b> ${tiempoTotalStr}</p>
                        <p style="margin:2px 0;"><b>🛣️ Km Totales Recorridos:</b> ${kmTotalesAcumuladosGlobal.toFixed(1)} km</p>
                        <p style="margin:2px 0;"><b>💵 Ingresos Totales Recibidos:</b> $${presupuestoTotalAcumuladoGlobal.toFixed(2)} MXN</p>
                    `;

                    actualizarKm();
                } else {
                    alert(data.detail);
                }
            }

            async function actualizarKm() {
                let marca = document.getElementById("marca").value;
                let modelo = document.getElementById("modelo").value;
                let anio = parseInt(document.getElementById("anio").value) || 2024;
                let km_actual = parseFloat(document.getElementById("km").value) || 0;
                let peso_piloto = parseFloat(document.getElementById("peso_piloto").value) || 68.0;
                let altura_piloto = parseFloat(document.getElementById("altura_piloto").value) || 165.0;
                let nombre_meta = document.getElementById("nombre_meta").value.trim() || "Llantas";
                let monto_meta = parseFloat(document.getElementById("monto_meta").value) || 900.0;

                let pctMeta = Math.min(100, Math.round((ahorroAcumuladoMetaGlobal / monto_meta) * 100));
                let restanteMeta = Math.max(0, monto_meta - ahorroAcumuladoMetaGlobal);
                let colorBarraMeta = pctMeta >= 100 ? "var(--accent-green)" : (pctMeta > 50 ? "var(--accent-cyan)" : "var(--accent-amber)");
                let msgMeta = pctMeta >= 100 ? "🏆 ¡Meta Alcanzada!" : `🚀 Estás al ${pctMeta}% de tu meta. Faltan $${restanteMeta.toFixed(2)} MXN.`;
                let tiempoTotalGlobalStr = formatoTiempoHorasMinutos(tiempoTotalAcumuladoGlobalMin);

                document.getElementById("diagnostico").innerHTML = `
                    <div class="diagnostico-container">
                        <!-- TARJETA 1: META DE AHORRO REAL AUDITADA -->
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
                                    <div class="progress-bar" style="width: ${pctMeta}%; background: ${colorBarraMeta};"></div>
                                </div>
                                <p style="margin:2px 0; color: var(--text-main);"><b>Estatus:</b> ${msgMeta}</p>
                                <p style="margin:4px 0 0 0; color: var(--text-muted); font-size:10px;">📊 <b>Balances Auditados:</b> Pagos Recibidos ($${presupuestoTotalAcumuladoGlobal.toFixed(2)}) − Inversión Real Gasolina ($${gastoGasolinaRealGlobal.toFixed(2)}) − Descuento por Consumo en Rutas Sin Pago</p>
                            </div>
                        </div>

                        <!-- TARJETA 2: ACUMULADOS GLOBALES DE TIEMPO Y DISTANCIA -->
                        <div class="diag-card" onclick="toggleDesplegable('details-acumulados', 'arrow-acumulados')">
                            <div class="diag-header">
                                <div class="diag-header-left">
                                    <span class="diag-icon">📈</span>
                                    <div style="display:flex; flex-direction:column;">
                                        <span class="diag-title">ACUMULADOS GLOBALES DE JORNADA</span>
                                        <span class="diag-subtitle" style="color: var(--accent-cyan);">${kmTotalesAcumuladosGlobal.toFixed(1)} km | ${tiempoTotalGlobalStr}</span>
                                    </div>
                                </div>
                                <span id="arrow-acumulados" class="diag-arrow">▼</span>
                            </div>
                            <div id="details-acumulados" class="diag-details">
                                <ul>
                                    <li><b>Km Totales Recorridos:</b> ${kmTotalesAcumuladosGlobal.toFixed(1)} km</li>
                                    <li><b>Tiempo Total en Ruta:</b> ${tiempoTotalGlobalStr}</li>
                                    <li><b>Ingresos Totales Recibidos:</b> $${presupuestoTotalAcumuladoGlobal.toFixed(2)} MXN</li>
                                    <li><b>Litros Consumidos Totales:</b> ${(kmTotalesAcumuladosGlobal / 30.0).toFixed(2)} L</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                `;
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
                    document.getElementById("current-user").innerText = u;
                    document.getElementById("auth").style.display = "none";
                    document.getElementById("app").style.display = "block";
                    await cargarEstadoVehiculo();
                } else {
                    alert("Credenciales incorrectas");
                }
            }

            function logout() {
                authToken = "";
                document.getElementById("auth").style.display = "block";
                document.getElementById("app").style.display = "none";
            }

            async function cargarEstadoVehiculo() {
                let res = await fetch(API + "/vehiculo", { headers: { "Authorization": "Bearer " + authToken } });
                if(res.ok) {
                    let data = await res.json();
                    if(data && data.marca) {
                        document.getElementById("marca").value = data.marca || "";
                        document.getElementById("modelo").value = data.modelo || "";
                        document.getElementById("anio").value = data.anio || "";
                        document.getElementById("km").value = data.km_actual || 0;
                        document.getElementById("nombre_meta").value = data.nombre_meta || "Llantas";
                        document.getElementById("monto_meta").value = data.monto_meta || 900.0;
                        ahorroAcumuladoMetaGlobal = data.ahorro_acumulado || 0.0;
                    }
                }
                actualizarKm();
            }

            function simularCarga() {}
            function simularRuta() {}
            function verificarAnuladores() {}
            function confirmarLeidoProtocolo() {}
            function confirmarChequeoComponente(c) {}
            function registrarMantenimientoDirecto(c) {}
            function escucharVoz(i) {}
            function compartirReporte() {}
            function descargarRespaldo() {}
            function cargarCombustible() {}
            function reiniciarTanqueYTelemetria() {}
            function actualizarAcordeonViajes() {}
            function alternarVisibilidadConsulta() {}
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/combustible/evaluar")
def evaluar_ruta(e: EvaluarRuta, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if e.km_recorridos <= 0:
        raise HTTPException(status_code=400, detail="Los kilómetros deben ser mayores a 0")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    rendimiento_estandar = 30.0
    litros_consumidos = round(e.km_recorridos / rendimiento_estandar, 2)
    costo_viaje = round(litros_consumidos * e.precio_gasolina, 2)
    
    # CALCULAMOS EL BALANCE NETO (Si e.presupuesto es 0.0, balance_neto es -costo_viaje)
    balance_neto = round(e.presupuesto - costo_viaje, 2)

    cursor.execute("SELECT litros_tanque, gasto_gasolina_real FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_tanque = row[0] if row and row[0] is not None else 0.0
    gasto_gasolina_real = row[1] if row and row[1] is not None else 0.0

    litros_restantes = round(litros_tanque - litros_consumidos, 2)
    minutos_viaje = round((e.km_recorridos / 35.0) * 60)
    
    cursor.execute("""
        INSERT INTO estadisticas_rutas (usuario, km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min) 
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET 
            km_totales_acumulados = km_totales_acumulados + ?,
            gasto_total_acumulado = gasto_total_acumulado + ?,
            presupuesto_total_acumulado = presupuesto_total_acumulado + ?,
            tiempo_total_acumulado_min = tiempo_total_acumulado_min + ?
    """, (usuario, e.km_recorridos, costo_viaje, e.presupuesto, minutos_viaje, e.km_recorridos, costo_viaje, e.presupuesto, minutos_viaje))

    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, presupuesto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    km_totales_acumulados = est_row[0]
    gasto_total_acumulado = est_row[1]
    presupuesto_total_acumulado = est_row[2]
    tiempo_total_acumulado_min = est_row[3]

    # AHORRO REAL DE META: Pagos totales recibidos - Inversión directa en recargas - Descuento por viajes personales/sin pago
    # Si e.presupuesto es 0.0, se resta el costo_viaje de ese trayecto personal para no generar saldo ficticio
    cursor.execute("SELECT ahorro_acumulado FROM vehiculos WHERE usuario = ?", (usuario,))
    v_row = cursor.fetchone()
    ahorro_previo = v_row[0] if v_row and v_row[0] is not None else 0.0

    if e.presupuesto > 0:
        ahorro_real_meta = max(0.0, round(presupuesto_total_acumulado - gasto_gasolina_real, 2))
    else:
        # Trayecto personal sin pago: se deduce el costo directo del trayecto del fondo acumulado
        ahorro_real_meta = max(0.0, round(ahorro_previo - costo_viaje, 2))

    cursor.execute("UPDATE vehiculos SET ahorro_acumulado = ? WHERE usuario = ?", (ahorro_real_meta, usuario))

    cursor.execute("""
        INSERT INTO bitacora_rutas (usuario, nombre_ruta, km_recorridos, costo_viaje, presupuesto, balance_neto, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario, e.nombre_ruta, e.km_recorridos, costo_viaje, e.presupuesto, balance_neto, f"{minutos_viaje} min", e.clima_registro, e.hora_registro, e.red_registro, e.trafico_registro, e.ubicacion_registro, e.alerta_operativa))

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
        "litros_restantes": max(0.0, litros_restantes),
        "km_totales_acumulados": km_totales_acumulados,
        "gasto_total_acumulado": gasto_total_acumulado,
        "presupuesto_total_acumulado": presupuesto_total_acumulado,
        "tiempo_total_acumulado_min": tiempo_total_acumulado_min,
        "hora_registro": e.hora_registro
    }

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
    cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (user.username, hashed_password))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = secrets.token_hex(32)
    active_sessions[token] = user.username
    return {"token": token}

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT marca, modelo, anio, km_actual, nombre_meta, monto_meta, ahorro_acumulado FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
