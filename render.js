
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import { createCanvas } from 'canvas';
import ChartComponent from './VictoryChart.js';

console.log('Starting render process...');

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');
const chartData = {
  "type": "bar",
  "config": {
    "data": [{"x": "HDL", "y": 55}],
    "title": "HDL Cholesterol",
    "xlabel": "Test",
    "ylabel": "mg/dL",
    "referenceLines": {
      "Normal Range": 52.5
    }
  }
};

console.log('Chart data:', JSON.stringify(chartData, null, 2));

const element = React.createElement(ChartComponent, {graphData: chartData});
console.log('React element created');

const svg = ReactDOMServer.renderToString(element);
console.log('SVG rendered:', svg);

fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
console.log('Chart saved to file');
