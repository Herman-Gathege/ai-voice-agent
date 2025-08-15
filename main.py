# main.py
# This script sets up a WebSocket server that connects to Twilio and Deepgram for real-time audio processing.
# It handles audio streaming, function calls, and text-to-speech conversion using ElevenLabs API.
# The server listens for incoming audio from Twilio, processes it with Deepgram, and responds with audio or text messages.
# It also supports function calls defined in the `pharmacy_functions` module.
import asyncio
import base64
import json
# i have added requests importaion
import websockets
import requests
import os
from dotenv import load_dotenv
from pharmacy_functions import FUNCTION_MAP
import requests
import io
from pydub import AudioSegment

load_dotenv()
#i have added 11labs key
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
#i haave picked a voice id from 11labs
VOICE_ID = "pNInz6obpgDQGcFmaJgB"


#i have added a function to convert text to speech using ElevenLabs API
# This function converts text to μ-law audio format suitable for Twilio
# It uses the ElevenLabs API to generate the audio and then processes it to the required format
# def elevenlabs_tts_mulaw(text):
#     url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

#     headers = {
#         "Accept": "audio/mpeg",
#         "Content-Type": "application/json",
#         "xi-api-key": ELEVENLABS_API_KEY
#     }

#     data = {
#         "text": text,
#         "model_id": "eleven_multilingual_v2",
#         "voice_settings": {
#             "stability": 0.4,
#             "similarity_boost": 0.8
#         }
#     }

#     r = requests.post(url, headers=headers, json=data)
#     r.raise_for_status()

#     # Convert MP3 to μ-law 8000Hz (Twilio-ready)
#     audio = AudioSegment.from_file(io.BytesIO(r.content), format="mp3")
#     mulaw_audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2) \
#         .set_sample_width(1)  # μ-law uses 8-bit per sample
#     return mulaw_audio.raw_data


def sts_connect():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise Exception("DEEPGRAM_API_KEY not found")

    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws


def load_config():
    with open("config.json", "r") as f:
        config = json.load(f)
    # Inject ElevenLabs API key dynamically
    if "speak" in config["agent"] and "endpoint" in config["agent"]["speak"]:
        config["agent"]["speak"]["endpoint"]["headers"]["xi-api-key"] = ELEVENLABS_API_KEY
    return config


async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded["type"] == "UserStartedSpeaking":
        clear_message = {
            "event": "clear",
            "streamSid": streamsid
        }
        await twilio_ws.send(json.dumps(clear_message))


def execute_function_call(func_name, arguments):
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**arguments)
        print(f"Function call result: {result}")
        return result
    else:
        result = {"error": f"Unknown function: {func_name}"}
        print(result)
        return result


def create_function_call_response(func_id, func_name, result):
    return {
        "type": "FunctionCallResponse",
        "id": func_id,
        "name": func_name,
        "content": json.dumps(result)
    }


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


async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)

    if decoded["type"] == "FunctionCallRequest":
        await handle_function_call_request(decoded, sts_ws)


async def sts_sender(sts_ws, audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)


# async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
#     print("sts_receiver started")
#     streamsid = await streamsid_queue.get()

#     async for message in sts_ws:
#         if type(message) is str:
#             print(message)
#             decoded = json.loads(message)
#             await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
#             continue

#         raw_mulaw = message

#         media_message = {
#             "event": "media",
#             "streamSid": streamsid,
#             "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
#         }

#         await twilio_ws.send(json.dumps(media_message))

async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()

    async for message in sts_ws:
        if isinstance(message, str):
            print(message)
            decoded = json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        # Binary message: This is the TTS audio from Deepgram (via ElevenLabs)
        raw_mulaw = message
        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
        }
        await twilio_ws.send(json.dumps(media_message))



async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    print("sts_receiver started")
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray(b"")

    async for message in twilio_ws:
        if isinstance(message, str):
            print(f"Text message: {message}")
        else:
            print(f"Audio chunk received: {len(message)} bytes")
        
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


async def twilio_handler(twilio_ws):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
        config_message = load_config()
        print(json.dumps(config_message, indent=2))
        await sts_ws.send(json.dumps(config_message))

        await asyncio.wait(
            [
                asyncio.ensure_future(sts_sender(sts_ws, audio_queue)),
                asyncio.ensure_future(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
                asyncio.ensure_future(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
            ]
        )

        await twilio_ws.close()


async def main():
    await websockets.serve(twilio_handler, "localhost", 5000)
    print("Started server.")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())