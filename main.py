from flask import Flask, request
from rcs import Pinnacle, Messaging
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
MODEL = "deepseek/deepseek-r1"
OPENROUTER_API_KEY = "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"  # Example placeholder key
IMGBB_API_KEY = "dc9385b3e6c2b601de1361a53e98e869"       # Example placeholder key

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
#  PINNACLE & MESSAGING SETUP
# -----------------------------

# Initialize RCS client
api_key = "2d327443-23ea-436e-be88-2eba46e15550"  
client = Pinnacle(
    api_key=api_key,
    timeout=60.0
)

messaging = Messaging(
    opt_in="Hey there, it's SlothMD! ... Reply 'STOP' anytime to end communication.",
    opt_out="Reply STOP to unsubscribe. ...",
    opt_out_keywords=["STOP", "UNSUBSCRIBE"],
    agent_use_case="SlothMD's agent assists with health management...",
    expected_agent_responses="General Inquiry: ... Escalation: ..."
)

# -----------------------------
#        HELPER FUNCTIONS
# -----------------------------

def create_context(query: str, can_use_rcs: bool = False) -> str:
    graph_formats = '''
GRAPH_DATA:{"type": "<graph_type>", "data": <data_object>}END_GRAPH_DATA

Example graph:
GRAPH_DATA:{"type": "bar", "data": {"labels": ["HbA1c", "Glucose", "LDL"], "values": [6.8, 110, 110], "title": "Lab Results", "xlabel": "Test", "ylabel": "Value", "referenceLines": {"HbA1c": 7.0, "Glucose": 100, "LDL": 100}}}END_GRAPH_DATA

Supported graph types and their data formats:
1. "line" - {"x": [...], "y": [...], "title": "...", "xlabel": "...", "ylabel": "..."}
2. "bar"  - {"labels": [...], "values": [...], "title": "...", "xlabel": "...", "ylabel": "..."}
3. "scatter" - {"x": [...], "y": [...], "title": "...", "xlabel": "...", "ylabel": "..."}
'''
    return f"""
You are an AI assistant for SlothMD. Your focus is to provide concise, empathetic, and expert health management guidance. 
RCS capability is {"enabled" if can_use_rcs else "disabled"}—when enabled, you may use richer formatting; otherwise, stick to plain text or MMS. 
Always communicate in a friendly, accessible style.

When you need to visualize data, embed the following marker in your response:
{graph_formats}

When providing insights, generate at least 3. Each insight:
• References relevant data points
• Offers a clear problem-to-solution flow
• Includes actionable steps with timelines
• Draws connections among multiple health metrics
• Suggests concrete ways to track progress
• Stays succinct: ~3-4 sentences each
• Highlights tangible markers of success

Below is the patient's FHIR data:
{json.dumps(FHIR_DATA, indent=2)}

Only address healthcare-related questions. Do not generate code or answer unrelated queries.
"""


def call_openrouter(messages, to_number: str) -> dict:
    """
    Calls the OpenRouter API with the conversation history plus relevant context.
    Returns a dict with at least {"content": "..."}.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }
    latest_message = messages[-1]["content"] if messages else ""

    # Check RCS capability
    try:
        rcs_functionality = client.get_rcs_functionality(phone_number=to_number)
        can_use_rcs = bool(getattr(rcs_functionality, 'is_enabled', False))
    except Exception as e:
        logger.error(f"Failed to check RCS functionality: {e}")
        can_use_rcs = False

    context = create_context(latest_message, can_use_rcs)
    data = {
        "model": MODEL,
        "messages": [{"role": "system", "content": context}, *messages],
    }

    try:
        logger.info(f"Sending request to OpenRouter: {data}")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"Received OpenRouter response: {response_json}")
        return response_json["choices"][0]["message"]
    except Exception as e:
        logger.error(f"OpenRouter API error: {str(e)}")
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

def send_message_with_retry(to_number: str, text: str = "", media_urls=None) -> None:
    """
    Send a text or media message to 'to_number' via RCS if possible, otherwise SMS/MMS.
    Automatically chunks very long messages into multiple parts.
    Retries up to 3 times with exponential backoff.
    """
    if media_urls is None:
        media_urls = []

    # Check RCS capability once
    try:
        rcs_func = client.get_rcs_functionality(phone_number=to_number)
        can_use_rcs = bool(getattr(rcs_func, 'is_enabled', False))
    except Exception:
        can_use_rcs = False

    # Break text into chunks
    max_length = 1600
    chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)] or [""]

    for chunk in chunks:
        for attempt in range(3):
            try:
                if can_use_rcs:
                    if media_urls:
                        # Minimal example of sending RCS with media
                        response = client.send.rcs(
                            to=to_number,
                            from_="test",
                            text=chunk,  # or using RCS cards
                        )
                    else:
                        response = client.send.rcs(
                            to=to_number,
                            from_="test",
                            text=chunk
                        )
                else:
                    # If not RCS, fallback to MMS if we have media, else SMS
                    if media_urls:
                        response = client.send.mms(
                            to=to_number,
                            from_="+18337750778",
                            text=chunk if chunk.strip() else None,
                            media_urls=media_urls
                        )
                    else:
                        response = client.send.sms(
                            to=to_number,
                            from_="+18337750778",
                            text=chunk
                        )
                logger.info(f"Message sent successfully (attempt {attempt+1}): {response}")
                break
            except Exception as e:
                logger.error(f"Send attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep(1 << attempt)  # exponential backoff: 1s, 2s
                else:
                    logger.error("Max retries reached, message send failed")

def extract_and_send_graph(response_content: str, to_number: str) -> str:
    """
    Detect graph data in response_content, generate/upload the graph, then send it.
    Returns the text content after extracting the graph section (if any).
    """
    if "GRAPH_DATA:" not in response_content:
        return response_content  # No graph data, do nothing

    try:
        # Split out the portion before "GRAPH_DATA:" (graph_part) just for leading text
        graph_part, remainder = response_content.split("GRAPH_DATA:", 1)
        graph_data_str = remainder.split("END_GRAPH_DATA")[0].strip()
        after_graph = remainder.split("END_GRAPH_DATA", 1)[1]

        graph_info = json.loads(graph_data_str)
        img_b64 = generate_graph(
            graph_info["type"],
            graph_info.get("data", {})
        )

        # Upload to imgbb and send
        image_url = upload_base64_to_imgbb(img_b64)
        # Send leading text + the graph image
        if graph_part.strip():
            send_message_with_retry(to_number, graph_part.strip(), media_urls=[image_url])
        else:
            send_message_with_retry(to_number, media_urls=[image_url])

        # Return whatever text remains after the graph
        return after_graph.strip()

    except Exception as e:
        logger.error(f"Failed to generate or send graph: {e}")
        return "Sorry, I couldn't generate the graph.\n" + response_content

# -----------------------------
#         FLASK ROUTES
# -----------------------------

@app.route("/", methods=['GET', 'POST'])
@app.route("/webhook", methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'POST':
        raw_data = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Received webhook at {timestamp} - Raw data: {raw_data}")

        try:
            json_data = request.get_json()
            parsed_data = Pinnacle.parse_inbound_message(json_data)
            logger.info(f"Parsed inbound message: {parsed_data}")
        except Exception as e:
            logger.error(f"Failed to parse message: {str(e)}")
            parsed_data = None

        # Always store for debug
        app.messages.append({
            'timestamp': timestamp,
            'data': raw_data,
            'parsed': parsed_data if parsed_data else "Parse error"
        })

        if not parsed_data or not hasattr(parsed_data, 'text'):
            return "Webhook received", 200

        from_number = parsed_data.from_
        user_text = parsed_data.text.lower().strip()

        # Simple subscription flows
        if 'slothmd' in user_text:
            send_message_with_retry(
                from_number,
                "Hey there, it's SlothMD! ... Standard message & data rates may apply. Reply 'STOP' anytime."
            )
        elif 'sloth' in user_text:
            send_message_with_retry(
                from_number,
                "You're in! Expect access to early texting features..."
            )
        else:
            # General conversation logic
            app.conversation_history.setdefault(from_number, [])
            app.conversation_history[from_number].append({"role": "user", "content": parsed_data.text})

            # Limit to last 6 messages
            conversation_slice = app.conversation_history[from_number][-6:]
            try:
                ai_response = call_openrouter(conversation_slice, from_number)
                response_text = ai_response.get("content", "").strip()

                if not response_text:
                    raise ValueError("Empty AI response")

                # If there's a GRAPH_DATA section, handle it first
                remainder_text = extract_and_send_graph(response_text, from_number)

                # Send the rest of the text
                if remainder_text:
                    send_message_with_retry(from_number, remainder_text)

                # Save assistant response
                app.conversation_history[from_number].append({"role": "assistant", "content": response_text})

            except Exception as e:
                logger.error(f"Failed to process chat message: {e}")

        return "Webhook received", 200

    else:
        # GET request: show last inbound messages
        html_content = '''
            <h1>Webhook Receiver</h1>
            <meta http-equiv="refresh" content="30">
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
            <table>
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

@app.route("/send", methods=['GET'])
def send_message():
    return '''
        <h2>Send Message</h2>
        <form action="/send_message" method="post">
            Phone Number (include +1): <input type="text" name="to_number"><br>
            Message: <input type="text" name="message"><br>
            Media URL (optional): <input type="text" name="media_urls[]"><br>
            Media URL (optional): <input type="text" name="media_urls[]"><br>
            <input type="submit" value="Send Message">
        </form>
    '''

@app.route("/send_message", methods=['POST'])
def send_unified_message():
    to_number = request.form['to_number']
    message_body = request.form['message']
    media_urls = [url.strip() for url in request.form.getlist('media_urls[]') if url.strip()]

    try:
        send_message_with_retry(to_number, message_body, media_urls)
        return f"Message sent to {to_number}"
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return f"Error: {str(e)}"

@app.route("/logs")
def view_logs():
    html_content = '''
        <h1>Application Logs</h1>
        <meta http-equiv="refresh" content="5">
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

@app.route("/send_mms", methods=['POST'])
def send_mms():
    to_number = request.form['to_number']
    message_body = request.form.get('message', '')
    media_urls = [url.strip() for url in request.form.getlist('media_urls[]') if url.strip()]
    graph_data = request.form.get('graph_data', '')

    # If graph_data is provided, generate it
    if graph_data:
        try:
            graph_info = json.loads(graph_data)
            img_b64 = generate_graph(graph_info["type"], graph_info["data"])
            temp_url = upload_base64_to_imgbb(img_b64)
            media_urls.append(temp_url)
        except Exception as e:
            logger.error(f"Failed to generate graph: {str(e)}")
            return f"Error generating graph: {str(e)}", 400

    if not media_urls:
        return "Error: No valid media URLs", 400

    try:
        send_message_with_retry(to_number, message_body, media_urls)
        return f"MMS sent to {to_number}"
    except Exception as e:
        logger.error(f"Error sending MMS: {str(e)}")
        return f"Error: {str(e)}", 400

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
