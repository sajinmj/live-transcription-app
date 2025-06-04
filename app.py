import os
import queue
import threading
from flask import Flask, render_template, request, abort
from flask_socketio import SocketIO, emit
from google.cloud import speech
import base64
from datetime import datetime
import spacy
import dateparser

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

client = speech.SpeechClient()

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

audio_queues = {}
final_transcripts = {}

nlp = spacy.load("en_core_web_sm")
SYMPTOMS_KEYWORDS = ['pain', 'fever', 'cough', 'fatigue', 'vomiting', 'headache', 'nausea', 'rash']

def extract_keywords(text):
    doc = nlp(text)
    times = []
    symptoms = []
    diseases = [] 

    for ent in doc.ents:
        if ent.label_ in ["TIME", "DATE"]:
            parsed_time = dateparser.parse(ent.text)
            if parsed_time:
                times.append(ent.text)

    for token in doc:
        if token.lemma_.lower() in SYMPTOMS_KEYWORDS:
            symptoms.append(token.text)

    return {
        "times": list(set(times)),
        "symptoms": list(set(symptoms)),
        "diseases": list(set(diseases))
    }

@app.route("/")
def index():
    return render_template("index.html")

def get_report_files():
    report_dir = "reports"
    file_list = []
    for root, _, files in os.walk(report_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, report_dir).replace("\\", "/")
            file_list.append(rel_path)
    return file_list

@app.route("/reports")
def report_list():
    os.makedirs("reports", exist_ok=True)
    files = get_report_files()
    return render_template("report_list.html", files=files)

@app.route("/report/<path:filename>")
def view_report(filename):
    if ".." in filename or filename.startswith("/"):
        abort(400, "Invalid filename")

    filepath = os.path.join("reports", filename)
    if not os.path.isfile(filepath):
        return f"Report {filename} not found.", 404

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        keywords = extract_keywords(content)
        return render_template("report.html", filename=filename, content=content, keywords=keywords)
    except PermissionError:
        return "Permission denied when accessing the report.", 403
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@socketio.on("connect")
def on_connect(auth):
    print("Client connected:", request.sid)
    audio_queues[request.sid] = queue.Queue()

@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected:", request.sid)
    audio_queues.pop(request.sid, None)
    final_transcripts.pop(request.sid, None)

@socketio.on("audio_chunk")
def on_audio_chunk(data):
    audio_content = base64.b64decode(data["audio_data"])
    q = audio_queues.get(request.sid)
    if q:
        q.put(audio_content)

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

            socketio.emit('transcript_update', {'transcript': transcript, 'is_final': is_final})


            if is_final:
                print(f"Final transcript from {client_id}: {transcript}")
                final_transcripts.setdefault(client_id, []).append(transcript)
    except Exception as e:
        print(f"Error in listen_print_loop: {e}")
        socketio.emit('transcript_error', {'error': str(e)}, to=client_id)

@socketio.on("start_transcription")
def start_transcription():
    client_id = request.sid
    print(f"Starting transcription for client {client_id}")
    q = audio_queues.get(client_id)

    def background_thread():
        requests = request_generator(q)
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

    if client_id in final_transcripts:
        now = datetime.now()
        dir_path = os.path.join("reports", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        os.makedirs(dir_path, exist_ok=True)

        time_str = now.strftime("%H-%M-%S")
        filename = f"{time_str}_{client_id}.txt"
        filepath = os.path.join(dir_path, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(final_transcripts[client_id]))

        print(f"Transcript saved to {filepath}")
        del final_transcripts[client_id]

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)