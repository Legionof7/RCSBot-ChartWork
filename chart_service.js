const express = require('express');
const puppeteer = require('puppeteer-core');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const {
  VictoryChart,
  VictoryLine,
  VictoryBar,
  VictoryScatter,
  VictoryAxis,
  VictoryTheme
} = require('victory');

const app = express();
app.use(express.json());

// Simple endpoint for health checks
app.get('/', (req, res) => {
  res.send('Chart service is running');
});

// Serve debug HTML for manual inspection in a browser
app.get('/debug_chart.html', (req, res) => {
  res.sendFile(__dirname + '/debug_chart.html');
});

async function renderChart(type, data) {
  console.log('\n=== Chart Generation Debug ===');
  console.log('Received chart type:', type);
  console.log('Received data:', JSON.stringify(data, null, 2));

  // 1) Parse the data into an array of { x, y }
  let chartData;

  if (Array.isArray(data)) {
    // Already an array of { x, y } objects?
    // Or at least something we can pass to Victory.
    if (data.every(d => d.x !== undefined && d.y !== undefined)) {
      chartData = data;
      console.log('Using array data directly as chartData');
    } else {
      console.error('Invalid array format: each item must have { x, y }');
      throw new Error('Invalid array format for chart data');
    }
  } else if (data && typeof data === 'object') {
    // Possibly an object with { labels: [...], values: [...] }?
    if (data.labels && data.values && Array.isArray(data.labels) && Array.isArray(data.values)) {
      if (data.labels.length !== data.values.length) {
        console.error('Mismatch in length of labels and values');
        throw new Error('labels and values array length mismatch');
      }
      console.log('Converting labels/values to chart data');
      chartData = data.labels.map((label, index) => ({
        x: label,
        y: data.values[index]
      }));
      console.log('Converted chart data:', JSON.stringify(chartData, null, 2));
    } else {
      console.error('Invalid data object: expected { labels, values } or an array of { x, y }');
      throw new Error('Invalid data format');
    }
  } else {
    console.error('Data is neither an object nor an array');
    throw new Error('Invalid data format');
  }

  // 2) Pick the Victory chart component by type
  const ChartMap = {
    'line': VictoryLine,
    'bar': VictoryBar,
    'scatter': VictoryScatter
  };
  const SelectedChart = ChartMap[type];
  if (!SelectedChart) {
    console.error(`Unsupported chart type: ${type}`);
    throw new Error(`Unsupported chart type: ${type}`);
  }

  // 3) Define a React component to render the chart
  const ChartComponent = ({ chartType, chartProps, chartData }) => {
    return React.createElement(
      VictoryChart,
      {
        theme: VictoryTheme.material,
        domainPadding: 20,
        height: 400,
        width: 600,
        padding: { top: 50, bottom: 50, left: 60, right: 40 }
      },
      React.createElement(VictoryAxis, {
        label: chartProps.xlabel || 'X Axis',
        style: { axisLabel: { padding: 35 } }
      }),
      React.createElement(VictoryAxis, {
        dependentAxis: true,
        label: chartProps.ylabel || 'Y Axis',
        style: { axisLabel: { padding: 45 } }
      }),
      React.createElement(SelectedChart, {
        data: chartData,
        style: { data: { fill: '#4287f5' } }
      })
    );
  };

  // 4) Render the React component to static HTML
  const chartHTML = ReactDOMServer.renderToString(
    React.createElement(ChartComponent, {
      chartType: type,
      chartProps: data,  // might contain { xlabel, ylabel }
      chartData
    })
  );

  // Puppeteer logic
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
    headless: 'new' // or 'true' / 'false' depending on your environment
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

  // 5) Build an HTML string that includes the rendered React content
  const htmlContent = `
    <html>
      <body style="margin:0; background:white;">
        <div id="root" style="width:600px; height:400px; background:white; padding:20px; box-sizing:border-box;">
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

  // 6) Load the HTML into Puppeteer
  await page.setViewport({ width: 600, height: 400 });
  await page.setContent(htmlContent);

  // Wait until the Victory SVG is rendered
  await page.waitForFunction(() => {
    const svg = document.querySelector('#root svg');
    // Ensure there's at least some path or shape elements
    return svg && svg.querySelectorAll('path, rect, circle').length > 0;
  }, { timeout: 5000 });

  // A small delay to ensure final layout
  await new Promise(resolve => setTimeout(resolve, 1000));

  // 7) Take a screenshot
  console.log('Taking screenshot...');
  const imageBuffer = await page.screenshot({
    type: 'png',
    fullPage: false,
    omitBackground: false,
    path: 'debug_chart.png'  // Save to local file
  }).catch(err => {
    console.error('Failed to take screenshot:', err);
    throw err;
  });

  // Validate screenshot
  if (!imageBuffer || imageBuffer.length < 1000) {
    console.error('Screenshot appears invalid - size too small');
    throw new Error('Invalid screenshot generated');
  }
  console.log('Screenshot captured successfully');

  const savedFileSize = fs.statSync('debug_chart.png').size;
  console.log('Saved PNG file size:', savedFileSize, 'bytes');

  // Close the browser
  console.log('Closing browser...');
  await browser.close();
  console.log('Browser closed successfully');

  // 8) Validate the PNG header
  const headerBytes = Array.from(imageBuffer.slice(0, 4));
  console.log('PNG header bytes:', headerBytes);  // Should be [137, 80, 78, 71] for a PNG

  if (headerBytes[0] !== 0x89 ||
      headerBytes[1] !== 0x50 ||
      headerBytes[2] !== 0x4E ||
      headerBytes[3] !== 0x47) {
    console.error('Invalid PNG header detected');
    throw new Error('Invalid PNG format');
  }

  // 9) Convert to base64 with data URI
  const base64Data = imageBuffer.toString('base64');
  const cleanBase64 = base64Data.replace(/[^A-Za-z0-9+/]/g, '');
  const padding = '='.repeat((4 - cleanBase64.length % 4) % 4);
  const validBase64 = cleanBase64 + padding;
  console.log('Base64 validation:', {
    length: validBase64.length,
    startsWithiVBOR: validBase64.startsWith('iVBOR')
  });

  return `data:image/png;base64,${validBase64}`;
}

app.post('/render-chart', async (req, res) => {
  try {
    const { type, data } = req.body;
    if (!type || !data) {
      return res.status(400).json({ error: 'Missing type or data parameter' });
    }
    console.log('Received chart request:', { type, data });
    const base64Image = await renderChart(type, data);
    if (!base64Image) {
      return res.status(500).json({ error: 'Failed to generate chart' });
    }
    res.json({ image_base64: base64Image });
  } catch (error) {
    console.error('Chart generation error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Start server
app.listen(3001, '0.0.0.0', () => {
  console.log('Chart service running on port 3001');
});
