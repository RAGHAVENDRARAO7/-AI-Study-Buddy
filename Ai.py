"""
AI Study Buddy - Streamlit app

Single-file app. Features:
1) Input student question (English or Telugu)
2) Uses OpenAI Responses API to generate:
   - Simple English explanation
   - Simple Telugu explanation
   - 3 practice questions + answers
   - If the input is a math/stat problem: step-by-step solution
3) Displays results
4) Optional TTS via gTTS (English 'en', Telugu 'te')
5) Clear comments and instructions

Requirements:
    pip install streamlit openai gtts python-dotenv

Run:
    export OPENAI_API_KEY="sk-..."
    streamlit run app.py
    (or place OPENAI_API_KEY in a .env file)
"""

import os
import json
import re
import tempfile
from io import BytesIO

import streamlit as st

# Use OpenAI's official Python client (responses API)
# This is the modern client interface: `from openai import OpenAI`
# (Make sure openai package is installed: pip install openai)
from openai import OpenAI

# gTTS for offline-ish TTS option (optional)
# Install: pip install gTTS
from gtts import gTTS

# Optional: load .env for local dev convenience
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; not required in production
    pass

st.set_page_config(page_title="AI Study Buddy", layout="centered")

st.title("📚 AI Study Buddy — Telugu + English")
st.markdown(
    """
A helper for Telugu & English-medium students: ask a concept question or a math/stat problem.
- Explains the concept in **simple English** and **simple Telugu**
- Generates **3 practice questions with answers**
- **If** it detects a math/stat problem, you'll also get a step-by-step solution
- Optional: convert the explanations to speech (gTTS)
"""
)

# ---- Sidebar: settings ----
st.sidebar.header("Settings")
model = st.sidebar.selectbox(
    "OpenAI model (Responses API)",
    options=["gpt-4o-mini", "gpt-4o", "gpt-4o-mini-preview"],
    index=0,
    help="Pick a model you have access to. The app uses OpenAI Responses API."
)
use_tts = st.sidebar.checkbox("Enable TTS (gTTS) for explanations", value=False)
# Allow user to select which language audio to produce
tts_lang_choices = []
if use_tts:
    tts_en = st.sidebar.checkbox("English audio", value=True)
    tts_te = st.sidebar.checkbox("Telugu audio", value=True)
else:
    tts_en = False
    tts_te = False

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Set your OpenAI API key in the environment variable `OPENAI_API_KEY` (or a `.env` file)."
)

# ---- Main: input box ----
question = st.text_area(
    "Enter the student's question here (English or Telugu):",
    height=140,
    placeholder="e.g., Explain mean, median, mode with an example.  OR  సమీకరణం 2x + 3 = 11 ను పరిష్కరించండి",
)

if not os.getenv("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"):
    st.warning(
        "OPENAI_API_KEY environment variable not found. "
        "Set it before running (export OPENAI_API_KEY='sk-...')."
    )

# Generate button
if st.button("Generate explanation & practice →"):
    if not question.strip():
        st.warning("Please type a question first.")
    else:
        # Call OpenAI Responses API
        with st.spinner("Contacting OpenAI and generating explanation..."):
            try:
                # Instantiate OpenAI client (reads OPENAI_API_KEY from env by default)
                client = OpenAI(api_key=os.getenv("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"))

                # Clear instruction: ask model to return JSON only.
                # The Responses API accepts "instructions" and "input".
                instructions = """
You are "AI Study Buddy", a friendly tutor for Telugu and English medium students.
Produce a JSON object and return ONLY valid JSON (nothing else). The JSON must have these keys:

{
  "explanation_en": "<Simple English explanation - 3-6 short sentences>",
  "explanation_te": "<Simple Telugu explanation - 3-6 short sentences>",
  "practice_questions": [
      {"q_en":"<question in simple English>", "a_en":"<answer in English>",
       "q_te":"<same question in Telugu>", "a_te":"<answer in Telugu>"},
      ... (3 items)
  ],
  "math_solution": null OR {
      "is_math": true,
      "problem": "<the original math/stat problem>",
      "steps": ["step 1", "step 2", ...],
      "final_answer": "<final numeric or symbolic answer>"
  }
}

If the user's input is a math or statistics problem (algebra, calculus, probability, mean, variance, equation solving, integrals, derivatives, hypothesis testing, combinatorics, etc.) then set math_solution to the object above and produce a clear step-by-step solution (each step a short sentence). Otherwise set math_solution to null. Keep all text short and simple for school students.
"""

                # Call the Responses API
                response = client.responses.create(
                model=model,
                instructions=instructions,
                input=question,
           temperature=0.2,
    # If available, you can uncomment to cap output length:
    # output_tokens=800,
)

                # The client.responses.create() typically provides .output_text with concatenated output
                raw_text = getattr(response, "output_text", None)
                if raw_text is None:
                    # fallback: try string conversion
                    raw_text = str(response)

                # Attempt to extract JSON substring robustly (in case assistant wraps text)
                json_text = None
                # Try to find the first { ... } block
                m = re.search(r"\{(?:.|\s)*\}\s*$", raw_text.strip())
                if m:
                    json_text = m.group(0)
                else:
                    # try find first { ... } anywhere
                    m2 = re.search(r"\{(?:.|\s)*\}", raw_text)
                    if m2:
                        json_text = m2.group(0)

                parsed = None
                if json_text:
                    try:
                        parsed = json.loads(json_text)
                    except Exception as e:
                        # If JSON parse fails, we'll show raw output below
                        parsed = None

                # If we couldn't parse JSON, show raw response (but try to salvage useful sections)
                if not parsed:
                    st.error(
                        "Could not parse JSON from the model response. Showing raw output below — consider tweaking the model or instructions."
                    )
                    st.subheader("Raw model response")
                    st.code(raw_text, language="json")
                else:
                    # Display outputs
                    st.subheader("Explanation — English")
                    st.write(parsed.get("explanation_en", "No English explanation returned."))
                    st.subheader("Explanation — Telugu")
                    st.write(parsed.get("explanation_te", "No Telugu explanation returned."))

                    st.subheader("Practice questions (3)")
                    pqs = parsed.get("practice_questions", [])
                    if not pqs:
                        st.write("No practice questions returned.")
                    else:
                        for i, pq in enumerate(pqs, start=1):
                            st.markdown(f"**Q{i} (EN):** {pq.get('q_en','')}")
                            st.markdown(f"**A{i} (EN):** {pq.get('a_en','')}")
                            st.markdown(f"**Q{i} (TE):** {pq.get('q_te','')}")
                            st.markdown(f"**A{i} (TE):** {pq.get('a_te','')}")
                            st.markdown("---")

                    # Math solution block (if present)
                    ms = parsed.get("math_solution")
                    if ms:
                        if isinstance(ms, dict) and ms.get("is_math"):
                            st.subheader("Math / Statistics Step-by-step Solution")
                            st.write("Problem: ", ms.get("problem", question))
                            steps = ms.get("steps", [])
                            if steps:
                                for idx, step in enumerate(steps, start=1):
                                    st.markdown(f"**Step {idx}:** {step}")
                            final = ms.get("final_answer")
                            if final is not None:
                                st.markdown(f"**Final Answer:** {final}")
                        else:
                            # Explicitly null or not math
                            st.info("No math steps required for this question.")

                    # TTS (gTTS) if requested
                    if use_tts and (tts_en or tts_te):
                        st.subheader("Audio (gTTS)")

                        # Helper to create mp3 bytes using gTTS
                        def make_gtts_bytes(text: str, lang: str = "en") -> bytes:
                            if not text or text.strip() == "":
                                return b""
                            mp3_fp = BytesIO()
                            try:
                                tts = gTTS(text=text, lang=lang)
                                tts.write_to_fp(mp3_fp)
                                mp3_fp.seek(0)
                                return mp3_fp.read()
                            except Exception as e:
                                # gTTS may fail for long text or unsupported lang
                                st.warning(f"gTTS error for lang={lang}: {e}")
                                return b""

                        # Build combined audio text (short) for each selected lang
                        if tts_en:
                            text_en = parsed.get("explanation_en", "").strip()
                            if text_en:
                                st.write("English audio:")
                                en_bytes = make_gtts_bytes(text_en, lang="en")
                                if en_bytes:
                                    st.audio(en_bytes, format="audio/mp3")
                                    st.download_button(
                                        "Download English MP3",
                                        data=en_bytes,
                                        file_name="explanation_en.mp3",
                                        mime="audio/mpeg",
                                    )
                                else:
                                    st.write("Could not generate English audio.")
                        if tts_te:
                            text_te = parsed.get("explanation_te", "").strip()
                            if text_te:
                                st.write("Telugu audio:")
                                te_bytes = make_gtts_bytes(text_te, lang="te")
                                if te_bytes:
                                    st.audio(te_bytes, format="audio/mp3")
                                    st.download_button(
                                        "Download Telugu MP3",
                                        data=te_bytes,
                                        file_name="explanation_te.mp3",
                                        mime="audio/mpeg",
                                    )
                                else:
                                    st.write("Could not generate Telugu audio.")
            except Exception as e:
                st.exception(f"Error while calling OpenAI: {e}")
