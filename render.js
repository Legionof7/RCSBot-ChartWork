
import ReactDOMServer from 'react-dom/server';
import React from 'react';
import fs from 'fs';
import { createCanvas } from 'canvas';
import ChartComponent from './VictoryChart.mjs';

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');
const chartData = {"type": "bar", "config": {"data": [{"x": "LDL", "y": 110}], "title": "LDL Cholesterol", "xlabel": "Test", "ylabel": "Value (mg/dL)", "referenceLines": {"LDL": 100}}};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

// Ensure directory exists
const tmpDir = '/tmp/tmp66snpgeg';
if (!fs.existsSync(tmpDir)) {
  fs.mkdirSync(tmpDir, { recursive: true });
}

fs.writeFileSync(`${tmpDir}/chart.png`, canvas.toBuffer());
