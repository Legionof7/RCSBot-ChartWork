
import React, { useState } from 'react';
import { VictoryChart, VictoryBar, VictoryAxis, VictoryContainer } from 'victory';

export default function App() {
  const [graphData] = useState({
    type: "bar",
    data: {
      labels: ["HDL"],
      datasets: [{
        label: "HDL Cholesterol (mg/dL)",
        data: [55],
        backgroundColor: ["rgba(54, 162, 235, 0.2)"],
        borderColor: ["rgba(54, 162, 235, 1)"],
        borderWidth: 1
      }]
    }
  });

  // Transform data for Victory
  const transformedData = graphData.data.labels.map((label, index) => ({
    x: label,
    y: graphData.data.datasets[0].data[index]
  }));

  return (
    <div style={{ width: '800px', height: '600px', margin: '20px auto', background: 'white' }}>
      <h2>Test Graph Rendering</h2>
      <VictoryChart
        padding={{ top: 50, bottom: 50, left: 80, right: 50 }}
        width={800}
        height={600}
        containerComponent={<VictoryContainer responsive={false}/>}
      >
        <VictoryBar
          data={transformedData}
          style={{
            data: {
              fill: graphData.data.datasets[0].backgroundColor[0],
              stroke: graphData.data.datasets[0].borderColor[0],
              strokeWidth: graphData.data.datasets[0].borderWidth
            }
          }}
        />
        <VictoryAxis
          label={graphData.data.datasets[0].label}
          style={{
            axisLabel: { padding: 40 },
            grid: { stroke: "none" }
          }}
        />
        <VictoryAxis
          dependentAxis
          label="Value"
          style={{
            axisLabel: { padding: 45 },
            grid: { stroke: "#e0e0e0" }
          }}
        />
      </VictoryChart>
    </div>
  );
}
