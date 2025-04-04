
# Sample FHIR Patient Resource
SAMPLE_PATIENT = {
    "resourceType": "Patient",
    "id": "example",
    "meta": {
        "lastUpdated": "2024-01-22T12:00:00Z",
        "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
    },
    "identifier": [{
        "system": "urn:oid:2.16.840.1.113883.19.5",
        "value": "12345",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                "code": "MR",
                "display": "Medical Record Number"
            }]
        }
    }],
    "active": True,
    "name": [{
        "use": "official",
        "family": "Smith",
        "given": ["John", "Edward"],
        "prefix": ["Mr."]
    }],
    "telecom": [
        {
            "system": "phone",
            "value": "+1-555-555-5555",
            "use": "home"
        },
        {
            "system": "email",
            "value": "john.smith@email.com",
            "use": "work"
        }
    ],
    "gender": "male",
    "birthDate": "1970-01-25",
    "deceasedBoolean": False,
    "address": [{
        "use": "home",
        "type": "physical",
        "line": ["123 Main St"],
        "city": "Boston",
        "state": "MA",
        "postalCode": "02115",
        "country": "USA"
    }],
    "maritalStatus": {
        "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
            "code": "M",
            "display": "Married"
        }]
    },
    "communication": [{
        "language": {
            "coding": [{
                "system": "urn:ietf:bcp:47",
                "code": "en",
                "display": "English"
            }]
        },
        "preferred": True
    }],
    "medicalConditions": [
        {
            "code": "E11.9",
            "system": "ICD-10",
            "display": "Type 2 Diabetes",
            "dateRecorded": "2020-03-15",
            "status": "active"
        },
        {
            "code": "I10",
            "system": "ICD-10",
            "display": "Hypertension",
            "dateRecorded": "2019-06-22",
            "status": "active"
        }
    ],
    "medications": [
        {
            "name": "Metformin",
            "code": "860975",
            "system": "RxNorm",
            "dosage": "500mg",
            "frequency": "twice daily",
            "startDate": "2020-03-15",
            "status": "active"
        },
        {
            "name": "Lisinopril",
            "code": "203644",
            "system": "RxNorm",
            "dosage": "10mg",
            "frequency": "once daily",
            "startDate": "2019-06-22",
            "status": "active"
        }
    ],
    "vitalSigns": [
        {
            "date": "2024-01-15",
            "bloodPressure": {"systolic": 128, "diastolic": 82, "unit": "mmHg"},
            "heartRate": {"value": 72, "unit": "bpm"},
            "temperature": {"value": 37.0, "unit": "Celsius"},
            "weight": {"value": 80.5, "unit": "kg"},
            "height": {"value": 180, "unit": "cm"}
        },
        {
            "date": "2023-10-15",
            "bloodPressure": {"systolic": 132, "diastolic": 84, "unit": "mmHg"},
            "heartRate": {"value": 75, "unit": "bpm"},
            "weight": {"value": 82.1, "unit": "kg"}
        },
        {
            "date": "2023-07-15",
            "bloodPressure": {"systolic": 135, "diastolic": 86, "unit": "mmHg"},
            "heartRate": {"value": 78, "unit": "bpm"},
            "weight": {"value": 83.4, "unit": "kg"}
        },
        {
            "date": "2023-04-15",
            "bloodPressure": {"systolic": 138, "diastolic": 88, "unit": "mmHg"},
            "heartRate": {"value": 76, "unit": "bpm"},
            "weight": {"value": 84.2, "unit": "kg"}
        }
    ],
    "labResults": [
        {
            "date": "2024-01-15",
            "test": "HbA1c",
            "value": 6.8,
            "unit": "%",
            "referenceRange": "4.0-5.6",
            "interpretation": "High"
        },
        {
            "date": "2023-10-15",
            "test": "HbA1c",
            "value": 7.1,
            "unit": "%",
            "referenceRange": "4.0-5.6",
            "interpretation": "High"
        },
        {
            "date": "2023-07-15",
            "test": "HbA1c",
            "value": 7.4,
            "unit": "%",
            "referenceRange": "4.0-5.6",
            "interpretation": "High"
        },
        {
            "date": "2023-04-15",
            "test": "HbA1c",
            "value": 7.6,
            "unit": "%",
            "referenceRange": "4.0-5.6",
            "interpretation": "High"
        },
        {
            "date": "2024-01-15",
            "test": "Cholesterol",
            "value": 185,
            "unit": "mg/dL",
            "referenceRange": "125-200",
            "interpretation": "Normal"
        },
        {
            "date": "2024-01-15",
            "test": "HDL",
            "value": 55,
            "unit": "mg/dL",
            "referenceRange": "40-60",
            "interpretation": "Normal"
        },
        {
            "date": "2024-01-15",
            "test": "LDL",
            "value": 110,
            "unit": "mg/dL",
            "referenceRange": "0-100",
            "interpretation": "Borderline High"
        },
        {
            "date": "2024-01-15",
            "test": "Triglycerides",
            "value": 150,
            "unit": "mg/dL",
            "referenceRange": "0-150",
            "interpretation": "Normal"
        },
        {
            "date": "2024-01-15",
            "test": "Fasting Glucose",
            "value": 110,
            "unit": "mg/dL",
            "referenceRange": "70-100",
            "interpretation": "High"
        },
        {
            "date": "2024-01-15",
            "test": "Creatinine",
            "value": 1.1,
            "unit": "mg/dL",
            "referenceRange": "0.7-1.3",
            "interpretation": "Normal"
        }
    ],
    "carePlan": {
        "created": "2024-01-15",
        "status": "active",
        "goals": [
            "Maintain HbA1c below 7.0%",
            "Blood pressure control below 130/80",
            "Regular exercise 30 minutes daily",
            "Follow diabetic diet plan"
        ],
        "nextReview": "2024-04-15"
    },
    "lastVisit": "2024-01-15",
    "nextAppointment": "2024-02-15",
    "emergencyContact": {
        "relationship": "Spouse",
        "name": "Jane Smith",
        "phone": "+1-555-555-5556"
    }
}

import logging

def get_patient_data(data_type='all'):
    logging.info(f"Retrieving FHIR patient data for type: {data_type}")

    data_type = data_type.lower()  # Normalize input to lowercase
    data_mapping = {
        "all": SAMPLE_PATIENT,
        "conditions": {"medicalConditions": SAMPLE_PATIENT.get("medicalConditions", [])},
        "medications": {"medications": SAMPLE_PATIENT.get("medications", [])},
        "vitals": {"vitalSigns": SAMPLE_PATIENT.get("vitalSigns", [])},
        "labs": {"labResults": SAMPLE_PATIENT.get("labResults", [])}
    }

    if data_type not in data_mapping:
        logging.warning(f"Unknown data type: {data_type}. Returning an empty dictionary.")
        return {}

    return data_mapping[data_type]
# a = get_patient_data()
# print(a)