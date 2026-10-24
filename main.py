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
            gasto_total_acumulado REAL DEFAULT 0.0
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
    km_recorridos: float
    precio_gasolina: float

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
        <title>DEMONION MVP - Telemetría Pro</title>
        <style>
            body { font-family: sans-serif; margin: 15px; background: #f4f4f9; color: #333; }
            .card { background: white; padding: 15px; margin-bottom: 12px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            input, select, button { padding: 8px; margin: 3px 0; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; font-size: 13px; }
            button { background: #0284c7; color: white; border: none; font-weight: bold; cursor: pointer; }
            .btn-voice { background: #8b5cf6; width: auto; padding: 6px 10px; font-size: 11px; margin: 0; }
            .btn-share { background: #25d366; font-weight: bold; margin-top: 10px; }
            .btn-backup { background: #475569; font-weight: bold; margin-top: 5px; }
            .btn-mantenimiento { background: #d97706; font-weight: bold; margin-top: 6px; }
            .btn-reset-tanque { background: #e11d48; font-weight: bold; font-size: 12px; padding: 8px; width: 30%; }
            .btn-main-carga { width: 68%; }
            .btn-leido { background: #16a34a; font-weight: bold; margin-top: 10px; }
            #app, #auth { display: none; }
            .flex-row { display: flex; gap: 5px; align-items: center; }
            .telemetria-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-bottom: 8px; }
            .telemetria-item { display: flex; flex-direction: column; gap: 2px; }
            .telemetria-item label { font-size: 11px; font-weight: bold; color: #475569; }
            .input-voz-group { display: flex; gap: 4px; align-items: center; }
            .entorno-box { background: #eff6ff; border: 1px solid #bfdbfe; padding: 8px; border-radius: 6px; font-size: 11px; color: #1e3a8a; margin-bottom: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
            
            /* Tarjetas de Diagnóstico Organizadas */
            .diagnostico-container { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
            .diag-card { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; display: flex; align-items: flex-start; gap: 8px; }
            .diag-icon { font-size: 18px; line-height: 1; }
            .diag-content { display: flex; flex-direction: column; gap: 2px; width: 100%; font-size: 12px; }
            .diag-title { font-weight: bold; color: #0f172a; font-size: 13px; }
            
            .checklist-box { background: #fffbeb; padding: 12px; border-radius: 6px; border: 1px solid #fcd34d; margin-top: 10px; margin-bottom: 10px; }
            .checklist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
            .check-item { background: #fff; padding: 8px; border-radius: 4px; border: 1px solid #e2e8f0; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
            .check-item select { padding: 5px; font-size: 12px; margin: 0; }
            .bloqueado { background: #94a3b8 !important; cursor: not-allowed !important; }
            .progress-container { background: #e2e8f0; border-radius: 4px; height: 10px; width: 100%; margin: 5px 0; overflow: hidden; }
            .progress-bar { height: 100%; width: 100%; background: #22c55e; transition: width 0.3s ease; }
            .bitacora-box { background: #f1f5f9; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 10px; font-size: 12px; color: #334155; }
            .panel-oficial { background: #f0fdf4; border: 1px solid #bbf7d0; padding: 10px; border-radius: 6px; margin-top: 8px; }
            .alerta-normativa { background: #eff6ff; border: 1px solid #2563eb; padding: 12px; border-radius: 6px; font-size: 12px; color: #1e3a8a; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div id="auth" class="card" style="display:block;">
            <h3>Acceso DEMONION MVP</h3>
            <input type="text" id="user" placeholder="Usuario">
            <input type="password" id="pass" placeholder="Contraseña">
            <button onclick="login()">Iniciar Sesión</button>
            <button onclick="register()" style="background:#10b981;">Registrarse</button>
        </div>

        <div id="app" class="card">
            <h3>Panel Operativo (<span id="current-user"></span>)</h3>
            <hr>
            
            <h4>1. Control de Combustible y Autonomía</h4>
            <div class="flex-row">
                <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados" oninput="simularCarga()">
                <button type="button" class="btn-voice" onclick="escucharVoz('litros_carga')">🎤 Voz</button>
            </div>
            
            <div class="flex-row">
                <button id="btn_cargar" class="btn-main-carga" onclick="cargarCombustible()">Registrar Carga y Acumular Tanque</button>
                <button id="btn_reset" class="btn-reset-tanque" onclick="reiniciarTanqueYTelemetria()">🔄 Reiniciar</button>
            </div>

            <div class="flex-row" style="margin-top: 10px;">
                <input type="number" id="km_ruta" placeholder="Km a Recorrer (Nueva Ruta)" oninput="simularRuta()">
                <button type="button" class="btn-voice" onclick="escucharVoz('km_ruta')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="precio_gas" placeholder="Precio Gasolina ($ / Litro)" value="24.0" oninput="simularRuta()">
                <button type="button" class="btn-voice" onclick="escucharVoz('precio_gas')">🎤 Voz</button>
            </div>
            <button id="btn_evaluar" onclick="evaluarRuta()">Evaluar Costo, Ruta y Descontar (Oficial)</button>
            
            <div id="diagnostico-combustible" style="margin-top: 8px;"></div>
            <div id="diagnostico-oficial" class="panel-oficial" style="display:none;"></div>

            <hr>
            <h4>2. Mantenimiento Preventivo y Checklist de Inspección</h4>
            
            <div id="contenedor-inspeccion">
                <div id="checklist-contenedor" class="checklist-box">
                    <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: bold; font-size: 13px; color: #ea580c;">⚠️ Inspección preventiva: Confirme los 6 puntos críticos de seguridad.</p>
                    <div class="checklist-grid">
                        <div class="check-item">
                            <span>🛑 Frenos / Suspensión</span>
                            <select id="anulador_frenos" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                        <div class="check-item">
                            <span>⛓ Kit Arrastre / Piñones</span>
                            <select id="anulador_cadena" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                        <div class="check-item">
                            <span>🛞 Llantas / Presión</span>
                            <select id="anulador_llantas" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                        <div class="check-item">
                            <span>💡 Sistema Eléctrico / Intermitentes</span>
                            <select id="anulador_luces" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                        <div class="check-item">
                            <span>🪖 Casco / Indumentaria (EPP)</span>
                            <select id="anulador_epp" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                        <div class="check-item">
                            <span>📄 Licencia / Póliza Vigente</span>
                            <select id="anulador_docs" onchange="verificarAnuladores()">
                                <option value="revision" selected>Requiere Revisión</option>
                                <option value="ok">Operativo (OK)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div id="protocolo-normativo" class="alerta-normativa" style="display:none;">
                    <p style="margin:0 0 4px 0; font-weight:bold; color:#1e40af; font-size:13px;">🛡️ PROTOCOLO DE SEGURIDAD OPERATIVA Y NORMATIVA VIAL</p>
                    <p style="margin:0 0 4px 0;">Has confirmado los 6 puntos críticos de inspección. Cumple estrictamente la reglamentación oficial:</p>
                    <ul style="margin: 4px 0 8px 15px; padding: 0;">
                        <li><b>Límites de Velocidad:</b> Máximo <b>50 km/h</b> en secundarias y <b>80 km/h</b> en acceso controlado. <b>30 km/h</b> en escuelas.</li>
                        <li><b>Equipo de Protección (EPP):</b> Casco certificado (DOT / ECE) y chaleco reflejante nocturno.</li>
                        <li><b>Cero Invasión:</b> Prohibido circular en banquetas, ciclovías o carriles confinados.</li>
                    </ul>
                    <button class="btn-leido" onclick="confirmarLeidoProtocolo()">✔ Entendido y Confirmado (Regresar)</button>
                </div>
            </div>

            <select id="tipo_serv" onchange="sincronizarVistaComponente()" style="margin-top: 10px;">
                <option value="Cambio de Aceite" data-ciclo="2500">Cambio de Aceite (Ciclo: 2,
