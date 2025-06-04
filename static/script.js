const socket = io();

const micButton = document.getElementById("mic-button");
const transcriptionDiv = document.getElementById("transcription");

let audioContext;
let processor;
let input;
let globalStream;
let isRecording = false;

// Debug socket connection
socket.on('connect', () => {
  console.log('Socket.IO connected with id:', socket.id);
});

socket.on('connect_error', (error) => {
  console.error('Socket.IO connection error:', error);
  transcriptionDiv.innerText = "[Socket.IO connection error]";
});

micButton.addEventListener("click", async () => {
  console.log("Mic button clicked. isRecording:", isRecording);
  if (!isRecording) {
    micButton.classList.add("recording");
    transcriptionDiv.innerText = "Listening...";
    try {
      await startRecording();
      console.log("Recording started.");
    } catch (err) {
      console.error("Error in startRecording:", err);
      transcriptionDiv.innerText = "Error accessing microphone: " + err.message;
      micButton.classList.remove("recording");
      isRecording = false;
      return;
    }
  } else {
    micButton.classList.remove("recording");
    stopRecording();
    transcriptionDiv.innerText = "Stopped";
    console.log("Recording stopped.");
  }
  isRecording = !isRecording;
});

async function startRecording() {
  // Ask for mic permission and get audio stream
  globalStream = await navigator.mediaDevices.getUserMedia({ audio: true });

  // Create AudioContext with 16kHz sample rate
  audioContext = new AudioContext({ sampleRate: 16000 });

  // Resume AudioContext if suspended (required by some browsers)
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
    console.log("AudioContext resumed.");
  }

  input = audioContext.createMediaStreamSource(globalStream);

  processor = audioContext.createScriptProcessor(4096, 1, 1);

  processor.onaudioprocess = (e) => {
    const floatSamples = e.inputBuffer.getChannelData(0);
    const int16Samples = convertFloat32ToInt16(floatSamples);
    const base64Data = arrayBufferToBase64(int16Samples.buffer);

    socket.emit("audio_chunk", { audio_data: base64Data });
  };

  input.connect(processor);
  processor.connect(audioContext.destination);

  socket.emit("start_transcription");
}

function stopRecording() {
  socket.emit("stop_transcription");

  if (processor) {
    processor.disconnect();
    processor = null;
  }
  if (input) {
    input.disconnect();
    input = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (globalStream) {
    globalStream.getTracks().forEach(track => track.stop());
    globalStream = null;
  }
}

// Helper to convert Float32 [-1..1] audio to Int16 PCM
function convertFloat32ToInt16(buffer) {
  let l = buffer.length;
  const buf = new Int16Array(l);
  while (l--) {
    let s = Math.max(-1, Math.min(1, buffer[l]));
    buf[l] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return buf;
}

// Helper to convert ArrayBuffer to base64 string
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let b of bytes) {
    binary += String.fromCharCode(b);
  }
  return btoa(binary);
}

// Listen for transcripts from server
socket.on('transcript_update', (data) => {
  transcriptionDiv.innerText = data.transcript + (data.is_final ? ' (final)' : '...');
});

socket.on('transcript_error', (data) => {
  transcriptionDiv.innerText = "[Error] " + data.error;
});