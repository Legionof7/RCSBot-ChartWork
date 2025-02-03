
    import React from 'react';
    import ReactDOMServer from 'react-dom/server';
    import fs from 'fs';
    import { createCanvas } from 'canvas';
    import ChartComponent from './VictoryChart.mjs';

    const canvas = createCanvas(800, 600);
    const ctx = canvas.getContext('2d');
    const chartData = {"type": "bar", "config": {"data": [{"x": "LDL", "y": 110}, {"x": "Optimal", "y": 100}], "title": "LDL Cholesterol", "xlabel": "Level", "ylabel": "mg/dL", "referenceLines": {"Optimal": 100}}};

    const element = React.createElement(ChartComponent, {graphData: chartData});
    const svg = ReactDOMServer.renderToString(element);

    fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
    