import requests
import base64
import os


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


def generate_graph(react_code: str) -> str:
    """Generates chart and returns Pinnacle URL"""

    print("Generating graph...")
    print("********************************")
    print(react_code)
    print("********************************")

    # Convert numpy arrays to lists if needed
    # if 'labels' in data and hasattr(data['labels'], 'tolist'):
    #     data['labels'] = data['labels'].tolist()

    # if 'values' in data and hasattr(data['values'], 'tolist'):
    #     data['values'] = data['values'].tolist()

    # # Handle datetime objects in x-values
    # if 'x' in data and isinstance(data['x'], (pd.Timestamp, datetime)):
    #     data['x'] = data['x'].isoformat()
    CHART_SERVICE_URL = "https://e84195c7-0bce-4bb6-8d08-d9dd7128af03-00-3nf0smkfdbxlk.pike.replit.dev:3002/render-react-chart"
    # CHART_SERVICE_URL = "http://0.0.0.0:3002/render-chart"

    # 1. Generate chart image
    try:
        # print(f"[graph_utils] Requesting chart: {graph_type}")
        response = requests.post(
            CHART_SERVICE_URL,
            json={"reactCode": react_code},
            timeout=30  # Seconds
        )
        response.raise_for_status()
        chart_data = response.json()
        return "https://www.example.com/image"

    except Exception as e:
        raise RuntimeError(f"Chart service error: {str(e)}")

    # 2. Save debug image
    print("-----------------+++++++++++++++++++++++++-----------------")
    print("-----------------+++++++++++++++++++++++++-----------------")
    print("-----------------+++++++++++++++++++++++++-----------------")
    print("-----------------+++++++++++++++++++++++++-----------------")

    print(f"[graph_utils] Saving debug image: {graph_type}")
    # try:
    #     image_bytes = base64.b64decode(
    #         chart_data["image_base64"].split(",")[-1])
    # with open("debug_chart.png", "wb") as f:
    #     print(chart_data)
    #     f.write(image_bytes)
    # except Exception as e:
    #     print(f"Warning: Failed to save debug image - {str(e)}")

    # 3. Upload to Pinnacle CDN
    # try:
    #     pinnacle_url = upload_to_pinnacle(image_bytes)
    #     return pinnacle_url
    # except Exception as e:
    #     print(f"Error uploading to Pinnacle: {str(e)}")
    #     return "https://pinnacle.com/fallback-chart.png"
