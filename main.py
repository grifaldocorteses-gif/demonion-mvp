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
    modelo: str
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
            input, select, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; border-radius: 4px; border: 1px solid #ccc; }
            button { background: #0284c7; color: white; border: none; font-weight: bold; cursor: pointer; }
            .btn-voice { background: #8b5cf6; margin-bottom: 8px; }
            .btn-share { background: #25d366; font-weight: bold; margin-top: 10px; }
            .btn-backup { background: #475569; font-weight: bold; margin-top: 5px; }
            .btn-mantenimiento { background: #d97706; font-weight: bold; margin-top: 6px; }
            .btn-reset-tanque { background: #e11d48; font-weight: bold; font-size: 12px; padding: 8px; width: 30%; }
            .btn-main-carga { width: 68%; }
            #app, #auth { display: none; }
            .flex-row { display: flex; gap: 5px; align-items: center; }
            .checklist-box { background: #fffbeb; padding: 12px; border-radius: 6px; border: 1px solid #fcd34d; margin-top: 10px; margin-bottom: 10px; }
            .checklist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
            .check-item { background: #fff; padding: 8px; border-radius: 4px; border: 1px solid #e2e8f0; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
            .check-item select { padding: 5px; font-size: 12px; margin: 0; }
            .bloqueado { background: #94a3b8 !important; cursor: not-allowed !important; }
            .progress-container { background: #e2e8f0; border-radius: 4px; height: 10px; width: 100%; margin: 5px 0; overflow: hidden; }
            .progress-bar { height: 100%; width: 100%; background: #22c55e; transition: width 0.3s ease; }
            .bitacora-box { background: #f1f5f9; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 10px; font-size: 12px; color: #334155; }
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
                <!-- VISTA PREVIA EN TIEMPO REAL CON ONINPUT -->
                <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados" oninput="simularCarga()">
                <button type="button" class="btn-voice" style="width:30%; margin:0;" onclick="escucharVoz('litros_carga')">🎤 Voz</button>
            </div>
            
            <div class="flex-row">
                <button id="btn_cargar" class="bloqueado btn-main-carga" onclick="cargarCombustible()">Registrar Carga y Acumular Tanque (Bloqueado)</button>
                <button id="btn_reset" class="bloqueado btn-reset-tanque" onclick="reiniciarTanqueYTelemetria()">🔄 Reiniciar Tanque/Telemetría</button>
            </div>

            <div class="flex-row" style="margin-top: 10px;">
                <input type="number" id="km_ruta" placeholder="Km a Recorrer (Nueva Ruta)" oninput="simularRuta()">
                <button type="button" class="btn-voice" style="width:30%; margin:0;" onclick="escucharVoz('km_ruta')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="precio_gas" placeholder="Precio Gasolina ($ / Litro)" value="24.0" oninput="simularRuta()">
                <button type="button" class="btn-voice" style="width:30%; margin:0;" onclick="escucharVoz('precio_gas')">🎤 Voz</button>
            </div>
            <button id="btn_evaluar" class="bloqueado" onclick="evaluarRuta()">Evaluar Costo, Ruta y Descontar (Oficial)</button>
            <div id="diagnostico-combustible" style="margin-top: 8px;"></div>

            <hr>
            <h4>2. Mantenimiento Preventivo y Checklist de Inspección</h4>
            
            <div class="checklist-box">
                <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: bold; font-size: 13px; color: #ea580c;">⚠️ Atención: Confirme que cada punto esté en "Operativo (OK)" para desbloquear el Bloque 1.</p>
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

            <select id="tipo_serv" onchange="sincronizarVistaComponente()">
                <option value="Cambio de Aceite" data-ciclo="2500">Cambio de Aceite (Ciclo: 2,500 km)</option>
                <option value="Kit de Arrastre / Piñones" data-ciclo="15000">Kit de Arrastre / Piñones (Ciclo: 15,000 km)</option>
                <option value="Pastillas de Freno" data-ciclo="5000">Pastillas de Freno (Ciclo: 5,000 km)</option>
            </select>

            <div style="background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 8px; margin-bottom: 10px;">
                <p style="margin: 0 0 5px 0; font-weight: bold; font-size: 13px;">📊 Vida Útil del Componente Seleccionado:</p>
                <div style="font-size: 12px; display: flex; justify-content: space-between;">
                    <span id="label-componente-activo">Desgaste por Kilometraje de Rutas</span>
                    <span id="porcentaje-vida">100% Vida Restante</span>
                </div>
                <div class="progress-container">
                    <div id="barra-vida" class="progress-bar" style="width: 100%;"></div>
                </div>
                <div id="alerta-inversion" style="font-size: 12px; margin-top: 4px; font-weight: bold; color: #16a34a;">Estado óptimo. Sin gastos imprevistos próximos.</div>
                
                <button class="btn-mantenimiento" onclick="registrarMantenimientoRealizado()">🔧 Registrar Mantenimiento Realizado (Reiniciar al 100%)</button>
            </div>

            <hr>
            <h4>3. Telemetría de Precisión y Bitácora Analítica</h4>
            <div class="flex-row">
                <input type="text" id="modelo" placeholder="Modelo (Ej. Pulsar NS 200)">
                <button type="button" class="btn-voice" style="width:30%; margin:0;" onclick="escucharVoz('modelo')">🎤 Voz</button>
            </div>
            <div class="flex-row">
                <input type="number" id="km" placeholder="Kilometraje Actual (Odómetro)">
                <button type="button" class="btn-voice" style="width:30%; margin:0;" onclick="escucharVoz('km')">🎤 Voz</button>
            </div>
            <button onclick="actualizarKm()">Sincronizar Odómetro y Auditar Telemetría</button>
            <div id="diagnostico"></div>

            <div class="bitacora-box">
                <p style="margin: 0 0 5px 0; font-weight: bold; font-size: 13px; color: #1e293b;">📋 Auditoría y Bitácora Analítica:</p>
                <div id="lista-bitacora">Sin registros analíticos en esta sesión.</div>
            </div>

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
            let sistemaBloqueado = true;
            let litrosActualesTanque = 0.0;
            let kmTotalesAcumuladosGlobal = 0.0;
            let gastoTotalAcumuladoGlobal = 0.0;
            let kmComponentes = {
                "Cambio de Aceite": 0,
                "Kit de Arrastre / Piñones": 0,
                "Pastillas de Freno": 0
            };
            let bitacoraLocal = [];

            function limpiarInterfaz() {
                document.getElementById("modelo").value = "";
                document.getElementById("km").value = "";
                document.getElementById("litros_carga").value = "";
                document.getElementById("km_ruta").value = "";
                document.getElementById("diagnostico").innerHTML = "";
                document.getElementById("diagnostico-combustible").innerHTML = "";
                document.getElementById("anulador_frenos").value = "revision";
                document.getElementById("anulador_cadena").value = "revision";
                document.getElementById("anulador_llantas").value = "revision";
                document.getElementById("anulador_luces").value = "revision";
                document.getElementById("anulador_epp").value = "revision";
                document.getElementById("anulador_docs").value = "revision";
                document.getElementById("lista-bitacora").innerHTML = "Sin registros analíticos en esta sesión.";
                litrosActualesTanque = 0.0;
                kmTotalesAcumuladosGlobal = 0.0;
                gastoTotalAcumuladoGlobal = 0.0;
                kmComponentes = { "Cambio de Aceite": 0, "Kit de Arrastre / Piñones": 0, "Pastillas de Freno": 0 };
                bitacoraLocal = [];
                bloquearSistema(true, "🔒 Verificación pendiente: Cambie el estatus de todos los componentes a 'Operativo (OK)' para habilitar el Bloque 1.");
                ultimoDiagnostico = "";
            }

            function bloquearSistema(bloquear, mensaje) {
                let btnCargar = document.getElementById("btn_cargar");
                let btnReset = document.getElementById("btn_reset");
                let btnEvaluar = document.getElementById("btn_evaluar");
                let div = document.getElementById("diagnostico-anulador");

                sistemaBloqueado = bloquear;
                div.innerHTML = mensaje;

                if (bloquear) {
                    btnCargar.classList.add("bloqueado");
                    btnCargar.style.background = "#94a3b8";
                    btnReset.classList.add("bloqueado");
                    btnReset.style.background = "#94a3b8";
                    btnEvaluar.classList.add("bloqueado");
                    btnEvaluar.style.background = "#94a3b8";
                } else {
                    btnCargar.classList.remove("bloqueado");
                    btnCargar.style.background = "#0284c7";
                    btnReset.classList.remove("bloqueado");
                    btnReset.style.background = "#e11d48";
                    btnEvaluar.classList.remove("bloqueado");
                    btnEvaluar.style.background = "#059669";
                }
            }

            function verificarAnuladores() {
                let f = document.getElementById("anulador_frenos").value;
                let c = document.getElementById("anulador_cadena").value;
                let ll = document.getElementById("anulador_llantas").value;
                let l = document.getElementById("anulador_luces").value;
                let epp = document.getElementById("anulador_epp").value;
                let docs = document.getElementById("anulador_docs").value;

                if (f === "revision" || c === "revision" || ll === "revision" || l === "revision" || epp === "revision" || docs === "revision") {
                    bloquearSistema(true, "⚠️ Precaución: Hay elementos pendientes de revisión. El Bloque 1 se habilitará cuando todos los puntos estén en 'Operativo (OK)'.");
                    ultimoDiagnostico = "Estado Operativo: Bloqueado por Seguridad Preventiva Integral";
                } else {
                    bloquearSistema(false, "✔ Inspección aprobada: Moto, EPP y documentos listos para operar con seguridad.");
                    ultimoDiagnostico = "Estado Operativo: Habilitado y Seguro (OK)";
                }
            }

            // SIMULACIÓN / VISTA PREVIA EN TIEMPO REAL AL DIGITAR LITROS
            function simularCarga() {
                let litrosEntrada = parseFloat(document.getElementById("litros_carga").value);
                let divDiag = document.getElementById("diagnostico-combustible");

                if (!litrosEntrada || litrosEntrada <= 0) {
                    // Si borra el input, se puede optar por no mostrar simulación o mantener el estado anterior
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
                    <p style="font-size:12px; color:#64748b; margin:0 0 4px 0;"><i>🔍 [Vista previa / Simulación de Carga]</i></p>
                    <p><b>Litros en Tanque (Post-Carga):</b> ${totalSimulado} L (${litrosActualesTanque} L actuales + ${litrosEntrada} L nuevos)</p>
                    <p><b>Autonomía Estimada (Pulsar NS 200):</b> ${autonomiaProyectada} km</p>
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
                let costoPorKm = round(costoViaje / kmRutaVal, 2);
                let litrosRestantesSimulados = round(litrosActualesTanque - litrosConsumidos, 2);
                let autonomiaRestanteKm = round(Math.max(0.0, litrosRestantesSimulados) * rendimientoEstandar, 1);

                let kmTotalesProyectados = round(kmTotalesAcumuladosGlobal + kmRutaVal, 1);
                let gastoTotalProyectado = round(gastoTotalAcumuladoGlobal + costoViaje, 2);

                let intensidadUso = "Óptima / Moderada";
                let colorIntensidad = "green";
                if (kmTotalesProyectados > 150) {
                    intensidadUso = "⚠️ Alta Exigencia / Jornada Pesada (Desgaste acelerado)";
                    colorIntensidad = "red";
                } else if (kmTotalesProyectados > 90) {
                    intensidadUso = "⚡ Exigencia Estándar / Operación Normal";
                    colorIntensidad = "orange";
                }

                let alertaColor = "green";
                let mensajeAlerta = `Ruta viable para aceptar.`;

                if (litrosRestantesSimulados < 1.0) {
                    alertaColor = "red";
                    mensajeAlerta = `⚠️ Alerta: Combustible insuficiente para completar este viaje.`;
                } else if (litrosRestantesSimulados < 3.0) {
                    alertaColor = "orange";
                    mensajeAlerta = `⚠️ Precaución: El tanque quedará muy bajo tras este servicio.`;
                }

                divDiag.innerHTML = `
                    <p style="font-size:12px; color:#64748b; margin:0 0 4px 0;"><i>🔍 [Vista previa / Simulación de Viaje y Proyección]</i></p>
                    <p><b>Consumo Ruta (Sim):</b> ${litrosConsumidos} L (<b>$${costoViaje} MXN</b>)</p>
                    <p><b>Costo Operativo:</b> $${costoPorKm} MXN / km</p>
                    <p><b>Autonomía Proyectada:</b> ${autonomiaRestanteKm} km restantes</p>
                    <p><b>Litros Restantes Estimados:</b> ${litrosRestantesSimulados} L</p>
                    <hr style="border: 0; border-top: 1px dashed #cbd5e1; margin: 6px 0;">
                    <p style="color: #1e3a8a; font-weight: bold;">📊 Proyección Post-Viaje (Acumulados):</p>
                    <p><b>Km Totales Proyectados:</b> ${kmTotalesProyectados} km</p>
                    <p><b>Gasto Total Proyectado:</b> $${gastoTotalProyectado} MXN</p>
                    <p style="color: ${colorIntensidad};"><b>Evaluación de Uso (Pulsar NS 200):</b> ${intensidadUso}</p>
                    <p style="color: ${alertaColor};"><b>Estado:</b> ${mensajeAlerta}</p>
                `;
            }

            function round(value, decimals) {
                return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
            }

            function sincronizarVistaComponente() {
                let selectElem = document.getElementById("tipo_serv");
                let tipoServicio = selectElem.value;
                let cicloMax = parseFloat(selectElem.options[selectElem.selectedIndex].getAttribute("data-ciclo"));
                
                document.getElementById("label-componente-activo").innerText = tipoServicio;

                let kmAcumulados = kmComponentes[tipoServicio] || 0;
                let vidaRestante = Math.max(0, Math.min(100, 100 - (kmAcumulados / cicloMax) * 100));
                
                let barra = document.getElementById("barra-vida");
                let txtVida = document.getElementById("porcentaje-vida");
                let alertaInv = document.getElementById("alerta-inversion");

                barra.style.width = vidaRestante + "%";
                txtVida.innerText = Math.round(vidaRestante) + "% Vida Restante (" + kmAcumulados + " / " + cicloMax + " km)";

                if (vidaRestante > 40) {
                    barra.style.background = "#22c55e";
                    alertaInv.style.color = "#16a34a";
                    alertaInv.innerText = `Estado óptimo para ${tipoServicio}. Sin gastos imprevistos próximos.`;
                } else if (vidaRestante > 15) {
                    barra.style.background = "#eab308";
                    alertaInv.style.color = "#ca8a04";
                    alertaInv.innerText = `⚠️ Precaución: El componente ${tipoServicio} se acerca al límite de su ciclo.`;
                } else {
                    barra.style.background = "#ef4444";
                    alertaInv.style.color = "#dc2626";
                    alertaInv.innerText = `🚨 Alerta de Inversión: Es tiempo obligatorio de cambiar ${tipoServicio}.`;
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
                    if (inputId === 'km' || inputId === 'litros_carga' || inputId === 'km_ruta' || inputId === 'precio_gas') {
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
                const textoReporte = "*REPORTE TELEMETRÍA DEMONION MVP*\\n" + ultimoDiagnostico;

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
                    sincronizarVistaComponente();
                    verificarAnuladores();
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
                    document.getElementById("diagnostico").innerHTML = `
                        <p><b>Odómetro Sincronizado:</b> ${data.km_actual} km</p>
                        <p><b>Distancia desde último servicio:</b> ${data.km_desde_servicio} km</p>
                        <p style="color: ${data.alerta_color};"><b>Telemetría:</b> ${data.mensaje_alerta}</p>
                    `;
                }
            }

            async function cargarCombustible() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada: Debe confirmar el checklist para usar el control de combustible.");
                    return;
                }
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
                        <p style="color: #047857; font-weight: bold;">✔ Carga Registrada y Tanque Acumulado:</p>
                        <p><b>Litros Totales en Tanque:</b> ${litrosActualesTanque} L</p>
                        <p><b>Autonomía Disponible (Pulsar NS 200):</b> ${autonomiaTanque} km</p>
                    `;
                    document.getElementById("litros_carga").value = "";
                } else {
                    alert(data.detail);
                }
            }

            async function reiniciarTanqueYTelemetria() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada: El sistema está bloqueado por seguridad.");
                    return;
                }
                if (!confirm("¿Estás seguro de reiniciar el tanque a 0 L y borrar todos los acumulados de telemetría de rutas?")) {
                    return;
                }
                let res = await fetch(API + "/combustible/reiniciar-telemetria", {
                    method: "POST",
                    headers: { 
                        "Authorization": "Bearer " + authToken
                    }
                });
                let data = await res.json();
                if(res.ok) {
                    litrosActualesTanque = 0.0;
                    kmTotalesAcumuladosGlobal = 0.0;
                    gastoTotalAcumuladoGlobal = 0.0;
                    document.getElementById("litros_carga").value = "";
                    document.getElementById("km_ruta").value = "";
                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: #047857; font-weight: bold;">✔ Acción realizada con éxito:</p>
                        <p><b>Tanque y Contadores de Telemetría:</b> Reiniciados a 0 correctamente.</p>
                    `;
                } else {
                    alert("Error al reiniciar.");
                }
            }

            async function evaluarRuta() {
                if (sistemaBloqueado) {
                    alert("⚠️ Acción bloqueada: Debe confirmar el checklist para evaluar rutas.");
                    return;
                }
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
                    litrosActualesTanque = data.litros_restantes;
                    kmTotalesAcumuladosGlobal = data.km_totales_acumulados;
                    gastoTotalAcumuladoGlobal = data.gasto_total_acumulado;

                    for (let comp in kmComponentes) {
                        kmComponentes[comp] += km_recorridos;
                    }
                    sincronizarVistaComponente();

                    let intensidadUso = "Óptima / Moderada";
                    let colorIntensidad = "green";
                    if (kmTotalesAcumuladosGlobal > 150) {
                        intensidadUso = "⚠️ Alta Exigencia / Jornada Pesada";
                        colorIntensidad = "red";
                    } else if (kmTotalesAcumuladosGlobal > 90) {
                        intensidadUso = "⚡ Exigencia Estándar / Operación Normal";
                        colorIntensidad = "orange";
                    }

                    document.getElementById("diagnostico-combustible").innerHTML = `
                        <p style="color: #047857; font-weight: bold;">✔ Ruta Oficial Registrada y Descontada:</p>
                        <p><b>Consumo Ruta:</b> ${data.litros_consumidos} L (<b>$${data.costo_viaje} MXN</b>)</p>
                        <p><b>Costo Operativo:</b> $${data.costo_por_km} MXN / km</p>
                        <p><b>Autonomía Proyectada:</b> ${data.autonomia_restante_km} km restantes</p>
                        <p><b>Litros Restantes en Tanque:</b> ${data.litros_restantes} L</p>
                        <hr style="border: 0; border-top: 1px dashed #cbd5e1; margin: 6px 0;">
                        <p style="color: #1e3a8a; font-weight: bold;">📊 Análisis Telemetría - Acumulados:</p>
                        <p><b>Km Totales Recorridos en Rutas:</b> ${kmTotalesAcumuladosGlobal} km</p>
                        <p><b>Gasto Total Acumulado en Gasolina:</b> $${gastoTotalAcumuladoGlobal} MXN</p>
                        <p style="color: ${colorIntensidad};"><b>Evaluación de Uso (Pulsar NS 200):</b> ${intensidadUso}</p>
                        <p style="color: ${data.alerta_color};"><b>Estado:</b> ${data.mensaje_alerta}</p>
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
                        document.getElementById("modelo").value = data.modelo || "";
                        document.getElementById("km").value = data.km_actual || 0;
                        document.getElementById("diagnostico").innerHTML = `
                            <p><b>Odómetro Sincronizado:</b> ${data.km_actual} km</p>
                            <p><b>Distancia desde último servicio:</b> ${data.km_desde_servicio || 0} km</p>
                        `;
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
                    sincronizarVistaComponente();
                }

                let resBitacora = await fetch(API + "/bitacora", {
                    headers: { "Authorization": "Bearer " + authToken }
                });
                if(resBitacora.ok) {
                    let dataBit = await resBitacora.json();
                    if(dataBit.length > 0) {
                        bitacoraLocal = dataBit.map(b => `✔ [Odómetro: ${b.km_realizado} km] Auditoría: ${b.componente} registrado.`);
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
    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"km_totales_acumulados": 0.0, "gasto_total_acumulado": 0.0}

@app.post("/combustible/reiniciar-telemetria")
def reiniciar_tanque_y_telemetria(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tanque_usuario SET litros_tanque = 0.0 WHERE usuario = ?", (usuario,))
    cursor.execute("UPDATE estadisticas_rutas SET km_totales_acumulados = 0.0, gasto_total_acumulado = 0.0 WHERE usuario = ?", (usuario,))
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
        cursor.execute("UPDATE vehiculos SET modelo = ?, km_actual = ? WHERE id = ?", (v.modelo, v.km_actual, vehiculo_id))
    else:
        ultimo_servicio = v.km_actual
        cursor.execute("INSERT INTO vehiculos (usuario, modelo, km_actual, ultimo_servicio) VALUES (?, ?, ?, ?)", 
                       (usuario, v.modelo, v.km_actual, ultimo_servicio))
    
    conn.commit()
    conn.close()
    
    km_desde_servicio = max(0.0, v.km_actual - (ultimo_servicio if ultimo_servicio else 0.0))

    return {
        "modelo": v.modelo,
        "km_actual": v.km_actual,
        "km_desde_servicio": km_desde_servicio,
        "alerta_color": "green",
        "mensaje_alerta": "Odómetro sincronizado y telemetría de precisión activa."
    }

@app.get("/vehiculo")
def obtener_vehiculo(authorization: str = Header(None)):
    usuario = verificar_token(authorization)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT modelo, km_actual, ultimo_servicio FROM vehiculos WHERE usuario = ?", (usuario,))
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
    cursor.execute("SELECT componente, km_realizado FROM bitacora_servicios WHERE usuario = ? ORDER BY id DESC LIMIT 5", (usuario,))
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

    cursor.execute("""
        INSERT INTO estadisticas_rutas (usuario, km_totales_acumulados, gasto_total_acumulado) 
        VALUES (?, ?, ?)
        ON CONFLICT(usuario) DO UPDATE SET 
            km_totales_acumulados = km_totales_acumulados + ?,
            gasto_total_acumulado = gasto_total_acumulado + ?
    """, (usuario, e.km_recorridos, costo_viaje, e.km_recorridos, costo_viaje))

    cursor.execute("SELECT km_totales_acumulados, gasto_total_acumulado FROM estadisticas_rutas WHERE usuario = ?", (usuario,))
    est_row = cursor.fetchone()
    km_totales_acumulados = est_row[0]
    gasto_total_acumulado = est_row[1]

    cursor.execute("""
        INSERT INTO tanque_usuario (usuario, litros_tanque) VALUES (?, ?)
        ON CONFLICT(usuario) DO UPDATE SET litros_tanque = ?
    """, (usuario, max(0.0, litros_restantes), max(0.0, litros_restantes)))

    cursor.execute("INSERT INTO combustible (usuario, km_recorridos, litros_consumidos, rendimiento) VALUES (?, ?, ?, ?)",
                   (usuario, e.km_recorridos, litros_consumidos, rendimiento_estandar))
    conn.commit()
    conn.close()

    if litros_restantes < 1.0:
        alerta_color = "red"
        mensaje_alerta = f"¡Alerta Crítica! Gasto estimado: ${costo_viaje}."
    elif litros_restantes < 3.0:
        alerta_color = "orange"
        mensaje_alerta = f"Precaución: Gasto estimado ${costo_viaje}."
    else:
        alerta_color = "green"
        mensaje_alerta = f"Ruta rentable. Gasto estimado: ${costo_viaje} MXN."

    return {
        "litros_consumidos": litros_consumidos,
        "costo_viaje": costo_viaje,
        "costo_por_km": costo_por_km,
        "autonomia_restante_km": autonomia_restante_km,
        "litros_restantes": max(0.0, litros_restantes),
        "km_totales_acumulados": km_totales_acumulados,
        "gasto_total_acumulado": gasto_total_acumulado,
        "alerta_color": alerta_color,
        "mensaje_alerta": mensaje_alerta
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)



































                    







