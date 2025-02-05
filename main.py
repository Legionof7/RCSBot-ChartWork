# main.py
from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime
import os
import requests
import time
import json
import base64
import traceback

from fhir_data import get_patient_data
from graph_utils import generate_graph

# --------------------------
#      CONFIG & GLOBALS
# --------------------------

FHIR_DATA = get_patient_data()  # Patient data
MODEL = "google/gemini-flash-1.5"
OPENROUTER_API_KEY = "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"

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
#        HELPER FUNCTIONS
# -----------------------------

def create_context(query: str) -> str:
    """
    Builds a system prompt that explains how to format the JSON for an RCS message
    and includes relevant instructions plus the patient's FHIR data.
    """
    graph_formats = '''
GRAPH_DATA:{"type": "<graph_type>", "data": <data_object>}END_GRAPH_DATA

Supported graph types and formats:

1. Bar Chart:
GRAPH_DATA:{"type": "bar", "data": {
    "labels": ["Label1", "Label2", "Label3"],
    "values": [10, 20, 30],
    "title": "Bar Chart Title",
    "xlabel": "Categories",
    "ylabel": "Values",
    "referenceLines": {"Label1": 15, "Label2": 25}
}}END_GRAPH_DATA

2. Line Chart:
GRAPH_DATA:{"type": "line", "data": {
    "x": ["2023-01", "2023-02", "2023-03"],
    "y": [10, 20, 15],
    "title": "Trend Analysis",
    "xlabel": "Time Period",
    "ylabel": "Values"
}}END_GRAPH_DATA

3. Scatter Plot:
GRAPH_DATA:{"type": "scatter", "data": {
    "x": [1, 2, 3, 4, 5],
    "y": [2, 4, 3, 5, 4],
    "title": "Correlation Plot",
    "xlabel": "X Values",
    "ylabel": "Y Values"
}}END_GRAPH_DATA
'''

    rcs_instructions = f"""
You are an AI assistant for SlothMD. Generate JSON in this format to make your reply. The JSON must follow this format for RCS:

{{
  "text": "Main message text",
  "cards": [
    {{
      "title": "Card title",
      "subtitle": "Card subtitle (main content)",
      "media_url": "{{GRAPH_URL_N}}",  // Use {{GRAPH_URL_0}}, {{GRAPH_URL_1}} etc for multiple graphs
      "buttons": [
        {{
          "title": "More Information",  // Always include for health information
          "type": "trigger",
          "payload": "more_info_[relevant_topic]"  // Replace [relevant_topic] with actual topic
        }}
      ]
    }}
  ],
  "quick_replies": [
    {{
      "title": "Quick reply text",
      "type": "trigger",
      "payload": "quick_reply_action"
    }}
  ],
  "graph": {{
    "type": "bar|line|scatter",
    "data": {{}}  // Always include for broad metric-related queries asking about levels/numbers
  }}
}}

Important:
1. All health information cards MUST include a "See More" button
2. All metric-related queries MUST include a graph visualization
3. Always include quick reply actions using the context of the metrics. You MUST have follow-up questions.:
Examples:
   - "Schedule Appointment" (payload: schedule_appointment)
   - "View Care Plan" (payload: view_care_plan)
   - "Contact Doctor" (payload: contact_doctor)
   - "View Medications" (payload: view_medications)
   - "Check Lab Results" (payload: check_labs)
   - "Connect Wearable" (payload: connect_wearable) <-- send this when more data is requested/needed
4. Use appropriate graph types:
   - bar: for comparing values
   - line: for trends over time
   - scatter: for correlation analysis
5. Titles MUST be under 25 characters in length.


When including a graph, embed data using:
{graph_formats}


Below is the patient's FHIR data (only address relevant healthcare questions):
{json.dumps(FHIR_DATA, indent=2)}
"""
    return rcs_instructions

def call_openrouter(messages) -> dict:
    """
    Calls the Deepseek model via OpenRouter with the conversation plus RCS context.
    Returns a dict with the JSON we expect for RCS.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }
    latest_message = messages[-1]["content"] if messages else ""
    context = create_context(latest_message)

    data = {
        "model": MODEL,
        "messages": [{"role": "system", "content": context}] + messages,
    }

    logger.info(f"Sending request to Deepseek (OpenRouter): {data}")
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"Deepseek response: {response_json}")
        return response_json["choices"][0]["message"]
    except Exception as e:
        logger.error(f"OpenRouter/Deepseek API error: {str(e)}")
        raise

def save_and_upload_image(img_path: str) -> str:
    """
    Upload a saved image from the local filesystem to Pinnacle.
    """
    try:
        # Verify the file exists and is not empty
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 100:
            raise ValueError("Invalid image file generated")

        # Upload using Pinnacle
        download_url = client.upload(img_path)
        return download_url
    except Exception as e:
        logger.error(f"Failed to upload image: {str(e)}")
        raise
        return download_url
    except Exception as e:
        logger.error(f"Failed to upload image: {str(e)}")
        raise

def send_rcs_message(to_number: str, response_data: dict):
    """
    Takes JSON from Deepseek (text/cards/quick_replies/graph),
    generates a graph if needed, then sends an RCS message via Pinnacle.
    """
    text = response_data.get("text", "")
    cards = response_data.get("cards", [])
    quick_replies = response_data.get("quick_replies", [])
    image_url = None

    logger.info("Checking for graph data...")
    print("\n=== Graph Generation Debug ===")
    print(f"Response data keys: {response_data.keys()}")
    if "graph" in response_data and response_data["graph"]:
        try:
            print(f"Graph data found: {json.dumps(response_data['graph'], indent=2)}")
            g_type = response_data["graph"]["type"]
            g_data = response_data["graph"]["data"]
            print(f"Attempting to generate {g_type} graph with data:")
            print(json.dumps(g_data, indent=2))
            logger.info(f"Generating graph of type {g_type}")
            generate_graph(g_type, g_data)  # This will save to debug_chart.png
            logger.info("Graph generated successfully, uploading to Pinnacle")
            image_url = save_and_upload_image('debug_chart.png')
            logger.info(f"Image uploaded successfully, URL: {image_url}")
        except Exception as e:
            logger.error(f"Graph generation/upload failed:")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    # Clean and validate cards
    valid_cards = []
    print("\n=== Card Processing Debug ===")
    print(f"Number of cards: {len(cards)}")
    print(f"Image URL available: {image_url}")

    logger.info(f"Processing {len(cards)} cards")
    for idx, card in enumerate(cards):
        print(f"\nCard {idx + 1}:")
        print(f"Raw card data: {json.dumps(card, indent=2)}")

        clean_card = {
            "title": card.get("title", "Information"),
            "subtitle": card.get("description", "") or card.get("subtitle", ""),  # Use description as subtitle, fallback to subtitle
            "buttons": card.get("buttons", [])
        }
        print(f"Initial media_url: {card.get('media_url')}")

        # Handle graph URL placeholder
        media_url = card.get("media_url")
        logger.info(f"Processing media_url: {media_url}, image_url available: {bool(image_url)}")
        if image_url and media_url and isinstance(media_url, str) and media_url.startswith("{GRAPH_URL_"):
            logger.info(f"Setting media_url to image_url: {image_url}")
            clean_card["media_url"] = image_url
        logger.info(f"Final card {idx + 1} media_url: {clean_card.get('media_url', 'not set')}")
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

        print("\n=== Final RCS Parameters ===")
        print(json.dumps(rcs_params, indent=2))

        rcs_response = client.send.rcs(**rcs_params)
        logger.info(f"RCS send response: {rcs_response}")
    except Exception as e:
        logger.error(f"Failed to send RCS message: {str(e)}")
        raise

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
                # Handle button/quick reply actions
                user_text = f"{parsed_data.action_title}: {parsed_data.payload}"
                logger.info(f"Received action: {user_text}")

                # Handle Terra wearable connection
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

        # Call Deepseek
        try:
            ai_response = call_openrouter(conversation_slice)
            content = ai_response.get("content", "{}")
            print("\n=== AI Model Response ===")
            print(content)
            print("=====================\n")
            logger.info(f"Raw Deepseek response content: {content}")

            # Extract JSON content between code fences
            json_start = content.find('```json')
            if json_start != -1:
                json_end = content.find('```', json_start + 7)
                if json_end != -1:
                    json_content = content[json_start + 7:json_end].strip()
                else:
                    json_content = "{}"
            else:
                # Try to find a complete JSON object
                start_brace = content.find('{')
                if start_brace != -1:
                    # Find matching end brace
                    brace_count = 0
                    for i in range(start_brace, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_content = content[start_brace:i+1].strip()
                                break
                    else:
                        json_content = "{}"


                else:
                    json_content = "{}"

            try:
                # Ensure we're working with valid JSON
                json_content = json_content.strip()
                if not json_content.startswith('{'):
                    json_content = "{}"
                response_data = json.loads(json_content)
                if not isinstance(response_data, dict):
                    response_data = {"text": "I apologize, but I encountered an error. How else can I help you today?"}

                # Extract graph data if present
                if 'GRAPH_DATA:' in content:
                    try:
                        graph_data = content.split('GRAPH_DATA:', 1)[1].split('END_GRAPH_DATA')[0]
                        graph_json = json.loads(graph_data)
                        if isinstance(graph_json, dict) and 'type' in graph_json and 'data' in graph_json:
                            response_data['graph'] = graph_json
                        else:
                            logger.error(f"Invalid graph data structure: {graph_json}")
                            response_data['graph'] = None
                    except Exception as e:
                        logger.error(f"Failed to parse graph data: {str(e)}")
                        response_data['graph'] = None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Deepseek JSON response. Content: {json_content}")
                logger.error(f"JSON parse error: {str(e)}")
                # Fallback to simple text response
                response_data = {
                    "text": "I apologize, but I encountered an error processing your request. How else can I help you today?"
                }

            # Send RCS
            send_rcs_message(from_number, response_data)

            # Save assistant response
            app.conversation_history[from_number].append(
                {"role": "assistant", "content": json.dumps(response_data)}
            )
        except Exception as e:
            logger.error(f"Error processing user message: {e}")

        return "Webhook received", 200
    else:
        # On GET, display a simple table of recent inbound messages
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

        # Send RCS message with connection URL
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

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)