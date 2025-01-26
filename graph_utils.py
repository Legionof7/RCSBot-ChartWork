import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
import logging
import traceback
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def generate_graph(graph_type: str, data: Dict[str, Any]) -> str:
    """Generate a graph based on type and data, return base64 image"""
    logger.info(f"Generating {graph_type} graph with data type: {type(data)}")
    logger.debug(f"Full data content: {data}")
    
    if data is None:
        logging.error("Data is None")
        raise ValueError("Data cannot be None")
        
    if not isinstance(data, dict):
        logging.error(f"Invalid data type: {type(data)}. Expected dict. Data: {str(data)}")
        raise ValueError(f"Data must be a dictionary, got {type(data)}")
        
    required_fields = {
        "line": ["x", "y"],
        "bar": ["labels", "values"],
        "scatter": ["x", "y"]
    }
    
    if graph_type not in required_fields:
        logging.error(f"Invalid graph type: {graph_type}")
        raise ValueError(f"Invalid graph type. Must be one of: {list(required_fields.keys())}")
        
    missing_fields = [field for field in required_fields[graph_type] if field not in data]
    if missing_fields:
        logging.error(f"Missing required fields: {missing_fields}")
        raise ValueError(f"Missing required fields for {graph_type} graph: {missing_fields}")
    
    plt.figure(figsize=(10, 6))
    
    if graph_type == "line":
        plt.plot(data["x"], data["y"])
        plt.title(data.get("title", "Line Graph"))
        
    elif graph_type == "bar":
        plt.bar(data["labels"], data["values"])
        plt.title(data.get("title", "Bar Graph"))
        
        # Add reference lines if provided
        if "referenceLines" in data:
            for label, ref_value in data["referenceLines"].items():
                if label in data["labels"]:
                    idx = data["labels"].index(label)
                    plt.hlines(y=ref_value, xmin=idx-0.4, xmax=idx+0.4, 
                             colors='red', linestyles='dashed', label=f'{label} Target')
        
    elif graph_type == "scatter":
        plt.scatter(data["x"], data["y"])
        plt.title(data.get("title", "Scatter Plot"))
        
    plt.xlabel(data.get("xlabel", "X Axis"))
    plt.ylabel(data.get("ylabel", "Y Axis"))
    plt.grid(True)
    
    try:
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        
        # Convert to base64
        buf.seek(0)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        logging.info("Successfully generated graph image")
        return img_b64
    except Exception as e:
        plt.close()  # Ensure figure is closed even on error
        logger.error(f"Failed to generate graph image: {str(e)}")
        logger.error(f"Graph generation traceback: {traceback.format_exc()}")
        logger.error(f"Graph data that caused error: {data}")
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
