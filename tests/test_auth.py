def test_register_doctor_and_login(client):
    register_response = client.post("/auth/register-doctor", json={
        "name": "Dr. Test",
        "email": "doctor@test.com",
        "address": "Sofia",
        "password": "123456"
    })

    assert register_response.status_code == 200
    data = register_response.json()
    assert data["message"] == "Doctor registered successfully"

    login_response = client.post("/auth/login", json={
        "email": "doctor@test.com",
        "password": "123456",
        "role": "doctor"
    })

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"





def test_register_patient(client):
    doctor_response = client.post("/auth/register-doctor", json={
        "name": "Dr. Test",
        "email": "doctor@test.com",
        "address": "Sofia",
        "password": "123456"
    })

    doctor_id = doctor_response.json()["doctor_id"]

    patient_response = client.post("/auth/register-patient", json={
        "name": "Patient Test",
        "email": "patient@test.com",
        "phone": "0888000000",
        "password": "123456",
        "doctor_id": doctor_id
    })

    assert patient_response.status_code == 200
    data = patient_response.json()
    assert data["message"] == "Patient registered successfully"