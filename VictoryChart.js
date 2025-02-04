
import React from 'react';
import {
  VictoryChart,
  VictoryBar,
  VictoryAxis,
  VictoryTheme,
  VictoryLabel,
  VictoryContainer
} from 'victory';

const ChartComponent = ({ graphData }) => {
  if (!graphData || !graphData.config) return null;
  
  const { type, config } = graphData;
  const { data, title, xlabel, ylabel, referenceLines } = config;

  const chartStyle = {
    parent: {
      border: "1px solid #ccc",
      borderRadius: "8px",
      padding: "16px"
    },
    data: {
      fill: "#4CAF50"
    },
    labels: {
      fontSize: 14
    }
  };

  return (
    <VictoryChart
      width={800}
      height={600}
      theme={VictoryTheme.material}
      domainPadding={50}
      containerComponent={
        <VictoryContainer 
          responsive={false}
          style={{
            touchAction: "auto",
            userSelect: "auto"
          }}
        />
      }
      style={chartStyle}
    >
      <VictoryBar
        data={data}
        style={chartStyle}
        barRatio={0.8}
        alignment="middle"
      />
      <VictoryAxis
        label={xlabel}
        style={{
          axisLabel: { padding: 40, fontSize: 14 },
          tickLabels: { fontSize: 12 },
          grid: { stroke: "none" }
        }}
      />
      <VictoryAxis
        dependentAxis
        label={ylabel}
        style={{
          axisLabel: { padding: 45, fontSize: 14 },
          tickLabels: { fontSize: 12 },
          grid: { stroke: "#e0e0e0" }
        }}
      />
      <VictoryLabel
        text={title}
        x={400}
        y={30}
        textAnchor="middle"
        style={{ fontSize: 18, fontWeight: "bold" }}
      />
    </VictoryChart>
  );
};

export default ChartComponent;
