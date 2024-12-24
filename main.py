
from flask import Flask, request
from rcs import Pinnacle
import logging
import datetime

client = Pinnacle(api_key="75bd3093-6309-448f-969c-37928ab59e84")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
messages = []

@app.route("/", methods=['GET', 'POST'])
@app.route("/webhook", methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'POST':
        raw_data = request.get_data(as_text=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"Received webhook at {timestamp}")
        logger.info(f"Raw data: {raw_data}")
        
        messages.append({
            'timestamp': timestamp,
            'data': raw_data
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
                <tr><th>Time</th><th>Data</th></tr>
        '''
        
        for msg in reversed(messages):
            html_content += f'''
                <tr>
                    <td>{msg['timestamp']}</td>
                    <td><pre>{msg['data']}</pre></td>
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
