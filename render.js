
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import sharp from 'sharp';
import ChartComponent from './VictoryChart.js';

const canvas = document.createElement('canvas');
canvas.width = 800;
canvas.height = 600;

const chartData = {
  "type": "bar",
  "config": {
    "data": [{"x": "HDL", "y": 55}],
    "title": "HDL Cholesterol",
    "xlabel": "Test",
    "ylabel": "Value (mg/dL)",
    "referenceLines": {
      "HDL": {
        "value": 40,
        "label": "Normal Range (Low)"
      }
    }
  }
};

console.log('Rendering chart with data:', JSON.stringify(chartData, null, 2));

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

// Add SVG wrapper with proper dimensions
const wrappedSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <rect width="800" height="600" fill="white"/>
  ${svg}
</svg>
`;

fs.writeFileSync('chart.svg', wrappedSvg);

// Convert SVG to PNG
sharp(Buffer.from(wrappedSvg))
  .resize(800, 600)
  .png()
  .toFile('/tmp/tmpsxxe2_1i/chart.png')
  .then(() => console.log('Chart generated successfully'))
  .catch(err => console.error('Error generating chart:', err));
