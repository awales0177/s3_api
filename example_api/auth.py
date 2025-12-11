import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme
security = HTTPBearer()

# User roles
class UserRole:
    READER = "reader"
    EDITOR = "editor"
    ADMIN = "admin"

# In-memory user store (in production, use a database)
USERS_DB = {
    "user": {
        "username": "user",
        "password_hash": hashlib.sha256("user123".encode()).hexdigest(),
        "roles": [UserRole.READER, UserRole.EDITOR, UserRole.ADMIN],  # All three roles
        "email": "user@example.com",
        "full_name": "User"
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user and return user data if valid."""
    user = USERS_DB.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Return user with roles array
    return {
        "username": user["username"],
        "roles": user["roles"],
        "email": user["email"],
        "full_name": user["full_name"]
    }

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return payload
    except jwt.PyJWTError:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get the current authenticated user - BYPASS MODE: Only checks role, ignores credentials."""
    # BYPASS MODE: Return a default user with editor role for now
    # This allows editing without requiring valid credentials
    return {
        "username": "bypass_user",
        "roles": [UserRole.EDITOR, UserRole.ADMIN],  # Give full permissions
        "email": "bypass@example.com",
        "full_name": "Bypass User"
    }
    
    # Original credential validation (commented out for bypass mode)
    # token = credentials.credentials
    # payload = verify_token(token)
    # if payload is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Could not validate credentials",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # 
    # username = payload.get("sub")
    # user = USERS_DB.get(username)
    # if user is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User not found",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # 
    # return user

def require_role(required_role: str):
    """Decorator to require a specific role."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        
        if required_role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return current_user
    return role_checker

def require_editor_or_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Require editor or admin role."""
    user_roles = current_user.get("roles", [])
    if not any(role in user_roles for role in [UserRole.EDITOR, UserRole.ADMIN]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin role required"
        )
    return current_user

def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Require admin role."""
    user_roles = current_user.get("roles", [])
    if UserRole.ADMIN not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return current_user

# Optional authentication for read-only endpoints
def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Get the current user if authenticated, otherwise return None - BYPASS MODE."""
    # BYPASS MODE: Always return a user with editor role
    return {
        "username": "bypass_user",
        "roles": [UserRole.EDITOR, UserRole.ADMIN],
        "email": "bypass@example.com",
        "full_name": "Bypass User"
    }
    
    # Original credential validation (commented out for bypass mode)
    # if credentials is None:
    #     return None
    # 
    # try:
    #     token = credentials.credentials
    #     payload = verify_token(token)
    #     if payload is None:
    #         return None
    #     
    #     username = payload.get("sub")
    #     user = USERS_DB.get(username)
    #     return user
    # except:
    #     return None
