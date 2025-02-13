import asyncio
import json
import logging
import os
from typing import List, Dict, Any

from google import genai
from google.genai import types
from google.genai.types import FunctionDeclaration

from fhir_data import get_patient_data

logger = logging.getLogger(__name__)

def create_context() -> str:
    return """You are SlothMD, a helpful medical assistant bot. You help users understand their health data and provide insights in a friendly way.

Always respond in this JSON format for RCS messages:
{
    "text": "Main message text",
    "cards": [{
        "title": "Card Title",
        "subtitle": "Card description",
        "media_url": "{GRAPH_URL_1}",  // Optional, for graphs
        "buttons": [{
            "title": "Button Text",
            "type": "reply",
            "payload": "button_action"
        }]
    }],
    "quick_replies": ["Option 1", "Option 2"],  // Optional quick reply buttons
    "graph": {  // Optional graph data
        "type": "bar|line|scatter",
        "data": {
            "labels": [],
            "values": []
        }
    }
}"""

# Function declaration for get_patient_data
get_patient_data_declaration = {
    "name": "get_patient_data",
    "description": "Retrieves patient health data from FHIR server",
    "parameters": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "description": "Type of data to retrieve (all, conditions, medications, vitals, labs)",
                "enum": ["all", "conditions", "medications", "vitals", "labs"]
            }
        },
        "required": ["data_type"]
    }
}

async def handle_tool_call(session, tool_call):
    """Handle function calls from the model"""
    for fc in tool_call.function_calls:
        if fc.name == "get_patient_data":
            try:
                data_type = fc.args.get("data_type", "all")
                result = get_patient_data(data_type)
                await session.send(input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            name=fc.name,
                            id=fc.id,
                            response=json.dumps(result)
                        )
                    ]
                ))
            except Exception as e:
                logger.error(f"Error in get_patient_data: {str(e)}")
                raise

async def call_gemini(conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process user message and return RCS-formatted response"""
    try:
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

        config = {
            "tools": [
                {"function_declarations": [get_patient_data_declaration]},
                {"code_execution": {}}
            ]
        }

        system_prompt = create_context()
        messages = [{"role": "system", "content": system_prompt}] + conversation_history

        async with client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
            await session.send(input=json.dumps(messages), end_of_turn=True)

            final_response = None
            async for response in session.receive():
                if response.text:
                    try:
                        final_response = json.loads(response.text)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response: {response.text}")
                        continue

                if response.tool_call:
                    await handle_tool_call(session, response.tool_call)

            if not final_response:
                final_response = {
                    "text": "I apologize, but I encountered an error processing your request.",
                    "cards": [],
                    "quick_replies": ["Start Over"]
                }

            return final_response

    except Exception as e:
        logger.error(f"Error in call_gemini: {str(e)}")
        return {
            "text": "I apologize, but I encountered an error processing your request.",
            "cards": [],
            "quick_replies": ["Start Over"]
        }

def call_gemini_sync(conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Synchronous wrapper for call_gemini"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(call_gemini(conversation_history))


async def main():
    system_prompt = create_context()
    conversation_history = []

    while True:
        user_input = input("\nUser> ")
        if user_input.strip().lower() in ("exit", "quit"):
            print("Exiting...")
            break

        conversation_history.append({"role": "user", "content": user_input})
        response = call_gemini_sync(conversation_history)
        print(json.dumps(response, indent=2))
        conversation_history.append({"role": "assistant", "content": response.get("text", "")})


if __name__ == "__main__":
    asyncio.run(main())