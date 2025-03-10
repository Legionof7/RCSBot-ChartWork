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
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def create_context() -> str:
    return """
You are SlothMD, a consumer-facing medical chatbot designed to provide helpful, accurate, detailed health information using various tools.

## Core Rules/Guidelines

1. If the user is just asking for general health advice, reply them with a clear, detailed answer directly using the send_message_reply function. 

2. If the user is asking about their health data, lab results, etc. use the tool fetch_patient_data to fetch their appropriate health data from the FHIR server.

4. If the user is asking for visualizing data, Generate a chart using generate_chart tool. .

5. And finally, Always send your final response using the tool send_message_reply. This will deliver your message directly to the user via text message. No additional response is needed after sending the message.

Do not use more than one tool(fetch_patient_data, generate_chart) in a single code block. Use tools one by one. And, remember the way to use a tool is: print(default_api.tool_name(parameters)).

"""


# **You should send the message directly addressing the user query. Avoid small talk. When user asks question related to his data, your response should always be based on the data.**
# **Only use one function/tool(fetch_patient_data, generate_chart, send_message_reply) at a time. *Wait* for the response before using/calling another one.**

# Perform each task stap by step. No need to think out loud. Just perform actions. *Don't use code execution at all.*

rcs_messaging_instructions = """
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
    If you provide "cards", do not provide a top-level "mediaUrl". However, we are **extending** the structure to include an optional "graph" object. This is custom logic and not standard RCS, but required for our system.

4. **Charts and GRAPH_DATA**  
   - When including a chart(if a chart/graph url is provided above), store its type ("line", "bar", or "scatter") in graph.type.  
   - Provide all relevant data points in graph.data.  
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
   - If you want **structured data** with buttons, subtitles, or visuals, use cards.  
   - **Do not** mix text, mediaUrl, and cards at the top-level. If you have multiple data blocks, you can use multiple cards inside the "cards" array.

9. **Error Handling and Additional Guidelines**  
   - If no data is found or if an error occurs, provide an explanatory message in "text" or within a card’s "subtitle".  
   - You can optionally include a fallback object if advanced RCS features are not supported by the user’s device. However, this is optional.


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

**You should send the message directly addressing the user query. Avoid small talk. When user asks question related to his data, your response should always be based on the data.**
"""

fetch_patient_data_declaration = {
    "name": "fetch_patient_data",
    "description":
    "Retrieves appropriate patient's health data from FHIR server based on the provided query.",
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
                ("data necessary to draw chart/graph to address user's query"),
            },
            "user_query": {
                "type": "string",
                "description": ("user query"),
            }
        },
        "required": ["data", "user_query"]
    }
}

send_message_reply_declaration = {
    "name": "send_message_reply",
    "description": "Sends a text message to the user.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_query": {
                "type":
                "string",
                "description":
                "The user query to which the response is being sent."
            },
            "health_data": {
                "type":
                "string",
                "description":
                "All the appropriate raw health data *relevant* to the user query."
            },
            "message": {
                "type": "string",
                "description": "reply message to be sent to the user"
            },
            "chartURL": {
                "type":
                "string",
                "description":
                "URL of the chart generated by genertate_graph tool if any. if no graph generated set it to <no-chart-generated>."
            }
        },
        "required": ["user_query", "health_data", "message", "chartURL"]
    }
}


def extract_javascript_code(text):
    match = re.search(r"```javascript\n(.*?)\n```", text, re.DOTALL)
    return match.group(1) if match else None


async def handle_tool_call(session, tool_call):
    """Handle function calls (tool calls) from the model."""
    for fc in tool_call.function_calls:
        if fc.name == "fetch_patient_data":
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
            return ""

        elif fc.name == "generate_chart":
            # print("********************")
            # print("****************************************")
            # print("********************")

            data = fc.args.get("data")
            user_query = fc.args.get("user_query")

            prompt = f"""
Given this data of user's health records:
{data}

and the user query to visualize this data:
{user_query}

Write react component code to render a suitable visualization to address the user query. 

# Guidelines:
1. The component should be named `MyChart` and must NOT expect any props. 

2. The data for the chart MUST be defined *within* the `MyChart` component itself.

3. React code should be written using `React.createElement`(NOT JSX) to render the chart.(it is to be rendered in server)

4.It should be simple with proper naming, title, legends. It should be simple and easy to understand. Beautiful Design. You can use Victory Library. Do not use other external libraries."

5. If the user query requires processed data (e.g., aggregations, transformations, filtering), you can perform these computations inside the `MyChart` component body and use the calculated values for visualization.

**Example of ACCEPTABLE React code:**
```javascript
const MyChart = () => {{
    const data = [
        {{ x: 'A', y: 10 }},
        {{ x: 'B', y: 20 }},
        {{ x: 'C', y: 30 }}
    ];
    return React.createElement(
        VictoryChart,
        {{ theme: VictoryTheme.material, domainPadding: 20, width: 1000, height: 800 }},
        React.createElement(VictoryBar, {{
            data: data,
            style: {{ data: {{ fill: '#4CAF50' }} }},
            labels: ({{ datum }}) => datum.y
        }})
    );
}};
```
"""

            client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt,
            )

            react_code = extract_javascript_code(response.text)
            # print(react_code)

            if not react_code:
                raise ValueError("react_code cannot be empty")
            try:
                print("==============================================")
                graph_url = await generate_graph(react_code)
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

            return ""

        elif fc.name == "send_message_reply":
            user_query = fc.args.get("user_query")
            health_data = fc.args.get("health_data")
            message = fc.args.get("message")
            chartURL = fc.args.get("chartURL")

            client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

            print("chartURLLLLLLLLLL", chartURL)

            prompt = f"""
You are SlothMD, an AI-powered medical chatbot designed to provide helpful, accurate health information to consumers in a friendly and conversational manner. Your responses will be formatted as rich RCS messages for seamless integration with messaging platforms.

Here is the user's query:
<user_query>
{user_query}
</user_query>

Here is the relevant health data fetched from the FHIR server:
<health_data>
{health_data}
</health_data>

Here is the chart URL if the user request involved visualization:
<chart_url>
{chartURL}
</chart_URL>

Here is the initial response generated by the health assistant:
<initial_response>
{message}
</initial_response>

Your task is to analyze the user's query, the provided health data, and the initial response, then format a final response as an RCS message. Follow these steps:
1. Review the user's query, health data, and initial response.
2. Ensure the information is accurate, helpful, and relevant to the user's concern.
3. Format the response according to the RCS Messaging guidelines provided below.
4. Create appropriate cards and quick replies that enhance the user experience without overwhelming them.
5. Maintain a friendly and conversational tone throughout the message and provide a detailed clear explanation.

RCS Messaging Guidelines:
<rcs_messaging_instructions>
{rcs_messaging_instructions}
</rcs_messaging_instructions>.

Remember:
- Focus solely on addressing the user's query.
- Create only the necessary cards and quick replies.
- Keep the message concise and avoid overwhelming the user with excessive information.
- Do not include any performative or meta-commentary about the task itself.
"""

            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt,
            )

            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(
                    name=fc.name, id=fc.id, response={"info": "message sent"})
            ])
            await session.send(input=tool_response)

            return response.text

        else:
            tool_response = LiveClientToolResponse(function_responses=[
                FunctionResponse(name=fc.name,
                                 id=fc.id,
                                 response={"error": "Unknown function call"})
            ])
            await session.send(input=tool_response)
            return ""


async def run_gemini_conversation(system_prompt: str,
                                  conversation_text: str) -> str:
    client = genai.Client(
        api_key=os.getenv('GEMINI_API_KEY'),
        http_options={'api_version': 'v1alpha'}  # Live (experimental)
    )

    config = {
        'automatic_function_calling': {
            'disable': True
        },
        "tools": [{
            "function_declarations": [
                fetch_patient_data_declaration, generate_chart_declaration,
                send_message_reply_declaration
            ]
        }],
        "generation_config": {
            "response_modalities": ["TEXT"]
        },
    }

    # https://ai.google.dev/gemini-api/docs/function-calling

    #         "tool_config": {
    #   "function_calling_config": {
    #     "mode": "ANY",
    #     "allowed_function_names": ["find_theaters", "get_showtimes"]
    #   },

    # ANY: The model is constrained to always predict a function call. If allowed_function_names is not provided, the model picks from all of the available function declarations. If allowed_function_names is provided, the model picks from the set of allowed functions.

    # {'code_execution': {}},

    # config2 = types.LiveConnectConfig(
    #     response_modalities=["TEXT"],
    #     tools=[],)

    final_text = ""
    final_message = ""

    async with client.aio.live.connect(model="gemini-2.0-flash-exp",
                                       config=config) as session:

        await session.send(
            input=f"{system_prompt}\n\n{conversation_text}",
            end_of_turn=True,
        )

        async for response in session.receive():
            # print("--------------------------------------------")
            if response.text:
                print(response.text)
                final_text += response.text

            if response.tool_call:
                function_name = [
                    fc.name for fc in response.tool_call.function_calls
                ]
                print("#######Tool Call: ", function_name)

                final_message = await handle_tool_call(session,
                                                       response.tool_call)

            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.executable_code:
                        print("\n----------------Generated Code ------")

                        logger.info(
                            f"Generated Python code$$$$$$$:\n{part.executable_code.code}"
                        )
                        print("--------\n")
                    if part.code_execution_result:
                        print("\n----------------Code execution result ------")
                        logger.info(
                            f"Code execution result$$$$$$$:\n{part.code_execution_result.output}"
                        )
                        print("----\n")

    # return final_text
    return final_message


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
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    print(conversation_slice)
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    system_prompt = create_context()
    conversation_text = build_conversation_text(conversation_slice)

    final_text = asyncio.run(
        run_gemini_conversation(system_prompt, conversation_text))

    print("#######################################################++")
    print("#######################################################++")
    print("#######################################################++")
    print("#######################################################++")
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
