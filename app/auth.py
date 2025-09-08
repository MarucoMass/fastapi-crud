# app/auth.py - Sistema de autenticación JWT

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import get_db
from .models import User as UserModel
from .schemas import User

# Configuración
SECRET_KEY = "tu-clave-super-secreta-cambiar-en-produccion-123456789"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Setup de password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup de OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ============================================================================
# FUNCIONES DE PASSWORD
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar password plano contra hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generar hash de password"""
    return pwd_context.hash(password)

# ============================================================================
# FUNCIONES DE JWT
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verificar y decodificar JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# ============================================================================
# FUNCIONES DE USUARIO
# ============================================================================

def authenticate_user(db: Session, email: str, password: str) -> Optional[UserModel]:
    """Autenticar usuario con email y password"""
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
    """Obtener usuario por email"""
    return db.query(UserModel).filter(UserModel.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[UserModel]:
    """Obtener usuario por ID"""
    return db.query(UserModel).filter(UserModel.id == user_id).first()

# ============================================================================
# DEPENDENCIES PARA AUTENTICACIÓN
# ============================================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserModel:
    """Obtener usuario actual desde el JWT token"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verificar token
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    # Obtener email del token
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    # Obtener usuario de la base de datos
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    """Obtener usuario actual y verificar que esté activo"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    return current_user