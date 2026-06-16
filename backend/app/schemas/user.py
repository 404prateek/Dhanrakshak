from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleResponse(RoleBase):
    id: int
    
    model_config = {"from_attributes": True}

class UserBase(BaseModel):
    employee_id: str
    full_name: str
    branch: Optional[str] = None
    role_id: Optional[int] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    role: Optional[RoleResponse] = None
    
    model_config = {"from_attributes": True}
