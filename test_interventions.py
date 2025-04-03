import requests
import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
# These settings are essential for proper log formatting throughout the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default server URL
SERVER_URL = "http://localhost:5000"


def test_glucose_intervention(phone_number):
    """Test a glucose alert intervention."""
    url = f"{SERVER_URL}/trigger-intervention"

    payload = {"phone_number": phone_number, "type": "glucose"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Glucose intervention triggered: {result}")
        return result
    except Exception as e:
        logger.error(f"Error triggering glucose intervention: {e}")
        return {"status": "error", "message": str(e)}


def test_medication_intervention(phone_number):
    """Test a medication reminder intervention."""
    url = f"{SERVER_URL}/trigger-intervention"

    payload = {"phone_number": phone_number, "type": "medication"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Medication intervention triggered: {result}")
        return result
    except Exception as e:
        logger.error(f"Error triggering medication intervention: {e}")
        return {"status": "error", "message": str(e)}


def test_activity_intervention(phone_number):
    """Test an activity prompt intervention."""
    url = f"{SERVER_URL}/trigger-intervention"

    payload = {"phone_number": phone_number, "type": "activity"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Activity intervention triggered: {result}")
        return result
    except Exception as e:
        logger.error(f"Error triggering activity intervention: {e}")
        return {"status": "error", "message": str(e)}


def test_auto_intervention(phone_number):
    """Test auto-selected intervention based on patient data."""
    url = f"{SERVER_URL}/trigger-intervention"

    payload = {"phone_number": phone_number, "type": "auto"}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Auto intervention triggered: {result}")
        return result
    except Exception as e:
        logger.error(f"Error triggering auto intervention: {e}")
        return {"status": "error", "message": str(e)}


def test_scheduled_interventions():
    """Test running scheduled interventions for all users."""
    url = f"{SERVER_URL}/scheduled-interventions"

    try:
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Scheduled interventions processed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing scheduled interventions: {e}")
        return {"status": "error", "message": str(e)}


def simulate_user_message(phone_number, message):
    """Simulate a user sending a message via webhook."""
    url = f"{SERVER_URL}/webhook"

    payload = {"from": phone_number, "text": message}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Message sent: {result}")
        return result
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return {"status": "error", "message": str(e)}


def simulate_button_click(phone_number, payload):
    """Simulate a user clicking a button/quick reply via webhook."""
    url = f"{SERVER_URL}/webhook"

    data = {"from": phone_number, "payload": payload}

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()

        logger.info(f"Button click simulated: {result}")
        return result
    except Exception as e:
        logger.error(f"Error simulating button click: {e}")
        return {"status": "error", "message": str(e)}


def print_help():
    """Print usage information."""
    print(
        """
Usage: python test_interventions.py [command] [phone_number]

Commands:
  glucose [phone]     - Test glucose intervention
  medication [phone]  - Test medication reminder
  activity [phone]    - Test activity prompt
  auto [phone]        - Test auto-detection intervention
  scheduled           - Test scheduled interventions
  message [phone] [text] - Simulate user sending a message
  button [phone] [payload] - Simulate user clicking a button

Examples:
  python test_interventions.py glucose +1234567890
  python test_interventions.py message +1234567890 "My glucose feels low"
  python test_interventions.py button +1234567890 EXPLAIN_GLUCOSE_ALERT
  python test_interventions.py scheduled
    """
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "help":
        print_help()
        sys.exit(0)

    # Default phone number if needed
    default_phone = os.getenv("TEST_PHONE_NUMBER", "+11234567890")

    if command == "glucose" and len(sys.argv) >= 3:
        test_glucose_intervention(sys.argv[2])
    elif command == "glucose":
        test_glucose_intervention(default_phone)

    elif command == "medication" and len(sys.argv) >= 3:
        test_medication_intervention(sys.argv[2])
    elif command == "medication":
        test_medication_intervention(default_phone)

    elif command == "activity" and len(sys.argv) >= 3:
        test_activity_intervention(sys.argv[2])
    elif command == "activity":
        test_activity_intervention(default_phone)

    elif command == "auto" and len(sys.argv) >= 3:
        test_auto_intervention(sys.argv[2])
    elif command == "auto":
        test_auto_intervention(default_phone)

    elif command == "scheduled":
        test_scheduled_interventions()

    elif command == "message" and len(sys.argv) >= 4:
        phone = sys.argv[2]
        message = sys.argv[3]
        simulate_user_message(phone, message)

    elif command == "button" and len(sys.argv) >= 4:
        phone = sys.argv[2]
        payload = sys.argv[3]
        simulate_button_click(phone, payload)

    else:
        print("Invalid command or missing parameters")
        print_help()
        sys.exit(1)
