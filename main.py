from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import sqlite3

app = FastAPI(title="Proyecto Demonion - Telemetría & Mantenimiento", version="3.0.0")
DB_FILE = "demonion.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_name TEXT NOT NULL,
                fuel_consumed REAL NOT NULL,
                mileage REAL NOT NULL,
                efficiency REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                odometer REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

init_db()

class TelemetryRecord(BaseModel):
    route_name: str = Field(..., min_length=1, max_length=100)
    fuel_consumed: float = Field(..., gt=0, le=500)
    mileage: float = Field(..., gt=0, le=5000)

class MaintenanceRecord(BaseModel):
    component: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., pattern="^(OPTIMO|DESGASTE|CRITICO)$")
    odometer: float = Field(..., ge=0)

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DEMONION // SYSTEM CORE</title>
    <style>
        :root { --bg: #090c10; --panel: #12171f; --border: #1f2937; --accent: #00f0ff; --ok: #10b981; --warn: #f59e0b; --crit: #ef4444; --text: #e5e7eb; }
        body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; margin: 0; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; max-width: 1200px; margin: auto; }
        .card { background: var(--panel); border: 1px solid var(--border); border-left: 3px solid var(--accent); padding: 16px; border-radius: 4px; }
        h1 { color: var(--accent); font-size: 1.4rem; letter-spacing: 2px; border-bottom: 1px solid var(--border); padding-bottom: 10px; max-width: 1200px; margin: 0 auto 20px; }
        h2 { font-size: 1rem; color: var(--accent); margin-top: 0; text-transform: uppercase; }
        input, select, button { width: 100%; box-sizing: border-box; background: #0d1117; border: 1px solid var(--border); color: var(--text); padding: 10px; margin-bottom: 10px; font-family: inherit; }
        button { background: var(--accent); color: #000; font-weight: bold; cursor: pointer; border: none; transition: 0.2s; }
        button:hover { opacity: 0.85; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 10px; }
        th, td { border-bottom: 1px solid var(--border); padding: 8px; text-align: left; }
        .badge-OPTIMO { color: var(--ok); } .badge-DESGASTE { color: var(--warn); } .badge-CRITICO { color: var(--crit); font-weight: bold; }
        #sys-log { font-size: 0.8rem; color: var(--ok); margin-bottom: 15px; max-width: 1200px; margin: 0 auto 15px; }
    </style>
</head>
<body>
    <h1>DEMONION // TELEMETRY & DIAGNOSTICS v3.0</h1>
    <div id="sys-log">[SYS_OK] Núcleo SQLite WAL activo. Esperando entrada...</div>
    <div class="grid">
        <div class="card">
            <h2>1. Auditoría de Ruta y Combustible</h2>
            <input type="text" id="route" placeholder="Identificador de Ruta (ej. CEDIS-Norte)" maxlength="100">
            <input type="number" id="fuel" placeholder="Combustible Consumido (Litros)" step="0.01" min="0.01">
            <input type="number" id="mileage" placeholder="Distancia Recorrida (km)" step="0.1" min="0.1">
            <button onclick="postTelemetry()">EJECUTAR REGISTRO</button>
            <table id="tel-table"><thead><tr><th>Ruta</th><th>km</th><th>L</th><th>km/L</th></tr></thead><tbody></tbody></table>
        </div>
        <div class="card">
            <h2>2. Bitácora de Componentes Críticos</h2>
            <input type="text" id="comp" placeholder="Componente (ej. Kit Arrastre, Aceite, Frenos)" maxlength="100">
            <select id="status">
                <option value="OPTIMO">ESTADO: ÓPTIMO</option>
                <option value="DESGASTE">ESTADO: DESGASTE MODERADO</option>
                <option value="CRITICO">ESTADO: CRÍTICO / REEMPLAZO</option>
            </select>
            <input type="number" id="odo" placeholder="Odómetro Actual (km)" step="1" min="0">
            <button onclick="postMaintenance()">ACTUALIZAR BITÁCORA</button>
            <table id="mnt-table"><thead><tr><th>Componente</th><th>Estado</th><th>Odómetro</th></tr></thead><tbody></tbody></table>
        </div>
    </div>
    <script>
        const log = (msg, err = false) => {
            const el = document.getElementById('sys-log');
            el.style.color = err ? '#ef4444' : '#10b981';
            el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        };

        async function loadAll() {
            const [tRes, mRes] = await Promise.all([fetch('/telemetry'), fetch('/maintenance')]);
            const tData = await tRes.json();
            const mData = await mRes.json();

            const tBody = document.querySelector('#tel-table tbody');
            tBody.innerHTML = '';
            tData.forEach(r => {
                const tr = document.createElement('tr');
                [r.route_name, r.mileage.toFixed(1), r.fuel_consumed.toFixed(2), r.efficiency.toFixed(2)].forEach(val => {
                    const td = document.createElement('td');
                    td.textContent = val;
                    tr.appendChild(td);
                });
                tBody.appendChild(tr);
            });

            const mBody = document.querySelector('#mnt-table tbody');
            mBody.innerHTML = '';
            mData.forEach(m => {
                const tr = document.createElement('tr');
                const tdComp = document.createElement('td'); tdComp.textContent = m.component;
                const tdStat = document.createElement('td'); tdStat.textContent = m.status; tdStat.className = `badge-${m.status}`;
                const tdOdo = document.createElement('td'); tdOdo.textContent = `${m.odometer} km`;
                tr.append(tdComp, tdStat, tdOdo);
                mBody.appendChild(tr);
            });
        }

        async function postTelemetry() {
            const payload = {
                route_name: document.getElementById('route').value.trim(),
                fuel_consumed: parseFloat(document.getElementById('fuel').value),
                mileage: parseFloat(document.getElementById('mileage').value)
            };
            const res = await fetch('/telemetry', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            if (res.ok) {
                log('Telemetría consolidada en base de datos.');
                document.getElementById('route').value = ''; document.getElementById('fuel').value = ''; document.getElementById('mileage').value = '';
                loadAll();
            } else { log('Error de validación en datos de ruta.', true); }
        }

        async function postMaintenance() {
            const payload = {
                component: document.getElementById('comp').value.trim(),
                status: document.getElementById('status').value,
                odometer: parseFloat(document.getElementById('odo').value)
            };
            const res = await fetch('/maintenance', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            if (res.ok) {
                log('Bitácora de mantenimiento actualizada.');
                document.getElementById('comp').value = ''; document.getElementById('odo').value = '';
                loadAll();
            } else { log('Error de validación en bitácora.', true); }
        }
        window.onload = loadAll;
    </script>
</body>
</html>"""

@app.post("/telemetry")
def add_telemetry(data: TelemetryRecord, db: sqlite3.Connection = Depends(get_db)):
    efficiency = round(data.mileage / data.fuel_consumed, 2)
    try:
        db.execute(
            "INSERT INTO telemetry (route_name, fuel_consumed, mileage, efficiency) VALUES (?, ?, ?, ?)",
            (data.route_name, data.fuel_consumed, data.mileage, efficiency)
        )
        db.commit()
        return {"status": "ok", "efficiency": efficiency}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/telemetry")
def get_telemetry(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 15;").fetchall()
    return [dict(r) for r in rows]

@app.post("/maintenance")
def add_maintenance(data: MaintenanceRecord, db: sqlite3.Connection = Depends(get_db)):
    try:
        db.execute(
            "INSERT INTO maintenance (component, status, odometer) VALUES (?, ?, ?)",
            (data.component, data.status, data.odometer)
        )
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/maintenance")
def get_maintenance(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM maintenance ORDER BY id DESC LIMIT 15;").fetchall()
    return [dict(r) for r in rows]
