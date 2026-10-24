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
        CREATE TABLE IF NOT EXISTS tanque_usuario (
            usuario TEXT PRIMARY KEY,
            litros_tanque REAL DEFAULT 0.0
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

class CargarCombustible(BaseModel):
    litros_cargados: float

class EvaluarRuta(BaseModel):
    km_recorridos: float
    precio_gasolina: float

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
            .checklist-box { background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0; margin-top: 8px; }
            .checklist-item { display: flex; align-items: center; gap: 10px; margin: 5px 0; font-size: 14px; }
            .checklist-item input { width: 20px; height: 20px; margin: 0; }
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
                <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados (Tanque Lleno / Nuevo)">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('litros_carga')">🎤 Voz</button>
            </div>
            <button onclick="cargarCombustible()" style="background:#059669;">Registrar Carga y Reiniciar Tanque</button>

            <div class="flex-row" style="margin-top: 10px;">
                <input type="number" id="km_ruta" placeholder="Km a Recorrer (Nueva Ruta)">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('km_ruta')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="precio_gas" placeholder="Precio Gasolina ($ / Litro)" value="24.0">
                <button type="button" class="btn-voice" style="width:30%;" onclick="escucharVoz('precio_gas')">🎤 Voz</button>
            </div>
            <button onclick="evaluarRuta()" style="background:#0284c7;">Evaluar Costo, Ruta y Descontar</button>
            <div id="diagnostico-combustible" style="margin-top: 8px;"></div>

            <hr>
            <h4>2. Mantenimiento Preventivo y Checklist Operativo</h4>
            <select id="tipo_serv">
                <option value="Cambio de Aceite">Cambio de Aceite</option>
                <option value="Kit de Arrastre / Cadena">Kit de Arrastre / Cadena</option>
                <option value="Pastillas de Freno">Pastillas de Freno</option>
                <option value="Afinacion General">Afinación General</option>
            </select>
            <button onclick="registrarMantenimiento()" style="background:#d97706;">Registrar Servicio Realizado</button>
            <div id="diagnostico-mantenimiento" style="margin-top: 8px; font-weight: bold;"></div>

            <div class="checklist-box">
                <p style="margin: 0 0 5px 0; font-weight: bold; font-size: 13px;">Checklist Pre-Ruta (Inspección Rápida):</p>
                <div class="checklist-item"><input type="checkbox" id="chk_frenos"> Frenos (Delantero y Trasero)</div>
                <div class="checklist-item"><input type="checkbox" id="chk_llantas"> Presión y Estado de Llantas</div>
                <div class="checklist-item"><input type="checkbox" id="chk_luces"> Luces, Stop e Intermitentes</div>
                <div class="checklist-item"><input type="checkbox" id="chk_cadena"> Tensión y Lubricación de Cadena</div>
                <button onclick="validarChecklist()" style="background:#475569; margin-top: 8px; font-size: 13px; padding: 6px;">Validar Estado de la Moto</button>
                <div id="diagnostico-checklist" style="margin-top: 5px; font-size: 13px;"></div>
            </div>

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
            <button onclick="actualizarKm()">Actualizar y Sincronizar Odómetro</button>
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
                document.getElementById("litros_carga").value = "";
                document.getElementById("km_ruta").value = "";
                document.getElementById("diagnostico").innerHTML = "";
                document.getElementById("diagnostico-combustible").innerHTML = "";
                document.getElementById("diagnostico-mantenimiento").innerHTML = "";
                document.getElementById("diagnostico-checklist").innerHTML = "";
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
                    if (inputId === 'km' || inputId === 'litros_carga' || inputId === 'km_ruta' || inputId === 'precio_gas') {
                        texto = texto.replace(/[^0-9.]/g, '');
                    }
                    document.getElementById(inputId).value = texto;
                };

                recognition.onerror = function(event) {
                    alert("Error de voz: " + event.error);
                };
            }

            function validarChecklist() {
                let f = document.getElementById("chk_frenos").checked;
                let l = document.getElementById("chk_llantas").checked;
                let lu = document.getElementById("chk_luces").checked;
                let c = document.getElementById("chk_cadena").checked;

                let div = document.getElementById("diagnostico-checklist");
                if (f && l && lu && c) {
                    div.innerHTML = "<span style='color: green; font-weight: bold;'>✔ Checklist OK: Moto en óptimas condiciones para repartir.</span>";
                    ultimoDiagnostico += "\nChecklist: Aprobado (Listo para ruta)";
                } else {
                    div.innerHTML = "<span style='color: red; font-weight: bold;'>⚠ Precaución: Faltan puntos críticos por revisar antes de salir.</span>";
                    ultimoDiagnostico += "\nChecklist: Alerta (Revisión pendiente)";
                }
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
                    ultimoDiagnostico = `Estado Odómetro: ${data.km_actual} km\nKm desde servicio: ${data.km_desde_servicio} km\nDiagnóstico Desgaste: ${data.mensaje_alerta}`;
                    document.getElementById("diagnostico").innerHTML = `
                        <p><b>Odómetro Sincronizado:</b> ${data.km_actual} km</p>
                        <p><b>Km desde último servicio:</b> ${data.km_desde_servicio} km</p>
                        <p style="color: ${data.alerta_color};"><b>Diagnóstico:</b> ${data.mensaje_alerta}</p>
                    `;
                }
            }

            async function cargarCombustible() {
                let litros_cargados = parseFloat(document.getElementById("litros_carga").value);
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
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: green;"><b>✔ Tanque Reiniciado y Actualizado:</b> Nuevos litros en tanque: <b>${data.litros_tanque} L</b></p>
                    `;
                } else {
                    alert(data.detail);
                }
            }

            async function evaluarRuta() {
                let km_recorridos = parseFloat(document.getElementById("km_ruta").value);
                let precio_gasolina = parseFloat(document.getElementById("precio_gas").value);
                let res = await fetch(API + "/combustible/evaluar", {
                    method: "POST",
                    headers: { 
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + authToken
                    },
                    body: JSON.stringify({ km_recorridos, precio_gasolina })
                });
                let data = await res.json();
                if(res.ok) {
                    ultimoDiagnostico += `\nRuta (${km_recorridos} km): Gasto $${data.costo_viaje} MXN | Restantes: ${data.litros_restantes} L`;
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p><b>Consumo Ruta:</b> ${data.litros_consumidos} L (<b>$${data.costo_viaje} MXN</b>)</p>
                        <p><b>Litros Restantes en Tanque:</b> ${data.litros_restantes} L</p>
                        <p style="color: ${data.alerta_color};"><b>Análisis:</b> ${data.mensaje_alerta}</p>
                    `;
                } else {
                    alert(data.detail);
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
                        actualizarKm();
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

@app.post("/combustible/cargar")
def cargar_combustible(c: CargarCombustible, authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    if c.litros_cargados <= 0:
        raise HTTPException(status_code=400, detail="Los litros deben ser mayores a 0")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    nuevo_total = round(c.litros_cargados, 2)
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
    cursor.execute("SELECT litros_tanque FROM tanque_usuario WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    
    litros_tanque = row[0] if row and row[0] is not None else 0.0

    rendimiento_estandar = 30.0
    litros_consumidos = round(e.km_recorridos / rendimiento_estandar, 2)
    costo_viaje = round(litros_consumidos * e.precio_gasolina, 2)
    litros_restantes = round(litros_tanque - litros_consumidos, 2)

    if row:
        cursor.execute("UPDATE tanque_usuario SET litros_tanque = ? WHERE usuario = ?", (max(0.0, litros_restantes), usuario))
    else:
        cursor.execute("INSERT INTO tanque_usuario (usuario, litros_tanque) VALUES (?, ?)", (usuario, max(0.0, litros_restantes)))

    cursor.execute("INSERT INTO combustible (usuario, km_recorridos, litros_consumidos, rendimiento) VALUES (?, ?, ?, ?)",
                   (usuario, e.km_recorridos, litros_consumidos, rendimiento_estandar))
    conn.commit()
    conn.close()

    if litros_restantes < 1.0:
        alerta_color = "red"
        mensaje_alerta = f"¡Alerta Crítica! Gasto estimado: ${costo_viaje}. Combustible insuficiente para esta ruta."
    elif litros_restantes < 3.0:
        alerta_color = "orange"
        mensaje_alerta = f"Precaución: Gasto estimado ${costo_viaje}. Tanque bajo después de este servicio."
    else:
        alerta_color = "green"
        mensaje_alerta = f"Ruta rentable. Gasto estimado: ${costo_viaje} MXN. Autonomía óptima."

    return {
        "litros_consumidos": litros_consumidos,
        "costo_viaje": costo_viaje,
        "litros_restantes": max(0.0, litros_restantes),
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
        raise HTTPException(status_code=400, detail="Debe registrar un vehículo primero en la sección 3")
    
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








                    







