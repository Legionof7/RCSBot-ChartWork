import asyncio
import json
import logging
import os

from google import genai
from google.genai import types
from google.genai.types import (
    FunctionDeclaration,
    GenerateContentConfig,
    Part,
    Tool,
    LiveClientToolResponse,
    FunctionResponse
)

def call_gemini(conversation_history):
    """Process conversation history with Gemini and return response"""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-pro')
    
    # Format conversation for Gemini
    gemini_messages = []
    for msg in conversation_history:
        gemini_messages.append({
            "role": msg["role"],
            "parts": [{"text": msg["content"]}]
        })
    
    # Call Gemini model
    chat = model.start_chat(history=gemini_messages)
    response = chat.send_message("")
    
    try:
        # Parse response into expected format
        response_data = json.loads(response.text)
        return response_data
    except json.JSONDecodeError:
        # Fallback if response is not valid JSON
        return {
            "text": response.text,
            "cards": [],
            "quick_replies": []
        }

# Example import for your FHIR data retrieval
from fhir_data import get_patient_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 1. SlothMD System Prompt
def create_context() -> str:
    return """# SlothMD System Prompt

You are a bot designed to answer questions about a user's health. Use the get_patient_data tool to get their health data.

Respond in JSON format with cards and graphs for an RCS response. Follow these rules:
1. For health data questions, use get_patient_data
2. For calculations, generate executable Python code
3. Include GRAPH_DATA in JSON response
4. Health cards must have "See More" button

Final JSON structure:
{
  "text": "Main message and data insights",
  "cards": [{
    "title": "...",
    "subtitle": "...",
    "media_url": "{{GRAPH_URL}}",
    "buttons": [...]
  }],
  "quick_replies": [...],
  "graph": {"type": "...", "data": {}}
}"""


# 2. Define a function declaration for get_patient_data
get_patient_data_declaration = {
    "name": "get_patient_data",
    "description": "Retrieves patient data from FHIR server based on the provided query.",
    "parameters": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "description": "Type of data to retrieve (all, conditions, medications, vitals, labs)",
                "enum": ["all", "conditions", "medications", "vitals", "labs"]
            }
        },
        "required": []
    }
}


def validate_rcs_response(response_data):
    """Validate and format response data for RCS"""
    if not isinstance(response_data, dict):
        raise ValueError("Response must be a dictionary")
        
    # Ensure minimum required structure
    if "text" not in response_data and "cards" not in response_data:
        raise ValueError("Response must contain either 'text' or 'cards'")
        
    # Format cards if present
    if "cards" in response_data:
        for card in response_data["cards"]:
            if not isinstance(card, dict):
                raise ValueError("Each card must be a dictionary")
            if "title" not in card:
                card["title"] = "Information"
            if "subtitle" not in card and "description" in card:
                card["subtitle"] = card.pop("description")
                
    return response_data

# 3. Handle function calls from the model
async def handle_tool_call(session, tool_call):
    """
    Captures any function calls (tool calls) from the model.
    If it's get_patient_data, we invoke our Python function and respond with the result.
    The code_execution tool is automatically handled by the API unless you want
    to intercept or modify code/results yourself.
    """
    for fc in tool_call.function_calls:
        if fc.name == "get_patient_data":
            data_type = fc.args.get("data_type", "all")
            try:
                # Call your FHIR retrieval function
                result = get_patient_data(data_type)
            except Exception as e:
                # Return error if needed
                result = {"error": str(e)}

            # Send the tool response back to the model
            tool_response = LiveClientToolResponse(
                function_responses=[
                    FunctionResponse(
                        name=fc.name,
                        id=fc.id,
                        response=result
                    )
                ]
            )
            await session.send(input=tool_response)

        else:
            # If we had another function, handle it here.
            tool_response = LiveClientToolResponse(
                function_responses=[
                    FunctionResponse(
                        name=fc.name,
                        id=fc.id,
                        response={"error": "Unknown function call"}
                    )
                ]
            )
            await session.send(input=tool_response)


# 4. Main async function that runs the conversation for one user query
async def run_conversation(system_prompt: str, user_message: str):
    # Create a client (replace with your actual API key)
    client = genai.Client(
        api_key=os.getenv('GEMINI_API_KEY'),
        http_options={'api_version': 'v1alpha'}  # Live API
    )

    # Combine system + user content into a single prompt
    combined_prompt = f"{system_prompt}\n\nUser: {user_message}"

    # Tools array: we declare our custom function, plus code_execution
    config = {
        "tools": [
            {"function_declarations": [get_patient_data_declaration]},  # custom function
            {"code_execution": {}}                                      # model-run Python
        ],
        "generation_config": {
            "response_modalities": ["TEXT"]  # just text back (no audio)
        }
    }

    # Open a Live Chat session with the Gemini model
    async with client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
        # Send our prompt
        await session.send(input=combined_prompt, end_of_turn=True)

        # Receive messages from the model
        async for response in session.receive():
            # 1. Normal text from the assistant
            if response.text:
                print("\nAssistant says:\n", response.text)

            # 2. If the model calls a function (tool)
            if response.tool_call:
                await handle_tool_call(session, response.tool_call)

            # 3. If the model sends code to execute or returns code-execution results
            if response.server_content:
                model_turn = response.server_content.model_turn
                if model_turn:
                    for part in model_turn.parts:
                        # The model’s generated Python code
                        if part.executable_code:
                            print("Generated Python code:\n", part.executable_code.code)
                        # The results of that code execution
                        if part.code_execution_result:
                            print("Code execution result:\n", part.code_execution_result.output)


# 5. Entry point with a loop for multiple user inputs
async def main():
    system_prompt = create_context()

    while True:
        user_input = input("\nUser> ")
        if user_input.strip().lower() in ("exit", "quit"):
            print("Exiting...")
            break

        # Call the conversation runner for each user input
        await run_conversation(system_prompt, user_input)


if __name__ == "__main__":
    asyncio.run(main())
