def test_doctor_can_set_working_hours(client):
    client.post("/auth/register-doctor", json={
        "name": "Dr. Test",
        "email": "doctor@test.com",
        "address": "Sofia",
        "password": "123456"
    })

    login_response = client.post("/auth/login", json={
        "email": "doctor@test.com",
        "password": "123456",
        "role": "doctor"
    })
    token = login_response.json()["access_token"]

    response = client.put(
        "/doctor/working-hours",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "days": [
                {
                    "day_of_week": 0,
                    "start_time": "08:30:00",
                    "end_time": "18:30:00",
                    "break_start": "12:00:00",
                    "break_end": "13:00:00"
                }
            ]
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Weekly working hours updated successfully"