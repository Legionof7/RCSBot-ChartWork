
require('@babel/register')({
  presets: ['@babel/preset-env', '@babel/preset-react'],
  extensions: ['.js', '.jsx']
});

const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { createCanvas } = require('canvas');
const fs = require('fs');
const ChartComponent = require('./VictoryChart.js').default;

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');
const chartData = {"type": "bar", "config": {"data": [{"x": "LDL", "y": 110}, {"x": "Ideal LDL", "y": 100}], "title": "LDL Cholesterol", "xlabel": "Level", "ylabel": "mg/dL", "referenceLines": {"Ideal LDL": 100}}};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
