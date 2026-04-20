from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_doctor
from app import models, schemas

router = APIRouter(prefix="/doctor", tags=["Doctor"])


def validate_working_hours(start_time, end_time, break_start, break_end):
    if start_time is None and end_time is None:
        return

    if start_time is None or end_time is None:
        raise HTTPException(status_code=400, detail="Both start_time and end_time are required")

    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    if (break_start is None) != (break_end is None):
        raise HTTPException(status_code=400, detail="Both break_start and break_end are required together")

    if break_start is not None and break_end is not None:
        if break_start >= break_end:
            raise HTTPException(status_code=400, detail="break_start must be before break_end")

        if break_start <= start_time or break_end >= end_time:
            raise HTTPException(
                status_code=400,
                detail="Break must be fully inside working hours"
            )



@router.put("/working-hours")
def update_weekly_working_hours(
    payload: schemas.WeeklyWorkingHoursUpdate,
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    if len(payload.days) == 0:
        raise HTTPException(status_code=400, detail="At least one day is required")

    seen_days = set()
    for day in payload.days:
        if day.day_of_week < 0 or day.day_of_week > 6:
            raise HTTPException(status_code=400, detail="day_of_week must be between 0 and 6")

        if day.day_of_week in seen_days:
            raise HTTPException(status_code=400, detail="Duplicate day_of_week")
        seen_days.add(day.day_of_week)

        validate_working_hours(day.start_time, day.end_time, day.break_start, day.break_end)

    db.query(models.WorkingHours).filter(
        models.WorkingHours.doctor_id == current_doctor.id
    ).delete()

    for day in payload.days:
        row = models.WorkingHours(
            doctor_id=current_doctor.id,
            day_of_week=day.day_of_week,
            start_time=day.start_time,
            end_time=day.end_time,
            break_start=day.break_start,
            break_end=day.break_end
        )
        db.add(row)

    db.commit()

    return {"message": "Weekly working hours updated successfully"}



@router.get("/working-hours")
def get_weekly_working_hours(
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    rows = db.query(models.WorkingHours).filter(
        models.WorkingHours.doctor_id == current_doctor.id
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



@router.post("/temporary-change")
def add_temporary_change(
    payload: schemas.TemporaryChangeCreate,
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    if payload.start_datetime >= payload.end_datetime:
        raise HTTPException(status_code=400, detail="start_datetime must be before end_datetime")

    validate_working_hours(
        payload.new_start_time,
        payload.new_end_time,
        payload.break_start,
        payload.break_end
    )

    existing = db.query(models.TemporaryChange).filter(
        models.TemporaryChange.doctor_id == current_doctor.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Doctor already has a temporary change"
        )

    temp_change = models.TemporaryChange(
        doctor_id=current_doctor.id,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        new_start_time=payload.new_start_time,
        new_end_time=payload.new_end_time,
        break_start=payload.break_start,
        break_end=payload.break_end
    )

    db.add(temp_change)
    db.commit()
    db.refresh(temp_change)

    return {
        "message": "Temporary change added successfully",
        "temporary_change_id": temp_change.id
    }


@router.get("/temporary-change")
def get_temporary_change(
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    row = db.query(models.TemporaryChange).filter(
        models.TemporaryChange.doctor_id == current_doctor.id
    ).first()

    if not row:
        return {"message": "No temporary change"}

    return {
        "id": row.id,
        "start_datetime": row.start_datetime,
        "end_datetime": row.end_datetime,
        "new_start_time": row.new_start_time,
        "new_end_time": row.new_end_time,
        "break_start": row.break_start,
        "break_end": row.break_end
    }



@router.delete("/temporary-change")
def delete_temporary_change(
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    row = db.query(models.TemporaryChange).filter(
        models.TemporaryChange.doctor_id == current_doctor.id
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="No temporary change found")

    db.delete(row)
    db.commit()

    return {"message": "Temporary change deleted successfully"}



@router.post("/permanent-change")
def add_permanent_change(
    payload: schemas.PermanentChangeCreate,
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    if payload.day_of_week < 0 or payload.day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week must be between 0 and 6")

    if payload.valid_from < (datetime.utcnow().date() + timedelta(days=7)):
        raise HTTPException(
            status_code=400,
            detail="Permanent change must start at least 7 days in the future"
        )

    validate_working_hours(
        payload.start_time,
        payload.end_time,
        payload.break_start,
        payload.break_end
    )

    row = models.PermanentChange(
        doctor_id=current_doctor.id,
        valid_from=payload.valid_from,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        break_start=payload.break_start,
        break_end=payload.break_end
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "message": "Permanent change added successfully",
        "permanent_change_id": row.id
    }



@router.get("/permanent-changes")
def get_permanent_changes(
    db: Session = Depends(get_db),
    current_doctor=Depends(require_doctor)
):
    rows = db.query(models.PermanentChange).filter(
        models.PermanentChange.doctor_id == current_doctor.id
    ).order_by(models.PermanentChange.valid_from, models.PermanentChange.day_of_week).all()

    return [
        {
            "id": row.id,
            "valid_from": row.valid_from,
            "day_of_week": row.day_of_week,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "break_start": row.break_start,
            "break_end": row.break_end
        }
        for row in rows
    ]