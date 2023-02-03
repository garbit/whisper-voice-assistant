import pyaudio
import wave
import whisper
import time
import sys
import numpy as np


class Transcriber:
    def __init__(self, wav_file, model) -> None:
        self.model = whisper.load_model(model)
        self.wav_file = wav_file
        self.text = ""

    def transcribe(self, frames):
        # load audio and pad/trim it to fit 30 seconds
        # audio = whisper.load_audio(self.wav_file)
        audio = whisper.pad_or_trim(np.array(frames))

        # make log-Mel spectrogram and move to the same device as the model
        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)

        # decode the audio
        options = whisper.DecodingOptions(fp16=False, language="english")
        result = whisper.decode(self.model, mel, options)

        # print the recognized text
        self.text += result.text
        print("result:", self.text)


class AudioRecorder:
    def __init__(self, input_device_index) -> None:
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.RECORD_SECONDS = 3
        self._pa = pyaudio.PyAudio()
        self.device_index = input_device_index
        self.stream = None
        self.frames = np.array([], dtype=np.float16)
        self.filename = "output.wav"
        self.transcriber = Transcriber(self.filename, "medium.en")
        self.wf = self.init_file()

    def init_file(self):
        wf = wave.open(self.filename, "wb")
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self._pa.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        return wf

    def record(self):
        self.stream = self._pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=self.device_index,
            stream_callback=self.get_callback(),
        )

    def save_frames(self):
        self.wf.writeframes(b"".join(self.frames))

        print(f"Saved {len(self.frames)} frames")

    def stop_recording(self):
        self.stream.close()
        self._pa.terminate()
        self.wf.close()

    def get_callback(self):
        def callback(in_data, frame_count, time_info, status):
            self.frames = np.append(
                self.frames, np.frombuffer(in_data, dtype=np.float16)
            )
            self.wf.writeframes(in_data)
            if (len(self.frames)) >= (self.CHUNK * self.RECORD_SECONDS):
                # self.frames = []
                self.transcriber.transcribe(self.frames)
            return in_data, pyaudio.paContinue

        return callback


def available_devices():
    pa = pyaudio.PyAudio()
    info = pa.get_host_api_info_by_index(0)
    numdevices = info.get("deviceCount")

    devices = {}

    for i in range(0, numdevices):
        if (
            pa.get_device_info_by_host_api_device_index(0, i).get("maxInputChannels")
        ) > 0:
            devices[
                i
            ] = f"Input Device id {i}, {pa.get_device_info_by_host_api_device_index(0, i).get('name')}"

    return devices


devices = available_devices()
for d in devices.items():
    print(d)

device_index = int(input("Select Input Device\n"))
print(f"Selected device {device_index} - {devices[device_index]}")

print("Initializing Audio Recorder")
audio_recorder = AudioRecorder(device_index)

print("Recording...")
audio_recorder.record()

loop_count = 0
while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped recording")
        audio_recorder.stop_recording()
        sys.exit()
