
import json
import logging
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def generate_graph(graph_type: str, data: Dict[str, Any]) -> str:
    """Generate graph using React SSR and return image path"""
    logger.info(f"Generating {graph_type} graph config with data type: {type(data)}")
    
    if data is None:
        raise ValueError("Data cannot be None")
        
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse graph data string: {e}")
            raise

    if not isinstance(data, dict):
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

    # Create temporary file to store the chart data
    temp_dir = '/tmp/tmpsxxe2_1i'
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, 'chart.png')
    
    # Write render script
    render_script = f'''
    import React from 'react';
    import ReactDOMServer from 'react-dom/server';
    import fs from 'fs';
    import {{ createCanvas }} from 'canvas';
    import ChartComponent from './VictoryChart.jsx';

    const canvas = createCanvas(800, 600);
    const ctx = canvas.getContext('2d');
    const chartData = {json.dumps(chart_data)};

    const element = React.createElement(ChartComponent, {{graphData: chartData}});
    const svg = ReactDOMServer.renderToString(element);

    fs.writeFileSync('{temp_file}', canvas.toBuffer());
    '''
    
    with open('render.js', 'w') as f:
        f.write(render_script)
    
    try:
        import subprocess
        subprocess.run(['node', 'render.js'], check=True)
        return temp_file
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to render graph: {e}")
        raise

def plot_patient_metrics(metric_name: str, values: List[float], dates: List[str]) -> Dict[str, Any]:
    """Generate specific health metric graphs"""
    data = {
        "data": [{"x": date, "y": value} for date, value in zip(dates, values)],
        "title": f"{metric_name} Over Time",
        "xlabel": "Date",
        "ylabel": metric_name
    }
    return generate_graph("line", data)
