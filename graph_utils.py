import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
import logging
import traceback
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def generate_graph(graph_type: str, data: Dict[str, Any]) -> str:
    """Generate a graph using Victory Charts service, return base64 image"""
    logger.info(f"Generating {graph_type} graph with data type: {type(data)}")
    logger.debug(f"Full data content: {data}")

    if data is None:
        logging.error("Data is None")
        raise ValueError("Data cannot be None")

    if not isinstance(data, dict):
        logging.error(f"Invalid data type: {type(data)}. Expected dict. Data: {str(data)}")
        raise ValueError(f"Data must be a dictionary, got {type(data)}")

    # Transform data for Victory Charts format
    victory_data = []
    if graph_type == "bar":
        victory_data = [{"x": label, "y": value} for label, value in zip(data["labels"], data["values"])]
    elif graph_type in ["line", "scatter"]:
        victory_data = [{"x": x, "y": y} for x, y in zip(data["x"], data["y"])]

    try:
        response = requests.post("http://localhost:3001/render-chart", 
                               json={"type": graph_type, "data": victory_data})
        response.raise_for_status()
        return response.json()["image_base64"]
    except Exception as e:
        logger.error(f"Error generating graph: {str(e)}")
        raise ValueError(f"Failed to generate graph: {str(e)}")
    except Exception as e:
        plt.close()  # Ensure figure is closed even on error
        logger.error(f"Graph generation failed")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"Graph type: {graph_type}")
        logger.error(f"Graph data: {json.dumps(data, indent=2)}")
        logger.error(f"Matplotlib version: {matplotlib.__version__}")
        raise ValueError(f"Graph generation failed: {str(e)}")

def plot_patient_metrics(metric_name: str, values: List[float], dates: List[str]) -> str:
    """Generate specific health metric graphs"""
    data = {
        "x": dates,
        "y": values,
        "title": f"{metric_name} Over Time",
        "xlabel": "Date",
        "ylabel": metric_name
    }
    return generate_graph("line", data)