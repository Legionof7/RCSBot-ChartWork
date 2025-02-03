
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
  const { type, config } = graphData;
  const { data, title, xlabel, ylabel, referenceLines } = config;

  const getChartComponent = () => {
    switch (type) {
      case 'line':
        return React.createElement(VictoryLine, { data });
      case 'bar':
        return React.createElement(VictoryBar, { data });
      case 'scatter':
        return React.createElement(VictoryScatter, { data });
      default:
        return null;
    }
  };

  return React.createElement(VictoryChart, {
    width: 800,
    height: 600,
    theme: VictoryTheme.material,
    standalone: true
  }, [
    React.createElement(VictoryLabel, {
      text: title,
      x: 400,
      y: 30,
      textAnchor: "middle",
      key: "title"
    }),
    React.createElement(VictoryAxis, {
      label: xlabel,
      style: { axisLabel: { padding: 30 } },
      key: "xAxis"
    }),
    React.createElement(VictoryAxis, {
      dependentAxis: true,
      label: ylabel,
      style: { axisLabel: { padding: 40 } },
      key: "yAxis"
    }),
    getChartComponent()
  ]);
};

export default ChartComponent;
