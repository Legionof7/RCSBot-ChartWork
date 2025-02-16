import asyncio
import json
import logging
import os
import re
import base64

from google import genai
from google.genai import types
from google.genai.types import (FunctionDeclaration, GenerateContentConfig,
                                Part, Tool, LiveClientToolResponse,
                                FunctionResponse)
from typing import Tuple, Optional

from fhir_data import get_patient_data

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

4.  **Charts and GRAPH_DATA**
    - When including a chart, generate **executable Python code** using the **Matplotlib** library to create the chart.
    - The code should:
        - Import `matplotlib.pyplot` as `plt`.
        - Import `io` and `base64`.
        - Create the chart (e.g., `plt.plot`, `plt.bar`, etc.).
        - Set appropriate labels and titles.
        - Save the chart to an in-memory `io.BytesIO` object.
        - Encode the image data as a base64 string.
        - Print the base64 string (this is how you'll get the image data).
    -  Example (Line Chart):
        ```python
        import matplotlib.pyplot as plt
        import io
        import base64

        # Sample data (replace with actual data)
        x_values = [1, 2, 3, 4, 5]
        y_values = [2, 4, 1, 3, 5]

        plt.plot(x_values, y_values)
        plt.xlabel("X-Axis")
        plt.ylabel("Y-Axis")
        plt.title("Sample Line Chart")

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        buf.close()
        print(f'data:image/png;base64,{image_base64}')

        ```
    - Example (Bar Chart):
          ```python
          import matplotlib.pyplot as plt
          import io
          import base64

          # Sample data
          labels = ['A', 'B', 'C']
          values = [10, 25, 15]

          plt.bar(labels, values)
          plt.xlabel("Categories")
          plt.ylabel("Values")
          plt.title("Sample Bar Chart")

          buf = io.BytesIO()
          plt.savefig(buf, format='png')
          plt.close()
          image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
          buf.close()
          print(f'data:image/png;base64,{image_base64}')
          ```

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

            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(name=fc.name, id=fc.id, response=result)
            ])
            await session.send(input=tool_response)
        else:
            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(name=fc.name,
                                 id=fc.id,
                                 response={"error": "Unknown function call"})
            ])
            await session.send(input=tool_response)


async def run_gemini_conversation(
        system_prompt: str,
        conversation_text: str) -> Tuple[str, Optional[str]]:
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
        "tools": [{
            "function_declarations": [get_patient_data_declaration]
        }, {
            "code_execution": {}
        }],
        "generation_config": {
            "response_modalities": ["TEXT"]
        }
    }

    final_text = ""
    final_image_base64 = None  # Store the base64 image data

    async with client.aio.live.connect(model="gemini-2.0-flash-exp",
                                       config=config) as session:
        # Send the combined prompt
        await session.send(input=f"{system_prompt}\n\n{conversation_text}",
                           end_of_turn=True)

        # Receive partial responses in a loop
        async for response in session.receive():
            # 1. If there's text, accumulate it
            if response.text:
                final_text += response.text

            # 2. If there's a tool call, handle it
            if response.tool_call:
                await handle_tool_call(session, response.tool_call)

            # 3. If there's code execution info, log it AND extract image
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        logger.info(
                            f"Generated Python code:\n{part.executable_code.code}"
                        )
                    if part.code_execution_result:
                        output = part.code_execution_result.output
                        logger.info(f"Code execution result:\n{output}")
                        # Extract base64 data URI
                        if output and output.startswith(
                                'data:image/png;base64,'):
                            final_image_base64 = output

        # Once the loop finishes, we have the full response in final_text
    return final_text, final_image_base64  # Return both text and image


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

    final_text, final_image_base64 = asyncio.run(
        run_gemini_conversation(system_prompt, conversation_text))

    # --- Parse the text response (same as before) ---
    json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_pattern, final_text, re.DOTALL)
    if matches:
        try:
            response_data = json.loads(matches[-1].strip())
            if isinstance(response_data, dict):
                pass  #good to go!
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            response_data = {
            }  # Create an empty dictionary if JSON parsing fails

    else:
        response_data = {
        }  # Create an empty dictionary if no matches are found.

    # --- Handle the image (NEW) ---
    if final_image_base64:
        # Save debug image
        try:
            image_bytes = base64.b64decode(final_image_base64.split(",")[1])
            with open("debug_chart.png", "wb") as f:
                f.write(image_bytes)
            if os.path.exists("debug_chart.png") and os.path.getsize(
                    "debug_chart.png") > 100:
                print("debug_chart.png created successfully.")
            else:
                print("debug_chart.png creation failed or file is too small.")
        except Exception as e:
            print(f"Warning: Failed to save debug image - {str(e)}")

        # Add the image to the response (choose ONE of the following):

        # Option 1: Add to a card (RECOMMENDED):
        if "cards" not in response_data:
            response_data["cards"] = []
        response_data["cards"].append({
            "title": "Generated Chart",
            "subtitle": "Chart created by Gemini",
            "media_url": final_image_base64,  # Use the data URI directly
        })

    # Ensure quick_replies are in correct format... (same as before)
    if "quick_replies" in response_data:
        #Rest of the code
        for qr in response_data["quick_replies"]:
            if not isinstance(qr, dict) or "title" not in qr:
                logger.error(f"Invalid quick reply format: {qr}")
                return "Error: Invalid quick reply format", 500

    return response_data


if __name__ == "__main__":
    ca = call_gemini([{"role": "user", "content": "Show my cholesterol levels as graph"}])
    print(ca)
