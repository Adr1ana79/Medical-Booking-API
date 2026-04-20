from datetime import timedelta

from tests.helpers import (
    register_doctor,
    register_patient,
    login_doctor,
    login_patient,
    auth_headers,
    set_working_hours,
    next_weekday_at,
)

from tests.conftest import TestingSessionLocal
db = TestingSessionLocal()


def setup_users_and_hours(client):
    doctor_response = register_doctor(client)
    doctor_id = doctor_response.json()["doctor_id"]

    patient_response = register_patient(client, doctor_id=doctor_id)
    patient_id = patient_response.json()["patient_id"]

    doctor_token = login_doctor(client)
    patient_token = login_patient(client)

    working_hours_response = set_working_hours(client, doctor_token)
    assert working_hours_response.status_code == 200

    return doctor_id, patient_id, doctor_token, patient_token


def test_create_appointment_success(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    start_dt = next_weekday_at(10, 0)
    end_dt = start_dt + timedelta(minutes=30)

    response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat()
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Appointment created successfully"


def test_create_appointment_fails_when_overlapping(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    start_dt = next_weekday_at(10, 0)
    end_dt = start_dt + timedelta(minutes=30)

    first_response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat()
        }
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": (start_dt + timedelta(minutes=15)).isoformat(),
            "end_time": (end_dt + timedelta(minutes=15)).isoformat()
        }
    )

    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Appointment overlaps existing appointment"


def test_create_appointment_fails_if_inside_break(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    start_dt = next_weekday_at(12, 15)
    end_dt = start_dt + timedelta(minutes=30)

    response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat()
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Appointment overlaps doctor break"


def test_create_appointment_fails_if_less_than_24_hours_before(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    from datetime import datetime
    start_dt = datetime.utcnow() + timedelta(hours=23)
    end_dt = start_dt + timedelta(minutes=30)

    response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat()
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Appointment must be created at least 24 hours in advance"




def test_cancel_appointment_success(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    start_dt = next_weekday_at(10, 0, days_ahead_min=3)
    end_dt = start_dt + timedelta(minutes=30)

    create_response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat()
        }
    )
    assert create_response.status_code == 200

    appointment_id = create_response.json()["appointment_id"]

    cancel_response = client.delete(
        f"/appointments/{appointment_id}",
        headers=auth_headers(patient_token)
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["message"] == "Appointment cancelled successfully"



def test_cancel_appointment_fails_if_less_than_12_hours_before(client):
    doctor_id, patient_id, doctor_token, patient_token = setup_users_and_hours(client)

    from datetime import datetime
    from tests.conftest import TestingSessionLocal
    from app import models

    create_start = (datetime.utcnow() + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    create_end = create_start + timedelta(minutes=30)

    create_response = client.post(
        "/appointments/",
        headers=auth_headers(patient_token),
        json={
            "patient_id": patient_id,
            "start_time": create_start.isoformat(),
            "end_time": create_end.isoformat()
        }
    )

    assert create_response.status_code == 200
    appointment_id = create_response.json()["appointment_id"]

    db = TestingSessionLocal()
    appointment = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id
    ).first()

    assert appointment is not None

    new_start = datetime.utcnow() + timedelta(hours=11, minutes=30)
    new_end = new_start + timedelta(minutes=30)

    appointment.start_time = new_start
    appointment.end_time = new_end
    db.commit()
    db.close()

    cancel_response = client.delete(
        f"/appointments/{appointment_id}",
        headers=auth_headers(patient_token)
    )

    assert cancel_response.status_code == 400
    assert cancel_response.json()["detail"] == "Appointment cannot be cancelled less than 12 hours before start time"