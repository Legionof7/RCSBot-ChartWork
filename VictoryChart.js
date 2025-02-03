
const React = require('react');
const Victory = require('victory');

const ChartComponent = ({ graphData }) => {
  const { type, config } = graphData;
  const { data, title, xlabel, ylabel, referenceLines } = config;

  const getChartComponent = () => {
    switch (type) {
      case 'line':
        return React.createElement(Victory.VictoryLine, { data });
      case 'bar':
        return React.createElement(Victory.VictoryBar, { data });
      case 'scatter':
        return React.createElement(Victory.VictoryScatter, { data });
      default:
        return null;
    }
  };

  return React.createElement('div',
    { style: { width: '100%', height: '400px' } },
    React.createElement(Victory.VictoryChart,
      {
        theme: Victory.VictoryTheme.material,
        containerComponent: React.createElement(Victory.VictoryContainer, { responsive: true })
      },
      React.createElement(Victory.VictoryLabel, {
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

module.exports = ChartComponent;
