# # app/main.py - Paso 6: FastAPI con autenticación JWT completa

from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
from datetime import timedelta

from .database import get_db, create_tables
from .models import User as UserModel, Item as ItemModel
from .schemas import (
    User, UserCreate, UserUpdate, UserWithItems,
    Item, ItemCreate, ItemUpdate, ItemResponse, ItemWithOwner,
    MessageResponse, Token
)
from .auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

app = FastAPI(
    title="Mi API Tutorial con JWT Async",
    version="1.0.0",
    description="API completa con autenticación JWT y SQLAlchemy Async"
)

# Startup: crear tablas
@app.on_event("startup")
async def startup_event():
    await create_tables()
    print("✅ Tablas creadas/verificadas en la base de datos")

# Dependencias comunes
def common_parameters(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    return {"skip": skip, "limit": limit, "search": search}

# -------------------
# Endpoints públicos
# -------------------

@app.get("/")
def read_root():
    return {"message": "¡API Async con JWT funcionando!", "docs": "/docs"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )

# -------------------
# Auth endpoints
# -------------------

@app.post("/auth/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).filter(UserModel.email == user.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Usuario ya existe")

    hashed_password = get_password_hash(user.password)
    db_user = UserModel(
        name=user.name,
        email=user.email,
        age=user.age,
        hashed_password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post("/auth/login", response_model=Token)
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: UserModel = Depends(get_current_active_user)):
    return current_user

# -------------------
# Usuarios
# -------------------

@app.get("/users/", response_model=List[User])
async def get_users(
    commons: dict = Depends(common_parameters),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = select(UserModel)
    if commons["search"]:
        search_term = f"%{commons['search']}%"
        query = query.filter(
            UserModel.name.ilike(search_term) |
            UserModel.email.ilike(search_term)
        )
    result = await db.execute(query.offset(commons["skip"]).limit(commons["limit"]))
    users = result.scalars().all()
    if not users:
        raise HTTPException(status_code=404, detail="No se encontraron usuarios")
    return users

@app.get("/users/{user_id}", response_model=UserWithItems)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

# -------------------
# Items
# -------------------

@app.get("/items/", response_model=List[ItemResponse])
async def get_items(commons: dict = Depends(common_parameters), db: AsyncSession = Depends(get_db)):
    query = select(ItemModel)
    if commons["search"]:
        search_term = f"%{commons['search']}%"
        query = query.filter(
            ItemModel.name.ilike(search_term) |
            ItemModel.description.ilike(search_term)
        )
    result = await db.execute(query.offset(commons["skip"]).limit(commons["limit"]))
    items = result.scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No se encontraron items")
    return [ItemResponse.from_orm_with_total(item) for item in items]

@app.get("/items/{item_id}", response_model=ItemWithOwner)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ItemModel).filter(ItemModel.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return item

@app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreate, db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    result = await db.execute(select(ItemModel).filter(ItemModel.name == item.name, ItemModel.owner_id == current_user.id))
    existing_item = result.scalars().first()
    if existing_item:
        raise HTTPException(status_code=409, detail="Ya tienes un item con este nombre")
    db_item = ItemModel(**item.dict(), owner_id=current_user.id)
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return ItemResponse.from_orm_with_total(db_item)

# Otros endpoints de items (update, delete, my-items) se adaptan igual: async + await db.commit()/refresh()

# -------------------
# Estadísticas
# -------------------

@app.get("/stats")
async def get_public_stats(db: AsyncSession = Depends(get_db)):
    total_users = (await db.execute(select(UserModel))).scalars().count()
    total_items = (await db.execute(select(ItemModel))).scalars().count()
    return {"total_users": total_users, "total_items": total_items}

@app.get("/my-stats")
async def get_my_stats(db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_active_user)):
    result = await db.execute(select(ItemModel).filter(ItemModel.owner_id == current_user.id))
    my_items_count = len(result.scalars().all())
    return {"user": current_user.name, "email": current_user.email, "my_items_count": my_items_count, "member_since": current_user.created_at}


# from fastapi import FastAPI, HTTPException, status, Depends, Query
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session
# from typing import Optional, List
# from datetime import timedelta

# # Importar nuestros módulos
# from .database import get_db, create_tables
# from .models import User as UserModel, Item as ItemModel
# from .schemas import (
#     User, UserCreate, UserUpdate, UserWithItems,
#     Item, ItemCreate, ItemUpdate, ItemResponse, ItemWithOwner,
#     MessageResponse, Token
# )
# from .auth import (
#     get_password_hash, authenticate_user, create_access_token,
#     get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
# )

# # Crear la instancia de FastAPI
# app = FastAPI(
#     title="Mi API Tutorial con JWT",
#     version="1.0.0",
#     description="API completa con autenticación JWT y SQLAlchemy"
# )

# # ============================================================================
# # STARTUP EVENT - CREAR TABLAS
# # ============================================================================

# @app.on_event("startup")
# def startup_event():
#     """Crear tablas al iniciar la aplicación"""
#     create_tables()
#     print("✅ Tablas creadas/verificadas en la base de datos")

# # ============================================================================
# # DEPENDENCIES
# # ============================================================================

# def common_parameters(
#     skip: int = Query(0, ge=0, description="Elementos a saltar"),
#     limit: int = Query(10, ge=1, le=100, description="Máximo de elementos"),
#     search: Optional[str] = Query(None, description="Texto a buscar")
# ):
#     """Parámetros comunes para paginación"""
#     return {"skip": skip, "limit": limit, "search": search}

# # ============================================================================
# # ENDPOINTS PÚBLICOS
# # ============================================================================

# @app.get("/")
# def read_root():
#     return {
#         "message": "¡API con autenticación JWT funcionando!",
#         "docs": "/docs",
#         "auth_endpoint": "/auth/login"
#     }

# @app.get("/health")
# def health_check(db: Session = Depends(get_db)):
#     """Health check"""
#     try:
#         db.execute("SELECT 1")
#         return {
#             "status": "healthy",
#             "database": "connected"
#         }
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail=f"Database error: {str(e)}"
#         )

# # ============================================================================
# # ENDPOINTS DE AUTENTICACIÓN
# # ============================================================================

# @app.post("/auth/register", response_model=User, status_code=status.HTTP_201_CREATED)
# def register_user(user: UserCreate, db: Session = Depends(get_db)):
#     """Registrar nuevo usuario"""
    
#     # Verificar si el email ya existe
#     existing_user = db.query(UserModel).filter(UserModel.email == user.email).first()
#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="Ya existe un usuario con este email"
#         )
    
#     # Crear usuario con password hasheado
#     user_data = user.dict()
#     password = user_data.pop("password")
#     hashed_password = get_password_hash(password)
    
#     db_user = UserModel(**user_data, hashed_password=hashed_password)
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
    
#     return db_user

# @app.post("/auth/login", response_model=Token)
# def login_user(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db)
# ):
#     """Login y obtener JWT token"""
    
#     # Autenticar usuario
#     user = authenticate_user(db, form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Email o password incorrectos",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     # Crear token
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(
#         data={"sub": user.email}, expires_delta=access_token_expires
#     )
    
#     return {"access_token": access_token, "token_type": "bearer"}

# @app.get("/auth/me", response_model=User)
# def get_current_user_info(current_user: UserModel = Depends(get_current_active_user)):
#     """Obtener información del usuario actual"""
#     return current_user

# # ============================================================================
# # ENDPOINTS DE USUARIOS
# # ============================================================================

# @app.get("/users/", response_model=List[User])
# def get_users(
#     commons: dict = Depends(common_parameters),
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)  # Requiere auth
# ):
#     """Obtener lista de usuarios (requiere autenticación)"""
    
#     query = db.query(UserModel)
    
#     if commons["search"]:
#         search_term = f"%{commons['search']}%"
#         query = query.filter(
#             UserModel.name.ilike(search_term) |
#             UserModel.email.ilike(search_term)
#         )
    
#     users = query.offset(commons["skip"]).limit(commons["limit"]).all()
    
#     if not users:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No se encontraron usuarios"
#         )
    
#     return users

# @app.get("/users/{user_id}", response_model=UserWithItems)
# def get_user(
#     user_id: int,
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Obtener usuario específico con sus items"""
    
#     user = db.query(UserModel).filter(UserModel.id == user_id).first()
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Usuario no encontrado"
#         )
    
#     return user

# # ============================================================================
# # ENDPOINTS DE ITEMS
# # ============================================================================

# @app.get("/items/", response_model=List[ItemResponse])
# def get_items(
#     commons: dict = Depends(common_parameters),
#     db: Session = Depends(get_db)
# ):
#     """Obtener items (público)"""
    
#     query = db.query(ItemModel)
    
#     if commons["search"]:
#         search_term = f"%{commons['search']}%"
#         query = query.filter(
#             ItemModel.name.ilike(search_term) |
#             ItemModel.description.ilike(search_term)
#         )
    
#     items = query.offset(commons["skip"]).limit(commons["limit"]).all()
    
#     if not items:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No se encontraron items"
#         )
    
#     return [ItemResponse.from_orm_with_total(item) for item in items]

# @app.get("/items/{item_id}", response_model=ItemWithOwner)
# def get_item(item_id: int, db: Session = Depends(get_db)):
#     """Obtener item específico (público)"""
    
#     item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
#     if not item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Item no encontrado"
#         )
    
#     return item

# @app.post("/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
# def create_item(
#     item: ItemCreate,
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Crear item (requiere autenticación)"""
    
#     # Verificar si ya existe un item con el mismo nombre del usuario actual
#     existing_item = db.query(ItemModel).filter(
#         ItemModel.name == item.name,
#         ItemModel.owner_id == current_user.id
#     ).first()
    
#     if existing_item:
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="Ya tienes un item con este nombre"
#         )
    
#     # Crear item para el usuario actual
#     db_item = ItemModel(**item.dict(), owner_id=current_user.id)
#     db.add(db_item)
#     db.commit()
#     db.refresh(db_item)
    
#     return ItemResponse.from_orm_with_total(db_item)

# @app.get("/my-items/", response_model=List[ItemResponse])
# def get_my_items(
#     commons: dict = Depends(common_parameters),
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Obtener mis items (requiere autenticación)"""
    
#     query = db.query(ItemModel).filter(ItemModel.owner_id == current_user.id)
    
#     if commons["search"]:
#         search_term = f"%{commons['search']}%"
#         query = query.filter(
#             ItemModel.name.ilike(search_term) |
#             ItemModel.description.ilike(search_term)
#         )
    
#     items = query.offset(commons["skip"]).limit(commons["limit"]).all()
    
#     if not items:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No tienes items todavía"
#         )
    
#     return [ItemResponse.from_orm_with_total(item) for item in items]

# @app.put("/items/{item_id}", response_model=ItemResponse)
# def update_item(
#     item_id: int,
#     item_update: ItemUpdate,
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Actualizar item (solo el dueño)"""
    
#     item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
#     if not item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Item no encontrado"
#         )
    
#     # Verificar que el usuario actual es el dueño
#     if item.owner_id != current_user.id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Solo puedes editar tus propios items"
#         )
    
#     # Actualizar campos
#     update_data = item_update.dict(exclude_unset=True)
#     for field, value in update_data.items():
#         setattr(item, field, value)
    
#     db.commit()
#     db.refresh(item)
    
#     return ItemResponse.from_orm_with_total(item)

# @app.delete("/items/{item_id}", response_model=MessageResponse)
# def delete_item(
#     item_id: int,
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Eliminar item (solo el dueño)"""
    
#     item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
#     if not item:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Item no encontrado"
#         )
    
#     if item.owner_id != current_user.id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Solo puedes eliminar tus propios items"
#         )
    
#     item_name = item.name
#     db.delete(item)
#     db.commit()
    
#     return MessageResponse(message=f"Item '{item_name}' eliminado exitosamente")

# # ============================================================================
# # ENDPOINTS DE ESTADÍSTICAS
# # ============================================================================

# @app.get("/stats")
# def get_public_stats(db: Session = Depends(get_db)):
#     """Estadísticas públicas"""
    
#     total_users = db.query(UserModel).count()
#     total_items = db.query(ItemModel).count()
    
#     return {
#         "total_users": total_users,
#         "total_items": total_items
#     }

# @app.get("/my-stats")
# def get_my_stats(
#     db: Session = Depends(get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     """Mis estadísticas personales"""
    
#     my_items_count = db.query(ItemModel).filter(ItemModel.owner_id == current_user.id).count()
    
#     return {
#         "user": current_user.name,
#         "email": current_user.email,
#         "my_items_count": my_items_count,
#         "member_since": current_user.created_at
#     }

# # Para ejecutar: uvicorn app.main:app --reload

# """
# CÓMO USAR LA AUTENTICACIÓN:

# 1. REGISTRARSE:
#    POST /auth/register
#    {
#      "name": "Juan Pérez",
#      "email": "juan@example.com", 
#      "age": 28,
#      "password": "mi_password_seguro"
#    }

# 2. LOGIN:
#    POST /auth/login
#    username: juan@example.com (¡usar email!)
#    password: mi_password_seguro

# 3. USAR EL TOKEN:
#    - Ve a /docs
#    - Haz clic en "Authorize" 
#    - Pon: Bearer tu_token_aqui
#    - Ahora puedes usar endpoints protegidos

# 4. ENDPOINTS PÚBLICOS (sin token):
#    - GET /
#    - GET /items/
#    - GET /items/{id}
#    - POST /auth/register
#    - POST /auth/login

# 5. ENDPOINTS PROTEGIDOS (necesitan token):
#    - GET /auth/me
#    - POST /items/
#    - GET /my-items/
#    - PUT /items/{id}
#    - DELETE /items/{id}
#    - GET /users/
#    - GET /my-stats
# """