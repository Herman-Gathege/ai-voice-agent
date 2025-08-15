from real_estate_functions import get_available_slots, book_appointment, save_lead

def run_test():
    print("\n--- Step 1: Get Available Slots ---")
    slots_result = get_available_slots("America/New_York", "tomorrow", "morning")
    print(slots_result)

    assert "slots" in slots_result, "Slots not returned!"
    assert len(slots_result["slots"]) > 0, "No available slots found!"

    chosen_slot = slots_result["slots"][0]["start_iso_company"]

    print("\n--- Step 2: Book Appointment ---")
    booking_result = book_appointment(
        full_name="Test Caller",
        email="testcaller@example.com",
        caller_timezone="America/New_York",
        start_iso_company=chosen_slot,
        notes="Testing booking flow"
    )
    print(booking_result)

    assert "appointment_id" in booking_result, "Appointment not booked!"

    print("\n--- Step 3: Save Lead ---")
    lead_result = save_lead(
        full_name="Test Caller",
        email="testcaller@example.com",
        goal="Increase sales",
        pains=["Inconsistent months", "Low quality leads"]
    )
    print(lead_result)

    assert lead_result["status"] == "saved", "Lead not saved!"

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    run_test()
