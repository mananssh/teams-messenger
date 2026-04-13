import json
import re


def extract_json(text: str):
    """
    Extract JSON from LLM response safely
    """
    try:
        # ✅ Case 1: direct valid JSON
        return json.loads(text)

    except:
        pass

    try:
        # ✅ Case 2: extract JSON inside ```json ... ```
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)

    except:
        pass

    try:
        # ✅ Case 3: extract first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)

    except Exception as e:
        print("❌ JSON extraction failed:", e)

    return None


def parse_llm_output(response_text: str):
    print("⚙️ Parsing LLM output...")

    data = extract_json(response_text)

    if data is None:
        print("❌ FINAL JSON PARSE FAILED")
    else:
        print("✅ JSON parsed successfully")

    return data