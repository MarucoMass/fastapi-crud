# app/models.py - Modelos SQLAlchemy (tablas de la base de datos)

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    """Modelo de Usuario"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    items = relationship("Item", back_populates="owner")

class Item(Base):
    """Modelo de Item"""
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    tax = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Foreign Key
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relaciones
    owner = relationship("User", back_populates="items")

class RequestLog(Base):
    """Modelo para logs de requests"""
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    duration_ms = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Opcional
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relación
    user = relationship("User")