
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
    "referenceLines": {"HDL": 60}
  }
};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

const fullSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  ${svg}
</svg>`;

sharp(Buffer.from(fullSvg))
  .resize(800, 600)
  .png()
  .toFile('/tmp/tmpsxxe2_1i/chart.png')
  .catch(err => console.error('Error converting SVG to PNG:', err));
    