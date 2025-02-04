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

  const referenceLineComponents = (referenceLines || []).map((line, index) => (
    React.createElement(VictoryLine, {
      key: `ref-${index}`,
      style: {
        data: { stroke: "#FF5722", strokeDasharray: "4,4" }
      },
      data: [
        { x: data[0].x, y: line.y },
        { x: data[data.length - 1].x, y: line.y }
      ],
      labelComponent: React.createElement(VictoryLabel, {
        text: line.label,
        x: 50,
        y: line.y,
        dx: 10,
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