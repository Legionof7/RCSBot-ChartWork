
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
      "HDL": {
        "value": 40,
        "label": "Normal Range (Low)"
      }
    }
  }
};

console.log('Input chart data:', JSON.stringify(chartData, null, 2));

// Create the React element
const element = React.createElement(ChartComponent, { graphData: chartData });
const svg = ReactDOMServer.renderToString(element);

// Log the raw SVG
console.log('Rendered SVG:', svg);

// Add SVG wrapper with proper dimensions and white background
const wrappedSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <rect width="800" height="600" fill="white"/>
  ${svg}
</svg>`;

// Log the wrapped SVG
console.log('Wrapped SVG:', wrappedSvg);

// Test with a simple SVG first
const simpleSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <rect width="800" height="600" fill="white"/>
  <circle cx="400" cy="300" r="100" fill="blue"/>
</svg>`;

// Try simple SVG first to verify sharp is working
sharp(Buffer.from(simpleSvg))
  .resize(800, 600)
  .png()
  .toFile('/tmp/tmpsxxe2_1i/test_chart.png')
  .then(() => {
    console.log('Simple test chart generated successfully');
    
    // If simple test works, try the actual chart
    return sharp(Buffer.from(wrappedSvg))
      .resize(800, 600)
      .png()
      .toFile('/tmp/tmpsxxe2_1i/chart.png');
  })
  .then(() => console.log('Main chart generated successfully'))
  .catch(err => console.error('Error generating chart:', err));
