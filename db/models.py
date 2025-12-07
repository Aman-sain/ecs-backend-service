from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from db.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    role = Column(String(100), nullable=False)
    salary = Column(Float, nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=True)
    department = Column(String(100), nullable=True)
    performance_rating = Column(Float, default=0.0)
    skills = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
