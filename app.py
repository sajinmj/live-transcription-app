import os
import queue
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from google.cloud import speech
import base64

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Google Cloud Speech Client
client = speech.SpeechClient()

# Audio config for Google Cloud STT
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="en-US",
    enable_automatic_punctuation=True,
)

streaming_config = speech.StreamingRecognitionConfig(
    config=config,
    interim_results=True,
)

# Dictionary to hold audio queues per client
audio_queues = {}

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("connect")
def on_connect(auth):
    print("Client connected:", request.sid)
    audio_queues[request.sid] = queue.Queue()

@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected:", request.sid)
    if request.sid in audio_queues:
        del audio_queues[request.sid]

@socketio.on("audio_chunk")
def on_audio_chunk(data):
    audio_content = base64.b64decode(data["audio_data"])
    q = audio_queues.get(request.sid)
    if q:
        q.put(audio_content)

# ✅ FIXED: Removed incorrect config yield
def request_generator(q):
    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

def listen_print_loop(responses, client_id):
    try:
        for response in responses:
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript
            is_final = result.is_final

            socketio.emit('transcript_update', {
                'transcript': transcript,
                'is_final': is_final
            }, room=client_id)

            if is_final:
                print(f"Final transcript from {client_id}: {transcript}")
    except Exception as e:
        print(f"Error in listen_print_loop: {e}")
        socketio.emit('transcript_error', {'error': str(e)}, room=client_id)

@socketio.on("start_transcription")
def start_transcription():
    client_id = request.sid
    print(f"Starting transcription for client {client_id}")
    q = audio_queues.get(client_id)

    def background_thread():
        requests = request_generator(q)
        # ✅ FIXED: Pass streaming_config here (not in the generator)
        responses = client.streaming_recognize(config=streaming_config, requests=requests)
        listen_print_loop(responses, client_id)

    thread = threading.Thread(target=background_thread)
    thread.start()

@socketio.on("stop_transcription")
def stop_transcription():
    client_id = request.sid
    print(f"Stopping transcription for client {client_id}")
    q = audio_queues.get(client_id)
    if q:
        q.put(None)

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
