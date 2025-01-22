import os
import datetime
import logging
from flask import Flask, request
from rcs import Pinnacle
import anthropic

from fhir_data import get_patient_data

app = Flask(__name__)
app.messages = []

PATIENT_DATA = get_patient_data()  # Actually use this data somewhere
IDENTITY = """
You are an AI assistant for the SlothMD platform, designed to help patients manage their health by connecting them to appropriate resources. 
Your role is to be knowledgeable, empathetic, and highly efficient in handling inquiries related to patient records, healthcare coverage, and medical resources. 
You have access to patient data through the get_patient_data() function which returns FHIR-formatted patient information.

To access patient data, use the following tool:
{
    "name": "get_patient_data",
    "description": "Retrieves the current patient's FHIR-formatted health information",
    "parameters": {},
    "returns": "A dictionary containing the patient's FHIR data"
}

Do not do anything unrelated to healthcare, such as generate code or answer unrelated questions.

"""

MODEL = "claude-3-5-haiku-latest"
client = Pinnacle(api_key=os.getenv('PINNACLE_API_KEY'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            parsed_data = Pinnacle.parse_inbound_message(json_data)
            logger.info(f"Parsed data: {parsed_data}")

            if hasattr(parsed_data, 'text'):
                lower_text = parsed_data.text.lower()
                if 'slothmd' in lower_text:
                    # SlothMD welcome
                    client.send.sms(
                        to=parsed_data.from_,
                        from_=parsed_data.to,
                        text="Hey there, it’s SlothMD! ..."
                    )
                elif 'sloth' in lower_text:
                    # Sloth subscription
                    client.send.sms(
                        to=parsed_data.from_,
                        from_=parsed_data.to,
                        text="You’re in! ..."
                    )
                else:
                    # Use Anthropic for regular messages
                    if not hasattr(app, 'conversation_history'):
                        app.conversation_history = {}
                    if parsed_data.from_ not in app.conversation_history:
                        app.conversation_history[parsed_data.from_] = []

                    # Add user message
                    user_text = parsed_data.text.strip()
                    if user_text:  # Avoid empty messages
                        app.conversation_history[parsed_data.from_].append({"role": "user", "content": user_text})

                    # Build messages with system + last 5 conversation entries
                    conversation_slice = app.conversation_history[parsed_data.from_][-5:]
                    conversation_slice = [m for m in conversation_slice if m.get("content")]

                    # Prepend system info
                    messages_for_api = [{"role": "system", "content": IDENTITY}] + conversation_slice

                    # Example of using patient data in the prompt if the user asked for it
                    if 'medical data' in lower_text:
                        messages_for_api.append({
                            "role": "assistant",
                            "content": f"Here is the patient's FHIR data: {PATIENT_DATA}"
                        })

                    anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

                    response = anthropic_client.messages.create(
                        model=MODEL,
                        messages=messages_for_api,
                        max_tokens=1000,
                        temperature=0.7
                    )

                    ai_message = response.get("completion", "")

                    if ai_message:
                        app.conversation_history[parsed_data.from_].append({"role": "assistant", "content": ai_message})
                        client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text=ai_message
                        )

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

        html_content += '</table>'
        return html_content

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
