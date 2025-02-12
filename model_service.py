import logging
import json
from typing import List, Dict, Any
from fhir_data import get_patient_data
from google import genai
from google.genai import types
from google.genai.types import FunctionDeclaration, GenerateContentConfig, Part, Tool

import os 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s: %(message).200s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def create_context() -> str:
    return """# SlothMD System Prompt

You are a bot designed to answer questions about a user's health. Use the get_patient_data tool to get their health data.

Respond in JSON format with cards and graphs for an RCS response. Follow these rules:
1. For health data questions, use get_patient_data
2. For calculations, generate executable Python code
3. Include GRAPH_DATA in JSON response
4. Health cards must have "See More" button

Final JSON structure:
{
  "text": "Main message and data insights",
  "cards": [{
    "title": "...", 
    "subtitle": "...",
    "media_url": "{{GRAPH_URL}}",
    "buttons": [...]
  }],
  "quick_replies": [...],
  "graph": {"type": "...", "data": {}}
}"""

def process_user_input(user_input: dict) -> dict:
    """Main entry point for console-based processing"""
    messages = [{"role": "user", "content": user_input.get("text", "")}]
    return call_gemini(messages)

def get_patient_datas(data_type: str = 'all') -> dict:
    """Get patient data from the FHIR server"""

    a = get_patient_data(data_type)
    return a

def call_gemini(messages: List[Dict[str, str]]) -> dict:
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        formatted_messages = []
        context_msg = {"role": "user", "content": create_context()}
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]

        # Interleave messages to maintain conversation flow
        # fhir_data = get_patient_data()
        formatted_messages = []
        formatted_messages.append(types.Content(
            role="user",
            parts=[types.Part(text=context_msg["content"])]
        ))

        for user_msg, asst_msg in zip(user_messages, assistant_messages + [None]):
            if user_msg:
                formatted_messages.append(types.Content(
                    role="user",
                    parts=[types.Part(text=user_msg["content"])]
                ))
            if asst_msg:
                formatted_messages.append(types.Content(
                    role="model",
                    parts=[types.Part(text=asst_msg["content"])]
                ))
        # print(formatted_messages)
        # "data_type": {
        #     "type": "string",
        #     "description": "Type of data to retrieve (all, conditions, medications, vitals, labs)",
        #     "enum": ["all", "conditions", "medications", "vitals", "labs"]
        # }
        get_product_info = FunctionDeclaration(
            name="get_patient_data",
            description="Retrieves patient data based on the provided query.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "data": {"type": "STRING", "description": "Retrieves patient data."}
                },
            },
        )

        patient_tool = Tool(
            function_declarations=[
                get_product_info
            ],
        )
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=formatted_messages,
            config=types.GenerateContentConfig(
                tools=[patient_tool]
            )
        )
        # Process code execution results
        graph_images = []
        code_output = ""
        text_response = ""
        for part in response.candidates[0].content.parts:
            if part.function_call:
                print("Function call detected:", part.function_call)
                function_name = part.function_call.name
                arguments = part.function_call.args

                if function_name == "get_patient_data":
                    result = get_patient_data(data_type='all') 
                    patient_details = json.dumps(result)
                    format = '''Final JSON structure:
                    {
                      "text": "Main message and main insights",
                      "cards": [{
                        "title": "...", 
                        "subtitle": "...",
                        "media_url": "{{GRAPH_URL}}",
                        "buttons": [...]
                      }],
                      "quick_replies": [...],
                      "graph": {"type": "...", "data": {}}
                    }'''
                    follow_up_prompt = f'''Based on this data, provide a {arguments}: {patient_details} Here is the final format :{format}. 
                    
                    '''
                    response = client.models.generate_content(            model='gemini-2.0-flash',
contents=follow_up_prompt)
                    print(response)
                    text_response = response.candidates[0].content.parts[0].text
            if part.code_execution_result:
                code_output += f"\n{part.code_execution_result.output}"
            if part.inline_data:
                graph_images.append(part.inline_data.data)
        text_response = "\n".join(part.text for part in response.candidates[0].content.parts if part.text)
        # Combine text response with code output
        full_response = text_response + "\n" + code_output

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
        # First try to find JSON block
        if "```json" in text:
            json_parts = text.split("```json")
            for part in json_parts[1:]:  # Skip the first part before ```json
                try:
                    json_str = part.split("```")[0].strip()
                    response_data = json.loads(json_str)
                    # If we successfully parsed JSON, check for graph data
                    if "GRAPH_DATA:" in text:
                        graph_str = text.split("GRAPH_DATA:")[1].split("END_GRAPH_DATA")[0]
                        response_data["graph"] = json.loads(graph_str)
                    return response_data
                except:
                    continue

        # If no valid JSON found, create a basic response
        return {
            "text": text.replace("```json", "").replace("```", "").strip(),
            "cards": [],
            "quick_replies": [{
                "title": "Try Again", 
                "type": "trigger",
                "payload": "retry_analysis"
            }]
        }

    except Exception as e:
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
if __name__ == "__main__":
    """Console interface for testing"""
    print("Health Assistant Console - Type 'exit' to quit")
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() == 'exit':
                break

            # Process as JSON input
            input_json = {"text": user_input}
            response = process_user_input(input_json)

            # Print raw JSON output
            print("\nAssistant JSON:")
            print(json.dumps(response, indent=2))

        except Exception as e:
            print(f"Error: {str(e)}")