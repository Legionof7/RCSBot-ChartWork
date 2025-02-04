
const express = require('express');
const puppeteer = require('puppeteer');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { VictoryChart, VictoryLine, VictoryBar, VictoryScatter, VictoryTheme } = require('victory');

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
  res.send('Chart service is running');
});

const renderChart = async (type, data) => {
  const ChartComponent = ({ type, data }) => {
    const Chart = {
      'line': VictoryLine,
      'bar': VictoryBar,
      'scatter': VictoryScatter
    }[type];

    return React.createElement(VictoryChart, { theme: VictoryTheme.material },
      React.createElement(Chart, { data: data })
    );
  };

  const chartHTML = ReactDOMServer.renderToString(
    React.createElement(ChartComponent, { type, data })
  );

  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setContent(`
    <html><body><div id="root">${chartHTML}</div></body></html>
  `);
  const imageBuffer = await page.screenshot({ type: 'png' });
  await browser.close();
  return imageBuffer.toString('base64');
};

app.post('/render-chart', async (req, res) => {
  try {
    const { type, data } = req.body;
    const base64Image = await renderChart(type, data);
    res.json({ image_base64: base64Image });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(3001, 'localhost', () => {
  console.log('Chart service running on port 3001');
});
