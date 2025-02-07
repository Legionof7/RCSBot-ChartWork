
import requests
import logging
import json
from typing import List, Dict, Any
from fhir_data import get_patient_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s: %(message).200s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_API_KEY = "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"

def create_context(query: str) -> str:
    """
    Builds a system prompt that explains how to format the JSON for an RCS message
    """
    graph_formats = '''
GRAPH_DATA:{"type": "<graph_type>", "data": <data_object>}END_GRAPH_DATA

Supported graph types and formats:

1. Bar Chart:
GRAPH_DATA:{"type": "bar", "data": {
    "labels": ["Label1", "Label2", "Label3"],
    "values": [10, 20, 30],
    "title": "Bar Chart Title",
    "xlabel": "Categories",
    "ylabel": "Values",
    "referenceLines": {"Label1": 15, "Label2": 25}
}}END_GRAPH_DATA

2. Line Chart:
GRAPH_DATA:{"type": "line", "data": {
    "x": ["2023-01", "2023-02", "2023-03"],
    "y": [10, 20, 15],
    "title": "Trend Analysis",
    "xlabel": "Time Period",
    "ylabel": "Values"
}}END_GRAPH_DATA

3. Scatter Plot:
GRAPH_DATA:{"type": "scatter", "data": {
    "x": [1, 2, 3, 4, 5],
    "y": [2, 4, 3, 5, 4],
    "title": "Correlation Plot",
    "xlabel": "X Values",
    "ylabel": "Y Values"
}}END_GRAPH_DATA
'''

    return f"""
You are an AI assistant for SlothMD. Generate JSON in this format to make your reply. Use FHIR tools to get patient data.

{{
  "text": "Main message text",
  "cards": [
    {{
      "title": "Card title",
      "subtitle": "Card subtitle (main content)",
      "media_url": "{{GRAPH_URL_N}}",  // Use {{GRAPH_URL_0}}, {{GRAPH_URL_1}} etc for multiple graphs
      "buttons": [
        {{
          "title": "More Information",  // Always include for health information
          "type": "trigger",
          "payload": "more_info_[relevant_topic]"  // Replace [relevant_topic] with actual topic
        }}
      ]
    }}
  ],
  "quick_replies": [
    {{
      "title": "Quick reply text",
      "type": "trigger",
      "payload": "quick_reply_action"
    }}
  ],
  "graph": {{
    "type": "bar|line|scatter",
    "data": {{}}  // Always include for broad metric-related queries asking about levels/numbers
  }}
}}

Important:
1. All health information cards MUST include a "See More" button
2. All metric-related queries MUST include a graph visualization
3. Always include quick reply actions using the context of the metrics. You MUST have follow-up questions
4. Use appropriate graph types:
   - bar: for comparing values
   - line: for trends over time
   - scatter: for correlation analysis
5. Titles MUST be under 25 characters in length.

When including a graph, embed data using:
{graph_formats}

Use the get_patient_data tool to retrieve FHIR information when needed.
"""

def call_openrouter(messages: List[Dict[str, str]], fhir_data: dict = None) -> dict:
    """
    Calls the Gemini model via OpenRouter with tool calling format.
    Returns a dict with the JSON we expect for RCS.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}", 
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }

    # Format messages like the example
    formatted_messages = []
    if len(messages) > 0:
        formatted_messages = [{"role": "system", "content": create_context(messages[-1]["content"])}]
        formatted_messages.extend([{
            "role": msg["role"],
            "content": msg["content"]
        } for msg in messages])
    latest_message = messages[-1]["content"] if messages else ""
    context = create_context(latest_message)

    # Format tool declaration more like Google's example
    tools = [{
        "type": "function",
        "function": {
            "name": "get_patient_data",
            "description": "Retrieve patient's FHIR data including name, patient info, medical conditions, medications, vital signs, and lab results",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "description": "Type of data to retrieve",
                        "enum": ["all", "conditions", "medications", "vitals", "labs"]
                    }
                },
                "required": ["data_type"]
            }
        }
    }]

    data = {
        "model": MODEL,
        "messages": [{"role": "system", "content": context}] + messages,
        "tools": tools,
        "tool_choice": "auto",
    }

    pretty_data = json.dumps(data, indent=2)
    logger.info(f"Sending request to Deepseek (OpenRouter):\n{pretty_data}")

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        response_json = response.json()
        
        # Get the assistant's response
        assistant_message = response_json["choices"][0]["message"]
        
        # Handle function calls similar to Google's format
        if "tool_calls" in assistant_message:
            tool_calls = assistant_message["tool_calls"]
            
            # Process each tool call
            for tool_call in tool_calls:
                if tool_call["function"]["name"] == "get_patient_data":
                    # Parse arguments with error handling
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool call arguments")
                        continue

                    # Get tool response
                    tool_response = get_patient_data(args.get("data_type", "all"))
                    
                    # Format messages like Google's example
                    messages.extend([
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call["id"],
                                    "type": "function",
                                    "function": {
                                        "name": "get_patient_data",
                                        "arguments": json.dumps(args)
                                    }
                                }
                            ]
                        },
                        {
                            "role": "tool",
                            "name": "get_patient_data",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps({
                                "content": tool_response
                            })
                        }
                    ])

            # Extend messages with tool results and make second call
            data["messages"] = formatted_messages
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                stream=False
            )
            response.raise_for_status()
            response_json = response.json()

        pretty_response = json.dumps(response_json, indent=2)
        logger.info(f"Deepseek response:\n{pretty_response}")
        
        content = response_json["choices"][0]["message"]["content"]
        return parse_model_response(content)
    except Exception as e:
        logger.error(f"OpenRouter/Deepseek API error: {str(e)}")
        raise

def parse_model_response(content: str) -> dict:
    """Parse the model's response and extract the JSON content"""
    try:
        # Extract JSON content between code fences
        json_start = content.find('```json')
        if json_start != -1:
            json_end = content.find('```', json_start + 7)
            if json_end != -1:
                json_content = content[json_start + 7:json_end].strip()
            else:
                json_content = "{}"
        else:
            # Try to find a complete JSON object
            start_brace = content.find('{')
            if start_brace != -1:
                # Find matching end brace
                brace_count = 0
                for i in range(start_brace, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_content = content[start_brace:i+1].strip()
                            break
                else:
                    json_content = "{}"
            else:
                json_content = "{}"

        # Extract graph data if present
        response_data = json.loads(json_content)
        if 'GRAPH_DATA:' in content:
            try:
                graph_data = content.split('GRAPH_DATA:', 1)[1].split('END_GRAPH_DATA')[0]
                graph_json = json.loads(graph_data)
                if isinstance(graph_json, dict) and 'type' in graph_json and 'data' in graph_json:
                    response_data['graph'] = graph_json
            except Exception as e:
                logger.error(f"Failed to parse graph data: {str(e)}")
                response_data['graph'] = None

        return response_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse model JSON response. Content: {json_content}")
        logger.error(f"JSON parse error: {str(e)}")
        return {"text": "I apologize, but I encountered an error processing your request. How else can I help you today?"}
