import requests
import base64
import os
import httpx
import random
import string


def upload_to_pinnacle(image_bytes: bytes) -> str:
    """Uploads image bytes to Pinnacle CDN"""
    PINNACLE_UPLOAD_URL = "https://api.pinnacle.com/v1/uploads"
    headers = {
        "Authorization": f"Bearer {os.getenv('PINNACLE_API_KEY')}",
        "Content-Type": "image/png"
    }

    try:
        response = requests.post(PINNACLE_UPLOAD_URL,
                                 data=image_bytes,
                                 headers=headers)
        response.raise_for_status()
        return response.json()["url"]
    except Exception as e:
        raise RuntimeError(f"Pinnacle upload failed: {str(e)}")


# def generate_graph(graph_type: str, data: dict) -> str:
async def generate_graph(react_code: str) -> str:
    """Generates chart and returns Pinnacle URL"""

    # Convert numpy arrays to lists if needed
    # if 'labels' in data and hasattr(data['labels'], 'tolist'):
    #     data['labels'] = data['labels'].tolist()

    # if 'values' in data and hasattr(data['values'], 'tolist'):
    #     data['values'] = data['values'].tolist()

    # # Handle datetime objects in x-values
    # if 'x' in data and isinstance(data['x'], (pd.Timestamp, datetime)):
    #     data['x'] = data['x'].isoformat()
    # CHART_SERVICE_URL = "http://0.0.0.0:3002/render-chart"
    CHART_SERVICE_URL = "https://551b2d48-af41-400b-84b7-85ccef0d6d00-00-3s50u072mkwoa.kirk.replit.dev:3002/render-react-chart"

    # 1. Generate chart image
    try:
        # print(f"[graph_utils] Requesting chart: {graph_type}")
        # response = requests.post(
        #     CHART_SERVICE_URL,
        #     json={"type": graph_type, "data": data},
        #     timeout=15  # Seconds
        # )

        print("*******************Generating graph(graph_utils)...")

        # Make an async HTTP POST request to the chart service

        # Optionally process the response if needed
        # response_data = await response.json()

        # response = requests.post(
        #     CHART_SERVICE_URL,
        #     json={"reactCode": react_code},
        #     timeout=30  # Seconds
        # )
        # response.raise_for_status()
        # chart_data = response.json()
        # Use httpx for async requests
        async with httpx.AsyncClient() as client:
            response = await client.post(CHART_SERVICE_URL,
                                         json={"reactCode": react_code},
                                         timeout=30)

        response.raise_for_status()  # Raise HTTP errors if any

        try:
            returned_string = response.text  # Extracting response as a string
            print("Response from Node.js service:", returned_string)

        except UnicodeDecodeError as ue:
            print("Unicode decoding error:", ue)
            return "www.cdn.pinnacle.com/fsdfhgfd.png"  # Or handle it as needed

        # Generate a random URL (ignoring response for now)
        random_string = ''.join(
            random.choices(string.ascii_letters + string.digits, k=10))
        url = f"https://api.pinnacle.com/chart/{random_string}.png"

        print("@", url)
        return url

    except httpx.HTTPStatusError as e:
        print("---)")
    # print(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.TimeoutException:
        print("Request timed out")
    except httpx.RequestError as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return "www.cdn.pinnacle.com/fsdfhgfd.png"  # Return None on failure

    # # 2. Save debug image
    # try:
    #     image_bytes = base64.b64decode(chart_data["image_base64"].split(",")[-1])
    #     with open("debug_chart.png", "wb") as f:
    #         f.write(image_bytes)
    # except Exception as e:
    #     print(f"Warning: Failed to save debug image - {str(e)}")

    # # 3. Upload to Pinnacle CDN
    # try:
    #     pinnacle_url = upload_to_pinnacle(image_bytes)
    #     return pinnacle_url
    # except Exception as e:
    #     print(f"Error uploading to Pinnacle: {str(e)}")
    #     return "https://pinnacle.com/fallback-chart.png"
