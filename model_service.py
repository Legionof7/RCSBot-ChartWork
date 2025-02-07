
import requests
import logging
import json
import re
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

def parse_code_blocks(text: str) -> list:
    code_fence_pattern = r'```(?:python|py|tool_code|.*)?\s*(.*?)\s*```'
    blocks = re.findall(code_fence_pattern, text, flags=re.DOTALL)
    return blocks

def parse_tool_calls(assistant_message: dict) -> list:
    if "tool_calls" in assistant_message:
        return assistant_message["tool_calls"]
    return []

def create_context(query: str) -> str:
    graph_formats = """
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
"""

    system_prompt = f"""
# SlothMD System Prompt

You are an AI assistant for SlothMD. 

Your goal is to respond in **JSON** format as shown below, using the available tools to retrieve patient data and perform computations. 
You **do not** need user permission to call tools—assume the user has already consented. 
If the user asks a question about labs, vitals, or other FHIR data, **always** call `get_patient_data`. 
If you must compute multiple values, do correlations, or generate code to handle the data, **use** `run_e2b_code` or produce your own fenced Python code blocks to be executed.

**Example**: If the user says "What is the sum of my HDL plus my LDL?," the correct approach is:
1. Call `get_patient_data(data_type='labs')`.
2. Wait for the tool result (the labs) as a `role="tool"` message.
3. If needed, generate a Python code block or call `run_e2b_code` with the code to sum the two values.
4. Finally, produce the JSON response with a short text message, a relevant card with "More Information" button, quick replies, and a graph.

---
## Final JSON Reply Structure

\"\"\"json
{{
  "text": "Main message text",
  "cards": [
    {{
      "title": "Card title",
      "subtitle": "Card subtitle (main content)",
      "media_url": "{{GRAPH_URL_N}}",  
      "buttons": [
        {{
          "title": "More Information",
          "type": "trigger",
          "payload": "more_info_[relevant_topic]"
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
    "data": {{}}
  }}
}}
\"\"\"

---
## Important Requirements

1. Health info cards MUST include a "See More" button.
2. Metric queries MUST include a graph (bar|line|scatter).
3. Always include quick replies for user follow-up.
4. Titles under 25 chars.
5. To embed a graph, use:
\"\"\"
GRAPH_DATA:{{"type":"<graph_type>","data":<data_object>}}END_GRAPH_DATA
\"\"\"

---
## Tool Usage

- Call `get_patient_data` for FHIR data.
- Call `run_e2b_code` or produce a fenced code block for Python analysis (no extra permissions needed).
- Then finalize your JSON response.

{graph_formats}
"""
    return system_prompt.strip()

def call_openrouter(messages: List[Dict[str, str]], fhir_data: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }

    sbx = Sandbox()

    def run_e2b_code_sandbox(code: str) -> dict:
        execution = sbx.run_code(code)
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

    latest_message = messages[-1]["content"] if messages else ""
    system_context = {"role": "system", "content": create_context(latest_message)}

    tools = [{
        "type": "function",
        "function": {
            "name": "get_patient_data",
            "description": "Retrieve patient's FHIR data including name, conditions, meds, vitals, labs",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "enum": ["all","conditions","medications","vitals","labs"]
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
            "description": "Run Python code in E2B for analysis",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run"
                    }
                },
                "required": ["code"]
            }
        }
    }]

    while True:
        data = {
            "model": MODEL,
            "messages": [system_context] + messages,
            "tools": tools,
            "tool_choice": "auto"
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

            logger.info("Deepseek response:\n%s", json.dumps(response_json, indent=2))

            assistant_message = response_json["choices"][0]["message"]
            content = assistant_message.get("content", "")
            new_tool_calls = parse_tool_calls(assistant_message)
            code_blocks = parse_code_blocks(content)

            handled_something = False

            if new_tool_calls:
                handled_something = True
                for tc in new_tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool call arguments: %s", tc["function"]["arguments"])
                        continue

                    tool_name = tc["function"]["name"]
                    tool_id = tc.get("id","")

                    if tool_name == "get_patient_data":
                        data_type = args.get("data_type","all")
                        tool_result = get_patient_data(data_type)
                    elif tool_name == "run_e2b_code":
                        code_str = args.get("code","")
                        tool_result = run_e2b_code_sandbox(code_str)
                    else:
                        tool_result = {"error":f"No such tool '{tool_name}'"}

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tc]
                    })
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "tool_call_id": tool_id,
                        "content": json.dumps(tool_result)
                    })

            if code_blocks:
                handled_something = True
                for i, block in enumerate(code_blocks):
                    tool_result = run_e2b_code_sandbox(block)
                    pseudo_tool_id = f"codeblock_{i}"
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": pseudo_tool_id,
                                "type": "function",
                                "function": {
                                    "name":"run_e2b_code",
                                    "arguments": json.dumps({"code":block})
                                }
                            }
                        ]
                    })
                    messages.append({
                        "role": "tool",
                        "name": "run_e2b_code",
                        "tool_call_id": pseudo_tool_id,
                        "content": json.dumps(tool_result)
                    })

            if handled_something:
                continue
            else:
                return parse_model_response(content)

        except Exception as e:
            logger.error(f"OpenRouter/Deepseek API error: {str(e)}")
            raise

def extract_top_level_json(text: str) -> str:
    start_brace = text.find('{')
    if start_brace == -1:
        return "{}"
    brace_count = 0
    for i in range(start_brace, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_brace:i+1]
    return "{}"

def parse_model_response(content: str) -> dict:
    try:
        json_start = content.find('```json')
        if json_start != -1:
            json_end = content.find('```', json_start + 7)
            if json_end != -1:
                json_content = content[json_start + 7:json_end].strip()
            else:
                json_content = "{}"
        else:
            json_content = extract_top_level_json(content)

        response_data = json.loads(json_content)

        if 'GRAPH_DATA:' in content:
            try:
                graph_data = content.split('GRAPH_DATA:',1)[1].split('END_GRAPH_DATA')[0]
                graph_json = json.loads(graph_data)
                if isinstance(graph_json, dict) and 'type' in graph_json and 'data' in graph_json:
                    response_data['graph'] = graph_json
            except Exception as e:
                logger.warning("Failed to parse graph data: %s", e)
                response_data['graph'] = None

        return response_data

    except json.JSONDecodeError as e:
        logger.error("JSON parse error on final model content: %s", e)
        return {"text": "Sorry, I encountered an error reading the response."}
