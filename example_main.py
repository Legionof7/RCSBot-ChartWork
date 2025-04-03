# example_main.py
from flask import Flask, request, jsonify
import logging
import json
from datetime import datetime
import os
from model_service import call_gemini
from message_handler import send_message, get_pinnacle_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize Pinnacle client once
pinnacle_client = get_pinnacle_client()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Pinnacle."""
    try:
        # Get request data
        webhook_data = request.json
        logger.info(f"Received webhook: {webhook_data}")
        
        # Parse inbound message using Pinnacle (in a real implementation)
        # inbound_msg = pinnacle_client.parse_inbound_message(webhook_data)
        
        # For this example, we'll simplify and just extract what we need
        from_number = webhook_data.get('from', '')
        user_content = webhook_data.get('text', '')
        
        if not from_number or not user_content:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
        # Process the message using Gemini
        conversation = [{"role": "user", "content": user_content}]
        rcs_response = call_gemini(conversation)
        
        # Send response with smart fallback
        response, message_type = send_message(
            to_number=from_number,
            rcs_response=rcs_response,
            pinnacle_client=pinnacle_client
        )
        
        logger.info(f"Sent {message_type} response to {from_number}")
        return jsonify({"status": "success", "message_type": message_type})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

if __name__ == '__main__':
    # Check if we have required environment variables
    if not os.getenv('PINNACLE_API_KEY'):
        logger.warning("PINNACLE_API_KEY not set. Some functionality will be limited.")
    
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("GEMINI_API_KEY not set. Application will not function correctly.")
        exit(1)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)