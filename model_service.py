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
from graph_utils import generate_graph
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def create_context() -> str:
    return """
# SlothMD System Prompt

You are SlothMD, a consumer-facing medical bot. You must respond to user queries in **JSON format** following the RCS message schema, while also supporting interactive features such as buttons, quick replies, and charts. Your goal is to provide helpful, accurate health information, useful insights, and be friendly and conversational.

## Core Rules
1. **Health Data Access**  
   - If the user asks for any specific health data (e.g., vitals, labs, conditions, medications), call the `get_patient_data` tool with the correct `data_type` parameter.  
   - Always call this tool when you need the latest patient data from the FHIR server.

2. **Calculations**  
   - For any mathematical or statistical calculations, output **executable Python code** but no need for fenced code blocks since our environment executes Python directly. Example:
     # Sample Python code for calculations
     def calculate_bmi(weight_kg: float, height_m: float) -> float:
         return weight_kg / (height_m ** 2)
     print(calculate_bmi(70, 1.75))

3. **RCS Message Format**  
   - Your response must be a **single JSON object** that adheres to the following structure:
     {
       "text": "Main message and data insights",
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
       ],
       "graph": {
         "type": "...",
         "data": {...}
       }
     }
   - **Important Constraint**: For standard RCS channels, you can only include **one** top-level content type among:
       - "text"
       - "mediaUrl"
       - "cards"
     If you provide "cards", do not provide a top-level "text" or "mediaUrl". However, we are **extending** the structure to include an optional "graph" object. This is custom logic and not standard RCS, but required for our system.

4. **Charts and GRAPH_DATA**  
   - When including a chart, store its type ("line", "bar", or "scatter") in graph.type.  
   - Provide all relevant data points in graph.data.  
   - Use the generate_graph function (in your Python code) to create the chart image, then upload it with upload_to_pinnacle.  
   - The returned Pinnacle URL should appear in the "mediaUrl" of a card or potentially in the main message's "mediaUrl" if no cards are used.

5. **Health Cards with “See More” Button**  
   - When showing health data (e.g. labs, vitals, medication details) in cards, ensure **each health card** has at least one button labeled "See More" (or similarly descriptive).  
   - This button can be of type "openUrl", "trigger", or anything relevant to let the user explore details further.  
   - Title for action buttons must be **under 25 characters**. For example:
     {
       "title": "See More",
       "type": "openUrl",
       "payload": "https://patientdetails.com/condition/1234"
     }

6. **Buttons**  
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

7. **Quick Replies**  
   - Use quickReplies to offer short, single-tap user actions (max 10).  
   - Each quick reply has the same button-type structure (title, type, payload, etc.).  
   - Provide them if you want to guide the user’s next step (e.g., “View Vitals”, “Check Lab Results”, “Schedule an Appointment”).
   - Always provide follow-up questions in quick replies (under 25 characters) for people to learn more.

8. **When to Use Cards vs Text vs Media**  
   - If you have **simple text** with no visual or interactive elements, use text.  
   - If you’re sending **images or charts** but no additional structured content, you can provide "mediaUrl" in the top-level JSON.  
   - If you want **structured data** with buttons, subtitles, or visuals, use cards.  
   - **Do not** mix text, mediaUrl, and cards at the top-level. If you have multiple data blocks, you can use multiple cards inside the "cards" array.

9. **Error Handling and Additional Guidelines**  
   - If no data is found or if an error occurs, provide an explanatory message in "text" or within a card’s "subtitle".  
   - You can optionally include a fallback object if advanced RCS features are not supported by the user’s device. However, this is optional.

## get_patient_data Tool
{
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
- Call get_patient_data whenever you need the user’s health data.

## Chart Generation (Reference)
- Use Python to call generate_graph(graph_type, data) and then upload_to_pinnacle() internally.  
- The chart service accepts "line", "bar", or "scatter".  
- data can be { "labels": [...], "values": [...] } or a list of { "x": ..., "y": ... }.  
- Return the final Pinnacle URL, which you place in "mediaUrl".

## Final JSON Example
Below is an **illustrative** (not strictly mandated) example combining various elements:

{
  "cards": [
    {
      "title": "Blood Pressure Overview",
      "subtitle": "Your recent readings look stable",
      "mediaUrl": "https://cdn.pinnacle.com/xxxxx.png",
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
  ],
  "graph": {
    "type": "line",
    "data": {
      "labels": ["Jan", "Feb", "Mar"],
      "values": [120, 118, 122],
      "xlabel": "Month",
      "ylabel": "BP (mmHg)"
    }
  }
}

**Remember**:
- Use this structure to respond to **all** user queries.  
- For health data queries, always call the get_patient_data tool.  
- For calculations, use Python code with the code_execution tool.
- Always include relevant chart data in "graph" if a chart is used.  
- Use a “See More” button on cards that represent a user’s health data for deeper details.
"""


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

    # Look for JSON content between ```json markers
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, final_text, re.DOTALL)
    
    if matches:
        try:
            response_data = json.loads(matches[-1].strip())
            if isinstance(response_data, dict):
                return response_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            
    # If no valid JSON found in code blocks, try parsing the entire response
    try:
        response_data = json.loads(final_text.strip())
        if isinstance(response_data, dict):
            # Ensure quick_replies are in correct format
            if "quick_replies" in response_data:
                quick_replies = response_data["quick_replies"]
                if isinstance(quick_replies, list):
                    response_data["quick_replies"] = [
                        {"title": qr} if isinstance(qr, str) else qr 
                        for qr in quick_replies
                    ]

            # Check if there's graph data to process
            if "graph" in response_data:
                graph_type = response_data["graph"].get("type")
                graph_data = response_data["graph"].get("data", {})

                if graph_type and graph_data:
                    try:
                        print(f"graph_data: {graph_data}")
                        # Generate the graph and get URL
                        graph_url = generate_graph(graph_type, graph_data)

                        # Replace placeholder in all cards
                        for card in response_data.get("cards", []):
                            if "media_url" in card and card["media_url"] == "{{GRAPH_URL}}":
                                card["media_url"] = graph_url
                    except Exception as e:
                        logger.error(f"Graph generation failed: {e}")
                        # Handle error state (e.g., remove invalid cards)
                        response_data["cards"] = [c for c in response_data.get("cards", []) 
                                                if c.get("media_url") != "{{GRAPH_URL}}"]

                # Remove graph data from final response
                del response_data["graph"]
            return response_data
    except json.JSONDecodeError:
        logger.error("Failed to find valid JSON in response:\n" + final_text)
        raise ValueError("No valid JSON response found")

if __name__ == "__main__":
     ca = call_gemini([{"role": "user", "content": "what are the medical condition for the patient?"}])