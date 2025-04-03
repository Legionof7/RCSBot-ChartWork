from flask import Flask, request, jsonify
import logging
from datetime import datetime
import os
import random
from typing import Dict, Any

from model_service import call_gemini, process_payload_response
from message_handler import send_message, get_pinnacle_client
from fhir_data import get_patient_data

# Configure logging
# These settings are used by basicConfig to properly format log messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize Pinnacle client once
pinnacle_client = get_pinnacle_client()

# Store user contexts (in a real app, this would be in a database)
user_contexts = {}


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming webhook requests from Pinnacle."""
    try:
        # Get request data
        webhook_data = request.json
        logger.info(f"Received webhook: {webhook_data}")

        # Extract essential data
        from_number = webhook_data.get("from", "")
        user_content = webhook_data.get("text", "")
        payload = webhook_data.get("payload", "")

        if not from_number:
            return jsonify({"status": "error", "message": "Missing sender number"}), 400

        # Handle button/quick reply payloads
        if payload:
            logger.info(f"Processing payload: {payload} from {from_number}")
            rcs_response = process_payload_response(payload)
        # Handle regular text messages
        elif user_content:
            # Get or create user context
            user_context = get_user_context(from_number)

            # Process the message using Gemini
            conversation = [{"role": "user", "content": user_content}]
            rcs_response = call_gemini(conversation, user_context)

            # Update user context based on this interaction
            update_user_context(from_number, user_content, rcs_response)
        else:
            return (
                jsonify({"status": "error", "message": "Missing text or payload"}),
                400,
            )

        # Send response with smart fallback
        response, message_type = send_message(
            to_number=from_number,
            rcs_response=rcs_response,
            pinnacle_client=pinnacle_client,
        )

        logger.info(f"Sent {message_type} response to {from_number}")
        return jsonify({"status": "success", "message_type": message_type})

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        }
    )


@app.route("/trigger-intervention", methods=["POST"])
def trigger_intervention():
    """Trigger a proactive micro-moment intervention."""
    try:
        data = request.json

        # Required parameters
        phone_number = data.get("phone_number")
        intervention_type = data.get(
            "type", "auto"
        )  # auto, glucose, medication, activity

        if not phone_number:
            return jsonify({"status": "error", "message": "Missing phone number"}), 400

        # Get user context or create if it doesn't exist
        user_context = get_user_context(phone_number)

        # Add or update context based on trigger type
        if intervention_type == "glucose":
            # Simulate decreasing glucose levels
            user_context["glucose_trend"] = "decreasing"
            user_context["current_glucose"] = 75
            user_context["intervention_type"] = "glucose"
        elif intervention_type == "medication":
            # Simulate medication reminder need
            user_context["medication_due"] = True
            user_context["intervention_type"] = "medication"
        elif intervention_type == "activity":
            # Simulate sedentary behavior
            user_context["activity_state"] = "sedentary"
            user_context["hours_inactive"] = 3
            user_context["intervention_type"] = "activity"
        else:
            # Auto-detect what intervention might be needed based on patient data
            patient_data = get_patient_data("all")
            user_context["intervention_type"] = "auto"

            # Example logic to determine intervention type
            # In a real app, this would be more sophisticated
            glucose_values = [
                lab["value"]
                for lab in patient_data.get("labResults", [])
                if lab.get("test") == "Fasting Glucose"
            ]
            if glucose_values and glucose_values[0] > 120:
                user_context["intervention_type"] = "glucose"
                user_context["current_glucose"] = glucose_values[0]

        # Create a special intervention request
        intervention_request = [
            {
                "role": "user",
                "content": "SYSTEM: Generate a proactive micro-moment intervention for the user.",
            }
        ]

        # Generate intervention using the AI model
        rcs_response = call_gemini(intervention_request, user_context)

        # Send the intervention
        response, message_type = send_message(
            to_number=phone_number,
            rcs_response=rcs_response,
            pinnacle_client=pinnacle_client,
        )

        logger.info(
            f"Sent proactive {intervention_type} intervention ({message_type}) to {phone_number}"
        )
        return jsonify(
            {
                "status": "success",
                "message_type": message_type,
                "intervention_type": intervention_type,
            }
        )

    except Exception as e:
        logger.error(f"Error triggering intervention: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/scheduled-interventions", methods=["POST"])
def run_scheduled_interventions():
    """
    Run scheduled interventions for all users.
    This would typically be triggered by a cron job or scheduler.
    """
    try:
        # Get all registered users (in a real app, from database)
        # Here we're using the in-memory user_contexts as a simulation
        results = []
        current_hour = datetime.now().hour

        for phone_number, context in user_contexts.items():
            # Check if user should receive an intervention based on time and data
            should_send = determine_if_intervention_needed(
                phone_number, context, current_hour
            )

            if should_send:
                # Determine intervention type based on user data and time of day
                intervention_type = select_intervention_type(context, current_hour)

                # Update context with intervention type
                context["intervention_type"] = intervention_type

                # Create intervention request
                intervention_request = [
                    {
                        "role": "user",
                        "content": f"SYSTEM: Generate a scheduled {intervention_type} intervention.",
                    }
                ]

                # Generate and send intervention
                rcs_response = call_gemini(intervention_request, context)
                response, message_type = send_message(
                    to_number=phone_number,
                    rcs_response=rcs_response,
                    pinnacle_client=pinnacle_client,
                )

                results.append(
                    {
                        "phone_number": phone_number,
                        "intervention_type": intervention_type,
                        "status": "sent",
                    }
                )

                logger.info(
                    f"Sent scheduled {intervention_type} intervention to {phone_number}"
                )
            else:
                results.append({"phone_number": phone_number, "status": "skipped"})

        return jsonify(
            {
                "status": "success",
                "interventions_processed": len(user_contexts),
                "interventions_sent": len(
                    [r for r in results if r.get("status") == "sent"]
                ),
                "results": results,
            }
        )

    except Exception as e:
        logger.error(f"Error processing scheduled interventions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


def get_user_context(phone_number: str) -> Dict[str, Any]:
    """
    Get or create user context.
    In a real app, this would be stored in a database.
    """
    if phone_number not in user_contexts:
        # Initialize with defaults
        user_contexts[phone_number] = {
            "last_interaction": datetime.now().isoformat(),
            "location": "unknown",
            "activity": "unknown",
            "time_of_day": get_time_of_day(),
            "last_meal": random.randint(1, 8),  # Hours since last meal
            "glucose_readings": [],
            "medication_adherence": {},
        }

    # Always update time of day
    user_contexts[phone_number]["time_of_day"] = get_time_of_day()

    return user_contexts[phone_number]


def update_user_context(
    phone_number: str, user_message: str, response: Dict[str, Any]
) -> None:
    """
    Update user context based on the interaction.
    In a real app, this would use more sophisticated NLP and data management.
    """
    context = user_contexts.get(phone_number, {})

    # Update last interaction time
    context["last_interaction"] = datetime.now().isoformat()

    # Basic NLP to detect location mentions (very simplified)
    location_keywords = {
        "home": ["home", "house", "apartment", "living room", "bedroom", "kitchen"],
        "work": ["work", "office", "job", "workplace", "desk"],
        "outside": ["outside", "walking", "running", "park", "gym"],
    }

    for location, keywords in location_keywords.items():
        if any(keyword in user_message.lower() for keyword in keywords):
            context["location"] = location
            break

    # Detect activity mentions (very simplified)
    activity_keywords = {
        "active": ["exercising", "walking", "running", "gym", "workout", "active"],
        "sedentary": ["sitting", "resting", "watching", "reading", "working"],
        "sleeping": ["sleeping", "nap", "bed", "tired", "rest"],
    }

    for activity, keywords in activity_keywords.items():
        if any(keyword in user_message.lower() for keyword in keywords):
            context["activity"] = activity
            break

    # Store the updated context
    user_contexts[phone_number] = context


def determine_if_intervention_needed(
    phone_number: str, context: Dict[str, Any], current_hour: int
) -> bool:
    """
    Determine if an intervention should be sent based on user data and time.
    In a real app, this would use more sophisticated logic.
    """
    # Don't send interventions during late night hours (11pm-6am)
    if current_hour >= 23 or current_hour < 6:
        return False

    # Check when last interaction occurred
    last_interaction = datetime.fromisoformat(
        context.get("last_interaction", "2020-01-01T00:00:00")
    )
    hours_since_interaction = (datetime.now() - last_interaction).total_seconds() / 3600

    # Don't send if user interacted in the last hour
    if hours_since_interaction < 1:
        return False

    # Randomize a bit to avoid predictability
    chance = random.random()

    # Higher chance of intervention if it's been a while
    if hours_since_interaction > 24:
        return chance < 0.8  # 80% chance
    elif hours_since_interaction > 12:
        return chance < 0.5  # 50% chance
    elif hours_since_interaction > 6:
        return chance < 0.3  # 30% chance
    else:
        return chance < 0.1  # 10% chance


def select_intervention_type(context: Dict[str, Any], current_hour: int) -> str:
    """
    Select which type of intervention to send based on context and time.
    In a real app, this would use more sophisticated logic.
    """
    # Morning (6am-10am): Focus on glucose and medication
    if 6 <= current_hour < 10:
        return random.choice(["glucose", "medication"])

    # Middle of day (10am-2pm): Focus on activity
    elif 10 <= current_hour < 14:
        return random.choice(["activity", "glucose"])

    # Afternoon (2pm-6pm): Mix of all types
    elif 14 <= current_hour < 18:
        return random.choice(["glucose", "activity", "medication"])

    # Evening (6pm-11pm): Focus on medication and educational
    else:
        return random.choice(["medication", "educational"])


def get_time_of_day() -> str:
    """Get the current time of day classification."""
    current_hour = datetime.now().hour

    if 5 <= current_hour < 12:
        return "morning"
    elif 12 <= current_hour < 17:
        return "afternoon"
    elif 17 <= current_hour < 22:
        return "evening"
    else:
        return "night"


if __name__ == "__main__":
    # Check if we have required environment variables
    if not os.getenv("PINNACLE_API_KEY"):
        logger.warning("PINNACLE_API_KEY not set. Some functionality will be limited.")

    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY not set. Application will not function correctly.")
        exit(1)

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)
