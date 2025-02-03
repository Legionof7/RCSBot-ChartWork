
require('@babel/register')({
  presets: ['@babel/preset-env', '@babel/preset-react']
});

const React = require('react');
const ReactDOMServer = require('react-dom/server');
const fs = require('fs');
const { createCanvas } = require('canvas');
const ChartComponent = require('./VictoryChart.jsx').default;

const canvas = createCanvas(800, 600);
const ctx = canvas.getContext('2d');
const chartData = {
  "type": "bar",
  "config": {
    "data": [{"x": "LDL", "y": 110}, {"x": "Target", "y": 100}],
    "title": "LDL Cholesterol",
    "xlabel": "Level",
    "ylabel": "mg/dL",
    "referenceLines": {"Target": 100}
  }
};

const element = React.createElement(ChartComponent, {graphData: chartData});
const svg = ReactDOMServer.renderToString(element);

const tmpDir = '/tmp/tmpsxxe2_1i';
if (!fs.existsSync(tmpDir)) {
  fs.mkdirSync(tmpDir, { recursive: true });
}

fs.writeFileSync(`${tmpDir}/chart.png`, canvas.toBuffer());
