from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime
import os
import json
import traceback
import requests

from fhir_data import get_patient_data
from graph_utils import generate_graph
from model_service import call_openrouter

# --------------------------
#      CONFIG & GLOBALS
# --------------------------

FHIR_DATA = get_patient_data()  # Patient data

app = Flask(__name__)
app.messages = []
app.conversation_history = {}

# Create a memory log handler
class MemoryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []

    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
                'level': record.levelname,
                'message': self.format(record),
                'exc_info': record.exc_info[1] if record.exc_info else None
            }
            self.logs.append(log_entry)
        except:
            pass

memory_handler = MemoryLogHandler()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
memory_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()
root_logger.handlers = []
root_logger.addHandler(memory_handler)
root_logger.addHandler(stream_handler)
logger = logging.getLogger(__name__)
logger.info("Logging system initialized")

# -----------------------------
#  PINNACLE RCS CLIENT SETUP
# -----------------------------

api_key = "2d327443-23ea-436e-be88-2eba46e15550"  # Example
client = Pinnacle(
    api_key=api_key,
    timeout=60.0
)

# -----------------------------
#        RCS FUNCTIONS
# -----------------------------

def save_and_upload_image(img_path: str) -> str:
    """Upload a saved image from the local filesystem to Pinnacle."""
    try:
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 100:
            raise ValueError("Invalid image file generated")
        return client.upload(img_path)
    except Exception as e:
        logger.error(f"Failed to upload image: {str(e)}")
        raise

def send_rcs_message(to_number: str, response_data: dict):
    """Process and send an RCS message via Pinnacle."""
    text = response_data.get("text", "")
    cards = response_data.get("cards", [])
    quick_replies = response_data.get("quick_replies", [])
    image_url = None

    logger.info("Checking for graph data...")
    if "graph" in response_data and response_data["graph"]:
        try:
            g_type = response_data["graph"]["type"]
            g_data = response_data["graph"]["data"]
            logger.info(f"Generating graph of type {g_type}")
            generate_graph(g_type, g_data)
            logger.info("Graph generated successfully, uploading to Pinnacle")
            image_url = save_and_upload_image('debug_chart.png')
            logger.info(f"Image uploaded successfully, URL: {image_url}")
        except Exception as e:
            logger.error(f"Graph generation/upload failed:")
            logger.error(traceback.format_exc())

    # Clean and validate cards
    valid_cards = []
    logger.info(f"Processing {len(cards)} cards")
    for idx, card in enumerate(cards):
        clean_card = {
            "title": card.get("title", "Information"),
            "subtitle": card.get("description", "") or card.get("subtitle", ""),
            "buttons": card.get("buttons", [])
        }

        media_url = card.get("media_url")
        if image_url and media_url and isinstance(media_url, str) and media_url.startswith("{GRAPH_URL_"):
            logger.info(f"Setting media_url to image_url: {image_url}")
            clean_card["media_url"] = image_url
        valid_cards.append(clean_card)

    # Send final RCS message
    try:
        rcs_params = {
            "to": to_number,
            "from_": "test"
        }

        if quick_replies:
            rcs_params["quick_replies"] = quick_replies

        if valid_cards:
            rcs_params["cards"] = valid_cards
        elif text:
            rcs_params["text"] = text
        else:
            rcs_params["text"] = "No content available"

        rcs_response = client.send.rcs(**rcs_params)
        logger.info(f"RCS send response: {rcs_response}")
    except Exception as e:
        logger.error(f"Failed to send RCS message: {str(e)}")
        raise

def connect_terra_wearable(from_number: str):
    """Generate Terra widget session and send URL via RCS"""
    try:
        response = requests.post(
            "https://api.tryterra.co/v2/auth/generateWidgetSession",
            headers={
                "dev-id": "slothmd-testing-1BYwaAYSKe",
                "x-api-key": "qb6CK_EcpleOaUWzh4E0MKYnQMAALrqm"
            },
            json={
                "reference_id": from_number,
                "lang": "en"
            }
        )
        url = response.json()["url"]

        client.send.rcs(
            to=from_number,
            from_="test",
            cards=[{
                "title": "Connect Device",
                "subtitle": "Click below to connect your wearable device",
                "buttons": [{
                    "title": "Connect Now",
                    "type": "openUrl",
                    "payload": url
                }]
            }]
        )
    except Exception as e:
        logger.error(f"Terra connection error: {str(e)}")

# -----------------------------
#         FLASK ROUTES
# -----------------------------

@app.route("/", methods=['GET', 'POST'])
@app.route("/webhook", methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'POST':
        raw_data = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Received webhook @ {timestamp}, raw data: {raw_data}")

        try:
            json_data = request.get_json()
            parsed_data = Pinnacle.parse_inbound_message(json_data)
            from_number = parsed_data.from_

            # Handle different types of inbound messages
            if hasattr(parsed_data, 'text'):
                user_text = parsed_data.text.strip()
            elif hasattr(parsed_data, 'postback'):
                user_text = parsed_data.postback.strip()
            elif hasattr(parsed_data, 'action_title') and hasattr(parsed_data, 'payload'):
                user_text = f"{parsed_data.action_title}: {parsed_data.payload}"
                logger.info(f"Received action: {user_text}")

                if parsed_data.payload == "connect_wearable":
                    connect_terra_wearable(from_number)
                    return "Webhook received", 200
            else:
                logger.warning(f"Unsupported message type received: {parsed_data}")
                return "Webhook received", 200
        except Exception as e:
            logger.error(f"Failed to parse inbound message: {str(e)}")
            return "Webhook received", 200

        # Store for debugging
        app.messages.append({
            'timestamp': timestamp,
            'data': raw_data,
            'parsed': parsed_data.__dict__ if parsed_data else "Parse error"
        })

        # Conversation logic
        app.conversation_history.setdefault(from_number, [])
        app.conversation_history[from_number].append({"role": "user", "content": user_text})
        conversation_slice = app.conversation_history[from_number][-6:]

        # Call model and send response
        try:
            response_data = call_openrouter(conversation_slice, FHIR_DATA)
            send_rcs_message(from_number, response_data)
            app.conversation_history[from_number].append(
                {"role": "assistant", "content": json.dumps(response_data)}
            )
        except Exception as e:
            logger.error(f"Error processing user message: {e}")

        return "Webhook received", 200
    else:
        # Display recent messages table
        html_content = '''
            <h1>RCS Webhook Receiver</h1>
            <meta http-equiv="refresh" content="20">
            <table border="1" cellspacing="0" cellpadding="5">
              <tr><th>Time</th><th>Raw Data</th><th>Parsed Data</th></tr>
        '''
        for msg in reversed(app.messages):
            html_content += f'''
              <tr>
                <td>{msg['timestamp']}</td>
                <td><pre>{msg['data']}</pre></td>
                <td><pre>{msg['parsed']}</pre></td>
              </tr>
            '''
        html_content += '</table>'
        return html_content

@app.route("/logs", methods=["GET"])
def view_logs():
    html_content = '''
        <h1>Application Logs</h1>
        <meta http-equiv="refresh" content="10">
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .INFO { color: black; }
            .ERROR { color: red; }
            .WARNING { color: orange; }
        </style>
        <table>
            <tr><th>Timestamp</th><th>Level</th><th>Message</th></tr>
    '''
    for log in reversed(memory_handler.logs):
        html_content += f'''
            <tr>
                <td>{log['timestamp']}</td>
                <td class="{log['level']}">{log['level']}</td>
                <td>{log['message']}</td>
            </tr>
        '''
    html_content += '</table>'
    return html_content

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)