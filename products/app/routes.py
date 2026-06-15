import sqlite3
import os
import httpx
from fastapi import APIRouter, HTTPException, status, Depends, Request
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
async def create_product(product: ProductCreate, request: Request, payload: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO products (name, description, price, stock)
        VALUES (?, ?, ?, ?)
    ''', (product.name, product.description, product.price, product.stock))
    
    product_id = cursor.lastrowid
    conn.commit()
    
    response_data = ProductResponse(
        id=product_id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock
    )
    
    # Lógica de Replicação Primary-Secondary
    secondary_url = os.getenv("SECONDARY_URL")
    if secondary_url:
        async with httpx.AsyncClient() as client:
            try:
                # Passa adiante o mesmo token de admin via headers
                headers = {"Authorization": request.headers.get("Authorization", "")}
                resp = await client.post(
                    f"{secondary_url}/internal/replicate/products",
                    json=response_data.model_dump(),
                    headers=headers,
                    timeout=5.0
                )
                resp.raise_for_status()
            except Exception as e:
                # Rollback local se a replicação falhar
                cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
                conn.commit()
                conn.close()
                raise HTTPException(status_code=500, detail=f"Falha na replicação para a Secundária: {str(e)}")
                
    conn.close()
    return response_data

@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, request: Request, payload: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    conn.commit()
    
    # Lógica de Replicação Primary-Secondary
    secondary_url = os.getenv("SECONDARY_URL")
    if secondary_url:
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": request.headers.get("Authorization", "")}
                resp = await client.delete(
                    f"{secondary_url}/internal/replicate/products/{product_id}",
                    headers=headers,
                    timeout=5.0
                )
                resp.raise_for_status()
            except Exception as e:
                # Como o delete local já ocorreu, logar o erro de desincronização
                conn.close()
                raise HTTPException(status_code=500, detail=f"Delete local realizado, mas replicação falhou: {str(e)}")

    conn.close()
    return None

# Rotas internas para serem chamadas unicamente pela Primária
@router.post("/internal/replicate/products", status_code=status.HTTP_201_CREATED)
def replicate_create_product(product: ProductResponse, payload: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO products (id, name, description, price, stock)
            VALUES (?, ?, ?, ?, ?)
        ''', (product.id, product.name, product.description, product.price, product.stock))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Produto com este ID já existe na secundária.")
    conn.close()
    return {"status": "replicated"}

@router.delete("/internal/replicate/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def replicate_delete_product(product_id: int, payload: dict = Depends(require_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    return None

@router.get("/health")
def health_check():
    return {"status": "ok"}
