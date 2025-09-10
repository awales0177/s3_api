from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from datetime import timedelta
from typing import Optional
import logging

from auth import (
    authenticate_user, 
    create_access_token, 
    get_current_user,
    UserRole,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

class RoleRequest(BaseModel):
    username: str
    password: str

class RoleResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict

class UserInfo(BaseModel):
    username: str
    email: str
    full_name: str
    role: str

@router.post("/role", response_model=RoleResponse)
async def changeRole(role_data: RoleRequest):
    """Authenticate user and return access token."""
    try:
        user = authenticate_user(role_data.username, role_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=access_token_expires
        )
        
        logger.info(f"User {user['username']} changed role successfully")
        
        return RoleResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            user={
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"]
            }
        )
        
    except Exception as e:
        logger.error(f"Role change error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during role change"
        )

@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return UserInfo(
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"]
    )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (client should discard token)."""
    logger.info(f"User {current_user['username']} logged out")
    return {"message": "Successfully logged out"}

@router.get("/roles")
async def get_available_roles():
    """Get available user roles."""
    return {
        "roles": [
            {
                "name": UserRole.READER,
                "description": "Can view all data but cannot create, edit, or delete",
                "permissions": ["read"]
            },
            {
                "name": UserRole.EDITOR,
                "description": "Can view, create, edit, and delete all data",
                "permissions": ["read", "create", "update", "delete"]
            },
            {
                "name": UserRole.ADMIN,
                "description": "Full access including user management",
                "permissions": ["read", "create", "update", "delete", "admin"]
            }
        ]
    }

@router.get("/test-users")
async def get_test_users():
    """Get test user credentials for development."""
    return {
        "test_users": [
            {
                "username": "reader1",
                "password": "reader123",
                "role": UserRole.READER,
                "description": "Read-only access"
            },
            {
                "username": "editor1", 
                "password": "editor123",
                "role": UserRole.EDITOR,
                "description": "Full edit access"
            },
            {
                "username": "admin",
                "password": "admin123", 
                "role": UserRole.ADMIN,
                "description": "Administrator access"
            }
        ]
    }
