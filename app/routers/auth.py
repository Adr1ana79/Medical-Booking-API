from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register-doctor")
def register_doctor(payload: schemas.DoctorRegister, db: Session = Depends(get_db)):
    existing = db.query(models.Doctor).filter(models.Doctor.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Doctor with this email already exists")

    doctor = models.Doctor(
        name=payload.name,
        email=payload.email,
        address=payload.address,
        password_hash=hash_password(payload.password)
    )

    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    return {
        "message": "Doctor registered successfully",
        "doctor_id": doctor.id
    }


@router.post("/register-patient")
def register_patient(payload: schemas.PatientRegister, db: Session = Depends(get_db)):
    existing = db.query(models.Patient).filter(models.Patient.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Patient with this email already exists")

    doctor = db.query(models.Doctor).filter(models.Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    patient = models.Patient(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        doctor_id=payload.doctor_id,
        password_hash=hash_password(payload.password)
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return {
        "message": "Patient registered successfully",
        "patient_id": patient.id
    }


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    if payload.role == "doctor":
        user = db.query(models.Doctor).filter(models.Doctor.email == payload.email).first()
    else:
        user = db.query(models.Patient).filter(models.Patient.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({
        "sub": str(user.id),
        "role": payload.role
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/me")
def get_me(current=Depends(get_current_user)):
    user = current["user"]
    role = current["role"]

    if role == "doctor":
        return {
            "role": "doctor",
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "address": user.address
        }

    return {
        "role": "patient",
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "doctor_id": user.doctor_id
    }