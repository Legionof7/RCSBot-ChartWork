from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime
import os
import requests
import time
import json
from fhir_data import get_patient_data

# Load FHIR data
FHIR_DATA = get_patient_data()

def create_context(query: str) -> str:
    return f"""You are an AI assistant for the SlothMD platform, designed to help patients manage their health by connecting them to appropriate resources.
Your role is to be knowledgeable, empathetic, and highly efficient in handling inquiries related to patient records, healthcare coverage, and medical resources.

Here is the complete patient FHIR data:
{json.dumps(FHIR_DATA, indent=2)}

Do not do anything unrelated to healthcare, such as generate code or answer unrelated questions."""

MODEL = "deepseek/deepseek-r1"
OPENROUTER_API_KEY = "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"

client = Pinnacle(api_key=os.getenv('PINNACLE_API_KEY'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]
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
            parsed_data = Pinnacle.parse_inbound_message(json_data)
            logger.info(f"Parsed data: {parsed_data}")

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

                        if not ai_response.get("content", "").strip():
                            raise ValueError("Empty response from OpenRouter")

                        app.conversation_history[parsed_data.from_].append(
                            {"role": "assistant", "content": ai_response["content"]}
                        )

                        max_retries = 3
                        retry_delay = 1
                        max_length = 1600

                        messages_to_send = [ai_response["content"][i:i + max_length] 
                                          for i in range(0, len(ai_response["content"]), max_length)]

                        for message_part in messages_to_send:
                            for attempt in range(max_retries):
                                try:
                                    response = client.send.sms(
                                        to=parsed_data.from_,
                                        from_=parsed_data.to,
                                        text=message_part
                                    )
                                    logger.info(f"Sent message part successfully")
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
        <form action="/send_sms" method="post">
            Phone Number (include +1): <input type="text" name="to_number"><br>
            Message: <input type="text" name="message"><br>
            <input type="submit" value="Send Message">
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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)