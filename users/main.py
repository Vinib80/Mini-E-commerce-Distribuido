import sqlite3
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from passlib.context import CryptContext
from contextlib import asynccontextmanager

# Configurar passlib para usar bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados no startup
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

class UserRegister(BaseModel):
    name: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

@app.post("/users/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register_user(user: UserRegister):
    hashed_password = pwd_context.hash(user.password)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
        ''', (user.name, user.email, hashed_password))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute('SELECT id, name, email, role FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        
        return UserResponse(
            id=row[0],
            name=row[1],
            email=row[2],
            role=row[3]
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email já cadastrado"
        )
    finally:
        conn.close()

@app.get("/health")
def health_check():
    return {"status": "ok"}
