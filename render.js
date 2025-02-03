
    const ReactDOMServer = require('react-dom/server');
    const {createElement} = require('react');
    const fs = require('fs');
    const {createCanvas} = require('canvas');
    const VictoryChart = require('./VictoryChart.jsx').default;
    
    const canvas = createCanvas(800, 600);
    const ctx = canvas.getContext('2d');
    const chartData = {"type": "bar", "config": {"data": [{"x": "LDL", "y": 110}, {"x": "Desirable Level", "y": 100}], "title": "LDL Cholesterol", "xlabel": "Level", "ylabel": "mg/dL", "referenceLines": {"Desirable Level": 100}}};
    
    const element = createElement(VictoryChart, {graphData: chartData});
    const svg = ReactDOMServer.renderToString(element);
    
    fs.writeFileSync('/tmp/tmpsxxe2_1i/chart.png', canvas.toBuffer());
    