import requests
import base64
import os

def generate_graph(graph_type: str, data: dict):
    """
    Calls the external Node.js chart service (Victory + Puppeteer) to generate a PNG chart.
    Saves the chart locally as 'debug_chart.png'.

    :param graph_type:  e.g. "line", "bar", or "scatter"
    :param data: a dict that either:
        - has 'labels' and 'values' arrays, OR
        - is an array of { x, y } points, OR
        - includes optional 'xlabel', 'ylabel' fields for axis labels
    """
    # The URL to your Node "chart service"
    CHART_SERVICE_URL = "http://0.0.0.0:3002/render-chart"  # matches chart_service.js port

    # Prepare the payload
    payload = {
        "type": graph_type,
        "data": data
    }

    try:
        print(f"[graph_utils] Sending chart request to Node service: {payload}")
        response = requests.post(CHART_SERVICE_URL, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to contact chart service: {str(e)}")

    # The chart service returns JSON with { "image_base64": "data:image/png;base64,..." }
    json_resp = response.json()
    if "image_base64" not in json_resp:
        raise ValueError(f"Chart service did not return 'image_base64': {json_resp}")

    # Typically "image_base64" is something like "data:image/png;base64, iVBORw0KGgoAAA..."
    image_base64 = json_resp["image_base64"]

    # Strip off data URI prefix if present
    prefix = "data:image/png;base64,"
    if image_base64.startswith(prefix):
        image_base64 = image_base64[len(prefix):]

    # Decode and save as debug_chart.png
    try:
        decoded_bytes = base64.b64decode(image_base64, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 data returned by chart service: {str(e)}")

    if len(decoded_bytes) < 1000:
        raise ValueError("Generated image is too small (less than 1000 bytes). Possibly invalid PNG.")

    with open("debug_chart.png", "wb") as f:
        f.write(decoded_bytes)

    # Double-check that file got created
    if not os.path.exists("debug_chart.png") or os.path.getsize("debug_chart.png") < 1000:
        raise ValueError("debug_chart.png was created but is invalid (too small).")

    print("[graph_utils] Chart saved to debug_chart.png successfully")
