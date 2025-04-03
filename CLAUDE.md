# CLAUDE.md - Guidelines for RCSBot-ChartWork

## Commands
- **Run Application**: `python main.py`
- **Install Dependencies**: `pip install -r requirements.txt`
- **Run Linting**: `flake8 *.py`
- **Type Checking**: `mypy *.py`
- **Run Chart Service**: `node chart_service.js`
- **Run Tests**: Not implemented yet

## Code Style Guidelines
- **Imports**: Group in order: standard library, third-party, local application
- **Formatting**: Use 4-space indentation, 88 character line limit
- **Types**: Add type hints to function parameters and return values
- **Naming**: Use snake_case for variables/functions, CamelCase for classes
- **Error Handling**: Use try/except blocks with specific exception types
- **Documentation**: Add docstrings to all functions and modules
- **Environment**: Use os.getenv() with load_dotenv() for configuration
- **Logging**: Use the logging module instead of print statements
- **Charts**: For charts, use Matplotlib in model_service.py
- **API Keys**: Never hardcode API keys; use environment variables

Remember to update .env from .env.example with actual API keys before running.