
from flask import Flask, request
import logging
import datetime

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
        return '''
            <h1>Webhook Receiver</h1>
            <meta http-equiv="refresh" content="30">
            <style>
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
            <table>
                <tr><th>Time</th><th>Data</th></tr>
                ''' + ''.join([
                    f'''
                    <tr>
                        <td>{msg['timestamp']}</td>
                        <td><pre>{msg['data']}</pre></td>
                    </tr>
                    ''' for msg in reversed(messages)
                ]) + '''
            </table>
        '''

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
