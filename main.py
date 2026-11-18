from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import sqlite3
import os

app = FastAPI(title="Proyecto Demonion - Telemetría Vehicular", version="2.0.0")

DB_FILE = "demonion.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Decisión autónoma adversarial: Activar WAL para evitar bloqueos por concurrencia
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_name TEXT NOT NULL,
            fuel_consumed REAL NOT NULL,
            mileage REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

class TelemetryRecord(BaseModel):
    route_name: str = Field(..., min_length=1, max_length=100)
    fuel_consumed: float = Field(..., gt=0)
    mileage: float = Field(..., gt=0)

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Demonion MVP - Cyber Tech</title>
        <style>
            body { background-color: #0d1117; color: #c9d1d9; font-family: monospace; padding: 20px; }
            h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
            .card { background: #161b22; border: 1px solid #30363d; padding: 15px; margin-bottom: 15px; border-radius: 6px; }
            input, button { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 8px; margin: 5px 0; font-family: monospace; }
            button { background: #238636; cursor: pointer; font-weight: bold; }
            button:hover { background: #2ea043; }
        </style>
    </head>
    <body>
        <h1>DEMONION // TELEMETRY_MVP</h1>
        <div class="card">
            <h3>Registro de Ruta</h3>
            <input type="text" id="route" placeholder="Nombre de Ruta" required><br>
            <input type="number" id="fuel" placeholder="Combustible (L)" step="0.1" required><br>
            <input type="number" id="mileage" placeholder="Kilometraje (km)" step="0.1" required><br>
            <button onclick="sendData()">Registrar Datos</button>
        </div>
        <div class="card" id="status">Estado del Sistema: Operativo</div>
        <script>
            async function sendData() {
                const route = document.getElementById('route').value;
                const fuel = parseFloat(document.getElementById('fuel').value);
                const mileage = parseFloat(document.getElementById('mileage').value);
                if(!route || isNaN(fuel) || isNaN(mileage)) {
                    alert("Complete los campos correctamente.");
                    return;
                }
                const res = await fetch('/telemetry', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({route_name: route, fuel_consumed: fuel, mileage: mileage})
                });
                if(res.ok) {
                    document.getElementById('status').innerText = "Estado: Registro guardado exitosamente.";
                } else {
                    document.getElementById('status').innerText = "Estado: Error en la transacción.";
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/telemetry")
def add_telemetry(data: TelemetryRecord, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO telemetry (route_name, fuel_consumed, mileage) VALUES (?, ?, ?)",
            (data.route_name, data.fuel_consumed, data.mileage)
        )
        db.commit()
        return {"status": "success", "message": "Telemetría registrada correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/telemetry")
def get_telemetry(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 50;")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]
