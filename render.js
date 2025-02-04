
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import { createCanvas } from 'canvas';
import ChartComponent from './VictoryChart.js';

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');

// Transform the data format to what VictoryChart expects
const rawData = {
  "type": "bar",
  "data": {
    "labels": ["HDL"],
    "datasets": [{
      "label": "HDL Cholesterol (mg/dL)",
      "data": [55]
    }]
  }
};

// Convert to Victory format
const chartData = {
  "type": "bar",
  "config": {
    "data": [{ "x": "HDL", "y": 55 }],
    "title": "HDL Cholesterol",
    "xlabel": "Test",
    "ylabel": "Value (mg/dL)",
    "referenceLines": {
      "Normal Range Low": 40,
      "Normal Range High": 60
    }
  }
};

console.log('Chart data being passed:', JSON.stringify(chartData, null, 2));

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);
console.log('Generated SVG:', svg);

fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
