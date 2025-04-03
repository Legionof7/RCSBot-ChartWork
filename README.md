# RCSBot-ChartWork

A healthcare communication bot that uses RCS (Rich Communication Services) to deliver interactive health information, charts, adaptive micro-moment interventions, and personalized medical data to patients.

## Features

- Interactive health information via RCS messages
- Dynamic chart generation for visualizing health data
- SMS/MMS fallback when RCS isn't available
- FHIR integration for patient data
- Smart message formatting with enhanced fallback mechanisms
- **Adaptive Micro-Moment Interventions** - contextual, just-in-time health nudges

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

Test micro-moment interventions:
```bash
python test_interventions.py glucose +1234567890
python test_interventions.py medication +1234567890
python test_interventions.py activity +1234567890
```

Run the example app to test the enhanced RCS fallback:
```bash
python example_main.py
```

## Environment Variables

See `.env.example` for required environment variables:
- `PINNACLE_API_KEY` - API key for Pinnacle's RCS services
- `GEMINI_API_KEY` - API key for Google's Gemini AI

## Adaptive Micro-Moment Interventions

The system supports dynamic health interventions that are:

- **Contextual**: Triggered by specific health data, time, and patient context
- **Progressive**: Start with essential information with options to expand
- **Interactive**: Provide quick actions and follow-up responses
- **Personalized**: Adapt to patient needs and preferences

### Intervention Types

1. **Physiological Alerts**
   - Pre-hypoglycemic glucose warnings
   - High blood pressure alerts
   - Abnormal lab result notifications

2. **Behavioral Nudges**
   - Medication reminders
   - Activity prompts after sedentary periods
   - Hydration reminders

3. **Educational Moments**
   - Condition management tips
   - Nutritional guidance based on health data
   - Preventive care information

4. **Progress Updates**
   - Health goal achievement notifications
   - Trend improvements in key metrics
   - Positive reinforcement messages

### Testing Interventions

Use the `test_interventions.py` script to simulate various micro-moment interventions:

```bash
# Test specific intervention types
python test_interventions.py glucose +1234567890
python test_interventions.py medication +1234567890
python test_interventions.py activity +1234567890

# Test auto-detection of appropriate intervention
python test_interventions.py auto +1234567890

# Test scheduled interventions for all users
python test_interventions.py scheduled

# Simulate a user message
python test_interventions.py message +1234567890 "My glucose feels low"

# Simulate button/quick reply interaction
python test_interventions.py button +1234567890 EXPLAIN_GLUCOSE_ALERT
```

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
- `main.py` - Main application with webhook handling and micro-moment interventions
- `test_interventions.py` - Test script for simulating various intervention scenarios

## Testing

Test the fallback functionality:
```bash
python -m message_handler
```