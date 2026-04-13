import whisper


def transcribe_audio(file_path: str) -> str:
    try:
        print("Loading Whisper model...")

        # load model (downloads once)
        model = whisper.load_model("base")

        print("Transcribing audio...")

        result = model.transcribe(file_path)

        return result["text"]

    except Exception as e:
        print("❌ ERROR:", e)
        return None