import os
import google.generativeai as genai
from dotenv import load_dotenv
from app.llm.prompt_template import SYSTEM_PROMPT   # ✅ import

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def generate_summary(transcript: str) -> str:
    try:
        print("Sending transcript to Gemini...")

        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={
                "temperature": 0.2
            }
        )

        # ✅ User input separated cleanly
        user_prompt = f"""
Meeting ID: meeting_001

Participant Registry:
{{
  "p1": "Ram",
  "p2": "Meera",
  "p3": "Karen",
  "p4": "Manoj",
  "p5": "Jack"
}}

Transcript:
{transcript}
"""

        response = model.generate_content([
            SYSTEM_PROMPT,
            user_prompt
        ])

        return response.text

    except Exception as e:
        print("❌ ERROR:", e)
        return None