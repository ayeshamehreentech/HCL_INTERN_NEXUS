import hashlib
import os

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from groq import Groq

from database.meetings import (
    list_meetings,
    mark_joined,
    save_meeting_transcription,
)


load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
TEAMS_MEETING_LINK = os.getenv("TEAMS_MEETING_LINK", "")


def get_client():
    return Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def transcribe_meeting_audio(audio_bytes):
    client = get_client()
    if not client:
        st.error("GROQ_API_KEY is missing.")
        return None
    try:
        options = {
            "file": ("meeting_audio.wav", audio_bytes),
            "model": "whisper-large-v3-turbo",
        }
        return client.audio.transcriptions.create(**options).text
    except Exception as error:
        st.error(f"Transcription failed: {error}")
        return None


def _chat(prompt, system_message):
    client = get_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as error:
        st.error(f"AI processing failed: {error}")
        return None


def summarize_meeting(transcript):
    return _chat(
        "Summarize this internship meeting with: summary, topics discussed, "
        "important points, tasks, deadlines, questions, and next steps.\n\n"
        + transcript,
        "You are a professional meeting summarizer.",
    )


def romanize_transcript(transcript):
    """Keep English as-is and transliterate Hindi into Roman English."""
    return _chat(
        "Detect the language of this meeting transcript automatically. "
        "Keep English sentences in English. If Hindi or another Indic language "
        "is present, write it using Roman English letters, not native script. "
        "Do not summarize, translate the meaning, or add explanations. "
        "For example, 'नमस्ते, मैं आयशा हूँ' becomes "
        "'Namaste, main Ayesha hoon'. Return only the complete transcript.\n\n"
        + transcript,
        "You prepare accurate bilingual meeting transcripts in Roman English.",
    )


def process_recording(recorded_audio):
    audio_bytes = recorded_audio.getvalue()
    recording_hash = hashlib.sha256(audio_bytes).hexdigest()
    if st.session_state.get("meeting_recording_hash") == recording_hash:
        return

    st.session_state.meeting_recording_hash = recording_hash
    with st.spinner("Transcribing meeting..."):
        transcript = transcribe_meeting_audio(audio_bytes)
    if not transcript:
        return

    with st.spinner("Converting Hindi to Roman English..."):
        roman_transcript = romanize_transcript(transcript)
    transcript = roman_transcript or transcript

    with st.spinner("Creating meeting summary..."):
        summary = summarize_meeting(transcript)
    st.session_state.meeting_transcript = transcript
    st.session_state.meeting_summary = summary or "Summary could not be generated."
    save_meeting_transcription(
        st.session_state.user_id,
        transcript,
        st.session_state.meeting_summary,
    )
    st.success("Recording transcribed and summarized.")


def render_meetings():
    st.subheader("📅 Internship Meetings")
    st.info("Regular meetings: Tuesday & Thursday, 4:00 PM – 4:30 PM")

    meetings = list_meetings(
        st.session_state.get("user_id"),
        role="student",
    )
    for meeting in meetings:
        with st.container(border=True):
            st.markdown(f"### {meeting.get('title', 'Internship Meeting')}")
            st.write(f"Date: {meeting.get('meeting_date', 'To be confirmed')}")
            st.write(f"Time: {meeting.get('meeting_time', 'To be confirmed')}")
            if meeting.get("meeting_link"):
                if st.button(
                    "🔗 Join Meeting",
                    key=f"student_join_{meeting['id']}",
                    use_container_width=True,
                ):
                    mark_joined(meeting["id"])
                    st.session_state["active_meeting_link"] = meeting["meeting_link"]
                    st.rerun()

    active_link = st.session_state.get("active_meeting_link", TEAMS_MEETING_LINK)
    if active_link:
        components.iframe(active_link, height=520, scrolling=True)
    else:
        st.warning("Add TEAMS_MEETING_LINK to .env to show the meeting here.")

    st.divider()
    st.subheader("🎙️ Meeting Recording")
    st.caption(
        "Language is detected automatically. Hindi is written in Roman English "
        "after transcription."
    )
    recorded_audio = st.audio_input(
        "Record this meeting. Processing starts when you stop recording.",
        key="meeting_audio_recorder",
    )
    if recorded_audio:
        process_recording(recorded_audio)

    transcript = st.session_state.get("meeting_transcript")
    if transcript:
        st.markdown("### 📄 Transcript")
        st.text_area(
            "Transcript",
            transcript,
            height=300,
            key="meeting_transcript_display",
        )

    if st.session_state.get("meeting_summary"):
        st.markdown("### 📋 AI Meeting Summary")
        st.markdown(st.session_state.meeting_summary)
