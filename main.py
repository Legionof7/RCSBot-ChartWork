from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Twilio configuration
account_sid = 'AC90b94224510cd211eacdf1ec564bb8e2'
auth_token = '154bc969e28b26c701c91df9355d7688'
twilio_number = '+16288000018'

client = Client(account_sid, auth_token)

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

# Keep your other routes the same...

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)