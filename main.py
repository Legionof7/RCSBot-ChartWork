
from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime

import os
import requests
import anthropic

from fhir_data import get_patient_data

# Constants for Anthropic
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

# Initialize patient data
PATIENT_DATA = get_patient_data()

MODEL = "claude-3-5-sonnet-20240620"

client = Pinnacle(api_key=os.getenv('PINNACLE_API_KEY'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.messages = []  # Store messages as app attribute

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
            
            # Check for SlothMD or sloth in the message text
            if hasattr(parsed_data, 'text'):
                lower_text = parsed_data.text.lower()
                if 'slothmd' in lower_text:
                    try:
                        response = client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text="Hey there, it's SlothMD! I'll text you at this number as soon as your spot opens up. You won't receive any other marketing information. If you want to sign up for updates that you will receive less than once a month, reply \"SLOTH\". Standard message and data rates may apply. Reply \"STOP\" anytime to end communication with SlothMD outside the app.  For support, you can reach us at founders@slothmd.io")
                        logger.info("Sent SlothMD welcome message")
                    except Exception as e:
                        logger.error(f"Failed to send SlothMD welcome message: {str(e)}")
                elif 'sloth' in lower_text:
                    try:
                        response = client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text="You're in! Expect access to early texting features and SlothMD updates less than once a month. Standard msg/data rates apply. Reply STOP anytime to unsubscribe.")
                        logger.info("Sent sloth subscription confirmation")
                    except Exception as e:
                        logger.error(f"Failed to send sloth subscription confirmation: {str(e)}")
                else:
                    # Handle regular messages with Anthropic
                    try:
                        # Maintain conversation history
                        if not hasattr(app, 'conversation_history'):
                            app.conversation_history = {}
                            
                        if parsed_data.from_ not in app.conversation_history:
                            app.conversation_history[parsed_data.from_] = []
                        
                        # Add user message to history
                        app.conversation_history[parsed_data.from_].append({"role": "user", "content": parsed_data.text})
                        
                        # Initialize Anthropic client
                        anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
                        
                        messages = app.conversation_history[parsed_data.from_][-5:]  # Keep last 5 messages
                        
                        response = anthropic_client.messages.create(
                            model=MODEL,
                            max_tokens=1000,
                            messages=messages,
                            system=IDENTITY,
                            temperature=0.7,
                            tools=[{
                                "name": "get_patient_data",
                                "parameters": {}
                            }]
                        )
                        
                        ai_message = response.content[0].text
                        # Add AI response to history
                        app.conversation_history[parsed_data.from_].append({"role": "assistant", "content": ai_message})
                        
                        # Send SMS response using Pinnacle
                        response = client.send.sms(
                            to=parsed_data.from_,
                            from_=parsed_data.to,
                            text=ai_message
                        )
                        logger.info("Sent Claude response")
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
