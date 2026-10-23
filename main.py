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
            
            <h4>1. Registrar Kilometraje (Desgaste Dinámico)</h4>
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
            <h4>3. Control de Combustible (Rango Metrológico)</h4>
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
                    document.getElementById("auth").style.display = "none";
                    document.getElementById("app").style.display = "block";
                    cargarEstadoVehiculo();
                } else {
                    alert("Credenciales inválidas");
                }
            }

            function logout() {
                authToken = "";
                limpiarInterfaz();
                document.getElementById("user").value = "";
                document.getElementById("pass").value = "";
                document.getElementById("auth").style.display = "block";
                document.getElementById("app").style.display = "none";
            }

            async function actualizarKm() {
                let modelo = document.getElementById("modelo").value;
                let km_actual = parseFloat(document.getElementById("km").value);
                let res = await fetch(API + "/vehiculo", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ modelo, km_actual })
                });
                let data = await res.json();
                if(res.ok) {
                    ultimoDiagnostico = "Estado: Sincronizado\\nKm desde servicio: " + data.km_desde_servicio + " km\\nDiagnóstico: " + data.mensaje_alerta;
                    document.getElementById("diagnostico").innerHTML = `
                        <p><b>Estado:</b> Sincronizado</p>
                        <p><b>Km desde último servicio:</b> ${data.km_desde_servicio} km</p>
                        <p style="color: ${data.alerta_color};"><b>Diagnóstico:</b> ${data.mensaje_alerta}</p>
                    `;
                }
            }

            async function registrarCombustible() {
                let km_recorridos = parseFloat(document.getElementById("km_rec").value);
                let litros_cargados = parseFloat(document.getElementById("litros").value);
                let res = await fetch(API + "/combustible", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ km_recorridos, litros_cargados })
                });
                let data = await res.json();
                if(res.ok) {
                    ultimoDiagnostico += "\\nRendimiento: " + data.rendimiento + " km/L\\nAnálisis: " + data.mensaje_alerta;
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p><b>Rendimiento:</b> ${data.rendimiento} km/L</p>
                        <p style="color: ${data.alerta_color};"><b>Análisis:</b> ${data.mensaje_alerta}</p>
                    `;
                }
            }

            async function registrarMantenimiento() {
                let tipo_servicio = document.getElementById("tipo_serv").value;
                let res = await fetch(API + "/mantenimiento", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ tipo_servicio })
                });
                let data = await res.json();
                if(res.ok) {
                    document.getElementById("diagnostico-mantenimiento").innerHTML = `
                        <span style="color: green;">✔ ${data.mensaje}</span>
                    `;
                    actualizarKm();
                }
            }

            async function cargarEstadoVehiculo() {
                let res = await fetch(API + "/vehiculo", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(res.ok) {
                    let data = await res.json();
                    if(data && Object.keys(data).length > 0) {
                        document.getElementById("modelo").value = data.modelo || "";
                        document.getElementById("km").value = data.km_actual || 0;
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
        cursor.execute("UPDATE vehiculos SET modelo = ?, km_actual = ? WHERE id = ?", (v.modelo, v.km_actual, vehiculo_id))
    else:
        ultimo_servicio = 0.0
        cursor.execute("INSERT INTO vehiculos (usuario, modelo, km_actual, ultimo_servicio) VALUES (?, ?, ?, ?)", 
                       (usuario, v.modelo, v.km_actual, ultimo_servicio))
    
    conn.commit()
    conn.close()
    
    km_desde_servicio = v.km_actual - ultimo_servicio
    
    if km_desde_servicio > 2500:
        alerta_color = "red"
        mensaje_alerta = "¡Urgente! Cambio de aceite y revisión de kit de arrastre requeridos."
    elif km_desde_servicio > 1800:
        alerta_color = "orange"
        mensaje_alerta = "Atención: Próximo a servicio preventivo (revisar pastillas de freno)."
    else:
        alerta_color = "green"
        mensaje_alerta = "Componentes óptimos. Desgaste en rangos normales."

    return {
        "modelo": v.modelo,
        "km_actual": v.km_actual,
        "km_desde_servicio": km_desde_servicio,
        "alerta_color": alerta_color,
        "mensaje_alerta": mensaje_alerta
    }

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT modelo, km_actual FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

@app.post("/combustible")
def registrar_combustible(c: CombustibleRegistro, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if c.litros_cargados <= 0:
        raise HTTPException(status_code=400, detail="Los litros deben ser mayores a 0")
    
    rendimiento = round(c.km_recorridos / c.litros_cargados, 2)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO combustible (usuario, km_recorridos, litros_cargados, rendimiento) VALUES (?, ?, ?, ?)",
                   (usuario, c.km_recorridos, c.litros_cargados, rendimiento))
    conn.commit()
    conn.close()

    if rendimiento < 25.0:
        alerta_color = "red"
        mensaje_alerta = "Consumo anormalmente alto. Revisa presión de neumáticos, filtros o afinación."
    elif rendimiento < 32.0:
        alerta_color = "orange"
        mensaje_alerta = "Rendimiento aceptable, pero mejorable con hábitos de conducción eficientes."
    else:
        alerta_color = "green"
        mensaje_alerta = "Excelente eficiencia de combustible en este ciclo."

    return {
        "rendimiento": rendimiento,
        "alerta_color": alerta_color,
        "mensaje_alerta": mensaje_alerta
    }

@app.post("/mantenimiento")
def registrar_mantenimiento(m: MantenimientoRegistro, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, km_actual FROM vehiculos WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Debe registrar un vehículo primero")
    
    vehiculo_id, km_actual = row
    cursor.execute("UPDATE vehiculos SET ultimo_servicio = ? WHERE id = ?", (km_actual, vehiculo_id))
    cursor.execute("INSERT INTO mantenimientos (usuario, tipo_servicio, km_realizado) VALUES (?, ?, ?)",
                   (usuario, m.tipo_servicio, km_actual))
    conn.commit()
    conn.close()

    return {"mensaje": f"Servicio '{m.tipo_servicio}' registrado a los {km_actual} km. Contador de desgaste reiniciado."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)




