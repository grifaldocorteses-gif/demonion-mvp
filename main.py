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
                <input type="number" id="litros_carga" placeholder="Litros de Gasolina Agregados">
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

            function simularRuta() {
                let kmRutaVal = parseFloat(document.getElementById("km_ruta").value);
                let precioGasVal = parseFloat(document.getElementById("precio_gas").value) || 24.0;
                let divDiag = document.getElementById("diagnostico-combustible");

                if (!kmRutaVal || kmRutaVal <= 0) {
                    divDiag.innerHTML = "";
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
                    <p><b>Consumo Ruta (Sim):</b> ${litrosConsumidos} L (<b>$${costoViaje} MXN</b>)</p> <p><b>Costo Operativo:</b> $${costoPorKm} MXN / km</p>
                    <p><b>Autonomía Proyectada:</b> ${autonomiaRestanteKm} km restantes</p>
                    <p><b>Litros Restantes Estimados:</b> ${litrosRestantesSimulados} L</p>
                    <hr style="border: 0; border-top: 1px dashed #cbd5e1; margin: 6px 0;">
                    <p style="color: #1e3a8a; font-weight: bold;">📊 Proyección Post-Viaje (Acumulados):</p>
                    <p><b>Km Totales Proyectados:</b> ${kmTotalesProyectados} km</p> <p><b>Gasto Total Proyectado:</b> $${gastoTotalProyectado} MXN</p>
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
                    bitacoraLocal.unshift(`✔ [Odómetro: ${kmActualVal} km] Auditoría: ${
































                    







