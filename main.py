from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Twilio configuration
account_sid = 'AC90b94224510cd211eacdf1ec564bb8e2'
auth_token = '154bc969e28b26c701c91df9355d7688'
twilio_number = '+16288000018'

client = Client(account_sid, auth_token)

# Store messages in memory
messages = []

from functools import wraps
from flask import request, Response

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
@requires_auth
def handle_webhook():
    if request.method == 'POST':
        body = request.values.get('Body', None)
        from_number = request.values.get('From', None)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        messages.append({
            'from': from_number,
            'body': body,
            'timestamp': timestamp
        })

        logger.info(f"Received message from {from_number}: {body}")

        resp = MessagingResponse()
        resp.message(f"Got your message: {body}")
        return str(resp)
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
                        <td>{msg['body']}</td>
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
            <input type="submit" value="Send SMS">
        </form>
    '''

@app.route("/send_sms", methods=['POST'])
def send_sms():
    to_number = request.form['to_number']
    message_body = request.form['message']

    try:
        # Check if this is a trial account
        account = client.api.accounts(account_sid).fetch()
        if account.type == "Trial":
            # Get verified numbers
            verified_numbers = client.outgoing_caller_ids.list()
            verified_numbers = [number.phone_number for number in verified_numbers]

            if to_number not in verified_numbers:
                return f"""
                Error: This appears to be a trial account and {to_number} is not verified.
                Please verify this number in your Twilio console first.
                Verified numbers: {', '.join(verified_numbers)}
                """

        message = client.messages.create(
            to=to_number,
            from_=twilio_number,
            body=message_body
        )

        # Get detailed message status
        message = client.messages(message.sid).fetch()

        return f"""
        Message Details:
        SID: {message.sid}
        Status: {message.status}
        To: {message.to}
        From: {message.from_}
        Body: {message.body}
        Direction: {message.direction}
        Error Code: {message.error_code if hasattr(message, 'error_code') else 'None'}
        Error Message: {message.error_message if hasattr(message, 'error_message') else 'None'}
        """

    except TwilioRestException as e:
        logger.error(f"Twilio Error: {str(e)}")
        return f"Twilio Error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        return f"Unexpected Error: {str(e)}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)