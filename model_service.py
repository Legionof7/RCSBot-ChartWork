(?:python|py|tool_code|.*)?\s*(.*?)\s*```'
    blocks = re.findall(code_fence_pattern, text, flags=re.DOTALL)
    return blocks

def parse_tool_calls(assistant_message: dict) -> list:
    return assistant_message.get("tool_calls", [])

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

{graph_formats}
"""
    return system_prompt.strip()

def call_openrouter(messages: List[Dict[str, str]], fhir_data: dict = None) -> dict:
    sbx = Sandbox()

    def run_e2b_code_sandbox(code: str) -> dict:
        execution = sbx.run_code(code)
        result = {
            "logs": str(execution.logs) if execution.logs else "",
            "error": None,
            "results": []
        }
        if execution.error:
            result["error"] = {
                "name": str(execution.error.name),
                "value": str(execution.error.value),
                "traceback": str(execution.error.traceback)
            }

        for i, cell_result in enumerate(execution.results):
            if cell_result.png:
                result["results"].append({
                    "chartIndex": i,
                    "base64_png": cell_result.png
                })
        return result

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://slothmd.repl.co",
        "X-Title": "SlothMD",
        "Content-Type": "application/json"
    }

    latest_message = messages[-1]["content"] if messages else ""
    system_context = {"role": "system", "content": create_context(latest_message)}

    tools = [
        {
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
        }
    ]

    max_iterations = 10
    iteration_count = 0

    while True:
        iteration_count += 1
        if iteration_count > max_iterations:
            logger.warning("Reached max iteration limit (%d). Stopping loop.", max_iterations)
            return {"text": "Sorry, I'm stuck in a loop. Stopping now."}

        data = {
            "model": MODEL,
            "messages": [system_context] + messages,
            "tools": tools,
            "tool_choice": "auto"
        }

        logger.info("===== Iteration %d =====", iteration_count)
        logger.info("Sending to OpenRouter:\n%s", json.dumps(data, indent=2))

        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                               headers=headers, json=data)
            resp.raise_for_status()
            response_json = resp.json()

            logger.info("OpenRouter response:\n%s", json.dumps(response_json, indent=2))

            assistant_message = response_json["choices"][0]["message"]
            content = assistant_message.get("content", "")

            # Check for direct content first
            if content and content.strip():
                logger.info("Got final user-facing content, parsing and returning")
                try:
                    final_json = json.loads(content)
                    return final_json
                except json.JSONDecodeError:
                    logger.warning("Content was not JSON, returning as text")
                    return {"text": content}

            # If no direct content, check for tool calls or code blocks
            tool_calls = parse_tool_calls(assistant_message)
            code_blocks = parse_code_blocks(content)

            handled_something = False

            if tool_calls:
                handled_something = True
                for tc in tool_calls:
                    logger.info("Handling tool call: %s", tc)
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool call args: %s", tc["function"]["arguments"])
                        continue

                    tool_name = tc["function"]["name"]
                    tool_id = tc.get("id", "(no_id)")

                    if tool_name == "get_patient_data":
                        data_type = args.get("data_type", "all")
                        logger.info("Running get_patient_data(%s)", data_type)
                        result_data = get_patient_data(data_type)
                    elif tool_name == "run_e2b_code":
                        code_str = args.get("code", "")
                        logger.info("Running run_e2b_code_sandbox:\n%s", code_str)
                        result_data = run_e2b_code_sandbox(code_str)
                    else:
                        logger.warning("Unknown tool: %s", tool_name)
                        result_data = {"error": f"No such tool '{tool_name}'"}

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tc]
                    })
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "tool_call_id": tool_id,
                        "content": json.dumps(result_data)
                    })

            if code_blocks:
                handled_something = True
                for code in code_blocks:
                    if code.strip():
                        logger.info("Running code block:\n%s", code)
                        result = run_e2b_code_sandbox(code)
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "function": {"name": "run_e2b_code", "arguments": json.dumps({"code": code})},
                                "id": str(uuid.uuid4())
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "name": "run_e2b_code",
                            "tool_call_id": str(uuid.uuid4()),
                            "content": json.dumps(result)
                        })

            if handled_something:
                logger.info("Handled tool calls or code blocks, continuing loop")
                continue

            logger.info("No content and no tool calls/code blocks, returning empty")
            return {}

        except Exception as e:
            logger.error("OpenRouter/OpenRouter API error: %s", e)
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
            json_end = content.find('