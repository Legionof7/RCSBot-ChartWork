
from flask import Flask, request, Response
from rcs import Pinnacle, Card, Action
import logging
import datetime
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Pinnacle configuration
client = Pinnacle(api_key="75bd3093-6309-448f-969c-37928ab59e84")

# Store messages in memory
messages = []

def check_auth(password):
    return password == 'SlothMD!123'

def authenticate():
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'POST':
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route("/", methods=['GET', 'POST'])
def handle_webhook():
    logger.info("=== Webhook Request Start ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Raw Data: {request.get_data(as_text=True)}")
    logger.info(f"Form Data: {request.form}")
    try:
        json_data = request.get_json(force=True, silent=True)
        logger.info(f"JSON Data: {json_data}")
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
    logger.info("=== Webhook Request End ===")
    
    if request.method == 'POST':
        try:
            # Get raw data first
            raw_data = request.get_data(as_text=True)
            logger.info(f"Raw POST data: {raw_data}")
            
            # Try to parse as form data first
            from_number = request.form.get('From')
            text = request.form.get('Body')
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # If form data is empty, try JSON
            if not from_number:
                data = request.get_json(force=True)
                from_number = data.get('from')
                text = data.get('text')
                timestamp = data.get('timestamp') or timestamp

            if from_number and text:
                messages.append({
                    'from': from_number,
                    'body': text,
                    'timestamp': timestamp
                })
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return "Error processing message", 400

        logger.info(f"Received message from {from_number}: {text}")
        
        # Check for START message and send auto-response
        if text and text.strip().lower() == "hi":
            try:
                client.send.sms(
                    to=from_number,
                    from_="+18337750778",
                    text="TEST_RESPONSE"
                )
                logger.info(f"Sent auto-response to {from_number}")
            except Exception as e:
                logger.error(f"Failed to send auto-response: {str(e)}")
        
        return "Message received", 200
    else:
        return '''
            <h1>SMS Service</h1>
            <meta http-equiv="refresh" content="30">
            <script>
                function refreshTable() {
                    fetch(window.location.href)
                        .then(response => response.text())
                        .then(html => {
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(html, 'text/html');
                            document.querySelector('table').outerHTML = doc.querySelector('table').outerHTML;
                        });
                }
                setInterval(refreshTable, 5000);
            </script>
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
            </style>
            <p><a href="/send">Send Message</a> | <a href="/">Refresh</a></p>
            <h2>Incoming Messages</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>From</th>
                    <th>Message</th>
                </tr>
                ''' + ''.join([
                    f'''
                    <tr>
                        <td>{msg['timestamp']}</td>
                        <td>{msg['from']}</td>
                        <td>
                            {msg['body']}
                            <details>
                                <summary>Show Raw Message</summary>
                                <pre>{str(msg)}</pre>
                            </details>
                        </td>
                    </tr>
                    ''' for msg in reversed(messages)
                ]) + '''
            </table>
            <p>SMS Receiver is running!</p>
        '''

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

        return f"""
        <style>
            details {{ margin: 10px 0; padding: 10px; background: #f5f5f5; }}
            summary {{ cursor: pointer; }}
            pre {{ white-space: pre-wrap; word-wrap: break-word; }}
        </style>
        <h2>Message Details:</h2>
        <p>
        To: {to_number}<br>
        Message: {message_body}<br>
        Status: Sent
        </p>
        <details>
            <summary>Show Raw Response</summary>
            <pre>{str(response)}</pre>
        </details>
        """

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
