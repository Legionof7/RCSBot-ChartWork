
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import sharp from 'sharp';
import ChartComponent from './VictoryChart.js';

const chartData = {"type": "bar", "config": {"data": [{"x": "HDL", "y": 55}], "title": "HDL Cholesterol", "xlabel": "Test", "ylabel": "Value (mg/dL)", "referenceLines": {"HDL": [40, 60]}}};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

// Wrap SVG in proper XML wrapper
const fullSvg = `
<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  ${svg}
</svg>
`;

// Convert SVG to PNG using sharp
sharp(Buffer.from(fullSvg))
  .resize(800, 600)
  .png()
  .toFile('/tmp/tmpsxxe2_1i/chart.png')
  .catch(err => console.error('Error converting SVG to PNG:', err));
