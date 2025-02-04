
import React from 'react';
import {
  VictoryChart,
  VictoryBar,
  VictoryAxis,
  VictoryLine,
  VictoryLabel,
  VictoryContainer
} from 'victory';

const ChartComponent = ({ graphData }) => {
  if (!graphData?.config) return null;
  
  const { data, title, xlabel, ylabel, referenceLines } = graphData.config;

  const referenceLineComponents = Object.entries(referenceLines || {}).map(([key, value]) => (
    React.createElement(VictoryLine, {
      key: `ref-${key}`,
      style: {
        data: { stroke: "#FF5722", strokeDasharray: "4,4" }
      },
      x: 0,
      y: value.value,
      labels: [value.label],
      labelComponent: React.createElement(VictoryLabel, {
        dy: -10,
        style: { fontSize: 12 }
      })
    })
  ));

  return React.createElement(VictoryChart, {
    padding: { top: 50, bottom: 50, left: 80, right: 50 },
    width: 800,
    height: 600,
    containerComponent: React.createElement(VictoryContainer, {
      responsive: false
    })
  }, [
    React.createElement(VictoryBar, {
      key: "bar",
      data: data,
      style: { data: { fill: "#4CAF50" } }
    }),
    React.createElement(VictoryAxis, {
      key: "xAxis",
      label: xlabel,
      style: {
        axisLabel: { padding: 40 },
        grid: { stroke: "none" }
      }
    }),
    React.createElement(VictoryAxis, {
      key: "yAxis",
      dependentAxis: true,
      label: ylabel,
      style: {
        axisLabel: { padding: 45 },
        grid: { stroke: "#e0e0e0" }
      }
    }),
    React.createElement(VictoryLabel, {
      key: "title",
      text: title,
      x: 400,
      y: 30,
      textAnchor: "middle"
    }),
    ...referenceLineComponents
  ]);
};

export default ChartComponent;
