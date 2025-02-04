
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import sharp from 'sharp';
import ChartComponent from './VictoryChart.js';

const chartData = {
  "type": "bar",
  "config": {
    "data": [{"x": "HDL", "y": 55}],
    "title": "HDL Cholesterol",
    "xlabel": "Test",
    "ylabel": "Value (mg/dL)",
    "referenceLines": {
      "HDL": {"value": 40, "label": "Lower Limit"},
      "HDL_2": {"value": 60, "label": "Upper Limit"}
    }
  }
};

// Create the React element
const element = React.createElement(ChartComponent, {graphData: chartData});

// Render to SVG string
const svg = ReactDOMServer.renderToString(element);

// Ensure SVG has proper XML declaration and namespace
const fullSvg = `<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <rect width="800" height="600" fill="white"/>
  ${svg}
</svg>`;

// Debug output
console.log('Generated SVG:', fullSvg);

// Convert SVG to PNG using sharp
sharp(Buffer.from(fullSvg))
  .resize(800, 600)
  .png()
  .toFile('/tmp/tmpsxxe2_1i/chart.png')
  .then(info => console.log('Chart saved successfully:', info))
  .catch(err => console.error('Error converting SVG to PNG:', err));
