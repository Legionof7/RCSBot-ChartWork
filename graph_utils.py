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
                data = json.loads(graph_json)
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

    # Extract nested config if present
    if "config" in data:
        data = data["config"]

    # Format data for Victory charts
    chart_data = {
        "type": graph_type,
        "config": {
            "data": data.get("data", []),
            "title": data.get("title", "Graph"),
            "xlabel": data.get("xlabel", "X Axis"),
            "ylabel": data.get("ylabel", "Y Axis"),
            "referenceLines": data.get("referenceLines", {})
        }
    }

    return chart_data

def plot_patient_metrics(metric_name: str, values: List[float], dates: List[str]) -> Dict[str, Any]:
    """Generate specific health metric graphs"""
    data = {
        "data": [{"x": date, "y": value} for date, value in zip(dates, values)],
        "title": f"{metric_name} Over Time",
        "xlabel": "Date",
        "ylabel": metric_name
    }
    return generate_graph("line", data)