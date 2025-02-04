
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import { createCanvas } from 'canvas';
import ChartComponent from './VictoryChart.js';

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');

// Set white background
ctx.fillStyle = 'white';
ctx.fillRect(0, 0, 800, 600);

const chartData = {"type": "bar", "config": {"data": [{"x": "HDL", "y": 55}], "title": "HDL Cholesterol", "xlabel": "Test", "ylabel": "Value (mg/dL)", "referenceLines": {"HDL": [40, 60]}}};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToStaticMarkup(element);

// Write the SVG string to file for debugging
fs.writeFileSync('debug.svg', svg);

// Save canvas as PNG
fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
