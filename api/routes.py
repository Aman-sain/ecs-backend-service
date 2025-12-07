from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from db.models import Employee
from schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse
)

# Health check router
health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "code": 200,
        "message": "Enterprise Employee Management System is running"
    }


# Employee router
employee_router = APIRouter()

@employee_router.get("", response_model=EmployeeListResponse)
async def get_employees(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all employees with optional filtering and pagination"""
    query = db.query(Employee)

    if search:
        query = query.filter(
            (Employee.name.contains(search)) |
            (Employee.role.contains(search))
        )

    if department:
        query = query.filter(Employee.department == department)

    total = query.count()
    employees = query.offset(skip).limit(limit).all()

    return EmployeeListResponse(total=total, employees=employees)


@employee_router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: int, db: Session = Depends(get_db)):
    """Get a specific employee by ID"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@employee_router.post("", response_model=EmployeeResponse, status_code=201)
async def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    """Create a new employee"""
    # Check if email already exists
    if employee.email:
        existing = db.query(Employee).filter(Employee.email == employee.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    db_employee = Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee


@employee_router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing employee"""
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Check email uniqueness if updating email
    if employee_update.email and employee_update.email != db_employee.email:
        existing = db.query(Employee).filter(Employee.email == employee_update.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    update_data = employee_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_employee, field, value)

    db.commit()
    db.refresh(db_employee)
    return db_employee


@employee_router.delete("/{employee_id}")
async def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    """Delete an employee"""
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.delete(db_employee)
    db.commit()
    return {"message": "Employee deleted successfully", "id": employee_id}


@employee_router.get("/stats/summary")
async def get_employee_stats(db: Session = Depends(get_db)):
    """Get employee statistics"""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    total_employees = db.query(func.count(Employee.id)).scalar() or 0
    avg_salary = db.query(func.avg(Employee.salary)).scalar()
    avg_performance = db.query(func.avg(Employee.performance_rating)).scalar()

    departments = db.query(
        Employee.department,
        func.count(Employee.id).label('count')
    ).group_by(Employee.department).all()

    # Calculate growth rate (employees added in last 30 days vs total)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_employees = db.query(func.count(Employee.id)).filter(
        Employee.created_at >= thirty_days_ago
    ).scalar() or 0

    growth_rate = round((recent_employees / total_employees * 100), 1) if total_employees > 0 else 0

    return {
        "total_employees": total_employees,
        "average_salary": round(avg_salary, 2) if avg_salary else 0,
        "average_performance": round(avg_performance, 1) if avg_performance else 0,
        "growth_rate": growth_rate,
        "recent_hires": recent_employees,
        "departments": [
            {"name": dept or "Unassigned", "count": count}
            for dept, count in departments
        ]
    }


@employee_router.post("/bulk")
async def bulk_create_employees(employees: List[EmployeeCreate], db: Session = Depends(get_db)):
    """Bulk create employees"""
    created = []
    errors = []

    for idx, emp_data in enumerate(employees):
        try:
            if emp_data.email:
                existing = db.query(Employee).filter(Employee.email == emp_data.email).first()
                if existing:
                    errors.append({"index": idx, "email": emp_data.email, "error": "Email already exists"})
                    continue

            db_employee = Employee(**emp_data.model_dump())
            db.add(db_employee)
            db.flush()
            created.append(db_employee.id)
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    db.commit()
    return {"created": len(created), "employee_ids": created, "errors": errors}


@employee_router.get("/export/csv")
async def export_employees_csv(db: Session = Depends(get_db)):
    """Export all employees as CSV"""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    employees = db.query(Employee).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Role', 'Department', 'Salary', 'Performance Rating', 'Skills', 'Created At'])

    for emp in employees:
        writer.writerow([
            emp.id, emp.name, emp.email or '', emp.role, emp.department or '',
            emp.salary, emp.performance_rating, emp.skills or '', emp.created_at
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees.csv"}
    )
