from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime
import os
import requests
import anthropic
import time

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

MODEL = "claude-3-5-haiku-latest"

client = Pinnacle(api_key=os.getenv('PINNACLE_API_KEY'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.messages = []  # Store messages as app attribute

# -----------------------------------------------------------------------------
# 1) Define your Anthropic "tools" in the format Anthropic expects.
#    Each "tool" has a name, description, and JSON schema describing the input.
#    Because get_patient_data() needs no arguments, we can define an empty schema.
# -----------------------------------------------------------------------------
anthropic_tools = [
    {
        "name": "get_patient_data",
        "description": (
            "Use this tool to retrieve the current patient's FHIR-formatted health "
            "information. This tool returns comprehensive patient data including "
            "demographics, medical conditions, medications, vital signs, lab results, "
            "and care plans. The data is formatted according to FHIR standards. "
            "Call this tool whenever the user requests medical data or it would help "
            "answer a clinical question about the patient."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# -----------------------------------------------------------------------------
# 2) This helper function calls Anthropic's "messages.create" endpoint.
#    - First call: ask Claude the question.
#    - If Claude requests a "tool_use", we parse out the tool name & input,
#      run the tool on our back end, then do a second call with "tool_result".
# -----------------------------------------------------------------------------
def call_anthropic(messages):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    # First request to Claude with tools included.
    # We also pass our "system" prompt in separately if your library usage requires it.
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=messages,              # your conversation so far
        system=[{"type": "text", "text": IDENTITY}],  # system instructions
        tools=anthropic_tools,         # define the tools you have
        temperature=0.7,
        # By default tool_choice={"type":"auto"} is implied if you omit it.
        # You could also do tool_choice={"type":"auto"} explicitly:
        # tool_choice={"type": "auto"}
    )

    # If Claude decides to use a tool, it sets stop_reason="tool_use" and returns
    # a "tool_use" content block describing which tool it wants and its JSON input.
    if response.stop_reason == "tool_use":
        # We'll gather any final text pieces (in case Claude included partial text).
        ai_text_so_far = []
        tool_requests = []

        for block in response.content:
            if block["type"] == "text":
                ai_text_so_far.append(block["text"])
            elif block["type"] == "tool_use":
                tool_requests.append(block)

        # Typically there's only one tool_use per step, but we’ll loop just in case.
        final_ai_text = "\n".join(ai_text_so_far).strip()

        for tool_block in tool_requests:
            tool_name = tool_block["name"]
            tool_input = tool_block["input"]  # JSON input for that tool

            # Here is where you actually run the tool.
            # We only have one tool called "get_patient_data" with no required input.
            if tool_name == "get_patient_data":
                # In your code, you already have PATIENT_DATA from get_patient_data().
                # Just return it as a string, or you could do any logic you want here.
                tool_result_data = str(PATIENT_DATA)
            else:
                # Unrecognized tool, or some fallback
                tool_result_data = "Error: Unknown tool name requested."

            # Now you send a second request that includes a "tool_result" content block
            # so Claude can finalize the answer with the tool’s output.
            tool_result_message = [
                {
                    "role": "user",
                    "content": {
                        "type": "tool_result",
                        "tool_use_id": tool_block["id"],  # the ID from Claude’s tool_use
                        "content": tool_result_data
                    }
                }
            ]
            # Combine the original conversation with the partial text and the new user message
            # containing the tool_result block.
            # Create new messages array with original messages and tool result
            second_call_messages = messages[:]  # Original conversation
            if final_ai_text:
                second_call_messages.append({"role": "assistant", "content": final_ai_text})
            second_call_messages.extend(tool_result_message)

            second_response = anthropic_client.messages.create(
                model=MODEL,
                max_tokens=1000,
                messages=second_call_messages,
                system=[{"type": "text", "text": IDENTITY}],
                tools=anthropic_tools,
                temperature=0.7
            )

            # Process the second response and return it
            ai_message = ""
            logger.info(f"Processing second response: {second_response}")
            logger.info(f"Second response content type: {type(second_response.content)}")
            logger.info(f"Second response dir: {dir(second_response)}")
            
            if hasattr(second_response, 'content'):
                for block in second_response.content:
                    logger.info(f"Processing block: {block}")
                    logger.info(f"Block type: {type(block)}")
                    logger.info(f"Block dir: {dir(block)}")
                    
                    try:
                        if hasattr(block, 'text'):
                            logger.info(f"Block text: {block.text}")
                            ai_message += block.text
                        elif hasattr(block, 'type') and block.type == 'text':
                            logger.info(f"Block value: {block.value}")
                            ai_message += block.value
                        elif isinstance(block, dict) and block.get("type") == "text":
                            logger.info(f"Block dict text: {block.get('text')}")
                            ai_message += block.get("text", "")
                        else:
                            logger.info(f"Unhandled block type: {type(block)} with attributes: {dir(block)}")
                    except Exception as e:
                        logger.error(f"Error processing block: {str(e)}", exc_info=True)
            
            logger.info(f"Final AI message before processing: {ai_message}")
            
            if not ai_message.strip():
                raise ValueError("Empty AI message after processing blocks")
            
            # Create a modified response with the processed message
            processed_response = second_response
            processed_response.content = [{"type": "text", "text": ai_message}]
            logger.info(f"Final processed response content: {processed_response.content}")
            return processed_response

    # If stop_reason != "tool_use", then no tool was used; just return the single response.
    return response

# -----------------------------------------------------------------------------
# Now we integrate call_anthropic() into your existing Flask route
# -----------------------------------------------------------------------------
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
                    # Handle regular messages with Anthropic
                    try:
                        if not hasattr(app, 'conversation_history'):
                            app.conversation_history = {}

                        if parsed_data.from_ not in app.conversation_history:
                            app.conversation_history[parsed_data.from_] = []

                        # Add the user message, ignoring empty content
                        user_text = parsed_data.text.strip()
                        if user_text:
                            app.conversation_history[parsed_data.from_].append(
                                {"role": "user", "content": user_text}
                            )

                        # Slice and filter out any empty messages
                        conversation_slice = app.conversation_history[parsed_data.from_][-6:]
                        conversation_slice = [m for m in conversation_slice if m.get("content")]

                        # 3) Make the call to our helper that does two-step tool usage if needed
                        anthropic_response = call_anthropic(conversation_slice)

                        # Extract message from Anthropic response
                        ai_message = ""
                        logger.info(f"Anthropic response type: {type(anthropic_response)}")
                        logger.info(f"Anthropic response: {anthropic_response}")

                        if hasattr(anthropic_response, 'content'):
                            logger.info(f"Content type: {type(anthropic_response.content)}")
                            logger.info(f"Content: {anthropic_response.content}")
                            
                            for content_block in anthropic_response.content:
                                logger.info(f"Block type: {type(content_block)}")
                                logger.info(f"Block content: {content_block}")
                                
                                try:
                                    if hasattr(content_block, 'text'):
                                        logger.info("Processing text attribute")
                                        ai_message += content_block.text
                                    elif hasattr(content_block, 'value'):
                                        logger.info("Processing value attribute")
                                        ai_message += content_block.value
                                    elif isinstance(content_block, dict) and content_block.get("type") == "text":
                                        logger.info("Processing dict with text type")
                                        ai_message += content_block.get("text", "")
                                    else:
                                        logger.info(f"Unhandled content block type: {type(content_block)}")
                                except Exception as block_error:
                                    logger.error(f"Error processing block: {str(block_error)}")

                        logger.info(f"Final AI message: {ai_message}")

                        if not ai_message.strip():
                            logger.error("Empty AI message after processing")
                            raise ValueError("Empty response from Anthropic")

                        # Store in conversation
                        app.conversation_history[parsed_data.from_].append(
                            {"role": "assistant", "content": ai_message}
                        )

                        # Send via SMS with retry logic
                        max_retries = 3
                        retry_delay = 1  # seconds

                        for attempt in range(max_retries):
                            try:
                                response = client.send.sms(
                                    to=parsed_data.from_,
                                    from_=parsed_data.to,
                                    text=ai_message
                                )
                                logger.info("Sent Claude response successfully")
                                break
                            except Exception as sms_error:
                                logger.error(f"SMS send attempt {attempt + 1} failed: {str(sms_error)}")
                                if attempt < max_retries - 1:
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
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