
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
    <div style={{ width: '100%', height: '400px' }}>
      <VictoryChart
        theme={VictoryTheme.material}
        containerComponent={<VictoryContainer responsive={true} />}
      >
        <VictoryLabel
          text={title}
          x={225}
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
    </div>
  );
};

export default ChartComponent;
