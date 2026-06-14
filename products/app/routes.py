import sqlite3
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from .schemas import ProductCreate, ProductResponse
from .database import get_db_connection
from .auth import require_admin

router = APIRouter()

@router.get("/products", response_model=List[ProductResponse])
def list_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, price, stock FROM products')
    rows = cursor.fetchall()
    conn.close()
    
    return [
        ProductResponse(
            id=row[0],
            name=row[1],
            description=row[2],
            price=row[3],
            stock=row[4]
        ) for row in rows
    ]

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, price, stock FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        
    return ProductResponse(
        id=row[0],
        name=row[1],
        description=row[2],
        price=row[3],
        stock=row[4]
    )

@router.post("/products", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
def create_product(product: ProductCreate, payload: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO products (name, description, price, stock)
        VALUES (?, ?, ?, ?)
    ''', (product.name, product.description, product.price, product.stock))
    
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return ProductResponse(
        id=product_id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock
    )

@router.get("/health")
def health_check():
    return {"status": "ok"}
