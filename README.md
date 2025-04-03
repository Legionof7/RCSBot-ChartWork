# RCSBot-ChartWork

A healthcare communication bot that uses RCS (Rich Communication Services) to deliver interactive health information, charts, and personalized medical data to patients.

## Features

- Interactive health information via RCS messages
- Dynamic chart generation for visualizing health data
- SMS/MMS fallback when RCS isn't available
- FHIR integration for patient data
- Smart message formatting with enhanced fallback mechanisms

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on `.env.example` with your API keys

## Usage

Start the main Flask application:
```bash
python main.py
```

Run the example app to test the enhanced RCS fallback:
```bash
python example_main.py
```

## Environment Variables

See `.env.example` for required environment variables:
- `PINNACLE_API_KEY` - API key for Pinnacle's RCS services
- `GEMINI_API_KEY` - API key for Google's Gemini AI

## Enhanced Fallback Mechanism

This project includes an enhanced fallback system that gracefully degrades RCS content to MMS/SMS when needed:

1. Smart content reformatting - converts rich RCS content to SMS-friendly text
2. Button to text link conversion - preserves functionality in plain text
3. Image optimization - automatically resizes and compresses images for MMS
4. Structured formatting - maintains content hierarchy in plain text

## Architecture

- `model_service.py` - Handles AI-generated responses using Google Gemini
- `fhir_data.py` - Manages patient health data
- `message_handler.py` - Handles RCS/SMS/MMS message delivery with enhanced fallback
- `example_main.py` - Example webhook handler showing message processing

## Testing

Test the fallback functionality:
```bash
python -m message_handler
```