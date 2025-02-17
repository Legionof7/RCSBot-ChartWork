# test_chart_rendering.py
import requests
import json


def test_chart_rendering(react_code, output_filename="test_image.png"):
    """
    Sends React code (with embedded data) to the chart service.
    """
    url = "https://e84195c7-0bce-4bb6-8d08-d9dd7128af03-00-3nf0smkfdbxlk.pike.replit.dev:3003/render-react-chart"  # Replit URL, Port 3003
    headers = {"Content-Type": "application/json"}
    payload = {"reactCode": react_code, "filename": output_filename}

    try:
        response = requests.post(url,
                                 headers=headers,
                                 data=json.dumps(payload))
        response.raise_for_status()

        response_data = response.json()
        print(response_data["message"])

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Example 1: Simple Line Chart (Plain JavaScript)
    example_react_code_line = """
    const MyChart = () => {
        const data = [
          { x: 1, y: 2 },
          { x: 2, y: 3 },
          { x: 3, y: 5 },
          { x: 4, y: 4 },
          { x: 5, y: 7 }
        ];
        return React.createElement(
            VictoryChart,
            { theme: VictoryTheme.material },
            React.createElement(VictoryLine, { data: data })
        );
    };
    """
    # test_chart_rendering(example_react_code_line, "line_chart.png")

    # Example 2: Bar Chart with Axis Labels (Plain JavaScript)
    example_react_code_bar = """
    const MyChart = () => {
        const data = [
          { x: 'A', y: 25 },
          { x: 'B', y: 18 },
          { x: 'C', y: 32 },
          { x: 'D', y: 20 }
        ];
        return React.createElement(
            VictoryChart,
            { theme: VictoryTheme.material, domainPadding: 20 },
            React.createElement(VictoryBar, { data: data }),
            React.createElement(VictoryAxis, { label: "Categories", style: { axisLabel: { padding: 30 } } }),
            React.createElement(VictoryAxis, { dependentAxis: true, label: "Values", style: { axisLabel: { padding: 30 } } })
        );
    };
    """
    # test_chart_rendering(example_react_code_bar, "bar_chart.png")

    # Example 3: Scatter Plot with Legend (Plain JavaScript)
    example_react_code_scatter = """
    const MyChart = () => {
      const data1 = [
        { x: 1, y: 2, label: "A" },
        { x: 2, y: 3, label: "B" },
        { x: 3, y: 5, label: "C" }
      ];
      const data2 = [
        { x: 1, y: 4, label: "D" },
        { x: 2, y: 1, label: "E" },
        { x: 3, y: 2, label: "F" }
      ];
      return React.createElement(
          VictoryChart,
          { theme: VictoryTheme.material },
          React.createElement(VictoryScatter, {
            data: data1,
            size: 7,
            style: { data: { fill: "#c43a31" } }  // Red
          }),
          React.createElement(VictoryScatter, {
            data: data2,
            size: 7,
            style: { data: { fill: "#007AFF" } } // Blue
          }),
          React.createElement(VictoryLegend, {
            x: 125, y: 50,
            title: "Legend",
            centerTitle: true,
            orientation: "horizontal",
            gutter: 20,
            style: { border: { stroke: "black" }, title: { fontSize: 20 } },
            data: [
              { name: "Series 1", symbol: { fill: "#c43a31" } },
              { name: "Series 2", symbol: { fill: "#007AFF" } }
            ]
          })
      );
    };
    """
    # test_chart_rendering(example_react_code_scatter, "scatter_chart.png")

    # Example 4: Pie Chart (Plain JavaScript)
    example_react_code_pie = """
    const MyChart = () => {
        const data = [
            { x: "Cats", y: 35 },
            { x: "Dogs", y: 40 },
            { x: "Birds", y: 25 }
        ];
        return React.createElement(
            VictoryChart,
            { theme: VictoryTheme.material, width: 400, height: 400 },  // Set dimensions
            React.createElement(VictoryPie, {
                data: data,
                colorScale: ["tomato", "orange", "gold"],
                radius: 150 // Adjust radius
            })
        );
    };
    """
    test_chart_rendering(example_react_code_pie, "pie_chart.png")
