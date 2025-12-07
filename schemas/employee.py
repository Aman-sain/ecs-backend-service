from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class EmployeeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    salary: float = Field(..., ge=0)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, max_length=100)
    performance_rating: Optional[float] = Field(0.0, ge=0, le=5)
    skills: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, min_length=1, max_length=100)
    salary: Optional[float] = Field(None, ge=0)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, max_length=100)
    performance_rating: Optional[float] = Field(None, ge=0, le=5)
    skills: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    total: int
    employees: list[EmployeeResponse]
