import re

import pytest

from app.models import Patient
from tests.conftest import extract_csrf_token


pytestmark = pytest.mark.asyncio


async def test_demo_workspace_is_idempotent(authenticated_client, db_session, doctor_for_credentials):
    client = authenticated_client["client"]
    doctor = doctor_for_credentials(authenticated_client["username"])

    demo_page = await client.get("/demo")
    assert demo_page.status_code == 200
    csrf_token = extract_csrf_token(demo_page.text)

    first_response = await client.post(
        "/demo/create-workspace",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert first_response.status_code == 303
    first_location = first_response.headers["location"]

    match = re.fullmatch(r"/patients/(\d+)/cases", first_location)
    assert match is not None
    patient_id = int(match.group(1))

    second_demo_page = await client.get("/demo")
    assert second_demo_page.status_code == 200
    second_token = extract_csrf_token(second_demo_page.text)

    second_response = await client.post(
        "/demo/create-workspace",
        data={"csrf_token": second_token},
        follow_redirects=False,
    )
    assert second_response.status_code == 303
    assert second_response.headers["location"] == first_location

    case_page = await client.get(first_location)
    assert case_page.status_code == 200

    demo_email = f"demo-{doctor.id}@ayurvedaos.local"
    demo_patients = (
        db_session.query(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email == demo_email)
        .all()
    )
    assert len(demo_patients) == 1
    assert demo_patients[0].id == patient_id
