from fastapi import FastAPI, Request
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

# ====== Archivo plano ======
DATA_FILE = "/data/notas.txt"

# ====== Config DB (desde docker-compose) ======
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "usuario")
DB_PASS = os.getenv("DB_PASS", "password123")
DB_NAME = os.getenv("DB_NAME", "notasdb")

def get_conn():
    """Crea una conexión a PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME,
        cursor_factory=RealDictCursor,
    )

def init_db_with_retry(retries: int = 20, delay: int = 3):
    """Espera a que la DB esté lista y crea la tabla si no existe."""
    for i in range(retries):
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notas (
                        id SERIAL PRIMARY KEY,
                        contenido TEXT NOT NULL,
                        creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                conn.commit()
            print("✅ DB lista y tabla 'notas' verificada/creada.")
            return
        except Exception as e:
            print(f"⏳ Esperando DB ({i+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("No fue posible conectar a la DB tras varios intentos.")

@app.on_event("startup")
def startup_event():
    # Asegura que la carpeta del archivo exista
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    # Prepara la DB
    init_db_with_retry()

@app.post("/nota")
async def guardar_nota(request: Request):
    # 1) Guardar en archivo
    nota = await request.body()
    with open(DATA_FILE, "a") as f:
        f.write(nota.decode() + "\n")

    # 2) Guardar también en la base de datos
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO notas (contenido) VALUES (%s);", (nota,))
        conn.commit()

    return {"mensaje": "Nota guardada (archivo + DB)"}

@app.get("/conteo")
def contar_lineas():
    if not os.path.exists(DATA_FILE):
        return {"cantidad_de_lineas": 0}
    with open(DATA_FILE, "r") as f:
        lineas = f.readlines()
    return {"cantidad_de_lineas": len(lineas)}

@app.get("/")
def leer_notas():
    if not os.path.exists(DATA_FILE):
        return {"notas": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return {"notas": f.read().splitlines()}
    

@app.get("/notas-db")
def leer_notas_db():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, contenido, creada_en FROM notas ORDER BY creada_en DESC;")
        notas = cur.fetchall()
    return {"notas": notas}

@app.get("/autor")
def obtener_autor():
    # Lee el nombre del autor desde una variable de entorno
    autor = os.getenv("AUTOR", "Desconocido")
    return {"autor": autor}