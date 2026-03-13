import streamlit as st
st.title("Cover Letter Generator")

import uuid
import ollama
from paddleocr import PaddleOCR
from PIL import Image
import io
import numpy as np
from docx import Document
import re
import warnings

warnings.filterwarnings("ignore")

# ---------- LOAD OCR ----------
@st.cache_resource
def load_ocr():
    try:
        return PaddleOCR(lang='en', use_angle_cls=True, show_log=False)
    except:
        return None

ocr_reader = load_ocr()

# ---------- OCR ----------
def extract_text_from_image(image_bytes):
    if not ocr_reader:
        return ""

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = image.resize((1200, int(image.size[1]*(1200/image.size[0]))))
    result = ocr_reader.ocr(np.array(image), cls=True)

    text = []
    for line in result[0]:
        text.append(line[1][0])

    return " ".join(text)

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

# ---------- SESSION ----------
if "conversations" not in st.session_state:
    st.session_state.conversations = []

if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None

if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

# ---------- NEW CHAT ----------
def new_conversation():
    conv_id = str(uuid.uuid4())
    st.session_state.conversations.append({
        "id": conv_id,
        "title": f"Chat {len(st.session_state.conversations)+1}",
        "messages": []
    })
    st.session_state.current_conv_id = conv_id
    st.session_state.resume_text = ""

if not st.session_state.conversations:
    new_conversation()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("Chat History")
    if st.button("➕ New Chat"):
        new_conversation()
        st.rerun()

    for conv in st.session_state.conversations:
        if st.button(conv["title"], key=conv["id"]):
            st.session_state.current_conv_id = conv["id"]
            st.rerun()

current_conv = next(
    (c for c in st.session_state.conversations if c["id"] == st.session_state.current_conv_id),
    None
)

# ---------- SHOW CHAT ----------
for msg in current_conv["messages"]:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.write(msg["content"])
        if msg.get("file"):
            st.download_button(
                label=f"Download {msg.get('file_name')}",
                data=msg["file"],
                file_name=msg.get("file_name"),
                key=str(uuid.uuid4())
            )

# ---------- USER MESSAGE INPUT (BOTTOM) ----------
user_input = st.chat_input("Type job role + company")

# ---------- FILE UPLOAD (JUST ABOVE CHAT INPUT STYLE) ----------
uploaded_file = st.file_uploader(
    "Upload Resume (DOCX or Clear Image)",
    type=["docx", "txt", "png", "jpg", "jpeg"],
    key=f"uploader_{st.session_state.upload_key}"
)

# ---------- FILE UPLOAD LOGIC ----------
if uploaded_file:
    file_bytes = uploaded_file.getvalue()

    current_conv["messages"].append({
        "role": "user",
        "content": f"📎 File attached: {uploaded_file.name}"
    })

    if uploaded_file.type.startswith("image"):
        with st.spinner("Reading image..."):
            text = extract_text_from_image(file_bytes)
            st.session_state.resume_text = clean_text(text)

    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(io.BytesIO(file_bytes))
        st.session_state.resume_text = "\n".join([p.text for p in doc.paragraphs])

    elif uploaded_file.type == "text/plain":
        st.session_state.resume_text = file_bytes.decode()

    st.session_state.upload_key += 1
    st.rerun()

# ---------- USER MESSAGE PROCESS ----------
if user_input:

    if not st.session_state.resume_text.strip():
        st.warning("Please upload resume first.")
    else:

        current_conv["messages"].append({"role": "user", "content": user_input})

        with st.spinner("Generating cover letter..."):
            try:
                prompt = f"""
Write a short professional cover letter.

Resume:
{st.session_state.resume_text[:1500]}

Job Role:
{user_input}

Keep it concise and professional.
"""

                response = ollama.chat(
                    model='phi3',
                    messages=[{'role': 'user', 'content': prompt}],
                    options={
                        'num_predict': 250,
                        'temperature': 0.5
                    }
                )

                bot_reply = response['message']['content']

            except Exception as e:
                bot_reply = f"Ollama Error: {e}"

        current_conv["messages"].append({
            "role": "assistant",
            "content": bot_reply,
            "file": bot_reply.encode("utf-8"),
            "file_name": "cover_letter.txt"
        })

        st.rerun()