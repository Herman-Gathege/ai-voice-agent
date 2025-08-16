# AI Voice Agent
This project is an AI-powered voice agent that integrates Deepgram for speech-to-text (STT) processing and Twilio for real-time WebSocket communication. The agent supports real estate-specific functionality, handling user audio input and executing functions defined in real_estate_functions.py.

This README provides setup and running instructions for new developers.

# Prerequisites
Before starting, ensure you have the following installed:

Python 3.8+
pip (Python package manager)
uv (optional, for running the project with uv run)
ngrok (for exposing the local server to the internet)
A Deepgram API key (sign up at Deepgram)
A Twilio account with a phone number configured for WebSocket support

# Project Structure
main.py: The main script that runs the WebSocket server and handles Deepgram/Twilio integration.
real_estate_functions.py: Contains the FUNCTION_MAP with real estate-specific functions.
config.realestate.json: Configuration file for the Deepgram STT agent.
.env: Environment file for storing sensitive data (e.g., Deepgram API key).
.gitignore: Ignores sensitive and temporary files (e.g., .env, __pycache__).

# Setup Instructions
1. Clone the Repository
Clone the project to your local machine:
git clone https://github.com/Herman-Gathege/ai-voice-agent.git
cd ai-voice-agent

2. Set Up a Virtual Environment
Create and activate a virtual environment to manage dependencies:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

3. Install Dependencies
Install the required Python packages:
pip install -r requirements.txt

# Note: If requirements.txt is not present, install the following packages manually:
pip install websockets python-dotenv

4. Configure the Deepgram API Key
Create a .env file in the project root and add your Deepgram API key:
  echo "DEEPGRAM_API_KEY=your-deepgram-api-key" > .env

Replace your-deepgram-api-key with the API key from your Deepgram account. The .env file is ignored by .gitignore to keep sensitive data secure.

5. Configure Deepgram and Twilio Integration

Deepgram Configuration: The config.realestate.json file contains settings for the Deepgram STT agent (e.g., model, language, or real estate-specific parameters). Review and modify this file as needed for your use case.
Example structure (adjust as necessary):{
  "model": "nova-2",
  "language": "en",
  "features": {
    "real_estate_mode": true
  }
}




Twilio Setup: Ensure your Twilio account is configured with a phone number that supports WebSocket streams. Update the Twilio configuration with the public URL of your server (set up in the next step).

6. Expose Your Local Server with ngrok
To make your local server accessible to Twilio, use ngrok to create a public URL:
ngrok http 5000


Copy the generated public URL (e.g., https://abc123.ngrok.io).
Note: The server in main.py runs on localhost:5000 by default.

7. Update Twilio with the Public URL
In your Twilio Console:

Go to your phone number’s configuration.
Set the WebSocket URL to the ngrok URL (e.g., wss://abc123.ngrok.io).
Ensure the WebSocket is configured to handle inbound and outbound audio streams.

8. Run the Application
Start the server using one of the following commands:

If using uv (recommended for faster dependency resolution):uv run ./main.py


If using standard Python:python main.py



The server will start on localhost:5000, and you should see the message:
Started server.

How It Works

WebSocket Server: main.py creates a WebSocket server that listens for Twilio connections on localhost:5000.
Deepgram STT: The server connects to Deepgram’s STT service to process audio input, using the API key from .env and settings from config.realestate.json.
Twilio Integration: Handles real-time audio streams from Twilio, forwarding them to Deepgram for transcription and processing function calls (e.g., from real_estate_functions.py).
Function Calls: User inputs trigger functions defined in FUNCTION_MAP (in real_estate_functions.py), with results sent back to the client via Deepgram.

Troubleshooting

Deepgram Connection Issues: Ensure your DEEPGRAM_API_KEY is valid and correctly set in .env. Check for errors in the console output.
Twilio WebSocket Errors: Verify that the ngrok URL is correctly set in the Twilio Console and that your Twilio phone number supports WebSocket streams.
Configuration Errors: Check config.realestate.json for valid JSON and appropriate settings for your use case.
Dependencies: If you encounter missing package errors, ensure all dependencies are installed (websockets, python-dotenv, etc.).

Contributing

Clone the repository and create a feature branch:git checkout -b feature/your-feature


Make your changes and commit them with clear messages:git commit -m "Add feature: description"


Push to your clone and create a pull request:git push origin feature/your-feature


Ensure your code follows the project’s style (e.g., PEP 8 for Python) and includes appropriate comments.

License
This project is licensed under the MIT License. See the LICENSE file for details.
Contact
For questions or support, contact the project maintainer at remingtonherman7@gmail.com or open an issue on GitHub.