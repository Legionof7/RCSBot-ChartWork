
const express = require('express');
const puppeteer = require('puppeteer-core');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { VictoryChart, VictoryLine, VictoryBar, VictoryScatter, VictoryAxis, VictoryTheme } = require('victory');

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
  res.send('Chart service is running');
});

const renderChart = async (type, data) => {
  let chartData;
  if (Array.isArray(data)) {
    chartData = data;
  } else if (data.labels && data.values) {
    chartData = data.labels.map((label, index) => ({
      x: label,
      y: data.values[index]
    }));
  } else {
    throw new Error('Invalid data format');
  }

  const ChartComponent = ({ type, data, chartData }) => {
    const Chart = {
      'line': VictoryLine,
      'bar': VictoryBar,
      'scatter': VictoryScatter
    }[type];

    return React.createElement(VictoryChart, 
      { 
        theme: VictoryTheme.material,
        domainPadding: 20,
        height: 400,
        width: 600,
        padding: { top: 50, bottom: 50, left: 60, right: 40 }
      },
      React.createElement(VictoryAxis, {
        label: data.xlabel,
        style: { axisLabel: { padding: 35 } }
      }),
      React.createElement(VictoryAxis, {
        dependentAxis: true,
        label: data.ylabel,
        style: { axisLabel: { padding: 45 } }
      }),
      React.createElement(Chart, { 
        data: chartData,
        style: { data: { fill: "#4287f5" } }
      })
    );
  };

  const chartHTML = ReactDOMServer.renderToString(
    React.createElement(ChartComponent, { type, data, chartData })
  );

  const browser = await puppeteer.launch({
    executablePath: '/nix/store/chromium-121.0.6167.184-1/bin/chromium',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    headless: 'new'
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 600, height: 400 });
  await page.setContent(`
    <html>
      <body>
        <div id="root" style="width:600px;height:400px;">
          ${chartHTML}
        </div>
      </body>
    </html>
  `);
  const imageBuffer = await page.screenshot({ type: 'png' });
  await browser.close();
  return imageBuffer.toString('base64');
};

app.post('/render-chart', async (req, res) => {
  try {
    const { type, data } = req.body;
    console.log('Received chart request:', { type, data });
    const base64Image = await renderChart(type, data);
    res.json({ image_base64: base64Image });
  } catch (error) {
    console.error('Chart generation error:', error);
    res.status(500).json({ error: error.message });
  }
});

app.listen(3001, '0.0.0.0', () => {
  console.log('Chart service running on port 3001');
});
