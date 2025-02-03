
import React from 'react';
import {
  VictoryChart,
  VictoryLine,
  VictoryBar,
  VictoryScatter,
  VictoryAxis,
  VictoryTheme,
  VictoryLabel,
  VictoryContainer
} from 'victory';

const ChartComponent = ({ graphData }) => {
  if (!graphData || !graphData.config) return null;
  
  const { type, config } = graphData;
  const { data, title, xlabel, ylabel, referenceLines } = config;

  return React.createElement(VictoryChart, {
    width: 800,
    height: 600,
    padding: { top: 50, bottom: 50, left: 80, right: 50 },
    theme: VictoryTheme.material,
    domainPadding: { x: 50, y: [0, 20] },
    key: "chart"
  }, [
    React.createElement(VictoryBar, {
      data: data,
      key: "bar",
      style: { data: { fill: "#4CAF50" } }
    }),
    React.createElement(VictoryAxis, {
      label: xlabel,
      style: { 
        axisLabel: { padding: 40 },
        grid: { stroke: "none" }
      },
      key: "xAxis"
    }),
    React.createElement(VictoryAxis, {
      dependentAxis: true,
      label: ylabel,
      style: { 
        axisLabel: { padding: 45 },
        grid: { stroke: "#e0e0e0" }
      },
      key: "yAxis"
    }),
    React.createElement(VictoryLabel, {
      text: title,
      x: 400,
      y: 30,
      textAnchor: "middle",
      key: "title"
    })
  ]);
};

export default ChartComponent;
