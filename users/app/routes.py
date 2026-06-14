import sqlite3
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, status, Depends
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
from .schemas import UserCreate, UserResponse, UserLogin, Token
from .database import get_db_connection
from .auth import create_access_token, verify_token

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

@router.post("/users/login", response_model=Token)
def login_user(user: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, password_hash, role FROM users WHERE email = ?', (user.email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(user.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas"
        )
        
    access_token = create_access_token(data={"sub": str(row[0]), "role": row[2]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, payload: dict = Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, email, role FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        
    return UserResponse(
        id=row[0],
        name=row[1],
        email=row[2],
        role=row[3]
    )

@router.get("/health")
def health_check():
    return {"status": "ok"}
