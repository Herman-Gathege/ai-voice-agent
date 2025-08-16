#main.py

import asyncio
import base64
import json
import websockets
import os
from dotenv import load_dotenv
from real_estate_functions import FUNCTION_MAP

load_dotenv()

# The function sts_connect(): 
# Establishes a WebSocket connection to the Deepgram STT service using the API key from environment variables.
# Raises an exception if the API key is not found.
def sts_connect():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise Exception("DEEPGRAM_API_KEY not found")

    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws


# The function load_config(): 
# Loads configuration from 'config.realestate.json' for real estate-specific settings at the moment.
# Returns the parsed JSON configuration for use in the STT service.
def load_config():
    with open("config.realestate.json", "r") as f:
        return json.load(f)
    

# The function handle_barge_in(): 
# Handles barge-in events by sending a 'clear' message to the Twilio WebSocket.
# Stops the current message when the user starts speaking, identified by the 'UserStartedSpeaking' event.
async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded["type"] == "UserStartedSpeaking":
        clear_message = {
            "event": "clear",
            "streamSid": streamsid
        }
        await twilio_ws.send(json.dumps(clear_message))


# The function execute_function_call():
# Execute a function call stated in the FUNCTION_MAP within (service's file.py)
# Executes a function call from FUNCTION_MAP (defined in real_estate_functions.py currently) with the provided arguments.
# Returns the function result or an error if the function is not found in FUNCTION_MAP.
def execute_function_call(func_name, arguments):
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**arguments)
        print(f"Function call result: {result}")
        return result
    else:
        result = {"error": f"Unknown function: {func_name}"}
        print(result)
        return result
    

# The function create_function_call_response():
# Creates a JSON response for a function call result, including the function ID, name, and result content.
# Formatted for sending back to the Deepgram STT service.
def create_function_call_response(func_id, func_name, result):
    return {
        "type": "FunctionCallResponse",
        "id": func_id,
        "name": func_name,
        "content": json.dumps(result)
    }


# The function handle_function_call_request():
# Handles function call requests from the Deepgram STT service by executing each function in the request.
# Sends the results back to the STT service and handles errors by returning an error response.
async def handle_function_call_request(decoded, sts_ws):
    try:
        for function_call in decoded["functions"]:
            func_name = function_call["name"]
            func_id = function_call["id"]
            arguments = json.loads(function_call["arguments"])

            print(f"Function call: {func_name} (ID: {func_id}), arguments: {arguments}")

            result = execute_function_call(func_name, arguments)

            function_result = create_function_call_response(func_id, func_name, result)
            await sts_ws.send(json.dumps(function_result))
            print(f"Sent function result: {function_result}")

    except Exception as e:
        print(f"Error calling function: {e}")
        error_result = create_function_call_response(
            func_id if "func_id" in locals() else "unknown",
            func_name if "func_name" in locals() else "unknown",
            {"error": f"Function call failed with: {str(e)}"}
        )
        await sts_ws.send(json.dumps(error_result))


# The function handle_text_message():
# Processes text messages from the Deepgram STT service.
# Handles barge-in events by clearing the current message and dispatches function call requests to the appropriate handler.
async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)

    if decoded["type"] == "FunctionCallRequest":
        await handle_function_call_request(decoded, sts_ws)


#the function sts_sender():
# Sends audio chunks from the audio_queue to the Deepgram STT service via the WebSocket.
# Runs continuously to process queued audio data.
async def sts_sender(sts_ws, audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)


#The function sts_receiver():
# Listens for messages from the Deepgram STT service and processes them.
# Forwards text messages to the text message handler and sends media (audio) messages to the Twilio WebSocket,
# encoding audio as base64 and using the streamSid to identify the stream.
async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()

    async for message in sts_ws:
        if type(message) is str:
            print(message)
            decoded = json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        raw_mulaw = message

        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
        }

        await twilio_ws.send(json.dumps(media_message))


# The function twilio_receiver():
# Listens for messages from the Twilio WebSocket and processes start, media, and stop events.
# Extracts the streamSid from start events and buffers inbound media (audio) chunks using BUFFER_SIZE,
# forwarding them to the audio queue for further processing.
async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray(b"")

    async for message in twilio_ws:
        try:
            data = json.loads(message)
            event = data["event"]

            if event == "start":
                print("get our streamsid")
                start = data["start"]
                streamsid = start["streamSid"]
                streamsid_queue.put_nowait(streamsid)
            elif event == "connected":
                continue
            elif event == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if media["track"] == "inbound":
                    inbuffer.extend(chunk)
            elif event == "stop":
                break

            while len(inbuffer) >= BUFFER_SIZE:
                chunk = inbuffer[:BUFFER_SIZE]
                audio_queue.put_nowait(chunk)
                inbuffer = inbuffer[BUFFER_SIZE:]
        except:
            break

# The function twilio_handler():
# Main handler for Twilio WebSocket connections, coordinating with the Deepgram STT service.
# Creates audio and streamSid queues, sends the configuration to the STT service,
# and runs STT sender, receiver, and Twilio receiver tasks concurrently using asyncio.
# Closes the Twilio WebSocket after tasks complete.
async def twilio_handler(twilio_ws):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
        config_message = load_config()
        await sts_ws.send(json.dumps(config_message))

        await asyncio.wait(
            [
                asyncio.ensure_future(sts_sender(sts_ws, audio_queue)),
                asyncio.ensure_future(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
                asyncio.ensure_future(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
            ]
        )

        await twilio_ws.close()


# The function main():
# This is the main function that starts the Twilio handler
# It creates a WebSocket server that listens for incoming connections on localhost:5000
# It uses the websockets library to create the server and handle connections.
# It uses asyncio to run the server and handle connections concurrently.
# It is the entry point for the script and is called when the script is run.
# It uses the asyncio.run function to run the main function.
# It is used to start the server and handle incoming connections.
async def main():
    await websockets.serve(twilio_handler, "localhost", 5000)
    print("Started server.")
    await asyncio.Future()



# This is the entry point for the script
# It runs the main function using asyncio.run
# It is used to start the server and handle incoming connections.
# It is called when the script is run.
if __name__ == "__main__":
    asyncio.run(main())