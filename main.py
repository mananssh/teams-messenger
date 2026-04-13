import json
from app.transcription.whisper_service import transcribe_audio
from app.llm.gemini_service import generate_summary
from app.parser.json_parser import parse_llm_output
from app.dispatcher.dispatcher import dispatch_actions


def main():
    audio_path = "data/input_audio/sample.mp3"

    # 🔹 Step 1: Transcription
    print("\n🎧 Step 1: Transcribing audio...\n")
    transcript = transcribe_audio(audio_path)

    if not transcript:
        print("❌ Transcription failed")
        return

    # 🔹 Step 2: Gemini Processing
    print("\n🧠 Step 2: Sending to Gemini...\n")
    llm_output = generate_summary(transcript)

    if not llm_output:
        print("❌ Gemini response failed")
        return

    print("\n=== RAW LLM OUTPUT ===\n")
    print(llm_output)

    # 🔹 Step 3: Parse JSON
    print("\n⚙️ Step 3: Parsing output...\n")
    parsed_data = parse_llm_output(llm_output)

    if not parsed_data:
        print("❌ Parsing failed")
        return

    # 🔹 Step 4: Pretty Print
    print("\n✅ === CLEAN PARSED JSON ===\n")
    print(json.dumps(parsed_data, indent=4, ensure_ascii=False))

    # 🔹 Optional: Show only action items
    print("\n📌 === ACTION ITEMS ===\n")
    print(json.dumps(parsed_data.get("action_items", []), indent=4))

    # 🔹 Step 5: Dispatch actions
    dispatch_actions(parsed_data)


if __name__ == "__main__":
    main()