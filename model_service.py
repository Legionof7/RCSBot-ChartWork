# model_service.py
import asyncio
import json
import logging
import os
import re

from google import genai
from google.genai import types
from google.genai.types import (FunctionDeclaration, GenerateContentConfig,
                                Part, Tool, LiveClientToolResponse,
                                FunctionResponse)

from fhir_data import get_patient_data
from graph_utils import generate_graph

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def create_context() -> str:
    return """
# SlothMD System Prompt

You are SlothMD, a consumer-facing medical bot.  Your goal is to provide helpful and accurate health information.

## Core Rules

1.  **Health Data Access:** Use the `get_patient_data` tool.
2.  **Calculations:** Output executable Python code.
3.  **RCS Message Format:** Respond with a single JSON object:
    ```json
    {
      "text": "...",
      "cards": [{
        "title": "...",
        "subtitle": "...",
        "mediaUrl": "{{GRAPH_URL}}",  // Use this for charts!
        "buttons": [...]
      }],
      "quickReplies": [...]
    }
    ```
    Only ONE top-level content type: "text", "mediaUrl", OR "cards".

4.  **Charts and {{GRAPH_URL}}:**  Use the `generate_chart` tool. The returned URL will be placed in the `mediaUrl` of a card, replacing `{{GRAPH_URL}}`.

5.  **"See More" Button:**  Include a "See More" button on health data cards.

6.  **Buttons:** Up to 4 buttons per card. Supported types: `openUrl`, `call`, `trigger`, `requestUserLocation`, `scheduleEvent`, `sendLocation`.

7.  **Quick Replies:** Use `quickReplies` for short actions (max 10).

8.  **Cards vs. Text vs. Media:** Choose the appropriate content type.

9.  **Error Handling:** Provide explanatory messages.

## Tools

You have the following tools available:

"""


get_patient_data_declaration = {
    "name": "get_patient_data",
    "description":
    "Retrieves patient data from FHIR server based on the provided query.",
    "parameters": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "description":
                "Type of data to retrieve (all, conditions, medications, vitals, labs)",
                "enum": ["all", "conditions", "medications", "vitals", "labs"]
            }
        },
        "required": ["data_type"]  # data_type is now required
    }
}

generate_chart_declaration = {
    "name":
    "generate_chart",
    "description":
    ("Generates a chart from React code and returns the image URL. "
     "**IMPORTANT: You MUST provide valid React code that uses `React.createElement` exclusively.  Do NOT use JSX syntax.**\n\n"
     "The provided React code MUST define a functional component named `MyChart`.  This component should NOT expect any props.\n\n"
     "**The data for the chart MUST be defined *within* the `MyChart` component itself.** \n\n"
     "The React code should use the Victory charting library components (e.g., `VictoryChart`, `VictoryLine`, `VictoryBar`, etc.) to create the chart.\n\n"
     "Example of ACCEPTABLE React code (using React.createElement):\n"
     "```javascript\n"
     "const MyChart = () => {\n"
     "    const data = [\n"
     "      { x: 1, y: 2 },\n"
     "      { x: 2, y: 3 },\n"
     "      { x: 3, y: 5 }\n"
     "    ];\n"
     "    return React.createElement(\n"
     "        VictoryChart,\n"
     "        { theme: VictoryTheme.material },\n"
     "        React.createElement(VictoryLine, { data: data })\n"
     "    );\n"
     "};\n"),
    "parameters": {
        "type": "object",
        "properties": {
            "react_code": {
                "type":
                "string",
                "description":
                "The React code (using React.createElement, NOT JSX) to render the chart. The component should be named MyChart. The data MUST be defined within the component itself and should only be the data required for the chart."
            }
        },
        "required": ["react_code"]
    }
}


async def handle_tool_call(session, tool_call):
    """Handle function calls (tool calls) from the model."""
    for fc in tool_call.function_calls:
        if fc.name == "get_patient_data":
            data_type = fc.args.get("data_type", "all")  # "all" is a fallback
            if not data_type:  # data type should not be empty
                raise ValueError("data_type cannot be empty")
            try:
                result = get_patient_data(data_type)
            except Exception as e:
                result = {"error": str(e)}

            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(name=fc.name, id=fc.id, response=result)
            ])
            await session.send(input=tool_response)

        elif fc.name == "generate_chart":
            react_code = fc.args.get("react_code")
            if not react_code:
                raise ValueError("react_code cannot be empty")
            try:
                graph_url = generate_graph(react_code)
                tool_response = LiveClientToolResponse(function_responses=[
                    FunctionResponse(
                        name=fc.name, id=fc.id, response={"url": graph_url})
                ])
                await session.send(input=tool_response)
            except Exception as e:
                tool_response = LiveClientToolResponse(function_responses=[
                    FunctionResponse(
                        name=fc.name, id=fc.id, response={"error": str(e)})
                ])
                await session.send(input=tool_response)
        else:
            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(name=fc.name,
                                 id=fc.id,
                                 response={"error": "Unknown function call"})
            ])
            await session.send(input=tool_response)


async def run_gemini_conversation(system_prompt: str,
                                  conversation_text: str) -> str:
    """
    Open a live session with the Gemini model.
    """
    client = genai.Client(
        api_key=os.getenv('GEMINI_API_KEY'),
        http_options={'api_version': 'v1alpha'}  # Live (experimental)
    )

    config = {
        "tools": [
            {
                "function_declarations": [
                    get_patient_data_declaration,
                    generate_chart_declaration  
                ]
            },
            {
                "code_execution": {}
            }
        ],
        "generation_config": {
            "response_modalities": ["TEXT"]
        }
    }

    final_text = ""

    async with client.aio.live.connect(model="gemini-2.0-flash-exp",
                                       config=config) as session:
        await session.send(input=f"{system_prompt}\n\n{conversation_text}",
                           end_of_turn=True)

        async for response in session.receive():
            if response.text:
                final_text += response.text

            if response.tool_call:
                await handle_tool_call(session, response.tool_call)

            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        logger.info(
                            f"Generated Python code:\n{part.executable_code.code}"
                        )
                    if part.code_execution_result:
                        logger.info(
                            f"Code execution result:\n{part.code_execution_result.output}"
                        )

    return final_text


def build_conversation_text(conversation_slice):
    """Formats conversation history."""
    convo_lines = []
    for turn in conversation_slice:
        role = turn['role'].capitalize()
        content = turn['content']
        convo_lines.append(f"{role}: {content}")
    return "\n".join(convo_lines)


def remove_markdown_code_fences(text: str) -> str:
    """Removes markdown code fences."""
    pattern = r"```(?:[a-zA-Z0-9]+)?\s*(.*?)\s*```"
    cleaned = re.sub(pattern, r"\1", text, flags=re.DOTALL)
    return cleaned.strip()


def call_gemini(conversation_slice):
    """Main entry point from main.py."""
    system_prompt = create_context()
    conversation_text = build_conversation_text(conversation_slice)

    final_text = asyncio.run(
        run_gemini_conversation(system_prompt, conversation_text))

    # --- JSON Parsing (for the RCS response) ---
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, final_text, re.DOTALL)
    if matches:
        try:
            response_data = json.loads(matches[-1].strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            response_data = {}
    else:
        try:
            response_data = json.loads(final_text.strip())
        except:
            response_data = {}

    return response_data


if __name__ == "__main__":
    ca = call_gemini([{
        "role":
        "user",
        "content":
        "Show me my different cholesterol levels in a graph"  # Test query
    }])
    print(ca)
