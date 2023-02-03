import time
from collections import deque
import os
from dotenv import load_dotenv

import numpy as np
import pvporcupine
import pvcobra
import whisper
from pvrecorder import PvRecorder
import torch

load_dotenv()

porcupine = pvporcupine.create(
    access_key=os.environ.get("ACCESS_KEY"),
    keyword_paths=[os.environ.get("WAKE_WORD_MODEL_PATH")],
)

cobra = pvcobra.create(
    access_key=os.environ.get("ACCESS_KEY"),
)

recoder = PvRecorder(device_index=-1, frame_length=512)

# frame length = 512
# samples per frame = 16,000
# 1 sec = 16,000 / 512


class Transcriber:
    def __init__(self, model) -> None:
        print("loading model")
        # TODO: put model on GPU
        self.model = whisper.load_model(model)
        print("loading model finished")
        self.prompts = os.environ.get("WHISPER_INITIAL_PROMPT", "")
        print(f"Using prompts: {self.prompts}")

    def transcribe(self, frames):
        transcribe_start = time.time()
        samples = np.array(frames, np.int16).flatten().astype(np.float32) / 32768.0

        # audio = whisper.pad_or_trim(samples)
        # print(f"{transcribe_start} transcribing {len(frames)} frames.")
        # # audio = whisper.pad_or_trim(frames)

        # # make log-Mel spectrogram and move to the same device as the model
        # mel = whisper.log_mel_spectrogram(audio).to(self.model.device)

        # # decode the audio
        # options = whisper.DecodingOptions(fp16=False, language="english")
        # result = whisper.decode(self.model, mel, options)

        result = self.model.transcribe(
            audio=samples,
            language="en",
            fp16=False,
            initial_prompt=self.prompts,
        )

        # print the recognized text
        transcribe_end = time.time()
        # print(
        #     f"{transcribe_end} - {transcribe_end - transcribe_start}sec: {result.get('text')}",
        #     flush=True,
        # )
        return result.get("text", "speech not detected")


transcriber = Transcriber(os.environ.get("WHISPER_MODEL"))

sample_rate = 16000
frame_size = 512
vad_mean_probability_sensitivity = float(os.environ.get("VAD_SENSITIVITY"))

try:
    recoder.start()

    max_window_in_secs = 3
    window_size = sample_rate * max_window_in_secs
    samples = deque(maxlen=(window_size * 6))
    vad_samples = deque(maxlen=25)
    is_recording = False

    while True:
        data = recoder.read()
        vad_prob = cobra.process(data)
        vad_samples.append(vad_prob)
        # print(f"{vad_prob} - {np.mean(vad_samples)} - {len(vad_samples)}")
        if porcupine.process(data) >= 0:
            print(f"Detected wakeword")
            is_recording = True
            samples.clear()

        if is_recording:
            if (
                len(samples) < window_size
                or np.mean(vad_samples) >= vad_mean_probability_sensitivity
            ):
                samples.extend(data)
                print(f"listening - samples: {len(samples)}")
            else:
                print("is_recording: False")
                print(transcriber.transcribe(samples))
                is_recording = False
except KeyboardInterrupt:
    recoder.stop()
finally:
    porcupine.delete()
    recoder.delete()
    cobra.delete()
