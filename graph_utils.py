import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def generate_graph(graph_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate graph configuration for Victory"""
    logger.info(f"Generating {graph_type} graph config with data type: {type(data)}")

    if isinstance(data, str):
        if "GRAPH_DATA:" in data and "END_GRAPH_DATA" in data:
            try:
                graph_json = data.split('GRAPH_DATA:', 1)[1].split('END_GRAPH_DATA')[0].strip()
                parsed_data = json.loads(graph_json)
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse graph JSON data: {e}")
                logger.error(f"Attempted to parse: {graph_json}")
                raise

    if data is None:
        logging.error("Data is None")
        raise ValueError("Data cannot be None")

    if not isinstance(data, dict):
        logging.error(f"Invalid data type: {type(data)}. Expected dict.")
        raise ValueError(f"Data must be a dictionary, got {type(data)}")

    # Format data for Victory charts
    chart_data = {
        "type": graph_type,
        "config": {
            "data": [],
            "title": data.get("title", "Graph"),
            "xlabel": data.get("xlabel", "X Axis"),
            "ylabel": data.get("ylabel", "Y Axis")
        }
    }

    if "config" in data and "data" in data["config"]:
        return data  # Already in correct format
    elif graph_type == "line" or graph_type == "scatter":
        chart_data["config"]["data"] = [
            {"x": x, "y": y} for x, y in zip(data["x"], data["y"])
        ]
    elif graph_type == "bar":
        if "data" in data:
            chart_data["config"]["data"] = data["data"]
        else:
            chart_data["config"]["data"] = [
                {"x": label, "y": value} for label, value in zip(data["labels"], data["values"])
            ]
        if "referenceLines" in data:
            chart_data["config"]["referenceLines"] = data["referenceLines"]

    return chart_data

def plot_patient_metrics(metric_name: str, values: List[float], dates: List[str]) -> Dict[str, Any]:
    """Generate specific health metric graphs"""
    data = {
        "x": dates,
        "y": values,
        "title": f"{metric_name} Over Time",
        "xlabel": "Date",
        "ylabel": metric_name
    }
    return generate_graph("line", data)