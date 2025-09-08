# app/database.py - Configuración de base de datos
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./test.db"  # cambiar a postgresql+asyncpg://user:pass@host/db para prod

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Funciones de inicialización
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# import os

# # URL de la base de datos
# # Para SQLite (desarrollo rápido):
# DATABASE_URL = "sqlite:///./test.db"

# # Para PostgreSQL (producción):
# # DATABASE_URL = "postgresql://usuario:password@localhost/nombre_db"

# # Crear engine
# engine = create_engine(
#     DATABASE_URL,
#     # Solo para SQLite - no usar en PostgreSQL
#     connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
# )

# # Crear SessionLocal class
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # Crear Base class
# Base = declarative_base()

# # Dependency para obtener DB session
# def get_db():
#     """Dependency que proporciona una sesión de base de datos"""
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# # ============================================================================
# # FUNCIONES PARA INICIALIZAR LA BASE DE DATOS
# # ============================================================================

# def create_tables():
#     """Crear todas las tablas"""
#     Base.metadata.create_all(bind=engine)

# def drop_tables():
#     """Eliminar todas las tablas (cuidado!)"""
#     Base.metadata.drop_all(bind=engine)