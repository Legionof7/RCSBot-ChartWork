
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import { createCanvas, loadImage } from 'canvas';
import ChartComponent from './VictoryChart.js';

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');

// Set white background
ctx.fillStyle = 'white';
ctx.fillRect(0, 0, 800, 600);

const chartData = {
  "type": "bar",
  "config": {
    "data": [
      {
        "x": "HDL Cholesterol",
        "y": 55
      },
      {
        "x": "Normal Range",
        "y": 52.5
      }
    ],
    "title": "HDL Level",
    "xlabel": "Test",
    "ylabel": "Value (mg/dL)",
    "referenceLines": {
      "Normal Range": 52.5
    }
  }
};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

// Create a data URL from the SVG
const svgBuffer = Buffer.from(svg);
const dataUrl = `data:image/svg+xml;base64,${svgBuffer.toString('base64')}`;

// Load the SVG onto the canvas
loadImage(dataUrl).then((image) => {
  ctx.drawImage(image, 0, 0);
  fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
}).catch((err) => {
  console.error('Error rendering chart:', err);
  throw err;
});
