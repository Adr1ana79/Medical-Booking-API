from datetime import datetime, timedelta, time, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_patient
from app import models, schemas

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def is_time_range_inside(start_t, end_t, work_start, work_end):
    return work_start <= start_t and end_t <= work_end


def overlaps_break(start_t, end_t, break_start, break_end):
    if break_start is None or break_end is None:
        return False

    return start_t < break_end and end_t > break_start


def get_effective_working_hours(db: Session, doctor_id: int, appointment_start: datetime):
    appointment_date = appointment_start.date()
    appointment_weekday = appointment_start.weekday()
    appointment_dt = appointment_start

    temporary_change = db.query(models.TemporaryChange).filter(
        models.TemporaryChange.doctor_id == doctor_id,
        models.TemporaryChange.start_datetime <= appointment_dt,
        models.TemporaryChange.end_datetime >= appointment_dt
    ).first()

    if temporary_change:
        return {
            "start_time": temporary_change.new_start_time,
            "end_time": temporary_change.new_end_time,
            "break_start": temporary_change.break_start,
            "break_end": temporary_change.break_end
        }

    permanent_change = db.query(models.PermanentChange).filter(
        models.PermanentChange.doctor_id == doctor_id,
        models.PermanentChange.day_of_week == appointment_weekday,
        models.PermanentChange.valid_from <= appointment_date
    ).order_by(models.PermanentChange.valid_from.desc()).first()

    if permanent_change:
        return {
            "start_time": permanent_change.start_time,
            "end_time": permanent_change.end_time,
            "break_start": permanent_change.break_start,
            "break_end": permanent_change.break_end
        }

    weekly_hours = db.query(models.WorkingHours).filter(
        models.WorkingHours.doctor_id == doctor_id,
        models.WorkingHours.day_of_week == appointment_weekday
    ).first()

    if weekly_hours:
        return {
            "start_time": weekly_hours.start_time,
            "end_time": weekly_hours.end_time,
            "break_start": weekly_hours.break_start,
            "break_end": weekly_hours.break_end
        }

    return None




def validate_appointment_in_working_hours(db: Session, doctor_id: int, start_dt: datetime, end_dt: datetime):
    effective_hours = get_effective_working_hours(db, doctor_id, start_dt)

    if not effective_hours:
        raise HTTPException(status_code=400, detail="Doctor has no working hours for this day")

    work_start = effective_hours["start_time"]
    work_end = effective_hours["end_time"]
    break_start = effective_hours["break_start"]
    break_end = effective_hours["break_end"]

    if work_start is None or work_end is None:
        raise HTTPException(status_code=400, detail="Doctor does not work on this day")

    start_t = start_dt.time()
    end_t = end_dt.time()

    if not is_time_range_inside(start_t, end_t, work_start, work_end):
        raise HTTPException(status_code=400, detail="Appointment is outside working hours")

    if overlaps_break(start_t, end_t, break_start, break_end):
        raise HTTPException(status_code=400, detail="Appointment overlaps doctor break")




def validate_no_overlap(db: Session, doctor_id: int, start_dt: datetime, end_dt: datetime):
    overlapping = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.status == "active",
        models.Appointment.start_time < end_dt,
        models.Appointment.end_time > start_dt
    ).first()

    if overlapping:
        raise HTTPException(status_code=400, detail="Appointment overlaps existing appointment")



@router.post("/")
def create_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_patient=Depends(require_patient)
):
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    if payload.patient_id != current_patient.id:
        raise HTTPException(status_code=403, detail="You can only create appointments for yourself")

    doctor = db.query(models.Doctor).filter(
        models.Doctor.id == current_patient.doctor_id
    ).first()

    if not doctor:
        raise HTTPException(status_code=404, detail="Assigned doctor not found")

    if payload.start_time < datetime.utcnow() + timedelta(hours=24):
        raise HTTPException(
            status_code=400,
            detail="Appointment must be created at least 24 hours in advance"
        )

    if payload.start_time.date() != payload.end_time.date():
        raise HTTPException(
            status_code=400,
            detail="Appointment must be within a single day"
        )

    validate_appointment_in_working_hours(
        db,
        doctor_id=doctor.id,
        start_dt=payload.start_time,
        end_dt=payload.end_time
    )

    validate_no_overlap(
        db,
        doctor_id=doctor.id,
        start_dt=payload.start_time,
        end_dt=payload.end_time
    )

    appointment = models.Appointment(
        doctor_id=doctor.id,
        patient_id=current_patient.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status="active"
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {
        "message": "Appointment created successfully",
        "appointment_id": appointment.id
    }



@router.get("/me")
def get_my_appointments(
    db: Session = Depends(get_db),
    current=Depends(get_current_user)
):
    if current["role"] == "doctor":
        rows = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == current["user"].id
        ).order_by(models.Appointment.start_time).all()
    else:
        rows = db.query(models.Appointment).filter(
            models.Appointment.patient_id == current["user"].id
        ).order_by(models.Appointment.start_time).all()

    return [
        {
            "id": row.id,
            "doctor_id": row.doctor_id,
            "patient_id": row.patient_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "status": row.status
        }
        for row in rows
    ]



@router.get("/doctor-working-hours")
def get_my_doctor_working_hours(
    db: Session = Depends(get_db),
    current_patient=Depends(require_patient)
):
    rows = db.query(models.WorkingHours).filter(
        models.WorkingHours.doctor_id == current_patient.doctor_id
    ).order_by(models.WorkingHours.day_of_week).all()

    return [
        {
            "day_of_week": row.day_of_week,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "break_start": row.break_start,
            "break_end": row.break_end
        }
        for row in rows
    ]


def combine_date_and_time(target_date: date, target_time: time) -> datetime:
    return datetime.combine(target_date, target_time)



def is_slot_available(
    db: Session,
    doctor_id: int,
    slot_start: datetime,
    slot_end: datetime
) -> bool:
    overlapping = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.status == "active",
        models.Appointment.start_time < slot_end,
        models.Appointment.end_time > slot_start
    ).first()

    return overlapping is None



def generate_available_slots(
    db: Session,
    doctor_id: int,
    target_date: date,
    slot_minutes: int = 30
):
    fake_dt = datetime.combine(target_date, time(9, 0))
    effective_hours = get_effective_working_hours(db, doctor_id, fake_dt)

    if not effective_hours:
        return []

    work_start = effective_hours["start_time"]
    work_end = effective_hours["end_time"]
    break_start = effective_hours["break_start"]
    break_end = effective_hours["break_end"]

    if work_start is None or work_end is None:
        return []

    current_start = combine_date_and_time(target_date, work_start)
    work_end_dt = combine_date_and_time(target_date, work_end)

    available_slots = []

    while current_start + timedelta(minutes=slot_minutes) <= work_end_dt:
        current_end = current_start + timedelta(minutes=slot_minutes)

        start_t = current_start.time()
        end_t = current_end.time()

        if overlaps_break(start_t, end_t, break_start, break_end):
            current_start += timedelta(minutes=slot_minutes)
            continue

        if current_start < datetime.utcnow() + timedelta(hours=24):
            current_start += timedelta(minutes=slot_minutes)
            continue

        if is_slot_available(db, doctor_id, current_start, current_end):
            available_slots.append({
                "start_time": current_start,
                "end_time": current_end
            })

        current_start += timedelta(minutes=slot_minutes)

    return available_slots



@router.get("/available-slots")
def get_available_slots(
    target_date: date,
    db: Session = Depends(get_db),
    current_patient=Depends(require_patient)
):
    slots = generate_available_slots(
        db=db,
        doctor_id=current_patient.doctor_id,
        target_date=target_date,
        slot_minutes=30
    )

    return {
        "doctor_id": current_patient.doctor_id,
        "date": target_date,
        "available_slots": slots
    }




@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current=Depends(get_current_user)
):
    appointment = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status == "cancelled":
        raise HTTPException(status_code=400, detail="Appointment is already cancelled")

    is_patient_owner = (
        current["role"] == "patient" and
        appointment.patient_id == current["user"].id
    )

    is_doctor_owner = (
        current["role"] == "doctor" and
        appointment.doctor_id == current["user"].id
    )

    if not is_patient_owner and not is_doctor_owner:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to cancel this appointment"
        )

    if appointment.start_time < datetime.utcnow() + timedelta(hours=12):
        raise HTTPException(
            status_code=400,
            detail="Appointment cannot be cancelled less than 12 hours before start time"
        )

    appointment.status = "cancelled"
    db.commit()

    return {"message": "Appointment cancelled successfully"}