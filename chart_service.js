// chart_service2.js
const express = require("express");
const puppeteer = require("puppeteer-core");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fs = require("fs");
const {
  VictoryChart,
  VictoryLine,
  VictoryBar,
  VictoryScatter,
  VictoryAxis,
  VictoryTheme,
  VictoryPie,
  VictoryLegend,
} = require("victory");

const app = express();
app.use(express.json({ limit: "5mb" }));

app.get("/", (req, res) => {
  res.send("Chart service (v2 - accepting reactCode) is running");
});

async function renderChartFromReactCode(
  reactCode,
  filename = "test_image.png",
) {
  try {
    // NO MORE HARDCODED reactCode

    // Dynamically create the React component
    let MyChart;
    try {
      const wrapper = `(function(React, VictoryChart, VictoryLine, VictoryBar, VictoryScatter, VictoryAxis, VictoryTheme, VictoryPie, VictoryLegend) {
            ${reactCode}
            return MyChart;
        })`;
      MyChart = eval(wrapper)(
        React,
        VictoryChart,
        VictoryLine,
        VictoryBar,
        VictoryScatter,
        VictoryAxis,
        VictoryTheme,
        VictoryPie,
        VictoryLegend,
      );

      if (typeof MyChart !== "function") {
        throw new Error("Invalid React code: MyChart is not a function");
      }
    } catch (evalError) {
      console.error("Error evaluating React code:", evalError);
      throw new Error(`Error evaluating React code: ${evalError.message}`);
    }

    // Render the React component to HTML
    let chartHTML;
    try {
      chartHTML = ReactDOMServer.renderToString(React.createElement(MyChart));
    } catch (renderError) {
      console.error("Error rendering component:", renderError);
      throw new Error(
        `Error rendering React component: ${renderError.message}`,
      );
    }

    const htmlContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <title>Generated Chart</title>
          <meta http-equiv="Content-Security-Policy" content="default-src 'self' data: 'unsafe-inline'">
        </head>
        <body style="margin: 0; background: white;">
          <div id="root">${chartHTML}</div>
        </body>
      </html>`;

    // Launch Puppeteer to render the chart and take a screenshot
    const browser = await puppeteer.launch({
      executablePath:
        "/nix/store/zi4f80l169xlmivz8vja8wlphq74qqk0-chromium-125.0.6422.141/bin/chromium",
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
      headless: "new",
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 800, height: 900 });
    await page.setContent(htmlContent, { waitUntil: "domcontentloaded" });

    // Wait for Victory to render the chart
    await page.waitForFunction(
      () => {
        const svg = document.querySelector("#root svg");
        return svg && svg.querySelectorAll("path, rect, circle, g").length > 0;
      },
      { timeout: 10000 },
    );

    // Capture a screenshot of the rendered chart
    await page.screenshot({ path: filename, type: "png" });
    await browser.close();

    return filename;
  } catch (error) {
    console.error("renderChartFromReactCode Error:", error);
    throw error;
  }
}

// Endpoint to trigger the chart rendering, accepting reactCode
app.post("/render-react-chart", async (req, res) => {
  console.log("##heyy!!!!!!!!!!!!!");
  const { reactCode, filename } = req.body; // Get reactCode from the request
  console.log(reactCode);

  try {
    const savedFilename = await renderChartFromReactCode(reactCode, filename);
    res.json({ message: `Chart saved as ${savedFilename}` });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = 3002;
app.listen(PORT, "0.0.0.0", () => {
  console.log(
    `Chart service (v2 - accepting reactCode) listening on port ${PORT}`,
  );
});
