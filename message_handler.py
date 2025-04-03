# message_handler.py
import os
import logging
import requests
from typing import Dict, List, Tuple, Any, Optional
from PIL import Image
import io
import base64

# Import Pinnacle class if rcs package is installed
try:
    from rcs import Pinnacle
except ImportError:
    logging.warning("rcs package not installed. Pinnacle client will not be available.")
    Pinnacle = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def reformat_for_sms_mms(rcs_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert rich RCS content to SMS/MMS friendly format.
    
    Args:
        rcs_response: The rich RCS response from model_service
        
    Returns:
        Dictionary with text and mediaUrls suitable for SMS/MMS
    """
    sms_text = ""
    media_urls = []
    
    # Extract basic text content
    if "text" in rcs_response:
        sms_text += rcs_response["text"] + "\n\n"
    
    # Process cards and extract essential info
    if "cards" in rcs_response:
        for card in rcs_response["cards"]:
            if "title" in card:
                sms_text += f"{card['title']}\n"
            if "subtitle" in card:
                sms_text += f"{card['subtitle']}\n"
            if "mediaUrl" in card:
                media_urls.append(card["mediaUrl"])
            
            # Convert buttons to text links/instructions
            if "buttons" in card:
                for button in card["buttons"]:
                    if button["type"] == "openUrl":
                        sms_text += f"• {button['title']}: {button['payload']}\n"
                    elif button["type"] == "call":
                        sms_text += f"• {button['title']}: {button['payload']}\n"
                    else:
                        sms_text += f"• {button['title']}\n"
    
    # Convert quick replies to numbered options
    if "quickReplies" in rcs_response:
        sms_text += "\nOptions:\n"
        for i, qr in enumerate(rcs_response["quickReplies"], 1):
            sms_text += f"{i}. {qr['title']}\n"
    
    # Trim to SMS limit if needed (with note about truncation)
    if len(sms_text) > 1500:  # Leave room for truncation message
        sms_text = sms_text[:1500] + "...\n(Message truncated, see app for full content)"
    
    return {
        "text": sms_text.strip(),
        "mediaUrls": media_urls[:1]  # MMS typically supports 1 image
    }

def optimize_chart_for_fallback(chart_image_path: str, target_size_kb: int = None) -> str:
    """
    Optimize chart image for MMS delivery.
    
    Args:
        chart_image_path: Path to the original chart image
        target_size_kb: Target file size in KB
        
    Returns:
        Path to the optimized image
    """
    # Get settings from environment or use defaults
    if target_size_kb is None:
        target_size_kb = int(os.getenv('MMS_IMAGE_MAX_SIZE_KB', 100))
    
    max_dimension = int(os.getenv('MMS_IMAGE_MAX_DIMENSION', 800))
    
    try:
        # Open and compress image
        img = Image.open(chart_image_path)
        
        # Resize if needed (maintain aspect ratio)
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Save optimized version
        output_path = os.path.splitext(chart_image_path)[0] + "_optimized.jpg"
        
        # Start with quality 85 and decrease until target size
        quality = 85
        while quality > 45:
            img.save(output_path, "JPEG", quality=quality)
            size_kb = os.path.getsize(output_path) / 1024
            
            if size_kb <= target_size_kb:
                break
                
            quality -= 10
        
        logger.info(f"Optimized image from {os.path.getsize(chart_image_path)/1024:.1f}KB to {size_kb:.1f}KB")
        return output_path
    except Exception as e:
        logger.error(f"Failed to optimize image: {e}")
        return chart_image_path  # Return original if optimization fails

def optimize_base64_image(base64_image: str, target_size_kb: int = None) -> str:
    """
    Optimize a base64 encoded image for MMS delivery.
    
    Args:
        base64_image: Base64 encoded image (with or without data URI prefix)
        target_size_kb: Target file size in KB
        
    Returns:
        Optimized base64 encoded image
    """
    # Get settings from environment or use defaults
    if target_size_kb is None:
        target_size_kb = int(os.getenv('MMS_IMAGE_MAX_SIZE_KB', 100))
    
    max_dimension = int(os.getenv('MMS_IMAGE_MAX_DIMENSION', 800))
    
    try:
        # Extract the actual base64 data if it has a data URI prefix
        if base64_image.startswith('data:'):
            # Format: data:image/png;base64,actualbase64data
            image_format = base64_image.split(';')[0].split('/')[1]
            base64_data = base64_image.split(',')[1]
        else:
            image_format = 'png'  # Assume PNG if no prefix
            base64_data = base64_image
        
        # Decode base64 to image
        image_bytes = base64.b64decode(base64_data)
        img = Image.open(io.BytesIO(image_bytes))
        
        # Resize if needed
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Optimize using buffer
        buffer = io.BytesIO()
        
        # Try different qualities until we reach target size
        quality = 85
        while quality > 45:
            buffer.seek(0)
            buffer.truncate(0)
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = len(buffer.getvalue()) / 1024
            
            if size_kb <= target_size_kb:
                break
                
            quality -= 10
        
        # Convert back to base64
        optimized_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        logger.info(f"Optimized base64 image from {len(base64_data)/1024:.1f}KB to {size_kb:.1f}KB")
        
        # Return with data URI prefix for compatibility
        return f"data:image/jpeg;base64,{optimized_base64}"
    except Exception as e:
        logger.error(f"Failed to optimize base64 image: {e}")
        return base64_image  # Return original if optimization fails

def send_message(to_number: str, rcs_response: Dict[str, Any], pinnacle_client=None) -> Tuple[Dict[str, Any], str]:
    """
    Send message with smart fallback from RCS to MMS/SMS.
    
    Args:
        to_number: The recipient's phone number
        rcs_response: The RCS formatted response data
        pinnacle_client: An initialized Pinnacle client
        
    Returns:
        Tuple of (API response, message type sent)
    """
    if pinnacle_client is None:
        if Pinnacle is None:
            raise ImportError("rcs package is not installed. Cannot send messages.")
        
        api_key = os.getenv('PINNACLE_API_KEY')
        if not api_key:
            raise ValueError("PINNACLE_API_KEY environment variable not set")
        
        pinnacle_client = Pinnacle(api_key=api_key)
    
    # Optimize any charts/images before sending
    if "cards" in rcs_response:
        for card in rcs_response["cards"]:
            if "mediaUrl" in card and card["mediaUrl"].startswith("data:image"):
                # If it's a base64 image, optimize it
                card["mediaUrl"] = optimize_base64_image(card["mediaUrl"])
    
    # Check if we should force SMS fallback (for testing)
    force_fallback = os.getenv('FORCE_SMS_FALLBACK', 'false').lower() in ('true', '1', 'yes')
    
    # Check RCS capability with Pinnacle API (unless forced)
    if not force_fallback:
        capability_check = pinnacle_client.check_capabilities(to_number)
        rcs_supported = capability_check.get("rcs_supported", False)
    else:
        rcs_supported = False
        logger.info("Forcing SMS/MMS fallback for testing")
    
    # If RCS is supported, send full RCS message
    if rcs_supported:
        logger.info(f"Sending RCS message to {to_number}")
        response = pinnacle_client.send.rcs(
            to=to_number,
            **rcs_response
        )
        return response, "rcs"
    
    # Otherwise, reformat and send as MMS or SMS
    logger.info(f"RCS not supported for {to_number}, falling back to SMS/MMS")
    sms_content = reformat_for_sms_mms(rcs_response)
    
    # If we have media, send as MMS
    if sms_content["mediaUrls"]:
        logger.info(f"Sending MMS to {to_number}")
        response = pinnacle_client.send.mms(
            to=to_number,
            text=sms_content["text"],
            mediaUrls=sms_content["mediaUrls"]
        )
        return response, "mms"
    
    # Otherwise, send as plain SMS
    logger.info(f"Sending SMS to {to_number}")
    response = pinnacle_client.send.sms(
        to=to_number,
        text=sms_content["text"]
    )
    return response, "sms"

# Helper function to get Pinnacle client
def get_pinnacle_client() -> Any:
    """
    Get an initialized Pinnacle client.
    
    Returns:
        Initialized Pinnacle client or None if not available
    """
    if Pinnacle is None:
        logger.error("rcs package not installed. Cannot create Pinnacle client.")
        return None
    
    api_key = os.getenv('PINNACLE_API_KEY')
    if not api_key:
        logger.error("PINNACLE_API_KEY environment variable not set")
        return None
    
    return Pinnacle(api_key=api_key)

# Simple function to test the module
def test_message_handling():
    """Test the message handling functionality with a sample RCS response."""
    sample_rcs = {
        "cards": [
            {
                "title": "Blood Pressure Overview",
                "subtitle": "Your recent readings look stable",
                "mediaUrl": "debug_chart.png",
                "buttons": [
                    {
                        "title": "See More",
                        "type": "openUrl",
                        "payload": "https://patientportal.com/bp/details"
                    }
                ]
            }
        ],
        "quickReplies": [
            {
                "title": "View Labs",
                "type": "trigger",
                "payload": "SHOW_LABS"
            },
            {
                "title": "Schedule Visit",
                "type": "scheduleEvent",
                "payload": "appointment_1234",
                "eventStartTime": "2025-03-01T10:00:00Z",
                "eventEndTime": "2025-03-01T10:30:00Z",
                "eventTitle": "Follow-up Appointment"
            }
        ]
    }
    
    # Test reformatting for SMS/MMS
    sms_content = reformat_for_sms_mms(sample_rcs)
    print("Reformatted for SMS/MMS:")
    print(sms_content)
    
    # Can't test sending without actual credentials
    print("To send a message, use send_message() with valid credentials")

if __name__ == "__main__":
    test_message_handling()