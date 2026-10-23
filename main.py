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
            modelo TEXT,
            km_actual REAL,
            ultimo_servicio REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS combustible (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            km_recorridos REAL,
            litros_cargados REAL,
            rendimiento REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mantenimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            tipo_servicio TEXT,
            km_realizado REAL
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
    modelo: str
    km_actual: float

class CombustibleRegistro(BaseModel):
    km_recorridos: float
    litros_cargados: float

class MantenimientoRegistro(BaseModel):
    tipo_servicio: str

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
        <title>DEMONION MVP - Sistema Completo</title>
        <style>
            body { font-family: sans-serif; margin: 15px; background: #f4f4f9; color: #333; }
            .card { background: white; padding: 15px; margin-bottom: 12px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            input, select, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
            button { background: #0284c7; color: white; border: none; font-weight: bold; cursor: pointer; }
            .btn-voice { background: #8b5cf6; margin-bottom: 8px; }
            .btn-share { background: #25d366; font-weight: bold; margin-top: 10px; }
            .btn-backup { background: #475569; font-weight: bold; margin-top: 5px; }
            #app, #auth { display: none; }
            .flex-row { display: flex; gap: 5px; }
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
            
            <h4>1. Control de Combustible (Rango Metrológico)</h4>
            <div class="flex-row">
                <input type="number" id="km_rec" placeholder="Km Recorridos en el ciclo">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('km_rec')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="litros" placeholder="Litros Cargados">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('litros')">🎤 Voz</button>
            </div>
            <button onclick="registrarCombustible()" style="background:#059669;">Evaluar Consumo de Gasolina</button>
            <div id="diagnostico-combustible"></div>

            <hr>
            <h4>2. Registro de Mantenimiento Preventivo</h4>
            <select id="tipo_serv">
                <option value="Cambio de Aceite">Cambio de Aceite</option>
                <option value="Kit de Arrastre / Cadena">Kit de Arrastre / Cadena</option>
                <option value="Pastillas de Freno">Pastillas de Freno</option>
                <option value="Afinacion General">Afinación General</option>
            </select>
            <button onclick="registrarMantenimiento()" style="background:#d97706;">Registrar Servicio Realizado</button>
            <div id="diagnostico-mantenimiento" style="margin-top: 8px; font-weight: bold;"></div>

            <hr>
            <h4>3. Registrar Kilometraje (Desgaste Dinámico)</h4>
            <div class="flex-row">
                <input type="text" id="modelo" placeholder="Modelo (Ej. Pulsar NS 200)">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('modelo')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="km" placeholder="Kilometraje Actual">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('km')">🎤 Voz</button>
            </div>
            <button onclick="actualizarKm()">Actualizar y Evaluar Desgaste</button>
            <div id="diagnostico"></div>

            <hr>
            <button class="btn-share" onclick="compartirReporte()">📲 Compartir Reporte (WhatsApp / Local)</button>
            <button class="btn-backup" onclick="descargarRespaldo()">💾 Descargar Copia de Seguridad (DB)</button>
            
            <hr>
            <button onclick="logout()" style="background:#6b7280; margin-top: 10px;">Cerrar Sesión</button>
        </div>

        <script>
            const API = window.location.origin;
            let authToken = "";
            let ultimoDiagnostico = "";

            function limpiarInterfaz() {
                document.getElementById("modelo").value = "";
                document.getElementById("km").value = "";
                document.getElementById("km_rec").value = "";
                document.getElementById("litros").value = "";
                document.getElementById("diagnostico").innerHTML = "";
                document.getElementById("diagnostico-combustible").innerHTML = "";
                document.getElementById("diagnostico-mantenimiento").innerHTML = "";
                ultimoDiagnostico = "";
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
                    if (inputId === 'km' || inputId === 'km_rec' || inputId === 'litros') {
                        texto = texto.replace(/[^0-9.]/g, '');
                    }
                    document.getElementById(inputId).value = texto;
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
                const textoReporte = "*REPORTE OPERATIVO DEMONION MVP*\\n" + ultimoDiagnostico;

                if (navigator.share) {
                    navigator.share({
                        title: 'Reporte Operativo',
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
                limpiarInterfaz();
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
                    







