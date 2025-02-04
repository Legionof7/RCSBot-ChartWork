import React from 'react';
import {
  VictoryChart,
  VictoryBar,
  VictoryAxis,
  VictoryLabel,
  VictoryContainer
} from 'victory';

const ChartComponent = ({ graphData }) => {
  if (!graphData?.data) return null;

  // Transform data from Chart.js format to Victory format
  const transformedData = graphData.data.labels.map((label, index) => ({
    x: label,
    y: graphData.data.datasets[0].data[index]
  }));

  return React.createElement(VictoryChart, {
    padding: { top: 50, bottom: 50, left: 80, right: 50 },
    width: 800,
    height: 600,
    domainPadding: { x: 50 },
    containerComponent: React.createElement(VictoryContainer, {
      responsive: false
    })
  }, [
    React.createElement(VictoryBar, {
      key: "bar",
      data: transformedData,
      style: {
        data: {
          fill: "rgba(54, 162, 235, 0.2)",
          stroke: "rgba(54, 162, 235, 1)",
          strokeWidth: 1
        }
      }
    }),
    React.createElement(VictoryAxis, {
      key: "xAxis",
      label: graphData.data.datasets[0].label || "Value",
      style: {
        axisLabel: { padding: 40 },
        grid: { stroke: "none" }
      }
    }),
    React.createElement(VictoryAxis, {
      key: "yAxis",
      dependentAxis: true,
      label: "Value",
      style: {
        axisLabel: { padding: 45 },
        grid: { stroke: "#e0e0e0" }
      }
    })
  ]);
};

export default ChartComponent;