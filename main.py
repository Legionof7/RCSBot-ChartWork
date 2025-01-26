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

from fhir_data import get_patient_data
from graph_utils import generate_graph

# --------------------------
#      CONFIG & GLOBALS
# --------------------------

FHIR_DATA = get_patient_data()  # Patient data
MODEL = "deepseek/deepseek-r1-distill-llama-70b"
OPENROUTER_API_KEY = "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"
IMGBB_API_KEY = "dc9385b3e6c2b601de1361a53e98e869"

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

Example:
GRAPH_DATA:{"type": "bar", "data": {"labels": ["HbA1c", "Glucose", "LDL"], "values": [6.8, 110, 110], "title": "Lab Results", "xlabel": "Test", "ylabel": "Value", "referenceLines": {"HbA1c": 7.0, "Glucose": 100, "LDL": 100}}}END_GRAPH_DATA
'''

    rcs_instructions = f"""
You are an AI assistant for SlothMD. Generate JSON in this format to make your reply. The JSON must follow this format for RCS:

{{
  "text": "Main message text",
  "cards": [
    {{
      "title": "Card title",
      "subtitle": "Optional subtitle", 
      "description": "Card description",
      "media_url": "{{GRAPH_URL_N}}",  // Use {{GRAPH_URL_0}}, {{GRAPH_URL_1}} etc for multiple graphs
      "buttons": [
        {{
          "title": "Button text",
          "type": "trigger",
          "payload": "button_action"
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
    "data": {{}}
  }}
}}

When including a graph, embed data using:
{graph_formats}

When providing insights, generate at least 3. Each insight:
- References relevant data points
- Includes actionable steps
- Draws connections among metrics
- ~3-4 sentences each
- Highlights tangible markers of success

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

def upload_base64_to_imgbb(img_b64: str) -> str:
    """
    Upload base64 image data to imgbb and return the public URL.
    """
    upload_url = 'https://api.imgbb.com/1/upload'
    payload = {
        'key': IMGBB_API_KEY,
        'image': img_b64,
        'name': f'graph_{int(time.time())}.png'
    }
    resp = requests.post(upload_url, data=payload)
    resp.raise_for_status()
    return resp.json()['data']['url']

def send_rcs_message(to_number: str, response_data: dict):
    """
    Takes JSON from Deepseek (text/cards/quick_replies/graph),
    generates a graph if needed, then sends an RCS message via Pinnacle.
    """
    text = response_data.get("text", "")
    cards = response_data.get("cards", [])
    quick_replies = response_data.get("quick_replies", [])

    if "graph" in response_data:
        try:
            g_type = response_data["graph"]["type"]
            g_data = response_data["graph"]["data"]
            img_b64 = generate_graph(g_type, g_data)
            image_url = upload_base64_to_imgbb(img_b64)
            # Replace numbered placeholder URL in existing card
            graph_placeholder = f"{{GRAPH_URL_{len([c for c in cards if '{{GRAPH_URL_' in str(c.get('media_url', ''))])}}}"
            for card in cards:
                if card.get("media_url") == graph_placeholder:
                    card["media_url"] = image_url
                    break
        except Exception as e:
            logger.error(f"Graph generation/upload failed: {str(e)}")

    # Send final RCS message
    try:
        rcs_params = {
            "to": to_number,
            "from_": "test",
            "quick_replies": quick_replies
        }
        
        # Only include either text or cards, not both
        if cards:
            rcs_params["cards"] = cards
        else:
            rcs_params["text"] = text
            
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
            logger.info(f"Raw Deepseek response content: {content}")
            
            # Remove markdown code fences if present and split content
            json_content = content.split('GRAPH_DATA:', 1)[0].strip()
            if json_content.startswith('```json'):
                json_content = json_content[7:]  # Remove ```json prefix
            if json_content.endswith('```'):
                json_content = json_content[:-3]  # Remove ``` suffix
                
            json_content = json_content.strip()
            try:
                response_data = json.loads(json_content)
                
                # Extract graph data if present
                if 'GRAPH_DATA:' in content:
                    graph_data = content.split('GRAPH_DATA:', 1)[1].split('END_GRAPH_DATA')[0]
                    graph_json = json.loads(graph_data)
                    response_data['graph'] = graph_json
                    
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

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)