import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# ============ CONFIGURACIÓN ============
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Faltan las variables SUPABASE_URL o SUPABASE_KEY en Render")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI(title="Xenoport API")

# ============ CONFIGURACIÓN DE CORS (Permite la conexión del juego) ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ MODELOS DE DATOS ============
class UserData(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None
    telegram_name: Optional[str] = None

# ============ RUTAS DE LA API ============
@app.get("/")
def read_root():
    return {"message": "Xenoport Backend is running!"}

@app.post("/api/users")
async def create_or_get_user(user: UserData):
    response = supabase.table('users').select('*').eq('telegram_id', user.telegram_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    
    new_user = {
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "telegram_name": user.telegram_name,
        "balance_usdt": 0.0,
        "balance_stars": 0.0,
        "ships": [],
        "aliens": [],
        "planets": [],
        "fuel_available": 0,
        "has_done_expedition": False,
        "active_contract": None
    }
    insert_response = supabase.table('users').insert(new_user).execute()
    if insert_response.data:
        return insert_response.data[0]
    raise HTTPException(status_code=500, detail="Error al crear el usuario")

@app.get("/api/users/{telegram_id}")
async def get_user(telegram_id: int):
    response = supabase.table('users').select('*').eq('telegram_id', telegram_id).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

# ============ RUTAS PARA EL JUEGO HTML ============
@app.post("/api/sync")
async def sync_user_data(data: dict):
    telegram_id = data.get('telegram_id')
    response = supabase.table('users').select('*').eq('telegram_id', telegram_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = {
        'ships': data.get('ships', []),
        'aliens': data.get('aliens', []),
        'planets': data.get('planets', []),
        'balance_usdt': data.get('balance_usdt', 0.0),
        'balance_stars': data.get('balance_stars', 0.0),
        'fuel_available': data.get('fuel_available', 0),
        'has_done_expedition': data.get('has_done_expedition', False),
        'last_expedition_time': data.get('last_expedition_time', None),
        'active_contract': data.get('active_contract', None)
    }
    supabase.table('users').update(update_data).eq('telegram_id', telegram_id).execute()
    return {"status": "synced"}

@app.get("/api/p2p/listings/active")
async def get_active_listings():
    return []

# ============ ARRANQUE ============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
