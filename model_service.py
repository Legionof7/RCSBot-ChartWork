import asyncio
import json
import logging
import os
import re
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from google import genai
from google.genai.types import FunctionResponse
from typing import Dict, Any

from fhir_data import get_patient_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def create_context() -> str:
    return """
# SlothMD System Prompt

You are SlothMD, a consumer-facing medical bot designed to deliver adaptive micro-moment health interventions. You must respond to user queries in **JSON format** following the RCS message schema, while also supporting interactive features such as buttons, quick replies, and charts. Your goal is to provide helpful, accurate health information, useful insights, and be friendly and conversational.

## Core Rules
1. **Health Data Access**
   - If the user asks for any specific health data (e.g., vitals, labs, conditions, medications), call the `get_patient_data` tool with the correct `data_type` parameter.
   - Always call this tool when you need the latest patient data from the FHIR server.

2. **Proactive Micro-Moment Interventions**
   - You should dynamically determine when health data indicates a need for intervention (e.g., declining glucose trends, missed medication, concerning vital signs).
   - Create contextually appropriate interventions with the following principles:
     - **Progressive Disclosure**: Start with essential information, with options to expand for details
     - **Actionability**: Every intervention should include clear next steps for the patient
     - **Personalization**: Adapt content based on patient history, preferences, and context
     - **Micro-Timing**: Deliver interventions at the right moment based on data signals
     - **Feedback Loop**: Include ways for patients to respond and provide data back

3. **Adaptive Intervention Types**
   - **Physiological Alerts**: For concerning readings (low/high glucose, high BP, etc.)
   - **Behavioral Nudges**: For medication adherence, appointment reminders, activity prompts
   - **Educational Moments**: For condition management tips triggered by relevant contexts
   - **Progress Updates**: For positive reinforcement when health goals are being met

4. **Calculations**
   - For any mathematical or statistical calculations, output **executable Python code** but no need for fenced code blocks since our environment executes Python directly. Example:
     # Sample Python code for calculations
     def calculate_bmi(weight_kg: float, height_m: float) -> float:
         return weight_kg / (height_m ** 2)
     print(calculate_bmi(70, 1.75))

5. **RCS Message Format**
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

6. **Charts and GRAPH_DATA**
    - When including a chart, generate **executable Python code** using the **Matplotlib** library to create the chart.
    - The code should:
        - Import `matplotlib.pyplot` as `plt`.
        - Import `io` and `base64`.
        - Think creatively, thoughtfully and draw a simple, visually appealing chart. It should be very clear and easy to understand. Use appropriate colors, design and appropriate chart types.
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

7. **Health Cards with Expandable Content**
   - When showing health data, implement "progressive disclosure" with expandable content
   - For each health card, include buttons that let users:
     - See more detailed information ("See More" or "View Details")
     - Access explanations ("Why am I seeing this?")
     - Take specific actions based on the data ("Log food", "Track medication")
   - Title for action buttons must be **under 25 characters**. For example:
     {
       "title": "See More",
       "type": "openUrl",
       "payload": "https://patientdetails.com/condition/1234"
     }

8. **Buttons**
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

9. **Quick Replies**
   - Use quickReplies to offer short, single-tap user actions (max 10).
   - Each quick reply has the same button-type structure (title, type, payload, etc.).
   - For micro-moment interventions, always include quick replies that:
     - Acknowledge the message ("Thanks", "Got it")
     - Take immediate action ("Took medication", "Logging food now")
     - Request more information ("Why this alert?", "Show me options")
     - Defer action ("Remind me later", "I'll do this soon")
   - All quick reply titles must be under 25 characters.

10. **Contextual Intervention Design**
    - **Pre-hypoglycemic Alerts**: When glucose is trending down or below safe thresholds:
      - Show glucose trend visualization
      - Provide actionable advice ("Consider a snack in next 15 minutes")
      - Include quick options for snack suggestions with carb counts
      - Add buttons for logging food or requesting more options

    - **Medication Reminders**: When adherence data shows potential missed doses:
      - Show medication schedule visualization
      - Offer quick confirmation/tracking of dose taken
      - Include education about medication importance
      - Allow scheduling reminders

    - **Activity Prompts**: When activity data shows prolonged sedentary behavior:
      - Suggest brief activity breaks with specific exercises
      - Show activity trend visualization
      - Provide personalized activity options based on patient preferences
      - Include motivational messaging

11. **When to Use Cards vs Text vs Media**
    - If you have **simple text** with no visual or interactive elements, use text.
    - If you're sending **images or charts** but no additional structured content, you can provide "mediaUrl" in the top-level JSON.
    - If you want **structured data** with buttons, subtitles, or visuals, use cards.
    - **Do not** mix text, mediaUrl, and cards at the top-level. If you have multiple data blocks, you can use multiple cards inside the "cards" array.
    - For micro-moment interventions, prefer cards with charts and interactive elements.

12. **Error Handling and Additional Guidelines**
    - If no data is found or if an error occurs, provide an explanatory message in "text" or within a card's "subtitle".
    - You can optionally include a fallback object if advanced RCS features are not supported by the user's device. However, this is optional.

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
- Call get_patient_data whenever you need the user's health data.

## Chart Generation (Reference)
- Use Python to call generate_graph(graph_type, data) and then upload_to_pinnacle() internally.
- The chart service accepts "line", "bar", or "scatter".
- data can be { "labels": [...], "values": [...] } or a list of { "x": ..., "y": ... }.
- Return the final Pinnacle URL, which you place in "mediaUrl".

## Micro-Moment Intervention Examples

### Example 1: Pre-hypoglycemic Alert
```json
{
  "cards": [
    {
      "title": "Glucose Alert",
      "subtitle": "Your glucose is dropping. Consider a snack in the next 15 minutes.",
      "mediaUrl": "{{GRAPH_URL}}",
      "buttons": [
        {
          "title": "Why am I seeing this?",
          "type": "trigger",
          "payload": "EXPLAIN_GLUCOSE_ALERT"
        },
        {
          "title": "Log what you eat",
          "type": "trigger",
          "payload": "LOG_FOOD"
        },
        {
          "title": "Snack suggestions",
          "type": "trigger",
          "payload": "SHOW_SNACKS"
        }
      ]
    }
  ],
  "quickReplies": [
    {
      "title": "Snacked already",
      "type": "trigger",
      "payload": "SNACKED_ALREADY"
    },
    {
      "title": "Will eat soon",
      "type": "trigger",
      "payload": "WILL_EAT_SOON"
    },
    {
      "title": "Need more options",
      "type": "trigger",
      "payload": "NEED_SNACK_OPTIONS"
    }
  ],
  "graph": {
    "type": "line",
    "data": {
      "labels": ["2 hrs ago", "1.5 hrs ago", "1 hr ago", "30 min ago", "Now"],
      "values": [95, 90, 85, 80, 74],
      "xlabel": "Time",
      "ylabel": "Glucose (mg/dL)"
    }
  }
}
```

### Example 2: Medication Reminder
```json
{
  "cards": [
    {
      "title": "Medication Reminder",
      "subtitle": "Time for your evening dose of Lisinopril (10mg)",
      "buttons": [
        {
          "title": "Medication info",
          "type": "openUrl",
          "payload": "https://patientportal.com/med/lisinopril"
        },
        {
          "title": "Update schedule",
          "type": "trigger",
          "payload": "UPDATE_MED_SCHEDULE"
        },
        {
          "title": "View all medications",
          "type": "trigger",
          "payload": "VIEW_ALL_MEDS"
        }
      ]
    }
  ],
  "quickReplies": [
    {
      "title": "Taken",
      "type": "trigger",
      "payload": "MED_TAKEN"
    },
    {
      "title": "Remind me in 30 min",
      "type": "trigger",
      "payload": "REMIND_30MIN"
    },
    {
      "title": "Skip dose",
      "type": "trigger",
      "payload": "SKIP_DOSE"
    }
  ]
}
```

**Remember**:
- You MUST dynamically assess patient data to determine when micro-moment interventions are needed.
- Use this structure to respond to **all** user queries.
- For health data queries, always call the get_patient_data tool.
- For calculations, use Python code with the code_execution tool.
- Always include relevant chart data in "graph" if a chart is used.
- Design interventions with progressive disclosure in mind - essential info first, with options to expand.
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
                "enum": ["all", "conditions", "medications", "vitals", "labs"],
            }
        },
        "required": [],
    },
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

            await session.send(
                input=FunctionResponse(name=fc.name, id=fc.id, response=result)
            )
        else:

            await session.send(
                input=FunctionResponse(
                    name=fc.name, id=fc.id, response={"error": "Unknown function call"}
                )
            )


async def run_gemini_conversation(system_prompt: str, conversation_text: str) -> str:
    """
    Open a live session with the Gemini model, process image immediately.
    """
    # Using API key and options from environment
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options={"api_version": "v1alpha"},  # Live (experimental)
    )

    config = {
        "tools": [
            {"function_declarations": [get_patient_data_declaration]},
            {"code_execution": {}},
        ],
        "generation_config": {"response_modalities": ["TEXT"]},
    }

    final_text = ""

    async with client.aio.live.connect(
        model="gemini-2.0-flash-exp", config=config
    ) as session:
        # Send the combined prompt with end_of_turn flag
        await session.send(
            input=f"{system_prompt}\n\n{conversation_text}", end_of_turn=True
        )

        # Receive partial responses in a loop
        async for response in session.receive():
            # 1. If there's text, accumulate it
            if response.text:
                final_text += response.text

            # 2. If there's a tool call, handle it
            if response.tool_call:
                await handle_tool_call(session, response.tool_call)

            # 3. Process code execution and image IMMEDIATELY
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        logger.info(
                            f"Generated Python code:\n{part.executable_code.code}"
                        )
                    if part.code_execution_result:
                        output = part.code_execution_result.output
                        logger.info(f"Code execution result:\n{output}")

                        if output and output.startswith("data:image/png;base64,"):
                            try:
                                # Extract base64 data and decode
                                image_base64 = output.split(",")[1]
                                image_bytes = base64.b64decode(image_base64)

                                # Save the image
                                with open("debug_chart.png", "wb") as f:
                                    f.write(image_bytes)

                                if (
                                    os.path.exists("debug_chart.png")
                                    and os.path.getsize("debug_chart.png") > 100
                                ):
                                    logger.info("debug_chart.png created successfully.")
                                else:
                                    logger.warning(
                                        "debug_chart.png creation failed or file is too small."
                                    )

                            except Exception as e:
                                logger.error(f"Error processing image: {e}")

        # Once the loop finishes, we have the full response in final_text
    return final_text  # Only return the text


def build_conversation_text(conversation_slice):
    """
    Convert conversation_slice into a text block.
    """
    convo_lines = []
    for turn in conversation_slice:
        role = turn["role"].capitalize()  # "User" or "Assistant"
        content = turn["content"]
        convo_lines.append(f"{role}: {content}")
    return "\n".join(convo_lines)


def remove_markdown_code_fences(text: str) -> str:
    """
    Removes triple backtick code fences.
    """
    pattern = r"```(?:[a-zA-Z0-9]+)?\s*(.*?)\s*```"  # DOTALL will match across lines
    cleaned = re.sub(pattern, r"\1", text, flags=re.DOTALL)
    return cleaned.strip()


def call_gemini(conversation_slice, context_data: Dict[str, Any] = None):
    """
    Called from main.py.

    Args:
        conversation_slice: List of conversation turns
        context_data: Optional context data for smarter interventions
    """
    system_prompt = create_context()
    conversation_text = build_conversation_text(conversation_slice)

    # Add context data to the conversation if provided
    if context_data:
        # Format context as a structured block
        context_str = "\nContext Information:\n"
        for key, value in context_data.items():
            if isinstance(value, (dict, list)):
                # Handle nested structures for better readability
                context_str += f"{key}:\n"
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        context_str += f"  - {sub_key}: {sub_value}\n"
                else:  # list
                    for item in value:
                        context_str += f"  - {item}\n"
            else:
                context_str += f"{key}: {value}\n"
        conversation_text += context_str

    final_text = asyncio.run(run_gemini_conversation(system_prompt, conversation_text))

    # --- Parse the text response ---
    json_pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(json_pattern, final_text, re.DOTALL)
    if matches:
        try:
            response_data = json.loads(matches[-1].strip())
            if isinstance(response_data, dict):
                pass  # good to go
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            response_data = {}
    else:
        response_data = {}

    # Ensure quick_replies are in correct format
    if "quick_replies" in response_data:
        for qr in response_data["quick_replies"]:
            if not isinstance(qr, dict) or "title" not in qr:
                logger.error(f"Invalid quick reply format: {qr}")
                response_data = {"text": "Error: Invalid quick reply format"}
                return response_data

    return response_data


def process_payload_response(
    payload: str, patient_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Process a payload from a button or quick reply to generate a follow-up response.

    Args:
        payload: The payload string from the button/quick reply
        patient_data: Optional patient data for context

    Returns:
        RCS message response object
    """
    # Get patient data if not provided
    if patient_data is None:
        patient_data = get_patient_data("all")

    # Create a special conversation for payload processing
    conversation = [
        {
            "role": "user",
            "content": f"SYSTEM: User clicked a button with payload {payload}. Generate an appropriate response.",
        }
    ]

    # Add contextual data
    context_data = {
        "payload": payload,
        "patient_data_summary": json.dumps(
            {
                "diabetic": True,
                "has_hypertension": True,
                "current_hba1c": (
                    patient_data.get("labResults", [])[0].get("value")
                    if "labResults" in patient_data
                    else None
                ),
                "medications": [
                    med["name"] for med in patient_data.get("medications", [])
                ],
            }
        ),
    }

    # Process with the LLM
    response = call_gemini(conversation, context_data)

    return response


if __name__ == "__main__":
    ca = call_gemini(
        [{"role": "user", "content": "Show my cholesterol levels as graph"}]
    )
    print(ca)

    # Test payload processing
    sample_response = process_payload_response("EXPLAIN_GLUCOSE_ALERT")
    print("\nSample payload response:")
    print(json.dumps(sample_response, indent=2))
