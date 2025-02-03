
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

  return React.createElement('div',
    { style: { width: '100%', height: '400px' } },
    React.createElement(VictoryChart,
      {
        theme: VictoryTheme.material,
        containerComponent: React.createElement(VictoryContainer, { responsive: true })
      },
      React.createElement(VictoryLabel, {
        text: title,
        x: 225,
        y: 30,
        textAnchor: "middle"
      }),
      React.createElement(Victory.VictoryAxis, {
        label: xlabel,
        style: { axisLabel: { padding: 30 } }
      }),
      React.createElement(Victory.VictoryAxis, {
        dependentAxis: true,
        label: ylabel,
        style: { axisLabel: { padding: 40 } }
      }),
      getChartComponent()
    )
  );
};

export default ChartComponent;
