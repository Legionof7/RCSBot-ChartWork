
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

app.get('/debug_chart.html', (req, res) => {
  res.sendFile(__dirname + '/debug_chart.html');
});

const renderChart = async (type, data) => {
  console.log('\n=== Chart Generation Debug ===');
  console.log('Received chart type:', type);
  console.log('Received data:', JSON.stringify(data, null, 2));

  let chartData;
  if (Array.isArray(data)) {
    chartData = data;
    console.log('Using array data directly');
  } else if (data.labels && data.values) {
    console.log('Converting labels/values to chart data');
    chartData = data.labels.map((label, index) => ({
      x: label,
      y: data.values[index]
    }));
    console.log('Converted chart data:', JSON.stringify(chartData, null, 2));
  } else {
    console.error('Invalid data format received');
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

  console.log('Launching Puppeteer browser...');
  const browser = await puppeteer.launch({
    executablePath: '/nix/store/zi4f80l169xlmivz8vja8wlphq74qqk0-chromium-125.0.6422.141/bin/chromium',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--single-process'
    ],
    ignoreDefaultArgs: ['--disable-extensions'],
    headless: 'new'
  }).catch(err => {
    console.error('Failed to launch browser:', err);
    throw err;
  });
  
  console.log('Browser launched successfully');
  console.log('Creating new page...');
  const page = await browser.newPage().catch(err => {
    console.error('Failed to create new page:', err);
    throw err;
  });
  console.log('Page created successfully');
  await page.setViewport({ width: 600, height: 400 });
  const htmlContent = `
    <html>
      <body>
        <div id="root" style="width:600px;height:400px;">
          ${chartHTML}
        </div>
      </body>
    </html>
  `;
  
  // Save HTML for debugging
  const fs = require('fs');
  const debugPath = 'debug_chart.html';
  fs.writeFileSync(debugPath, htmlContent);
  console.log(`Debug HTML saved to: ${debugPath}`);
  
  await page.setContent(htmlContent);
  console.log('Taking screenshot...');
  
  await page.evaluate(() => {
    document.body.style.margin = '0';
    document.body.style.background = 'white';
    const root = document.getElementById('root');
    root.style.background = 'white';
    root.style.padding = '20px';
    root.style.boxSizing = 'border-box';
  });

  // Wait for rendering and add extra delay using evaluate
  await page.waitForFunction(() => {
    const svg = document.querySelector('#root svg');
    const paths = svg?.querySelectorAll('path');
    return svg && paths.length > 0 && Array.from(paths).every(p => p.getTotalLength() > 0);
  }, { timeout: 5000 });
  
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  console.log('Attempting to take screenshot...');
  const imageBuffer = await page.screenshot({ 
    type: 'png',
    fullPage: false,
    omitBackground: false
  }).catch(err => {
    console.error('Failed to take screenshot:', err);
    throw err;
  });

  // Validate screenshot buffer
  if (!imageBuffer || imageBuffer.length < 1000) {
    console.error('Screenshot appears invalid - size too small');
    throw new Error('Invalid screenshot generated');
  }

  console.log('Screenshot details:', {
    size: imageBuffer.length,
    isEmpty: !imageBuffer,
    first10Bytes: imageBuffer.slice(0, 10).toString('hex')
  });
  
  if (!imageBuffer || imageBuffer.length < 1000) {
    console.error('Screenshot appears invalid - size too small');
    throw new Error('Invalid screenshot generated');
  }
  
  console.log('Screenshot captured successfully');
  console.log('Screenshot details:', {
    size: imageBuffer.length,
    isEmpty: !imageBuffer,
    first10Bytes: imageBuffer.slice(0, 10).toString('hex')
  });
  
  console.log('Closing browser...');
  await browser.close();
  console.log('Browser closed successfully');
  
  // Log PNG header for debugging
  const headerBytes = Array.from(imageBuffer.slice(0, 4));
  console.log('PNG header bytes:', headerBytes);
  
  // Check for valid PNG signature: 89 50 4E 47
  if (headerBytes[0] !== 0x89 || 
      headerBytes[1] !== 0x50 || 
      headerBytes[2] !== 0x4E || 
      headerBytes[3] !== 0x47) {
    console.error('Invalid PNG header detected');
    throw new Error('Invalid PNG format');
  }

  // Convert buffer to base64 and ensure proper padding
  const base64Data = imageBuffer.toString('base64');
  const paddedBase64 = base64Data.replace(/=/g, '').padEnd(Math.ceil(base64Data.length / 4) * 4, '=');
  
  console.log('Base64 validation:', {
    length: paddedBase64.length,
    start: paddedBase64.slice(0, 30),
    end: paddedBase64.slice(-30),
    startsWithiVBOR: paddedBase64.startsWith('iVBOR')
  });

  // Return with data URI prefix and proper padding
  return `data:image/png;base64,${paddedBase64}`;
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
