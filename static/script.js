const DEEPGRAM_API_KEY = 'a03a9bd3623eb702599bd7b7f4fdff10d7592f17'; // API key

const micButton = document.getElementById("mic-button");
const transcriptionDiv = document.getElementById("transcription");

let mediaRecorder;
let deepgramSocket;
let isRecording = false;

micButton.addEventListener("click", async () => {
  if (!isRecording) {
    micButton.classList.add("recording");
    transcriptionDiv.innerText = "Listening...";
    await startRecording();
  } else {
    micButton.classList.remove("recording");
    stopRecording();
  }
  isRecording = !isRecording;
});

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

  deepgramSocket = new WebSocket(`wss://api.deepgram.com/v1/listen`, [
    "token",
    DEEPGRAM_API_KEY
  ]);

  deepgramSocket.onopen = () => {
    mediaRecorder.start(250);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0 && deepgramSocket.readyState === WebSocket.OPEN) {
        deepgramSocket.send(event.data);
      }
    };
  };

  deepgramSocket.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.channel && data.channel.alternatives[0]) {
      const transcript = data.channel.alternatives[0].transcript;
      if (transcript) {
        transcriptionDiv.innerText = transcript;
      }
    }
  };
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (deepgramSocket && deepgramSocket.readyState === WebSocket.OPEN) {
    deepgramSocket.close();
  }
}
