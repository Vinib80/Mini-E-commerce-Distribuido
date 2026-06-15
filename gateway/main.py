import httpx
import itertools
import asyncio
import logging
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PRODUCTS_REPLICAS = ["http://localhost:5002", "http://localhost:5012"]
products_replica_iterator = itertools.cycle(PRODUCTS_REPLICAS)

SERVICES_URLS = [
    "http://localhost:5001",
    "http://localhost:5002",
    "http://localhost:5012",
    "http://localhost:5003"
]

SERVICE_STATUS = {url: {"up": True, "failures": 0} for url in SERVICES_URLS}

async def heartbeat_task():
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(5)
            for url in SERVICES_URLS:
                try:
                    resp = await client.get(f"{url}/health", timeout=2.0)
                    if resp.status_code == 200:
                        if not SERVICE_STATUS[url]["up"]:
                            logging.info(f"Recuperação: O serviço {url} voltou a responder.")
                            SERVICE_STATUS[url]["up"] = True
                        SERVICE_STATUS[url]["failures"] = 0
                    else:
                        raise Exception(f"Status code {resp.status_code}")
                except Exception as e:
                    if SERVICE_STATUS[url]["up"]:
                        SERVICE_STATUS[url]["failures"] += 1
                        if SERVICE_STATUS[url]["failures"] >= 2:
                            SERVICE_STATUS[url]["up"] = False
                            logging.error(f"Falha detectada: O serviço {url} não respondeu após 2 tentativas.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(heartbeat_task())
    yield
    task.cancel()

app = FastAPI(title="API Gateway", lifespan=lifespan)
security = HTTPBearer()

async def forward_request(method: str, url: str, headers: dict = None, json: dict = None):
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    if base_url in SERVICE_STATUS and not SERVICE_STATUS[base_url]["up"]:
        raise HTTPException(status_code=503, detail="Service Unavailable")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                timeout=5.0
            )
            return response
        except httpx.RequestError as e:
            logging.error(f"Request error to {url}: {e}")
            raise HTTPException(status_code=502, detail=f"Erro de comunicação com o serviço interno: {str(e)}")

@app.get("/products")
async def get_products(request: Request):
    # Round-Robin para leitura
    target_url = next(products_replica_iterator) + "/products"
    
    # Forward the request
    headers = dict(request.headers)
    headers.pop("host", None)
    
    resp = await forward_request("GET", target_url, headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

@app.get("/products/{product_id}")
async def get_product(product_id: int, request: Request):
    # Round-Robin para leitura
    target_url = next(products_replica_iterator) + f"/products/{product_id}"
    
    headers = dict(request.headers)
    headers.pop("host", None)
    
    resp = await forward_request("GET", target_url, headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

@app.post("/products")
async def create_product(request: Request, payload: dict, token: str = Depends(security)):
    # Primary-Secondary: Gateway encaminha escrita apenas para a Primária
    body = payload
    
    # Repassa apenas os headers estritamente necessários para não conflitar com o httpx
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    
    primary_url = PRODUCTS_REPLICAS[0] + "/products"
    
    resp = await forward_request("POST", primary_url, headers=headers, json=body)
    return JSONResponse(status_code=resp.status_code, content=resp.json() if resp.content else None)

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, request: Request):
    # Gateway encaminha delete apenas para a Primária
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    
    primary_url = PRODUCTS_REPLICAS[0] + f"/products/{product_id}"
    
    resp = await forward_request("DELETE", primary_url, headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

@app.post("/users/register")
async def register_user(request: Request, payload: dict):
    resp = await forward_request("POST", f"{SERVICES_URLS[0]}/users/register", json=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json() if resp.content else None)

@app.post("/users/login")
async def login_user(request: Request, payload: dict):
    resp = await forward_request("POST", f"{SERVICES_URLS[0]}/users/login", json=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json() if resp.content else None)

@app.get("/users/{user_id}")
async def get_user(user_id: int, request: Request, token: str = Depends(security)):
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    resp = await forward_request("GET", f"{SERVICES_URLS[0]}/users/{user_id}", headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

@app.post("/orders")
async def create_order(request: Request, payload: dict, token: str = Depends(security)):
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    resp = await forward_request("POST", f"{SERVICES_URLS[3]}/orders", headers=headers, json=payload)
    return JSONResponse(status_code=resp.status_code, content=resp.json() if resp.content else None)

@app.get("/orders/{user_id}")
async def get_user_orders(user_id: int, request: Request, token: str = Depends(security)):
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    resp = await forward_request("GET", f"{SERVICES_URLS[3]}/orders/{user_id}", headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
