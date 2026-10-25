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
            ultimo_servicio REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tanque_usuario (
            usuario TEXT PRIMARY KEY,
            litros_tanque REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estadisticas_rutas (
            usuario TEXT PRIMARY KEY,
            km_totales_acumulados REAL DEFAULT 0.0,
            gasto_total_acumulado REAL DEFAULT 0.0,
            tiempo_total_acumulado_min REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_rutas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            nombre_ruta TEXT,
            km_recorridos REAL,
            costo_viaje REAL,
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

class CargarCombustible(BaseModel):
    litros_cargados: float

class EvaluarRuta(BaseModel):
    nombre_ruta: str = "Ruta General"
    km_recorridos: float
    precio_gasolina: float
    clima_registro: str = "N/D"
    hora_registro: str = "N/D"
    red_registro: str = "N/D"
    trafico_registro: str = "N/D"
    ubicacion_registro: str = "N/D"
    alerta_operativa: str = "N/D"

class RegistrarMantenimiento(BaseModel):
    componente: str

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
            h4 { color: #e2e8f0; font-size: 14px; font-weight: 600; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; margin: 15px 0 10px 0; }
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
            .btn-mantenimiento { background: #d97706; font-weight: 600; margin-top: 8px; }
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
            
            .progress-container { background: #1e293b; border-radius: 6px; height: 10px; width: 100%; margin: 6px 0; overflow: hidden; border: 1px solid var(--border-color); }
            .progress-bar { height: 100%; width: 100%; background: var(--accent-green); transition: width 0.3s ease; }
            
            .bitacora-box { background: #0b1120; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 10px; font-size: 11px; color: var(--text-muted); }
            .panel-oficial { background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.3); padding: 12px; border-radius: 8px; margin-top: 8px; }
            .alerta-normativa { background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.3); padding: 12px; border-radius: 8px; font-size: 12px; color: #93c5fd; margin-top: 10px; }
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

        <div id="app" class="card">
            <h3>⚡ PANEL OPERATIVO [<span id="current-user" style="color:var(--accent-cyan)"></span>]</h3>
            <hr>
            
            <h4>1. Control de Combustible y Autonomía</h4>
            <div class="flex-row">
                <div class="input-voz-group">
                    <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados" oninput="simularCarga()">
                    <button type="button" class="btn-voice" onclick="escucharVoz('litros_carga')">🎤 Voz</button>
                </div>
            </div>
            
            <div class="flex-row" style="margin-top: 4px;">
                <button id="btn_cargar" class="btn-main-carga" onclick="cargarCombustible()">Registrar Carga y Acumular Tanque</button>
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
            <button id="btn_evaluar" style="background:#059669; margin-top:8px;" onclick="evaluarRuta()">Evaluar Costo, Ruta y Descontar (Oficial)</button>
            
            <div id="diagnostico-combustible" style="margin-top: 8px;"></div>
            
            <!-- Menú desplegable de viajes registrados con controles de ocultar/mostrar la consulta seleccionada -->
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

            <hr>
            <h4>2. Mantenimiento Preventivo y Checklist de Inspección</h4>
            
            <div id="contenedor-inspeccion">
                <div id="checklist-contenedor" class="checklist-box">
                    <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: 600; font-size: 12px; color: var(--accent-amber);">⚠️ Inspección preventiva: Confirme los 6 puntos críticos de seguridad.</p>
                    
                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-frenos', 'arrow-frenos')">
                            <span style="font-size:12px; font-weight:600;">🛑 1. Frenos / Suspensión</span>
                            <span id="arrow-frenos" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-frenos" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones Asociadas:</b> Pastillas de freno, líquido de frenos DOT 4, retenes de horquilla.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $350 - $900 MXN</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Pérdida de poder de frenado, distancia de frenado prolongada, daño a discos y riesgo de colisión.</p>
                            <select id="anulador_frenos" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-cadena', 'arrow-cadena')">
                            <span style="font-size:12px; font-weight:600;">⛓ 2. Kit Arrastre / Piñones</span>
                            <span id="arrow-cadena" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-cadena" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones Asociadas:</b> Cadena de transmisión, sprocket (corona) y piñón de ataque.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $1,200 - $2,500 MXN</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Ruptura de cadena en marcha, bloqueo de rueda trasera o daño severo al cárter del motor.</p>
                            <select id="anulador_cadena" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-llantas', 'arrow-llantas')">
                            <span style="font-size:12px; font-weight:600;">🛞 3. Llantas / Presión</span>
                            <span id="arrow-llantas" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-llantas" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones Asociadas:</b> Neumáticos delantero y trasero, válvulas y parches/cámaras.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $800 - $2,200 MXN c/u</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Pérdida de tracción en curvas, deslizamiento en piso mojado, mayor consumo de combustible y pinchazos súbitos.</p>
                            <select id="anulador_llantas" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-luces', 'arrow-luces')">
                            <span style="font-size:12px; font-weight:600;">💡 4. Sistema Eléctrico / Intermitentes</span>
                            <span id="arrow-luces" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-luces" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones Asociadas:</b> Focos LED/halógenos, batería, fusibles y relay de direccionales.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $100 - $1,200 MXN</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Nula visibilidad nocturna, incapacidad de señalar giros (riesgo de atropellamiento) y fallo de arranque.</p>
                            <select id="anulador_luces" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-epp', 'arrow-epp')">
                            <span style="font-size:12px; font-weight:600;">🪖 5. Casco / Indumentaria (EPP)</span>
                            <span id="arrow-epp" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-epp" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones Asociadas:</b> Mica de repuesto, barboquejo, guantes con protección y chaleco.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $400 - $3,000 MXN</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Lesiones graves en caso de impacto cefálico, multas de tránsito y falta de visibilidad ante otros conductores.</p>
                            <select id="anulador_epp" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                    <div class="check-accordion-card">
                        <div class="check-accordion-header" onclick="toggleAcordeon('body-docs', 'arrow-docs')">
                            <span style="font-size:12px; font-weight:600;">📄 6. Licencia / Póliza Vigente</span>
                            <span id="arrow-docs" style="font-size:10px; font-weight:600;">▼</span>
                        </div>
                        <div id="body-docs" class="check-accordion-body">
                            <p style="margin:0 0 4px 0;"><b>Refacciones / Trámites Asociados:</b> Renovación de licencia de conducir tipo A/C, póliza de seguro anual.</p>
                            <p style="margin:0 0 4px 0;"><b>Costo Aprox:</b> $800 - $3,500 MXN</p>
                            <p style="margin:0 0 6px 0; color:var(--accent-red);"><b>Consecuencias de omisión:</b> Remisión de la motocicleta al corralón, multas elevadas y desprotección financiera ante accidentes viales.</p>
                            <select id="anulador_docs" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>

                </div>

                <div id="protocolo-normativo" class="alerta-normativa" style="display:none;">
                    <p style="margin:0 0 4px 0; font-weight:600; color:#60a5fa; font-size:12px;">🛡️ PROTOCOLO DE SEGURIDAD OPERATIVA Y NORMATIVA VIAL</p>
                    <p style="margin:0 0 4px 0;">Cumple estrictamente la reglamentación:</p>
                    <p style="margin:0 0 4px 0; font-size:11px;">• <b>Límites:</b> Máx 50 km/h secundarias, 80 km/h acceso controlado, 30 km/h escuelas.</p>
                    <p style="margin:0 0 4px 0; font-size:11px;">• <b>EPP:</b> Casco certificado (DOT/ECE) y chaleco reflejante nocturno.</p>
                    <p style="margin:0 0 6px 0; font-size:11px; color:#fca5a5;">• <b>Prohibiciones:</b> Cero invasión de carriles confinados o banquetas, prohibido conducir cansado o bajo efectos de alcohol.</p>
                    <button class="btn-leido" onclick="confirmarLeidoProtocolo()">✔ Entendido y Confirmado (Regresar)</button>
                </div>
            </div>

            <select id="tipo_serv" onchange="sincronizarVistaComponente()" style="margin-top: 10px;">
                <option value="Cambio de Aceite" data-ciclo="2500">Cambio de Aceite (Ciclo: 2,500 km)</option>
                <option value="Kit de Arrastre / Piñones" data-ciclo="15000">Kit de Arrastre / Piñones (Ciclo: 15,000 km)</option>
                <option value="Pastillas de Freno" data-ciclo="5000">Pastillas de Freno (Ciclo: 5,000 km)</option>
            </select>

            <div style="background: #0b1120; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 8px; margin-bottom: 10px;">
                <p style="margin: 0 0 6px 0; font-weight: 600; font-size: 12px; color: var(--text-muted);">📊 VIDA ÚTIL DEL COMPONENTE SELECCIONADO:</p>
                <div style="font-size: 12px; display: flex; justify-content: space-between;">
                    <span id="label-componente-activo" style="font-weight:600;">Cambio de Aceite</span>
                    <span id="porcentaje-vida" style="color:var(--accent-green); font-weight: 600;">100% Vida Restante</span>
                </div>
                <div class="progress-container">
                    <div id="barra-vida" class="progress-bar" style="width: 100%;"></div>
                </div>
                <div id="alerta-inversion" style="font-size: 11px; margin-top: 4px; font-weight: 600; color: var(--accent-green);">Estado óptimo. Sin gastos imprevistos próximos.</div>
                
                <button class="btn-mantenimiento" onclick="registrarMantenimientoRealizado()">🔧 Registrar Mantenimiento Realizado (Reiniciar al 100%)</button>
            </div>

            <hr>
            <h4>3. Telemetría Avanzada y Entorno Dinámico</h4>
            
            <div id="entorno-dispositivo" class="entorno-box">
                <span id="info-clima">🌤️ Clima: Cargando...</span>
                <span id="info-bateria">🔋 Batería: --%</span>
                <span id="info-horario">🕒 Hora: --:--</span>
                <span id="info-red">📶 Red: Analizando...</span>
                <span id="info-ubicacion" style="grid-column: span 2;">📍 Ubicación: Obteniendo GPS...</span>
            </div>

            <div class="telemetria-grid">
                <div class="telemetria-item">
                    <label>Marca</label>
                    <div class="input-voz-group">
                        <input type="text" id="marca" placeholder="Ej. Bajaj">
                        <button type="button" class="btn-voice" onclick="escucharVoz('marca')">🎤</button>
                    </div>
                </div>
                <div class="telemetria-item">
                    <label>Modelo</label>
                    <div class="input-voz-group">
                        <input type="text" id="modelo" placeholder="Ej. Pulsar NS 200">
                        <button type="button" class="btn-voice" onclick="escucharVoz('modelo')">🎤</button>
                    </div>
                </div>
                <div class="telemetria-item">
                    <label>Año</label>
                    <div class="input-voz-group">
                        <input type="text" id="anio" placeholder="Ej. 2024">
                        <button type="button" class="btn-voice" onclick="escucharVoz('anio')">🎤</button>
                    </div>
                </div>
                <div class="telemetria-item">
                    <label>Odómetro (km)</label>
                    <div class="input-voz-group">
                        <input type="number" id="km" placeholder="Km Actual">
                        <button type="button" class="btn-voice" onclick="escucharVoz('km')">🎤</button>
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
            
            <hr>
            <button onclick="logout()" style="background:#475569; margin-top: 10px;">Cerrar Sesión</button>
        </div>

        <script>
            const API = window.location.origin;
            let authToken = "";
            let ultimoDiagnostico = "";
            let sistemaBloqueado = false;
            let litrosActualesTanque = 0.0;
            let kmTotalesAcumuladosGlobal = 0.0;
            let gastoTotalAcumuladoGlobal = 0.0;
            let tiempoTotalAcumuladoGlobalMin = 0.0;
            let protocoloConfirmadoLeido = false;
            let kmComponentes = {
                "Cambio de Aceite": 0,
                "Kit de Arrastre / Piñones": 0,
                "Pastillas de Freno": 0
            };
            let bitacoraLocal = [];
            let viajesJornadaList = [];
            let consultaViajeOculta = false;

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
                        let lat = position.coords.latitude;
                        let lon = position.coords.longitude;
                        
                        fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14`, {
                            headers: { 'Accept-Language': 'es' }
                        })
                        .then(res => res.json())
                        .then(data => {
                            let direccion = data && data.address ? (data.address.city || data.address.town || data.address.municipality || data.address.suburb || "Zona Aproximada") : "Ubicación GPS";
                            document.getElementById("info-ubicacion").innerText = `📍 Ubicación: ${direccion}`;
                        })
                        .catch(() => {
                            document.getElementById("info-ubicacion").innerText = `📍 Coordenadas: ${lat.toFixed(2)}, ${lon.toFixed(2)}`;
                        });

                        fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`)
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
                    elemRed.innerText = "📶 Red: Offline";
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
                    alertas.push("🛣️ [Ruta Larga detectada: Mayor desgaste general]");
                } else {
                    alertas.push("📍 [Trayecto corto / Estándar]");
                }

                if (minutosViaje > 120 || tiempoTotalAcumuladoGlobalMin > 120) {
                    alertas.push("🚨 [Jornada Excesiva / Fatiga Operativa: Se recomienda descanso]");
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
                    htmlContent += `
                        <div style="background: #0b1120; border: 1px solid var(--border-color); padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.2s;" onclick="seleccionarViajeAcordeon(${index})">
                            <div style="display: flex; justify-content: space-between; font-weight: 600; color: #38bdf8; font-size: 11px;">
                                <span>📌 ${viaje.nombre_ruta}</span>
                                <span style="color: var(--accent-green);">$${viaje.costo_viaje} MXN</span>
                            </div>
                            <div style="font-size: 10px; color: var(--text-muted); margin-top: 2px;">
                                🕒 ${viaje.hora_registro} | 🛣️ ${viaje.km_recorridos} km | ⏱️ ${viaje.tiempo_viaje}
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
                panelOficial.innerHTML = `
                    <p style="color: var(--accent-cyan); font-weight: 600; margin: 0 0 5px 0;">🔍 [Consulta de Viaje Seleccionado: ${viaje.nombre_ruta}]:</p>
                    <p style="margin:2px 0;"><b>${viaje.ubicacion_registro || 'N/D'}</b></p>
                    <p style="margin:2px 0;"><b>Entorno:</b> ${viaje.hora_registro} | ${viaje.clima_registro}</p>
                    <p style="margin:2px 0;"><b>Señal / Tráfico:</b> ${viaje.red_registro} | Tráfico: ${viaje.trafico_registro}</p>
                    <p style="margin:2px 0;"><b>Consumo / Costo:</b> ${viaje.litros_consumidos} L (<b>$${viaje.costo_viaje} MXN</b>)</p>
                    <p style="margin:2px 0;"><b>⏱️ Tiempo del Viaje:</b> ~${viaje.tiempo_viaje}</p>
                    <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${viaje.alerta_operativa || 'N/D'}</p>
                `;

                if (!consultaViajeOculta) {
                    panelOficial.style.display = "block";
                }
            }

            function limpiarVariablesLocales() {
                litrosActualesTanque = 0.0;
                kmTotalesAcumuladosGlobal = 0.0;
                gastoTotalAcumuladoGlobal = 0.0;
                tiempoTotalAcumuladoGlobalMin = 0.0;
                protocoloConfirmadoLeido = false;
                kmComponentes = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
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

                sistemaBloqueado = bloquear;
                if(div) div.innerHTML = mensaje;

                if (bloquear) {
                    if(btnCargar) btnCargar.classList.add("bloqueado");
                    if(btnReset) btnReset.classList.add("bloqueado");
                    if(btnEvaluar) btnEvaluar.classList.add("bloqueado");
                } else {
                    if(btnCargar) btnCargar.classList.remove("bloqueado");
                    if(btnReset) btnReset.classList.remove("bloqueado");
                    if(btnEvaluar) btnEvaluar.classList.remove("bloqueado");
                }
            }

            function verificarJornadaYDiagnostico() {
                let checklistElem = document.getElementById("checklist-contenedor");
                let protocoloElem = document.getElementById("protocolo-normativo");

                if (!protocoloConfirmadoLeido) {
                    let f = document.getElementById("anulador_frenos").value;
                    let c = document.getElementById("anulador_cadena").value;
                    let ll = document.getElementById("anulador_llantas").value;
                    let l = document.getElementById("anulador_luces").value;
                    let epp = document.getElementById("anulador_epp").value;
                    let docs = document.getElementById("anulador_docs").value;

                    if (f === "revision" || c === "revision" || ll === "revision" || l === "revision" || epp === "revision" || docs === "revision") {
                        bloquearSistema(true, "⚠️ Verificación de seguridad: Complete o confirme todos los puntos en 'Operativo (OK)'.");
                        if(checklistElem) checklistElem.style.display = "block";
                        if(protocoloElem) protocoloElem.style.display = "none";
                        ultimoDiagnostico = "Estado Operativo: Bloqueado por Seguridad Preventiva";
                    } else {
                        bloquearSistema(false, "✔ Inspección aprobada con éxito.");
                        if(checklistElem) checklistElem.style.display = "none";
                        if(protocoloElem) protocoloElem.style.display = "block";
                        ultimoDiagnostico = "Estado Operativo: Protocolo Vial Activo y Habilitado";
                    }
                } else {
                    if(checklistElem) checklistElem.style.display = "block";
                    if(protocoloElem) protocoloElem.style.display = "none";
                    bloquearSistema(false, "✔ Puntos de inspección confirmados y operativos.");
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
                let rendimientoEstandar = 30.0;
                let autonomiaProyectada = round(totalSimulado * rendimientoEstandar, 1);

                divDiag.innerHTML = `
                    <p style="font-size:11px; color:var(--text-muted); margin:0 0 4px 0;"><i>🔍 [Vista previa / Simulación de Carga]</i></p>
                    <p style="margin:2px 0;"><b>Carga Actual en Tanque:</b> ${litrosActualesTanque} L</p>
                    <p style="margin:2px 0;"><b>Carga Post-Carga (Total):</b> ${totalSimulado} L (${litrosActualesTanque} L actuales + ${litrosEntrada} L nuevos)</p>
                    <p style="margin:2px 0;"><b>Autonomía Estimada:</b> ${autonomiaProyectada} km</p>
                `;
            }

            function simularRuta() {
                let kmRutaVal = parseFloat(document.getElementById("km_ruta").value);
                let precioGasVal = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let divDiag = document.getElementById("diagnostico-combustible");

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
                let costoByKm = round(costoViaje / kmRutaVal, 2);
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
                let redActual = document.getElementById("info-red").innerText.replace("📶 Red: ", "");
                let ubicacionActual = document.getElementById("info-ubicacion").innerText.replace("📍 ", "");
                let alertasSimuladas = evaluarAlertasOperativas(kmRutaVal, minutosViaje, litrosConsumidos);

                divDiag.innerHTML = `
                    <p style="font-size:11px; color:var(--text-muted); margin:0 0 4px 0;"><i>🔍 [Vista previa / Indicadores de Entorno y Ruta]</i></p>
                    <p style="margin:2px 0;"><b>${ubicacionActual}</b></p>
                    <p style="margin:2px 0;"><b>Entorno Actual:</b> ${horaActual} | ${climaActual}</p>
                    <p style="margin:2px 0;"><b>Señal / Tráfico:</b> ${redActual} | Tráfico: ${traficoInfo.nivel}</p>
                    <p style="margin:2px 0;"><b>Consumo / Costo:</b> ${litrosConsumidos} L (<b>$${costoViaje} MXN</b>)</p>
                    <p style="margin:2px 0;"><b>⏱️ Tiempo Estimado:</b> ~${tiempoEstimadoSim}</p>
                    <p style="margin:2px 0;"><b>Autonomía Restante:</b> ${autonomiaRestanteKm} km (${litrosRestantesSimulados} L)</p>
                    <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${alertasSimuladas}</p>
                `;
            }

            function round(value, decimals) {
                return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
            }

            function sincronizarVistaComponente() {
                let selectElem = document.getElementById("tipo_serv");
                if(!selectElem) return;
                let tipoServicio = selectElem.value;
                let cicloMax = parseFloat(selectElem.options[selectElem.selectedIndex].getAttribute("data-ciclo"));
                
                document.getElementById("label-componente-activo").innerText = tipoServicio;

                let kmAcumulados = kmComponentes[tipoServicio] || 0;
                let vidaRestante = Math.max(0, Math.min(100, 100 - (kmAcumulados / cicloMax) * 100));
                
                let barra = document.getElementById("barra-vida");
                let txtVida = document.getElementById("porcentaje-vida");
                let alertaInv = document.getElementById("alerta-inversion");

                if(barra) barra.style.width = vidaRestante + "%";
                if(txtVida) txtVida.innerText = Math.round(vidaRestante) + "% Vida Restante (" + kmAcumulados + " / " + cicloMax + " km)";

                if (vidaRestante > 40) {
                    if(barra) barra.style.background = "var(--accent-green)";
                    if(alertaInv) { alertaInv.style.color = "var(--accent-green)"; alertaInv.innerText = `Estado óptimo para ${tipoServicio}. Sin gastos imprevistos.`; }
                } else if (vidaRestante > 15) {
                    if(barra) barra.style.background = "var(--accent-amber)";
                    if(alertaInv) { alertaInv.style.color = "var(--accent-amber)"; alertaInv.innerText = `⚠️ Precaución: El componente ${tipoServicio} se acerca al límite.`; }
                } else {
                    if(barra) barra.style.background = "var(--accent-red)";
                    if(alertaInv) { alertaInv.style.color = "var(--accent-red)"; alertaInv.innerText = `🚨 Alerta: Es tiempo obligatorio de cambiar ${tipoServicio}.`; }
                }
            }

            async function registrarMantenimientoRealizado() {
                let selectElem = document.getElementById("tipo_serv");
                let tipoServicio = selectElem.value;
                
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
                    sincronizarVistaComponente();
                    
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
                    if (inputId === 'km' || inputId === 'litros_carga' || inputId === 'km_ruta' || inputId === 'precio_gas' || inputId === 'anio') {
                        texto = texto.replace(/[^0-9.]/g, '');
                    }
                    document.getElementById(inputId).value = texto;
                    if (inputId === 'litros_carga') {
                        simularCarga();
                    } else if (inputId === 'km_ruta' || inputId === 'precio_gas') {
                        simularRuta();
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
                
                let res = await fetch(API + "/vehiculo", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ marca, modelo, anio: anio.toString(), km_actual })
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

                    document.getElementById("diagnostico").innerHTML = `
                        <div class="diagnostico-container">
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

                        </div>
                    `;
                    ultimoDiagnostico = `Unidad: ${data.marca} ${data.modelo} ${data.anio} | Valor Est: $${valorMonetarioEstimado} MXN | Prox Mantenimiento: ${mantenimientoProximo}`;
                }
            }

            async function cargarCombustible() {
                let litros_cargados = parseFloat(document.getElementById("litros_carga").value);
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
                    body: JSON.stringify({ litros_cargados })
                });
                let data = await res.json();
                if(res.ok) {
                    litrosActualesTanque = data.litros_tanque;
                    let rendimientoEstandar = 30.0;
                    let autonomiaTanque = round(litrosActualesTanque * rendimientoEstandar, 1);

                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600; margin:4px 0;">✔ Carga Registrada y Tanque Acumulado:</p>
                        <p style="margin:2px 0;"><b>Litros Totales en Tanque:</b> ${litrosActualesTanque} L</p>
                        <p style="margin:2px 0;"><b>Autonomía Disponible:</b> ${autonomiaTanque} km</p>
                    `;
                    document.getElementById("litros_carga").value = "";
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
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600;">✔ Acción realizada con éxito.</p>
                    `;
                    verificarJornadaYDiagnostico();
                } else {
                    alert("Error al reiniciar.");
                }
            }

            async function evaluarRuta() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada: Debe confirmar el checklist de seguridad obligatorio.");
                    return;
                }
                let nombre_ruta = document.getElementById("nombre_ruta").value.trim() || "Ruta General";
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                let precio_gasolina = parseFloat(document.getElementById("precio_gas").value);
                
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
                    body: JSON.stringify({ nombre_ruta, km_recorridos, precio_gasolina, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa })
                });
                let data = await res.json();
                if(res.ok) {
                    litrosActualesTanque = data.litros_restantes;
                    kmTotalesAcumuladosGlobal = data.km_totales_acumulados;
                    gastoTotalAcumuladoGlobal = data.gasto_total_acumulado;
                    tiempoTotalAcumuladoGlobalMin = data.tiempo_total_acumulado_min;

                    for (let comp in kmComponentes) {
                        kmComponentes[comp] += km_recorridos;
                    }
                    sincronizarVistaComponente();
                    verificarJornadaYDiagnostico();

                    viajesJornadaList.unshift({
                        nombre_ruta: data.nombre_ruta,
                        costo_viaje: data.costo_viaje,
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

                    panelOficial.innerHTML = `
                        <p style="color: var(--accent-green); font-weight: 600; margin: 0 0 5px 0;">✔ Rendimiento Registrado [${data.nombre_ruta}] <span style="font-size:10px; color:var(--text-muted); font-weight:normal;">(Últimos registros del sistema de ruta)</span>:</p>
                        <p style="margin:2px 0;"><b>${data.ubicacion_registro}</b></p>
                        <p style="margin:2px 0;"><b>Entorno:</b> ${data.hora_registro} | ${data.clima_registro}</p>
                        <p style="margin:2px 0;"><b>Señal / Tráfico:</b> ${data.red_registro} | Tráfico: ${data.trafico_registro}</p>
                        <p style="margin:2px 0;"><b>Consumo / Costo:</b> ${data.litros_consumidos} L (<b>$${data.costo_viaje} MXN</b>)</p>
                        <p style="margin:2px 0;"><b>⏱️ Tiempo del Viaje:</b> ~${data.tiempo_viaje}</p>
                        <p style="margin:2px 0;"><b>Autonomía Restante:</b> ${data.autonomia_restante_km} km (${data.litros_restantes} L)</p>
                        <p style="margin:2px 0; color:var(--accent-amber);"><b>🛡️ Alertas Operativas:</b> ${data.alerta_operativa}</p>
                        <hr style="border: 0; border-top: 1px dashed rgba(16, 185, 129, 0.3); margin: 6px 0;">
                        <p style="color: #60a5fa; font-weight: 600; margin:2px 0;">📊 Acumulados Globales:</p>
                        <p style="margin:2px 0;"><b>Km Totales:</b> ${kmTotalesAcumuladosGlobal} km | Gasto: $${gastoTotalAcumuladoGlobal} MXN</p>
                    `;
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
                    }
                }
                
                let resTanque = await fetch(API + "/tanque/estado", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resTanque.ok) {
                    let dataTanque = await resTanque.json();
                    litrosActualesTanque = dataTanque.litros_tanque || 0.0;
                }

                let resEstadisticas = await fetch(API + "/estadisticas/rutas", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resEstadisticas.ok) {
                    let dataEst = await resEstadisticas.json();
                    kmTotalesAcumuladosGlobal = dataEst.km_totales_acumulados || 0.0;
                    gastoTotalAcumuladoGlobal = dataEst.gasto_total_acumulado || 0.0;
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

                        bitacoraLocal = dataBit.map(b => `✔ [${b.nombre_ruta}] ${b.ubicacion_registro || ''} | ${b.km_recorridos}km | $${b.costo_viaje} MXN | ${b.alerta_operativa || ''}`);
                        document.getElementById("lista-bitacora").innerHTML = bitacoraLocal.join("<br>");
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

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
    cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (user.username, hashed_password))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = secrets.token_hex(32)
    active_sessions[token] = user.username
    return {"token": token}

@app.get("/tanque/estado")
def obtener_estado_tanque(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return {"litros_tanque": row[0] if row and row[0] is not None else 0.0}

@app.get("/estadisticas/rutas")
def obtener_estadisticas_rutas(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"km_totales_acumulados": 0.0, "gasto_total_acumulado": 0.0, "tiempo_total_acumulado_min": 0.0}

@app.post("/combustible/reiniciar-telemetria")
def reiniciar_tanque_y_telemetria(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tanque_usuario SET litros_tanque = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE estadisticas_rutas SET km_totales_acumulados = 0.0, gasto_total_acumulado = 0.0, tiempo_total_acumulado_min = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("DELETE FROM bitacora_rutas WHERE usuario = ?", (usuario,))
    conn.commit()
    conn.close()
    return {"mensaje": "Tanque y contadores de telemetría reiniciados con éxito."}

@app.post("/vehiculo")
def gestionar_vehiculo(v: VehiculoUpdate, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, km_actual, ultimo_servicio FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    
    if row:
        vehiculo_id, km_previo, ultimo_servicio = row
        if ultimo_servicio is None:
            ultimo_servicio = 0.0
        cursor.execute("UPDATE vehiculos SET marca = ?, modelo = ?, anio = ?, km_actual = ? WHERE id = ?", 
                       (v.marca, v.modelo, v.anio, v.km_actual, vehiculo_id))
    else:
        ultimo_servicio = v.km_actual
        cursor.execute("INSERT INTO vehiculos (usuario, marca, modelo, anio, km_actual, ultimo_servicio) VALUES (?, ?, ?, ?, ?, ?)", 
                       (usuario, v.marca, v.modelo, v.anio, v.km_actual, ultimo_servicio))
    
    conn.commit()
    conn.close()
    
    km_desde_servicio = max(0.0, v.km_actual - (ultimo_servicio if ultimo_servicio else 0.0))

    return {
        "marca": v.marca,
        "modelo": v.modelo,
        "anio": v.anio,
        "km_actual": v.km_actual,
        "km_desde_servicio": km_desde_servicio,
        "alerta_color": "green",
        "mensaje_alerta": "Odómetro sincronizado y ficha técnica actualizada."
    }

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT marca, modelo, anio, km_actual, ultimo_servicio FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        data = dict(row)
        data["km_desde_servicio"] = max(0.0, data["km_actual"] - (data["ultimo_servicio"] if data["ultimo_servicio"] else 0.0))
        return data
    return {}

@app.get("/mantenimiento/estado")
def obtener_estado_mantenimiento(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT componente, km_acumulados FROM mantenimiento_componentes WHERE usuario = ?", (usuario,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/bitacora")
def obtener_bitacora(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_ruta, km_recorridos, costo_viaje, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa FROM bitacora_rutas WHERE usuario = ? ORDER BY id DESC LIMIT 5", (usuario,))
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
        INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados) VALUES (?, ?, 0.0)
        ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = 0.0
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
    
    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_anteriores = row[0] if row and row[0] is not None else 0.0
    
    nuevo_total = round(litros_anteriores + c.litros_cargados, 2)
    
    cursor.execute("""
        INSERT INTO tanque_usuario (usuario, litros_tanque) VALUES (?, ?)
        ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?
    """, (usuario, nuevo_total, nuevo_total))
    conn.commit()
    conn.close()
    return {"litros_tanque": nuevo_total}

@app.post("/combustible/evaluar")
def evaluar_ruta(e: EvaluarRuta, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if e.km_recorridos <= 0:
        raise HTTPException(status_code=400, detail="Los kilómetros deben ser mayores a 0")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for comp in ["Cambio de Aceite", "Kit de Arrastre / Piñones", "Pastillas de Freno"]:
        cursor.execute("""
            INSERT INTO mantenimiento_componentes (usuario, componente, km_acumulados) 
            VALUES (?, ?, ?)
            ON CONFLICT(usuario, componente) DO UPDATE SET km_acumulados = km_acumulados + ?
        """, (usuario, comp, e.km_recorridos, e.km_recorridos))

    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    litros_tanque = row[0] if row and row[0] is not None else 0.0

    rendimiento_estandar = 30.0
    litros_consumidos = round(e.km_recorridos / rendimiento_estandar, 2)
    costo_viaje = round(litros_consumidos * e.precio_gasolina, 2)
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
        INSERT INTO estadisticas_rutas (usuario, km_totales_acumulados, gasto_total_acumulado, tiempo_total_acumulado_min) 
        VALUES (?, ?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET 
            km_totales_acumulados = km_totales_acumulados + ?,
            gasto_total_acumulado = gasto_total_acumulado + ?,
            tiempo_total_acumulado_min = tiempo_total_acumulado_min + ?
    """, (usuario, e.km_recorridos, costo_viaje, minutos_viaje, e.km_recorridos, costo_viaje, minutos_viaje))

    cursor.execute("""
        INSERT INTO bitacora_rutas (usuario, nombre_ruta, km_recorridos, costo_viaje, tiempo_viaje, clima_registro, hora_registro, red_registro, trafico_registro, ubicacion_registro, alerta_operativa) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario, e.nombre_ruta, e.km_recorridos, costo_viaje, tiempo_viaje_str, e.clima_registro, e.hora_registro, e.red_registro, e.trafico_registro, e.ubicacion_registro, e.alerta_operativa))

    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado, tiempo_total_acumulado_min FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    km_totales_acumulados = est_row[0]
    gasto_total_acumulado = est_row[1]
    tiempo_total_acumulado_min = est_row[2]

    cursor.execute("""
        INSERT INTO tanque_usuario (usuario, litros_tanque) VALUES (?, ?)
        ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?
    """, (usuario, max(0.0, litros_restantes), max(0.0, litros_restantes)))

    cursor.execute("INSERT INTO combustible (usuario, km_recorridos, litros_consumidos, rendimiento) VALUES (?, ?, ?, ?)",
                   (usuario, e.km_recorridos, litros_consumidos, rendimiento_estandar))
    conn.commit()
    conn.close()

    return {
        "nombre_ruta": e.nombre_ruta,
        "litros_consumidos": litros_consumidos,
        "costo_viaje": costo_viaje,
        "costo_por_km": costo_por_km,
        "tiempo_viaje": tiempo_viaje_str,
        "autonomia_restante_km": autonomia_restante_km,
        "litros_restantes": max(0.0, litros_restantes),
        "km_totales_acumulados": km_totales_acumulados,
        "gasto_total_acumulado": gasto_total_acumulado,
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
