import sqlite3
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from .schemas import OrderCreate, OrderResponse
from .database import get_db_connection
from .auth import verify_token

router = APIRouter()

@router.post("/orders", status_code=status.HTTP_201_CREATED, response_model=OrderResponse)
def create_order(order: OrderCreate, payload: dict = Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO orders (user_id, product_id, quantity)
        VALUES (?, ?, ?)
    ''', (order.user_id, order.product_id, order.quantity))
    
    order_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute('SELECT id, user_id, product_id, quantity, created_at FROM orders WHERE id = ?', (order_id,))
    row = cursor.fetchone()
    conn.close()
    
    return OrderResponse(
        id=row[0],
        user_id=row[1],
        product_id=row[2],
        quantity=row[3],
        created_at=row[4]
    )

@router.get("/orders/{user_id}", response_model=List[OrderResponse])
def list_user_orders(user_id: int, payload: dict = Depends(verify_token)):
    # Opcional: verificar se o usuário no token é o mesmo que está buscando os pedidos ou se é admin
    # if payload.get("sub") != str(user_id) and payload.get("role") != "admin":
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, user_id, product_id, quantity, created_at FROM orders WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        OrderResponse(
            id=row[0],
            user_id=row[1],
            product_id=row[2],
            quantity=row[3],
            created_at=row[4]
        ) for row in rows
    ]

@router.get("/health")
def health_check():
    return {"status": "ok"}
