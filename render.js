
    import React from 'react';
    import ReactDOMServer from 'react-dom/server';
    import fs from 'fs';
    import { createCanvas } from 'canvas';
    import ChartComponent from './VictoryChart.js';

    const canvas = createCanvas(800, 600);
    const ctx = canvas.getContext('2d');
    const chartData = {"type": "bar", "config": {"data": [{"x": "HDL", "y": 55}], "title": "HDL Cholesterol", "xlabel": "Test", "ylabel": "Value (mg/dL)", "referenceLines": {"HDL": 60}}};

    const element = React.createElement(ChartComponent, {graphData: chartData});
    const svg = ReactDOMServer.renderToString(element);

    fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
    