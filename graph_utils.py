
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
from typing import List, Dict, Any

def generate_graph(graph_type: str, data: Dict[str, Any]) -> str:
    """Generate a graph based on type and data, return base64 image"""
    logging.info(f"Generating {graph_type} graph with data: {data}")
    plt.figure(figsize=(10, 6))
    
    if graph_type == "line":
        plt.plot(data["x"], data["y"])
        plt.title(data.get("title", "Line Graph"))
        
    elif graph_type == "bar":
        plt.bar(data["labels"], data["values"])
        plt.title(data.get("title", "Bar Graph"))
        
    elif graph_type == "scatter":
        plt.scatter(data["x"], data["y"])
        plt.title(data.get("title", "Scatter Plot"))
        
    plt.xlabel(data.get("xlabel", "X Axis"))
    plt.ylabel(data.get("ylabel", "Y Axis"))
    plt.grid(True)
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    
    # Convert to base64
    buf.seek(0)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return img_b64

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
