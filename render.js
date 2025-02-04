import React from 'react';
    import ReactDOMServer from 'react-dom/server';
    import fs from 'fs';
    import { createCanvas } from 'canvas';
    import ChartComponent from './VictoryChart.js';

    const canvas = createCanvas(800, 600);
    const ctx = canvas.getContext('2d');
    const chartData = {"type": "bar", "config": {"data": [{"x": "HDL", "y": 55}, {"x": "Normal Range", "y": 52.5}], "title": "HDL Cholesterol", "xlabel": "HDL", "ylabel": "mg/dL", "referenceLines": {"Normal Range": 52.5}}};

    const element = React.createElement(ChartComponent, {graphData: chartData});
    const svg = ReactDOMServer.renderToString(element);
    console.log('Generated SVG:', svg);

    // Draw the SVG on canvas
    const Image = canvas.Image;
    const img = new Image();
    img.onload = () => {
        ctx.drawImage(img, 0, 0);
        fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
    };
    img.onerror = (err) => {
        console.error('Error loading image:', err);
    };

    // Convert SVG to data URL
    const svgUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
    img.src = svgUrl;