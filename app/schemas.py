# app/schemas.py - Schemas Pydantic (validación y serialización)

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserBase(BaseModel):
    """Base schema para User"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=18, le=120)
    is_active: bool = True

class UserCreate(UserBase):
    """Schema para crear usuario"""
    password: str = Field(..., min_length=6, max_length=50)

class UserUpdate(BaseModel):
    """Schema para actualizar usuario"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=18, le=120)
    is_active: Optional[bool] = None

class User(UserBase):
    """Schema para respuesta de usuario (sin password)"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class Token(BaseModel):
    """Schema para token JWT"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Schema para datos del token"""
    email: Optional[str] = None

# ============================================================================
# ITEM SCHEMAS
# ============================================================================

class ItemBase(BaseModel):
    """Base schema para Item"""
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0)
    tax: Optional[float] = Field(None, ge=0, le=100)

class ItemCreate(ItemBase):
    """Schema para crear item"""
    pass

class ItemUpdate(BaseModel):
    """Schema para actualizar item"""
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    tax: Optional[float] = Field(None, ge=0, le=100)

class Item(ItemBase):
    """Schema para respuesta de item"""
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ItemWithOwner(Item):
    """Schema de item con información del dueño"""
    owner: User

# ============================================================================
# USER WITH ITEMS
# ============================================================================

class UserWithItems(User):
    """Schema de usuario con sus items"""
    items: List[Item] = []

# ============================================================================
# COMPUTED SCHEMAS (con campos calculados)
# ============================================================================

class ItemResponse(Item):
    """Schema de respuesta con campos calculados"""
    total_price: float
    
    @classmethod
    def from_orm_with_total(cls, item_orm):
        """Factory method para crear ItemResponse con total calculado"""
        total_price = item_orm.price
        if item_orm.tax:
            total_price += item_orm.price * (item_orm.tax / 100)
        
        return cls(
            id=item_orm.id,
            name=item_orm.name,
            description=item_orm.description,
            price=item_orm.price,
            tax=item_orm.tax,
            owner_id=item_orm.owner_id,
            created_at=item_orm.created_at,
            updated_at=item_orm.updated_at,
            total_price=total_price
        )

# ============================================================================
# LOG SCHEMAS
# ============================================================================

class RequestLogBase(BaseModel):
    """Base schema para RequestLog"""
    method: str
    path: str
    duration_ms: float
    user_id: Optional[int] = None

class RequestLog(RequestLogBase):
    """Schema para respuesta de log"""
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# UTILITY SCHEMAS
# ============================================================================

class PaginatedResponse(BaseModel):
    """Schema genérico para respuestas paginadas"""
    total: int
    page: int
    size: int
    items: List[dict]  # Será sobrescrito por schemas específicos

class MessageResponse(BaseModel):
    """Schema para respuestas simples"""
    message: str
    status: str = "success"