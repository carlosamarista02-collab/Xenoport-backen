import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from typing import List, Optional
import uvicorn
# ✅ AGREGADO: Import necesario para permitir conexiones externas (CORS)
from fastapi.middleware.cors import CORSMiddleware

# ============ CONFIGURACIÓN ============
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Faltan las variables SUPABASE_URL o SUPABASE_KEY en Render")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI(title="Xenoport API")

# ============ CONFIGURACIÓN DE CORS (MUY IMPORTANTE) ============
# Esto le dice al Backend que permita conexiones desde el Bot, el Juego (Netlify) y cualquier otro lado.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir cualquier origen (dominio)
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, PUT, OPTIONS, etc.)
    allow_headers=["*"],
)

# ============ MODELOS DE DATOS ============
class UserData(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None
    telegram_name: Optional[str] = None

class WalletRequest(BaseModel):
    telegram_id: int
    telegram_name: str
    type: str
    amount: float
    currency: str = "USDT"
    network: Optional[str] = None
    txid: Optional[str] = None

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
        "fuel_available": 0
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

@app.get("/api/users")
async def get_all_users():
    response = supabase.table('users').select('*').execute()
    return response.data

@app.get("/api/stats")
async def get_stats():
    users = supabase.table('users').select('*').execute()
    total_users = len(users.data)
    total_usdt = sum(u.get('balance_usdt', 0) for u in users.data)
    total_stars = sum(u.get('balance_stars', 0) for u in users.data)
    total_ships = sum(len(u.get('ships', [])) for u in users.data)
    
    return {
        "total_users": total_users,
        "total_usdt": total_usdt,
        "total_stars": total_stars,
        "total_ships": total_ships,
        "pending_requests": 0
    }

@app.post("/api/wallet-requests")
async def create_wallet_request(request: WalletRequest):
    data = request.dict()
    data['status'] = 'pending'
    insert_response = supabase.table('wallet_requests').insert(data).execute()
    if insert_response.data:
        return insert_response.data[0]
    raise HTTPException(status_code=500, detail="Error al crear la solicitud")

@app.get("/api/wallet-requests/pending")
async def get_pending_requests():
    response = supabase.table('wallet_requests').select('*').eq('status', 'pending').execute()
    return response.data

@app.put("/api/wallet-requests/{request_id}")
async def update_request_status(request_id: int, data: dict):
    status = data.get("status")
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    req_response = supabase.table('wallet_requests').select('*').eq('id', request_id).execute()
    if not req_response.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    request_data = req_response.data[0]
    update_response = supabase.table('wallet_requests').update({"status": status}).eq('id', request_id).execute()
    
    if status == "approved" and request_data.get('type') == 'deposit':
        user_id = request_data.get('telegram_id')
        amount = request_data.get('amount', 0)
        supabase.table('users').update({
            "balance_usdt": supabase.table('users').select('balance_usdt').eq('telegram_id', user_id).execute().data[0]['balance_usdt'] + amount
        }).eq('telegram_id', user_id).execute()
        
    return update_response.data[0] if update_response.data else {"status": "updated"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
