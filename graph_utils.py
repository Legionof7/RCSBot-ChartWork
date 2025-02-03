import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def generate_graph(graph_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate graph configuration for Victory"""
    logger.info(f"Generating {graph_type} graph config with data type: {type(data)}")

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

    if graph_type == "line" or graph_type == "scatter":
        chart_data["config"]["data"] = [
            {"x": x, "y": y} for x, y in zip(data["x"], data["y"])
        ]
    elif graph_type == "bar":
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