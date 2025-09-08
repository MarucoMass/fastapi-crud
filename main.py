# main.py - Paso 4: Dependency Injection

from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Annotated
from datetime import datetime
import time

# Crear la instancia de FastAPI
app = FastAPI(title="Mi API Tutorial", version="1.0.0")

# Security scheme para demos
security = HTTPBearer()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None
    total_price: float
    created_at: datetime

class User(BaseModel):
    name: str
    email: EmailStr
    age: int
    is_active: bool = True

class RequestLog(BaseModel):
    timestamp: datetime
    method: str
    path: str
    duration_ms: float

# Base de datos falsa
fake_items_db = []
fake_users_db = []
request_logs = []

# ============================================================================
# DEPENDENCIES (Dependencias)
# ============================================================================

def get_db():
    """Simulación de conexión a base de datos"""
    print("🔌 Conectando a la base de datos...")
    try:
        # Aquí normalmente estarías creando una conexión real
        db_connection = {"status": "connected", "type": "fake_db"}
        yield db_connection  # yield permite cleanup automático
    finally:
        print("🔌 Cerrando conexión a la base de datos...")

def validate_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validar API key simple (demo de autenticación)"""
    valid_token = "mi-api-key-secreta"
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorización requerido"
        )
    
    if credentials.credentials != valid_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    
    return credentials.credentials

def get_current_user(token: str = Depends(validate_api_key)):
    """Obtener usuario actual basado en el token"""
    # En una app real, decodificarías el JWT y obtendrías el usuario de la DB
    return {
        "id": 1,
        "name": "Usuario Demo",
        "email": "user@example.com",
        "role": "admin"
    }

def log_request():
    """Dependencia para logging de requests"""
    start_time = time.time()
    
    def create_log(method: str, path: str):
        duration = (time.time() - start_time) * 1000  # ms
        log_entry = RequestLog(
            timestamp=datetime.now(),
            method=method,
            path=path,
            duration_ms=round(duration, 2)
        )
        request_logs.append(log_entry.model_dump())
        print(f"📝 {method} {path} - {duration:.2f}ms")
    
    return create_log

# Dependencias con parámetros
def common_parameters(
    skip: int = Query(0, ge=0, description="Número de elementos a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de elementos"),
    search: Optional[str] = Query(None, description="Texto a buscar")
):
    """Parámetros comunes para paginación y búsqueda"""
    return {"skip": skip, "limit": limit, "search": search}

def validate_item_data(item: Item):
    """Validaciones de negocio para items"""
    if item.price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El precio debe ser mayor a 0"
        )
    
    if item.tax and (item.tax < 0 or item.tax > 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El impuesto debe estar entre 0 y 100"
        )
    
    return item

# ============================================================================
# ENDPOINTS SIN AUTENTICACIÓN
# ============================================================================

@app.get("/")
def read_root():
    return {"message": "¡Hola mundo con FastAPI!"}

@app.get("/health")
def health_check(db = Depends(get_db), logger = Depends(log_request)):
    """Endpoint de salud que usa dependencias"""
    logger("GET", "/health")
    return {
        "status": "healthy",
        "database": db["status"],
        "timestamp": datetime.now()
    }

# ============================================================================
# ENDPOINTS PÚBLICOS CON DEPENDENCIAS
# ============================================================================

@app.get("/items/", response_model=list[ItemResponse])
def get_items(
    commons: dict = Depends(common_parameters),
    db = Depends(get_db),
    logger = Depends(log_request)
):
    """Obtener items con paginación y búsqueda"""
    logger("GET", "/items/")
    
    items = fake_items_db.copy()
    
    # Aplicar búsqueda si existe
    if commons["search"]:
        search_term = commons["search"].lower()
        items = [
            item for item in items 
            if search_term in item["name"].lower() or 
               (item["description"] and search_term in item["description"].lower())
        ]
    
    # Aplicar paginación
    start = commons["skip"]
    end = start + commons["limit"]
    paginated_items = items[start:end]
    
    if not paginated_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron items"
        )
    
    return paginated_items

@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: int,
    db = Depends(get_db),
    logger = Depends(log_request)
):
    """Obtener un item específico"""
    logger("GET", f"/items/{item_id}")
    
    if item_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID debe ser un número positivo"
        )
    
    for item in fake_items_db:
        if item["id"] == item_id:
            return item
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Item con ID {item_id} no encontrado"
    )

# ============================================================================
# ENDPOINTS PROTEGIDOS (requieren autenticación)
# ============================================================================

@app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    validated_item: Item = Depends(validate_item_data),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    logger = Depends(log_request)
):
    """Crear item (requiere autenticación)"""
    logger("POST", "/items/")
    
    # Verificar si ya existe
    for existing_item in fake_items_db:
        if existing_item["name"].lower() == validated_item.name.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un item con el nombre '{validated_item.name}'"
            )
    
    # Crear item
    item_id = len(fake_items_db) + 1
    created_at = datetime.now()
    
    total_price = validated_item.price
    if validated_item.tax:
        total_price += validated_item.price * (validated_item.tax / 100)
    
    item_response = ItemResponse(
        id=item_id,
        name=validated_item.name,
        description=validated_item.description,
        price=validated_item.price,
        tax=validated_item.tax,
        total_price=total_price,
        created_at=created_at
    )
    
    fake_items_db.append(item_response.model_dump())
    
    print(f"✅ Item creado por usuario: {current_user['name']}")
    return item_response

@app.put("/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    validated_item: Item = Depends(validate_item_data),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    logger = Depends(log_request)
):
    """Actualizar item (requiere autenticación)"""
    logger("PUT", f"/items/{item_id}")
    
    if item_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID debe ser un número positivo"
        )
    
    # Buscar item
    item_index = None
    for i, existing_item in enumerate(fake_items_db):
        if existing_item["id"] == item_id:
            item_index = i
            break
    
    if item_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item con ID {item_id} no encontrado"
        )
    
    # Actualizar
    total_price = validated_item.price
    if validated_item.tax:
        total_price += validated_item.price * (validated_item.tax / 100)
    
    updated_item = ItemResponse(
        id=item_id,
        name=validated_item.name,
        description=validated_item.description,
        price=validated_item.price,
        tax=validated_item.tax,
        total_price=total_price,
        created_at=fake_items_db[item_index]["created_at"]
    )
    
    fake_items_db[item_index] = updated_item.model_dump()
    
    print(f"✅ Item actualizado por usuario: {current_user['name']}")
    return updated_item

@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    logger = Depends(log_request)
):
    """Eliminar item (requiere autenticación)"""
    logger("DELETE", f"/items/{item_id}")
    
    if item_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID debe ser un número positivo"
        )
    
    for i, item in enumerate(fake_items_db):
        if item["id"] == item_id:
            fake_items_db.pop(i)
            print(f"✅ Item eliminado por usuario: {current_user['name']}")
            return
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Item con ID {item_id} no encontrado"
    )

# ============================================================================
# ENDPOINTS ADMINISTRATIVOS
# ============================================================================

@app.get("/admin/logs")
def get_logs(
    current_user: dict = Depends(get_current_user),
    commons: dict = Depends(common_parameters)
):
    """Ver logs de requests (solo admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    
    # Aplicar paginación
    start = commons["skip"]
    end = start + commons["limit"]
    paginated_logs = request_logs[start:end]
    
    return {
        "total_logs": len(request_logs),
        "returned": len(paginated_logs),
        "logs": paginated_logs
    }

@app.get("/admin/stats")
def get_stats(current_user: dict = Depends(get_current_user)):
    """Estadísticas del sistema (solo admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    
    return {
        "total_items": len(fake_items_db),
        "total_users": len(fake_users_db),
        "total_requests": len(request_logs),
        "current_user": current_user["name"]
    }

# Para ejecutar: uvicorn main:app --reload

"""
CÓMO PROBAR LA AUTENTICACIÓN:

1. Ve a http://localhost:8000/docs
2. Para endpoints protegidos, haz clic en el candado 🔒
3. En "Value" pon: mi-api-key-secreta
4. Ahora puedes acceder a endpoints protegidos

ENDPOINTS SIN AUTH:
- GET / 
- GET /health
- GET /items/ 
- GET /items/{id}

ENDPOINTS CON AUTH:
- POST /items/
- PUT /items/{id}
- DELETE /items/{id}
- GET /admin/logs
- GET /admin/stats
"""