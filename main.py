from flask import Flask, request
from rcs import Pinnacle, CompanyDetails, CompanyContact, Messaging
import logging
import datetime
import os
import requests
import time
import json
from fhir_data import get_patient_data
from graph_utils import generate_graph
import base64

# Load FHIR data
FHIR_DATA = get_patient_data()

def create_context(query: str) -> str:
    graph_formats = '''
GRAPH_DATA:{"type": "<graph_type>", "data": <data_object>}END_GRAPH_DATA

Example graph:
GRAPH_DATA:{"type": "bar", "data": {"labels": ["HbA1c", "Glucose", "LDL"], "values": [6.8, 110, 110], "title": "Lab Results", "xlabel": "Test", "ylabel": "Value", "referenceLines": {"HbA1c": 7.0, "Glucose": 100, "LDL": 100}}}END_GRAPH_DATA

Supported graph types and their data formats:
1. "line" - requires: {"x": [x_values], "y": [y_values], "title": "string", "xlabel": "string", "ylabel": "string"}
2. "bar" - requires: {"labels": [labels], "values": [values], "title": "string", "xlabel": "string", "ylabel": "string"}
3. "scatter" - requires: {"x": [x_values], "y": [y_values], "title": "string", "xlabel": "string", "ylabel": "string"}
'''
    return f"""You are an AI assistant for the SlothMD platform, designed to help patients manage their health by offering insights and analysis. 
Your role is to be knowledgeable, empathetic, and highly efficient in handling inquiries related to patient records, healthcare coverage, and medical resources. Keep answers short and concise, you are answering over SMS, remember that when formatting. Be human, conversational, and friendly.

When visualizing data, you can generate graphs by including a special marker in your response using this format:
{graph_formats}

When asked for insights, generate at least 3 insights. Each insight should follow these guidelines:
* Start with relevant data points that prompted this insight
* Flow naturally from problem to solution
* Include specific, actionable steps
* Provide clear timelines for implementation and expected results
* Utilize multiple metrics in a single insight to provide a comprehensive view of total health
* Connect to other health metrics naturally
* Include concrete ways to track progress
* Be concise, about 3-4 sentences at most
* Give clear markers of success


Here is the complete patient FHIR data:
{json.dumps(FHIR_DATA, indent=2)}

Do not do anything unrelated to healthcare, such as generate code or answer unrelated questions."""

MODEL = "deepseek/deepseek-r1"
OPENROUTER_API_KEY = "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"

# Initialize RCS client with messaging configuration
api_key = os.getenv('PINNACLE_API_KEY')
if api_key is None:
    raise ValueError("PINNACLE_API_KEY environment variable not set")
client = Pinnacle(
    api_key=api_key,
    timeout=60.0
)

# Configure and register messaging settings
messaging = Messaging(
    opt_in="Hey there, it's SlothMD! I'll text you at this number as soon as your spot opens up. You won't receive any other marketing information. Standard message and data rates may apply. Reply \"STOP\" anytime to end communication with SlothMD outside the app.  For support, you can reach us at founders@slothmd.io",
    opt_out="Reply STOP to unsubscribe. A confirmation message will be sent, and no further messages will be received unless you re-subscribe.",
    opt_out_keywords=["STOP", "UNSUBSCRIBE"],
    agent_use_case="SlothMD's agent assists with health management, medical insights, and patient support. It provides health data analysis, medication reminders, and helps track health metrics.",
    expected_agent_responses="General Inquiry: \"How can I help with your health today?\"\nHealth Data: \"Here's your latest health metrics.\"\nOpt-In: \"You're subscribed to SlothMD!\"\nOpt-Out: \"You've been unsubscribed.\"\nEscalation: \"Connecting you to support.\""
)


# Store messaging config for reference
messaging_config = {
    "opt_in": "Hey there, it's SlothMD! I'll text you at this number as soon as your spot opens up. You won't receive any other marketing information. Standard message and data rates may apply. Reply \"STOP\" anytime to end communication with SlothMD outside the app.  For support, you can reach us at founders@slothmd.io",
    "opt_out": "Reply STOP to unsubscribe. A confirmation message will be sent, and no further messages will be received unless you re-subscribe.",
    "opt_out_keywords": ["STOP", "UNSUBSCRIBE"],
    "agent_use_case": "SlothMD's agent assists with health management, medical insights, and patient support. It provides health data analysis, medication reminders, and helps track health metrics.",
    "expected_agent_responses": "General Inquiry: \"How can I help with your health today?\"\nHealth Data: \"Here's your latest health metrics.\"\nOpt-In: \"You're subscribed to SlothMD!\"\nOpt-Out: \"You've been unsubscribed.\"\nEscalation: \"Connecting you to support.\""
}

# Configure logging with a custom handler to store logs
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
            print(f"Log stored: {log_entry['timestamp']} - {log_entry['level']} - {log_entry['message']}")  # Debug print
        except Exception as e:
            print(f"Logging error in MemoryHandler: {str(e)}")
            import traceback
            print(traceback.format_exc())

memory_handler = MemoryLogHandler()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
memory_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()
root_logger.handlers = []  # Remove any existing handlers
root_logger.addHandler(memory_handler)
root_logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)
logger.info("Logging system initialized")

app = Flask(__name__)
app.messages = []
app.conversation_history = {}

def call_openrouter(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }

    # Get relevant context based on user's message
    latest_message = messages[-1]["content"] if messages else ""
    context = create_context(latest_message)
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": context},
            *messages
        ]
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

@app.route("/", methods=['GET', 'POST'])
@app.route("/webhook", methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'POST':
        raw_data = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Received webhook at {timestamp}")
        logger.info(f"Raw data: {raw_data}")

        try:
            json_data = request.get_json()
            logger.info(f"Processing JSON data: {json_data}")
            parsed_data = Pinnacle.parse_inbound_message(json_data)
            logger.info(f"Parsed message data: {parsed_data}")

            if hasattr(parsed_data, 'text'):
                lower_text = parsed_data.text.lower().strip()
                if 'slothmd' in lower_text:
                    try:
                        response = client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text="Hey there, it's SlothMD! I'll text you at this number as soon as your spot opens up. You won't receive any other marketing information. If you want to sign up for updates that you will receive less than once a month, reply \"SLOTH\". Standard message and data rates may apply. Reply \"STOP\" anytime to end communication with SlothMD outside the app.  For support, you can reach us at founders@slothmd.io"
                        )
                        logger.info("Sent SlothMD welcome message")
                    except Exception as e:
                        logger.error(f"Failed to send SlothMD welcome message: {str(e)}")
                elif 'sloth' in lower_text:
                    try:
                        response = client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text="You're in! Expect access to early texting features and SlothMD updates less than once a month. Standard msg/data rates apply. Reply STOP anytime to unsubscribe."
                        )
                        logger.info("Sent sloth subscription confirmation")
                    except Exception as e:
                        logger.error(f"Failed to send sloth subscription confirmation: {str(e)}")
                else:
                    try:
                        if parsed_data.from_ not in app.conversation_history:
                            app.conversation_history[parsed_data.from_] = []

                        user_text = parsed_data.text.strip()
                        if user_text:
                            app.conversation_history[parsed_data.from_].append(
                                {"role": "user", "content": user_text}
                            )

                        conversation_slice = app.conversation_history[parsed_data.from_][-6:]
                        ai_response = call_openrouter(conversation_slice)

                        response_content = ai_response.get("content", "").strip()
                        if not response_content:
                            raise ValueError("Empty response from OpenRouter")

                        # Check if response contains graph data
                        # Check RCS functionality first
                        try:
                            rcs_functionality = client.get_rcs_functionality(parsed_data.from_)
                            logger.info(f"RCS functionality for {parsed_data.from_}: {rcs_functionality}")
                            can_use_rcs = rcs_functionality.get("is_enabled", False)
                        except Exception as e:
                            logger.error(f"Failed to check RCS functionality: {str(e)}")
                            can_use_rcs = False

                        if "GRAPH_DATA:" in response_content:
                            try:
                                # Extract graph data and remaining message
                                logger.info("Detected graph data in response")
                                graph_part, message_part = response_content.split("GRAPH_DATA:", 1)
                                graph_data = message_part.split("END_GRAPH_DATA")[0]
                                logger.info(f"Raw graph data: {graph_data}")
                                graph_info = json.loads(graph_data)
                                logger.info(f"Parsed graph info: {graph_info}")
                                remaining_message = message_part.split("END_GRAPH_DATA")[1]

                                # Generate graph
                                graph_data = graph_info.get("data", graph_info)
                                img_b64 = generate_graph(
                                    graph_info["type"],
                                    graph_data
                                )
                                
                                # Upload image to imgbb
                                try:
                                    imgbb_key = os.getenv('IMGBB_API_KEY', 'dc9385b3e6c2b601de1361a53e98e869')
                                    upload_url = 'https://api.imgbb.com/1/upload'
                                    # Add data:image/png;base64, prefix required by imgbb
                                    payload = {
                                        'key': imgbb_key,
                                        'image': img_b64,  # Send raw base64 data
                                        'name': f'graph_{int(time.time())}.png'
                                    }
                                    upload_response = requests.post(upload_url, data=payload)
                                    upload_response.raise_for_status()
                                    
                                    image_url = upload_response.json()['data']['url']
                                    logger.info(f"Image uploaded successfully: {image_url}")

                                    # Send message with graph URL
                                    if can_use_rcs:
                                        response = client.send.rcs(
                                            to=parsed_data.from_,
                                            from_="test",  # Using test agent
                                            cards=[
                                                Card(
                                                    title="Health Data Visualization",
                                                    subtitle=graph_part.strip(),
                                                    media_url=image_url
                                                )
                                            ]
                                        )
                                        logger.info("Successfully sent RCS with graph")
                                    else:
                                        response = client.send.mms(
                                            to=parsed_data.from_,
                                            from_=parsed_data.to,
                                            text=graph_part.strip(),
                                            media_urls=[image_url]
                                        )
                                        logger.info("Successfully sent MMS with graph")
                                except Exception as mms_error:
                                    logger.error(f"Failed to send MMS: {str(mms_error)}", exc_info=True)
                                    raise
                                
                                # Send remaining message if any
                                if remaining_message.strip():
                                    response_content = remaining_message

                            except Exception as graph_error:
                                logger.error(f"Failed to generate graph: {str(graph_error)}")
                                response_content = "Sorry, I couldn't generate the graph. " + response_content

                        app.conversation_history[parsed_data.from_].append(
                            {"role": "assistant", "content": response_content}
                        )

                        max_retries = 3
                        retry_delay = 1
                        max_length = 1600

                        messages_to_send = [ai_response["content"][i:i + max_length] 
                                          for i in range(0, len(ai_response["content"]), max_length)]

                        for message_part in messages_to_send:
                            for attempt in range(max_retries):
                                try:
                                    logger.info(f"Attempting to send message part: {message_part[:100]}...")
                                    if can_use_rcs:
                                        response = client.send.rcs(
                                            to=parsed_data.from_,
                                            from_="test",
                                            text=message_part
                                        )
                                    else:
                                        response = client.send.sms(
                                            to=parsed_data.from_,
                                            from_=parsed_data.to,
                                            text=message_part
                                        )
                                    logger.info(f"Message sent successfully. Response: {response}")
                                    break
                                except Exception as sms_error:
                                    logger.error(f"SMS send attempt {attempt + 1} failed: {str(sms_error)}")
                                    if attempt < max_retries - 1:
                                        time.sleep(retry_delay)
                                        retry_delay *= 2
                                    else:
                                        logger.error("Max retries reached, SMS send failed")
                                        raise
                    except Exception as e:
                        logger.error(f"Failed to process chat message: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to parse message: {str(e)}")
            parsed_data = "Parse error"

        app.messages.append({
            'timestamp': timestamp,
            'data': raw_data,
            'parsed': parsed_data
        })
        return "Webhook received", 200

    else:
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

        html_content += '''
            </table>
        '''
        return html_content

@app.route("/send", methods=['GET'])
def send_message():
    return '''
        <h2>Send SMS</h2>
        <form action="/send_sms" method="post">
            Phone Number (include +1): <input type="text" name="to_number"><br>
            Message: <input type="text" name="message"><br>
            <input type="submit" value="Send SMS">
        </form>
        
        <h2>Send MMS</h2>
        <form action="/send_mms" method="post">
            Phone Number (include +1): <input type="text" name="to_number"><br>
            Message (optional): <input type="text" name="message"><br>
            Media URL: <input type="text" name="media_urls[]"><br>
            Media URL: <input type="text" name="media_urls[]"><br>
            <input type="submit" value="Send MMS">
        </form>
    '''

@app.route("/send_sms", methods=['POST'])
def send_sms():
    to_number = request.form['to_number']
    message_body = request.form['message']

    try:
        response = client.send.sms(
            to=to_number,
            from_="+18337750778",
            text=message_body
        )
        return f"Message sent to {to_number}"
    except Exception as e:
        logger.error(f"Error: {str(e)}")
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

    if not media_urls and not graph_data:
        return "Error: Either media URLs or graph data is required", 400

    if graph_data:
        try:
            graph_info = json.loads(graph_data)
            img_b64 = generate_graph(
                graph_info["type"],
                graph_info["data"]
            )
            # Create temporary file for the image
            temp_path = f"/tmp/graph_{int(time.time())}.png"
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            media_urls.append(temp_path)
        except Exception as e:
            logger.error(f"Failed to generate graph: {str(e)}")
            return f"Error generating graph: {str(e)}", 400

    # Basic URL validation
    valid_urls = [url for url in media_urls if url.strip()]
    
    if not valid_urls:
        return "Error: No valid media URLs", 400

    try:
        response = client.send.mms(
            to=to_number,
            from_="+18337750778",
            text=message_body if message_body else None,
            media_urls=valid_urls
        )
        return f"MMS sent to {to_number}"
    except Exception as e:
        logger.error(f"Error sending MMS: {str(e)}")
        return f"Error: {str(e)}", 400

if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)