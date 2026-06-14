import sqlite3
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, status
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
from .schemas import UserCreate, UserResponse
from .database import get_db_connection

router = APIRouter()

# Configurar passlib para usar bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/users/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register_user(user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    
    conn = get_db_connection()
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

@router.get("/health")
def health_check():
    return {"status": "ok"}
