from datetime import datetime, timedelta


def register_doctor(client, email="doctor@test.com"):
    return client.post("/auth/register-doctor", json={
        "name": "Dr. Test",
        "email": email,
        "address": "Sofia",
        "password": "123456"
    })


def register_patient(client, doctor_id, email="patient@test.com"):
    return client.post("/auth/register-patient", json={
        "name": "Patient Test",
        "email": email,
        "phone": "0888000000",
        "password": "123456",
        "doctor_id": doctor_id
    })


def login_doctor(client, email="doctor@test.com"):
    response = client.post("/auth/login", json={
        "email": email,
        "password": "123456",
        "role": "doctor"
    })
    return response.json()["access_token"]


def login_patient(client, email="patient@test.com"):
    response = client.post("/auth/login", json={
        "email": email,
        "password": "123456",
        "role": "patient"
    })
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def set_working_hours(client, token):
    return client.put(
        "/doctor/working-hours",
        headers=auth_headers(token),
        json={
            "days": [
                {
                    "day_of_week": 0,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                },
                {
                    "day_of_week": 1,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                },
                {
                    "day_of_week": 2,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                },
                {
                    "day_of_week": 3,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                },
                {
                    "day_of_week": 4,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                },
                {
                    "day_of_week": 5,
                    "start_time": "09:00:00",
                    "end_time": "12:30:00",
                    "break_start": None,
                    "break_end": None
                },
                {
                    "day_of_week": 6,
                    "start_time": None,
                    "end_time": None,
                    "break_start": None,
                    "break_end": None
                }
            ]
        }
    )


def next_weekday_at(hour, minute=0, days_ahead_min=2):
    base = datetime.utcnow() + timedelta(days=days_ahead_min)
    while base.weekday() > 4:
        base += timedelta(days=1)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)