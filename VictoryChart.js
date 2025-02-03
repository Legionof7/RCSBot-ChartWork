
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
        return <VictoryLine data={data} />;
      case 'bar':
        return <VictoryBar data={data} />;
      case 'scatter':
        return <VictoryScatter data={data} />;
      default:
        return null;
    }
  };

  return (
    <svg width={800} height={600} viewBox="0 0 800 600">
      <VictoryChart
        width={800}
        height={600}
        theme={VictoryTheme.material}
        standalone={false}
      >
        <VictoryLabel
          text={title}
          x={400}
          y={30}
          textAnchor="middle"
        />
        <VictoryAxis
          label={xlabel}
          style={{ axisLabel: { padding: 30 } }}
        />
        <VictoryAxis
          dependentAxis
          label={ylabel}
          style={{ axisLabel: { padding: 40 } }}
        />
        {getChartComponent()}
      </VictoryChart>
    </svg>
  );
};

export default ChartComponent;
