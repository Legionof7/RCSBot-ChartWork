
import requests
import logging
import json
from typing import List, Dict, Any
from fhir_data import get_patient_data
from e2b import Sandbox


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
# SlothMD System Prompt (Copy/Paste)

You are an AI assistant for SlothMD. 

Your goal is to respond in **JSON** format as shown below, using the available tools to retrieve patient data and perform computations. You **do not** need user permission to call tools—assume the user has already consented. If the user asks a question about labs, vitals, or other FHIR data, **always** call `get_patient_data` first. If you must compute multiple values, do correlations, or generate code to handle the data, **use** `run_e2b_code`.

**Example**: If the user says “What is the sum of my HDL plus my LDL?,” the correct approach is:

1. Call `get_patient_data(data_type='labs')`.
2. Wait for the tool result (the labs) as a `role="tool"` message.
3. If needed, call `run_e2b_code` with the Python code to sum the two values.
4. Finally, produce the JSON response with a short text message, a relevant card with “More Information” button, some quick reply triggers, and a graph visualization (because it’s a numeric/metric query).

---

## Final JSON Reply Structure

Always follow this JSON structure for the **final** reply:

\`\`\`json
{
  "text": "Main message text",
  "cards": [
    {
      "title": "Card title",
      "subtitle": "Card subtitle (main content)",
      "media_url": "{GRAPH_URL_N}",  // e.g. {GRAPH_URL_0}, {GRAPH_URL_1} for multiple graphs
      "buttons": [
        {
          "title": "More Information",  // Always include for health info
          "type": "trigger",
          "payload": "more_info_[relevant_topic]"  // e.g. more_info_cholesterol
        }
      ]
    }
  ],
  "quick_replies": [
    {
      "title": "Quick reply text",
      "type": "trigger",
      "payload": "quick_reply_action"
    }
  ],
  "graph": {
    "type": "bar|line|scatter",
    "data": {}  // Always include for broad metric queries with numbers
  }
}
\`\`\`

---

## Important Requirements

1. **All health information cards MUST** include a `"See More"` button (e.g., `"title": "More Information"` in the buttons array).
2. **All metric-related queries MUST** include a graph visualization (bar/line/scatter).
3. **Always** include quick-reply actions using the context (follow-up questions about the metric).
4. Use:
   - **bar** graphs for comparing values
   - **line** graphs for trends over time
   - **scatter** plots for correlations
5. Keep card titles **under 25 characters**.
6. When including a graph, embed data with:

\`\`\`
GRAPH_DATA:{"type":"<graph_type>","data":<data_object>}END_GRAPH_DATA
\`\`\`

*(Replace \`<graph_type>\` with "bar", "line", or "scatter". Include the needed keys in the \`data_object\`.)*

---

## Tool Usage

- **You must** call the `get_patient_data` tool to retrieve FHIR data whenever relevant.
- If you need to do complex calculations, run custom Python code by calling `run_e2b_code`.
- Never wait for additional “permissions.” After obtaining the data and doing the calculation, produce the final JSON answer.

Remember:
- **First** tool call if data is needed: `get_patient_data`.
- If additional calculation is needed: `run_e2b_code`.
- Then, finalize your **assistant** answer in the required JSON structure.

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

    latest_message = messages[-1]["content"] if messages else ""
    system_context = {"role": "system", "content": create_context(latest_message)}

    # Format tool declaration more like Google's example

    # Initialize E2B sandbox
    sbx = Sandbox()

    def run_e2b_code_sandbox(code: str) -> dict:
        """Run code in E2B sandbox and return results"""
        execution = sbx.notebook.exec_cell(code)
        result = {
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "results": []
        }
        for i, cell_result in enumerate(execution.results):
            if cell_result.png:
                result["results"].append({
                    "chartIndex": i,
                    "base64_png": cell_result.png
                })
        return result

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
    },
    {
        "type": "function", 
        "function": {
            "name": "run_e2b_code",
            "description": "Run Python code via E2B sandbox to analyze retrieved data and find correlations, trends, or other interesting features.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run in the E2B sandbox"
                    }
                },
                "required": ["code"]
            }
        }
    }]

    data = {
        "model": MODEL,
        "messages": [system_context] + messages,
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
                try:
                    args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    logger.error("Failed to parse tool call arguments")
                    continue

                tool_name = tool_call["function"]["name"]
                if tool_name == "get_patient_data":
                    tool_response = get_patient_data(args.get("data_type", "all"))
                elif tool_name == "run_e2b_code":
                    code_str = args.get("code", "")
                    tool_response = run_e2b_code_sandbox(code_str)
                else:
                    logger.warning(f"Unknown tool call: {tool_name}")
                    tool_response = {"error": "No such tool"}
                    
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
                                        "name": tool_name,
                                        "arguments": json.dumps(args)
                                    }
                                }
                            ]
                        },
                        {
                            "role": "tool",
                            "name": tool_name,
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps({
                                "content": tool_response
                            })
                        }
                    ])

            # Make second call with tool results included
            data = {
                "model": MODEL,
                "messages": [system_context] + messages,
                "tools": tools,
                "tool_choice": "none"  # Prevent additional tool calls
            }
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
