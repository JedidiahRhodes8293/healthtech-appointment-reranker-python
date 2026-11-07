from src.appointment_reranker import AppointmentRequest, make_patient_notice


def test_notice_uses_the_top_ranked_appointment_and_safety_prompt():
    request = AppointmentRequest("Mina", "cardiology follow-up", ["one", "two"])

    notice = make_patient_notice(request, ["Cardiology follow-up, Tue 10:00", "Dermatology intake"])

    assert notice == "Mina: best match is Cardiology follow-up, Tue 10:00. Please confirm with the care team before travel."

