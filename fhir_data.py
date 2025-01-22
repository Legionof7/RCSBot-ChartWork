
# Sample FHIR Patient Resource
SAMPLE_PATIENT = {
    "resourceType": "Patient",
    "id": "example",
    "meta": {
        "lastUpdated": "2024-01-22T12:00:00Z"
    },
    "identifier": [{
        "system": "urn:oid:2.16.840.1.113883.19.5",
        "value": "12345"
    }],
    "active": True,
    "name": [{
        "use": "official",
        "family": "Smith",
        "given": ["John", "Edward"]
    }],
    "telecom": [{
        "system": "phone",
        "value": "+1-555-555-5555",
        "use": "home"
    }],
    "gender": "male",
    "birthDate": "1970-01-25",
    "address": [{
        "use": "home",
        "line": ["123 Main St"],
        "city": "Boston",
        "state": "MA",
        "postalCode": "02115",
        "country": "USA"
    }],
    "medicalConditions": [
        "Type 2 Diabetes",
        "Hypertension"
    ],
    "medications": [
        {
            "name": "Metformin",
            "dosage": "500mg",
            "frequency": "twice daily"
        },
        {
            "name": "Lisinopril",
            "dosage": "10mg",
            "frequency": "once daily"
        }
    ],
    "lastVisit": "2024-01-15",
    "nextAppointment": "2024-02-15"
}

def get_patient_data():
    return SAMPLE_PATIENT
