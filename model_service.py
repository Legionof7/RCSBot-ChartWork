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

You are SlothMD, a consumer-facing medical bot. Your goal is to provide helpful, accurate health information, useful insights, and be friendly and conversational.

## Core Rules 

**First, fetch relevant data from the FHIR server using get_patient_data tool.**

** Generate a chart using generate_chart tool. Pass the appropriate necessary data to create a appropriate chart to address user query.**

**Finally, respond to the user query. The final response should be in a RCS json format as described below. Strictly adhere to these rules.**

### RCS Message Format
    - After fetching data, analyze it and provide a respone in RCS json format so that the response can be displayed in the chat window.
    - Your response must be a **single JSON object** that adheres to the following structure:
    {
       "text": "<Full direct, detailed message to the user's query>",
       "cards": [
         {
           "title": "...",
           "subtitle": "...",
           "mediaUrl": "{{GRAPH_URL}}",
           "buttons": [
             {
               "title": "...",
               "type": "...",
               "payload": "...",
               "metadata": "...",
               "eventStartTime": "...",
               "eventEndTime": "...",
               "eventTitle": "...",
               "eventDescription": "...",
               "latLong": {"latitude": 0, "longitude": 0}
             }
           ]
         }
       ],
       "quickReplies": [
         {
           "title": "<Quick reply title>",
           "type": "...",
           "payload": "...",
           "metadata": "...",
           "eventStartTime": "...",
           "eventEndTime": "...",
           "eventTitle": "...",
           "eventDescription": "...",
           "latLong": {"latitude": 0, "longitude": 0}
         }
       ],
       "media_url": "<URL of the generated chart image>"
     }

   - **Important Constraint**: For standard RCS channels, you can only include **one** top-level content type among:
       - "text"
       - "mediaUrl"
       - "cards"
     If you provide "cards", do not provide a top-level "text" or "mediaUrl". However, we are **extending** the structure to include an optional "graph" object. This is custom logic and not standard RCS, but required for our system.

    **Health Cards with “See More” Button**  
        - When showing health data (e.g. labs, vitals, medication details) in cards, ensure **each health card** has at least one button labeled "See More" (or similarly descriptive).  
        - This button can be of type "openUrl", "trigger", or anything relevant to let the user explore details further.  
        - Title for action buttons must be **under 25 characters**. For example:
            {
            "title": "See More",
            "type": "openUrl",
            "payload": "https://patientdetails.com/condition/1234"
            }

    **Buttons**  
        - Up to **4 buttons** can be included in each card.  
        - Supported button types:  
            - openUrl: opens a URL  
            - call: dials a phone number  
            - trigger: sends a predefined payload to the webhook  
            - requestUserLocation: asks the user for location permission  
            - scheduleEvent: creates a calendar event  
            - sendLocation: sends a lat/long  
        - The payload property **must** be set appropriately for each type. For instance, openUrl requires the URL to open as payload, call requires a phone number, etc.  
        - metadata is only used for trigger type, where an additional data string can be sent to the webhook.

    **Quick Replies**  
        - Use quickReplies to offer short, single-tap user actions (max 10).  
        - Each quick reply has the same button-type structure (title, type, payload, etc.).  
        - Provide them if you want to guide the user’s next step (e.g., “View Vitals”, “Check Lab Results”, “Schedule an Appointment”).
        - Always provide follow-up questions in quick replies (under 25 characters) for people to learn more.

    **When to Use Cards vs Text vs Media**  
        - If you have **simple text** with no visual or interactive elements, use text.  
        - If you’re sending **images or charts** but no additional structured content, you can provide "mediaUrl" in the top-level JSON.  
        - If you want **structured data** with buttons, subtitles, or visuals, use cards.  
        - **Do not** mix text, mediaUrl, and cards at the top-level. If you have multiple data blocks, you can use multiple cards inside the "cards" array.


    **You should send the message directly addressing the user query. Avoid small talk. When user asks question related to his data, your response should always be based on the data.**
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
        "required": ["data_type"]
    }
}

generate_chart_declaration = {
    "name": "generate_chart",
    "description":
    "given FHIR data(labResults, vitals, etc) generates a chart and returns the chart image url",
    "parameters": {
        "type": "object",
        "properties": {
            "data": {
                "type":
                "string",
                "description":
                ("data to generate chart from(data can be rough, it will be processed and converted to chart)"
                 ),
            },
            "react_code": {
                "type":
                "string",
                "description":
                ("React code(using `React.createElement`, NOT JSX) to generate the chart. The component should be named `MyChart` and must NOT expect any props. The data for the chart MUST be defined *within* the `MyChart` component itself.\n\n"
                 "It should be simple with proper naming, title, legends. It should be simple and easy to understand. It should be understandable by a 5 year old."
                 "**Example of ACCEPTABLE React code:**\n"
                 "```javascript\n"
                 "const MyChart = () => {\n"
                 "    const data = [\n"
                 "      { x: 'A', y: 10 },\n"
                 "      { x: 'B', y: 20 },\n"
                 "      { x: 'C', y: 30 }\n"
                 "    ];\n"
                 "    return React.createElement(\n"
                 "        VictoryChart,\n"
                 "        { theme: VictoryTheme.material, domainPadding: 20, width: 1000, height: 800 },\n"
                 "        React.createElement(VictoryBar, {\n"
                 "            data: data,\n"
                 "            style: { data: { fill: '#4CAF50' } },\n"
                 "            labels: ({ datum }) => datum.y\n"
                 "        })\n"
                 "    );\n"
                 "};\n"
                 "```"),
            }
        },
        "required": ["data", "react_code"]
    }
}


async def handle_tool_call(session, tool_call):
    """Handle function calls (tool calls) from the model."""
    print(
        f"#################### [model_service] Received tool call: {tool_call}"
    )
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
            print()
            await session.send(input=tool_response)

        elif fc.name == "generate_chart":
            react_code = fc.args.get("react_code")
            data = fc.args.get("data")
            print(data)
            if not react_code:
                raise ValueError("react_code cannot be empty")
            try:
                graph_url = generate_graph(react_code)
                print("==============================================")
                # graph_url = generate_graph(data, data)
                print(graph_url)
                print(graph_url)
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
    client = genai.Client(
        api_key=os.getenv('GEMINI_API_KEY'),
        http_options={'api_version': 'v1alpha'}  # Live (experimental)
    )

    config = {
        "tools": [{
            "function_declarations":
            [get_patient_data_declaration, generate_chart_declaration]
        }],
        "generation_config": {
            "response_modalities": ["TEXT"]
        }
    }

    final_text = ""

    async with client.aio.live.connect(model="gemini-2.0-flash-exp",
                                       config=config) as session:

        await session.send(
            input=f"{system_prompt}\n\n{conversation_text}",
            end_of_turn=True,
        )

        async for response in session.receive():
            print(
                "-----------------------------------------------------------------------"
            )
            if response.text:
                print("Text Response: ", response.text)
                final_text += response.text

            if response.tool_call:
                print("Tool Call: ", response.tool_call)
                await handle_tool_call(session, response.tool_call)

            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        logger.info(
                            f"Generated Python code$$$$$$$:\n{part.executable_code.code}"
                        )
                    if part.code_execution_result:
                        logger.info(
                            f"Code execution result$$$$$$$:\n{part.code_execution_result.output}"
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
    print(
        ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>$$$$ model_service.py entrypoint"
    )
    print(conversation_slice)

    system_prompt = create_context()
    conversation_text = build_conversation_text(conversation_slice)

    final_text = asyncio.run(
        run_gemini_conversation(system_prompt, conversation_text))

    print("#######################################################++")
    print("FINAL TEXT: ", final_text)

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
        "role": "user",
        "content": "Tell me about my different cholestrol levels"  # Test query
    }])
    print(ca)
