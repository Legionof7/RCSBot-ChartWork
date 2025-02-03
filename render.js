
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import fs from 'fs';
import { createCanvas } from 'canvas';
import ChartComponent from './VictoryChart.js';

const chartData = {"type": "bar", "config": {"data": [{"x": "LDL", "y": 110}, {"x": "Ideal LDL", "y": 100}], "title": "LDL Cholesterol", "xlabel": "Level", "ylabel": "mg/dL", "referenceLines": {"Ideal LDL": 100}}};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToStaticMarkup(element);

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');

// Draw background
ctx.fillStyle = 'white';
ctx.fillRect(0, 0, 800, 600);

// Write SVG data
fs.writeFileSync('/tmp/chart.svg', svg);

// Save canvas as PNG
fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
