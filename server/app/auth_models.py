from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import re

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters long')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be 3-20 characters long')
        
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', v):
            raise ValueError('Username must start with a letter and contain only letters and numbers')
        
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UpdateUsernameRequest(BaseModel):
    username: str
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be 3-20 characters long')
        
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', v):
            raise ValueError('Username must start with a letter and contain only letters and numbers')
        
        return v

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserProfile(BaseModel):
    id: str
    username: str
    email: str

class RegisterResponse(BaseModel):
    user_id: str
    username: str
    email: str
    initial_player_id: str
    message: str

class GuestConversionRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    guest_player_id: str
    new_user_id: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters long')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be 3-20 characters long')
        
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', v):
            raise ValueError('Username must start with a letter and contain only letters and numbers')
        
        return v

class AnonymousGuestRequest(BaseModel):
    anonymous_user_id: str