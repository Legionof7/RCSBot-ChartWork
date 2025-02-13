import asyncio
import json
import logging
import os
import re

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

from fhir_data import get_patient_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

async def handle_tool_call(session, tool_call):
    """Handle function calls (tool calls) from the model."""
    for fc in tool_call.function_calls:
        if fc.name == "get_patient_data":
            data_type = fc.args.get("data_type", "all")
            try:
                result = get_patient_data(data_type)
            except Exception as e:
                result = {"error": str(e)}

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

async def run_gemini_conversation(system_prompt: str, conversation_text: str) -> str:
    """
    Open a live session with the Gemini model, feed it the system prompt + user/assistant messages,
    handle function calls, and return the final text. The streaming ends automatically once the
    model is done sending messages.
    """
    client = genai.Client(
        api_key=os.getenv('GEMINI_API_KEY'),
        http_options={'api_version': 'v1alpha'}  # Live (experimental)
    )

    config = {
        "tools": [
            {"function_declarations": [get_patient_data_declaration]},
            {"code_execution": {}}
        ],
        "generation_config": {
            "response_modalities": ["TEXT"]
        }
    }

    final_text = ""

    async with client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
        # Send the combined prompt
        await session.send(input=f"{system_prompt}\n\n{conversation_text}", end_of_turn=True)

        # Receive partial responses in a loop
        async for response in session.receive():
            # 1. If there's text, accumulate it
            if response.text:
                final_text += response.text

            # 2. If there's a tool call, handle it
            if response.tool_call:
                await handle_tool_call(session, response.tool_call)

            # 3. If there's code execution info, log it
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        logger.info(f"Generated Python code:\n{part.executable_code.code}")
                    if part.code_execution_result:
                        logger.info(f"Code execution result:\n{part.code_execution_result.output}")

        # Once the loop finishes, we have the full response in final_text
    return final_text

def build_conversation_text(conversation_slice):
    """
    Convert conversation_slice into a text block, e.g.:
        User: Hello, I'd like my latest vitals
        Assistant: Sure, do you have any date in mind?
        ...
    """
    convo_lines = []
    for turn in conversation_slice:
        role = turn['role'].capitalize()  # "User" or "Assistant"
        content = turn['content']
        convo_lines.append(f"{role}: {content}")
    return "\n".join(convo_lines)

def remove_markdown_code_fences(text: str) -> str:
    """
    Removes triple backtick code fences of the form:
        ```json
        { ... }
        ```
    or
        ```
        { ... }
        ```
    Returns the cleaned string without the fences.
    """
    pattern = r"```(?:[a-zA-Z0-9]+)?\s*(.*?)\s*```"  # DOTALL will match across lines
    cleaned = re.sub(pattern, r"\1", text, flags=re.DOTALL)
    return cleaned.strip()

def call_gemini(conversation_slice):
    """
    Called from main.py:
      1) Build system prompt + conversation context
      2) Run the async conversation with Gemini
      3) Remove any markdown fences
      4) Parse as JSON
      5) Return the final JSON dict
    """
    system_prompt = create_context()
    conversation_text = build_conversation_text(conversation_slice)

    final_text = asyncio.run(
        run_gemini_conversation(system_prompt, conversation_text)
    )

    # Extract the last valid JSON output from code execution
    lines = final_text.split('\n')
    last_json = ""
    for line in reversed(lines):
        if line.strip().startswith('{') and line.strip().endswith('}'):
            try:
                response_data = json.loads(line.strip())
                if isinstance(response_data, dict):
                    return response_data
            except:
                continue

    # If no valid JSON found, raise error
    logger.error("Failed to find valid JSON in response:\n" + final_text)
    raise ValueError("No valid JSON response found")

    return response_data
