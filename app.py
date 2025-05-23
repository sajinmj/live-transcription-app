from flask import Flask, render_template, request, redirect, url_for
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_transcript', methods=['POST'])
def save_transcript():
    data = request.get_json()
    transcript = data.get("transcript", "")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"transcript_{timestamp}.txt"

    os.makedirs("transcripts", exist_ok=True)
    filepath = os.path.join("transcripts", filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(transcript.strip())

    return filename  

@app.route('/report/<filename>')
def show_report(filename):
    transcript_dir = "transcripts"
    filepath = os.path.join(transcript_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return render_template("report_view.html", filename=filename, content=content)
    else:
        return "Report not found", 404


@app.route('/reports')
def list_reports():
    transcript_dir = "transcripts"
    os.makedirs(transcript_dir, exist_ok=True)
    files = sorted(os.listdir(transcript_dir), reverse=True)  
    return render_template('report_list.html', files=files)


if __name__ == '__main__':
    app.run(debug=True)
