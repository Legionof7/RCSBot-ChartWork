import logging
import json
from typing import List, Dict, Any
from fhir_data import get_patient_data
import google.generativeai as genai
from google.generativeai import types

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s: %(message).200s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

genai.configure(api_key="AIzaSyDXsEl3C4d4hi7zJue8-_mmEhcDp0twRM8")

def create_context() -> str:
    return """# SlothMD System Prompt
Respond in JSON format with cards and graphs. Follow these rules:
1. For health data questions, use get_patient_data
2. For calculations, generate executable Python code
3. Include GRAPH_DATA in JSON response
4. Health cards must have "See More" button

Final JSON structure:
{
  "text": "Main message",
  "cards": [{
    "title": "...", 
    "subtitle": "...",
    "media_url": "{{GRAPH_URL}}",
    "buttons": [...]
  }],
  "quick_replies": [...],
  "graph": {"type": "...", "data": {}}
}"""

def call_gemini(messages: List[Dict[str, str]]) -> dict:
    try:
        response = genai.generate_content(
            model='gemini-2.0-flash-exp',
            contents=[create_context()] + messages,
            generation_config=types.GenerationConfig(
                temperature=0.0
            ),
            tools=[types.Tool(
                code_execution=types.ToolCodeExecution()
            )],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingMode.ANY,
                    allowed_function_names=['get_patient_data']
                )
            )
        )

        # Process code execution results
        graph_images = []
        code_output = ""

        for part in response.candidates[0].content.parts:
            if part.code_execution_result:
                code_output += f"\n{part.code_execution_result.output}"
            if part.inline_data:
                graph_images.append(part.inline_data.data)

        # Combine text response with code output
        full_response = response.text + "\n" + code_output

        # Parse the combined response
        final_response = parse_model_response(full_response)

        # Attach first graph image if available
        if graph_images:
            final_response['graph_image'] = graph_images[0]

        return final_response

    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        return {"text": "Sorry, I encountered an error processing your request."}

def parse_model_response(text: str) -> dict:
    try:
        # Extract JSON response
        json_str = text.split("```json")[1].split("```")[0].strip()
        response_data = json.loads(json_str)

        # Extract graph data if present
        if "GRAPH_DATA:" in text:
            graph_str = text.split("GRAPH_DATA:")[1].split("END_GRAPH_DATA")[0]
            response_data["graph"] = json.loads(graph_str)

        return response_data

    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Response parsing error: {str(e)}")
        return {
            "text": "Here's the analysis:",
            "cards": [],
            "quick_replies": [{
                "title": "Try Again", 
                "type": "trigger",
                "payload": "retry_analysis"
            }]
        }
