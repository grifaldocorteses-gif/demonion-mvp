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
            .btn-leido { background: #16a34a; font-weight: bold; margin-top: 10px; }
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
            <div id="diagnostico-oficial" class="panel-oficial" style="display:none;"></div>

            <hr>
            <h4>2. Mantenimiento Preventivo y Checklist de Inspección</h4>
            
            <div id="contenedor-inspeccion">
                <div id="checklist-contenedor" class="checklist-box" style="display:none;">
                    <p id="diagnostico-anulador" style="margin: 0 0 8px 0; font-weight: bold; font-size: 13px; color: #ea580c;">⚠️ Jornada alta detectada: Confirme los 6 puntos críticos de seguridad para desbloquear el sistema.</p>
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
                    <p style="margin:0 0 4px 0;">Has confirmado los 6 puntos críticos de inspección debido a la alta exigencia de tu jornada. Cumple estrictamente la reglamentación oficial:</p>
                    <ul style="margin: 4px 0 8px 15px; padding: 0;">
                        <li><b>Límites de Velocidad:</b> Máximo <b>50 km/h</b> en avenidas secundarias y <b>80 km/h</b> en vías de acceso controlado. Reduzca a <b>30 km/h</b> en zonas escolares.</li>
                        <li><b>Equipo de Protección (EPP):</b> Uso obligatorio de casco certificado (DOT / ECE) y chaleco reflejante nocturno.</li>
                        <li><b>Cero Invasión:</b> Prohibido circular en banquetas, ciclovías o carriles confinados de transporte masivo.</li>
                    </ul>
                    <button class="btn-leido" onclick="confirmarLeidoProtocolo()">✔ Entendido y Confirmado (Regresar)</button>
                </div>
            </div>

            <select id="tipo_serv" onchange="sincronizarVistaComponente()" style="margin-top: 10px;">
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
            let protocoloConfirmadoLeido = false;
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
                let panelOficial = document.getElementById("diagnostico-oficial");
                panelOficial.innerHTML = "";
                panelOficial.style.display = "none";
                protocoloConfirmadoLeido = false;
                document.getElementById("protocolo-normativo").style.display = "none";
                document.getElementById("checklist-contenedor").style.display = "none";
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
                bloquearSistema(true, "🔒 Verificación pendiente.");
                ultimoDiagnostico = "";
            }

            function bloquearSistema(bloquear, mensaje) {
                let btnCargar = document.getElementById("btn_cargar");
                let btnReset = document.getElementById("btn_reset");
                let btnEvaluar = document.getElementById("btn_evaluar");
                let div = document.getElementById("diagnostico-anulador");

                sistemaBloqueado = bloquear;
                if(div) div.innerHTML = mensaje;

                if (bloquear) {
                    if(btnCargar) { btnCargar.classList.add("bloqueado"); btnCargar.style.background = "#94a3b8"; }
                    if(btnReset) { btnReset.classList.add("bloqueado"); btnReset.style.background = "#94a3b8"; }
                    if(btnEvaluar) { btnEvaluar.classList.add("bloqueado"); btnEvaluar.style.background = "#94a3b8"; }
                } else {
                    if(btnCargar) { btnCargar.classList.remove("bloqueado"); btnCargar.style.background = "#0284c7"; }
                    if(btnReset) { btnReset.classList.remove("bloqueado"); btnReset.style.background = "#e11d48"; }
                    if(btnEvaluar) { btnEvaluar.classList.remove("bloqueado"); btnEvaluar.style.background = "#059669"; }
                }
            }

            function verificarJornadaYDiagnostico() {
                let checklistElem = document.getElementById("checklist-contenedor");
                let protocoloElem = document.getElementById("protocolo-normativo");

                if (kmTotalesAcumuladosGlobal >= 90.0) {
                    if (!protocoloConfirmadoLeido) {
                        let f = document.getElementById("anulador_frenos").value;
                        let c = document.getElementById("anulador_cadena").value;
                        let ll = document.getElementById("anulador_llantas").value;
                        let l = document.getElementById("anulador_luces").value;
                        let epp = document.getElementById("anulador_epp").value;
                        let docs = document.getElementById("anulador_docs").value;

                        if (f === "revision" || c === "revision" || ll === "revision" || l === "revision" || epp === "revision" || docs === "revision") {
                            bloquearSistema(true, "⚠️ Jornada Alta (>90 km): Hay elementos críticos pendientes de revisión obligatoria.");
                            if(checklistElem) checklistElem.style.display = "block";
                            if(protocoloElem) protocoloElem.style.display = "none";
                            ultimoDiagnostico = "Estado Operativo: Bloqueado por Jornada Pesada";
                        } else {
                            bloquearSistema(false, "✔ Inspección aprobada para jornada pesada.");
                            if(checklistElem) checklistElem.style.display = "none";
                            if(protocoloElem) protocoloElem.style.display = "block";
                            ultimoDiagnostico = "Estado Operativo: Protocolo Vial Activo y Habilitado";
                        }
                    } else {
                        if(checklistElem) checklistElem.style.display = "block";
                        if(protocoloElem) protocoloElem.style.display = "none";
                        bloquearSistema(false, "✔ Jornada pesada auditada y protocolo vial confirmado.");
                    }
                } else {
                    protocoloConfirmadoLeido = false;
                    if(checklistElem) checklistElem.style.display = "none";
                    if(protocoloElem) protocoloElem.style.display = "none";
                    bloquearSistema(false, "✔ Jornada Óptima / Inicial: Sistema Operativo Habilitado Directamente.");
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
                let litrosEntrada = parseFloat(document.getElementById("litros_carga").value);
                let divDiag = document.getElementById("diagnostico-combustible");

                if (!litrosEntrada || litrosEntrada <= 0) {
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
                    if(barra) barra.style.background = "#22c55e";
                    if(alertaInv) { alertaInv.style.color = "#16a34a"; alertaInv.innerText = `Estado óptimo para ${tipoServicio}. Sin gastos imprevistos próximos.`; }
                } else if (vidaRestante > 15) {
                    if(barra) barra.style.background = "#eab308";
                    if(alertaInv) { alertaInv.style.color = "#ca8a04"; alertaInv.innerText = `⚠️ Precaución: El componente ${tipoServicio} se acerca al límite de su ciclo.`; }
                } else {
                    if(barra) barra.style.background = "#ef4444";
                    if(alertaInv) { alertaInv.style.color = "#dc2626"; alertaInv.innerText = `🚨 Alerta de Inversión: Es tiempo obligatorio de cambiar ${tipoServicio}.`; }
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
                    
                    // CORRECCIÓN ASÍNCRONA: Cargar estado completo antes de evaluar jornada
                    await cargarEstadoVehiculo();
                    sincronizarVistaComponente();
                    verificarJornadaYDiagnostico();
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
                    







































                    







