# Copyright (c) 2026 Ravitheja Reddy
# Licensed under the MIT License. See LICENSE file in the project root for full license information.

import streamlit as st
import requests
import json
import fitz  # PyMuPDF
from io import BytesIO

# OCR imports — optional, only needed for scanned PDFs
OCR_AVAILABLE = False
OCR_ERROR_MESSAGE = ""

try:
    from PIL import Image
    import pytesseract

    # On Windows, try common installation paths
    import platform
    if platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in possible_paths:
            import os
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

    # Quick check that tesseract binary is reachable
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except ImportError as e:
    OCR_ERROR_MESSAGE = f"PIL or pytesseract not installed: {str(e)}"
except pytesseract.TesseractNotFoundError:
    OCR_ERROR_MESSAGE = (
        "Tesseract OCR is not installed or not in PATH. "
        "Download from: https://github.com/UB-Mannheim/tesseract/wiki"
    )
except Exception as e:
    OCR_ERROR_MESSAGE = f"OCR initialization error: {str(e)}"


# --- PDF / OCR Helpers ---
def extract_text_from_pdf(file_bytes):
    """Extract text from a PDF. Falls back to OCR for scanned pages."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    ocr_skipped = 0

    for page in doc:
        page_text = page.get_text().strip()
        if page_text:
            text_parts.append(page_text)
        elif OCR_AVAILABLE:
            # Page has no selectable text — OCR it
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                text_parts.append(ocr_text)
        else:
            ocr_skipped += 1

    doc.close()

    if ocr_skipped > 0:
        st.warning(
            f"⚠️ {ocr_skipped} scanned page(s) could not be read (no OCR available)"
        )
        st.info(
            f"**Issue:** {OCR_ERROR_MESSAGE}\n\n"
            "**To fix:** Install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki"
        )

    return "\n\n".join(text_parts)


def extract_text_from_image(file_bytes):
    """Extract text from an image using OCR."""
    if not OCR_AVAILABLE:
        st.error("❌ OCR is not available")
        st.info(
            f"**Issue:** {OCR_ERROR_MESSAGE}\n\n"
            "**To fix:**\n"
            "1. Download Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "2. Install it (recommended: `C:\\Program Files\\Tesseract-OCR\\`)\n"
            "3. Restart this app\n\n"
            "Once installed, you'll be able to extract text from images."
        )
        return ""
    try:
        img = Image.open(BytesIO(file_bytes))
        text = pytesseract.image_to_string(img).strip()
        if not text:
            st.warning("⚠️ No text could be extracted from the image. Try a clearer screenshot.")
        return text
    except Exception as e:
        st.error(f"❌ Error during OCR: {e}")
        return ""


# --- Configuration ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2"

SYSTEM_PROMPT = (
    "You are a professional cover letter writer. When the user provides their resume and "
    "a job description, generate a polished, personalized cover letter that maps their "
    "experience to the job requirements. Keep it concise (under 400 words), professional, "
    "and do NOT invent experience they didn't mention. After generating, help the user "
    "refine the letter through conversation — adjusting tone, adding emphasis, shortening, etc."
)


# --- Ollama API ---
def stream_ollama_response(messages):
    payload = {"model": MODEL_NAME, "messages": messages, "stream": True}
    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "message" in chunk and "content" in chunk["message"]:
                        yield chunk["message"]["content"]
                    if chunk.get("done", False):
                        break
    except requests.exceptions.ConnectionError:
        yield "**Error:** Cannot connect to Ollama. Make sure Ollama is running (`ollama serve`)."
    except requests.exceptions.Timeout:
        yield "**Error:** Request to Ollama timed out."
    except Exception as e:
        yield f"**Error:** {str(e)}"


# --- Page Config ---
st.set_page_config(page_title="Cover Letter Generator", page_icon="📝", layout="wide")

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "jd_text" not in st.session_state:
    st.session_state.jd_text = ""
if "generated" not in st.session_state:
    st.session_state.generated = False

# --- Sidebar ---
with st.sidebar:
    st.title("📝 Cover Letter Generator")
    st.caption(f"Model: {MODEL_NAME}")
    
    # OCR Status Indicator
    if OCR_AVAILABLE:
        st.success("✅ OCR: Active")
    else:
        st.error("❌ OCR: Not Available")
        with st.expander("How to enable OCR"):
            st.markdown(
                f"**Issue:** {OCR_ERROR_MESSAGE}\n\n"
                "**Installation Steps:**\n"
                "1. Download Tesseract OCR: [Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki)\n"
                "2. Run the installer (use default path: `C:\\Program Files\\Tesseract-OCR`)\n"
                "3. Restart this app\n\n"
                "OCR enables text extraction from images and scanned PDFs."
            )
    
    st.divider()

    uploaded_resume = st.file_uploader(
        "Upload your resume",
        type=["txt", "md", "pdf"],
        help="Upload a text, markdown, or PDF resume (scanned PDFs supported via OCR).",
    )
    if uploaded_resume is not None:
        try:
            if uploaded_resume.name.lower().endswith(".pdf"):
                file_bytes = uploaded_resume.read()
                st.session_state.resume_text = extract_text_from_pdf(file_bytes)
            else:
                st.session_state.resume_text = uploaded_resume.read().decode("utf-8")
            st.success(f"Loaded: {uploaded_resume.name}")
        except Exception as e:
            st.error(f"Could not read file: {e}")

    resume_text = st.text_area(
        "Or paste your resume here",
        value=st.session_state.resume_text,
        height=200,
    )

    st.divider()
    st.subheader("Job Description")

    uploaded_jd_file = st.file_uploader(
        "Upload job description (PDF or screenshot)",
        type=["pdf", "png", "jpg", "jpeg", "bmp", "webp", "tiff"],
        help="Upload a PDF or screenshot of the job description. Text will be extracted automatically.",
    )
    if uploaded_jd_file is not None:
        try:
            file_bytes = uploaded_jd_file.read()
            
            # Handle PDF files
            if uploaded_jd_file.name.lower().endswith(".pdf"):
                st.session_state.jd_text = extract_text_from_pdf(file_bytes)
                st.success(f"Text extracted from PDF: {uploaded_jd_file.name}")
            # Handle image files
            else:
                # Reset the file pointer for st.image
                uploaded_jd_file.seek(0)
                st.image(uploaded_jd_file, caption="Uploaded JD image", use_container_width=True)
                # Use the bytes for OCR
                extracted = extract_text_from_image(file_bytes)
                if extracted:
                    st.session_state.jd_text = extracted
                    st.success("Text extracted from image.")
        except Exception as e:
            st.error(f"Could not process file: {e}")

    job_description = st.text_area(
        "Or paste / edit the job description here",
        value=st.session_state.jd_text,
        height=200,
    )

    generate_clicked = st.button(
        "Generate Cover Letter", type="primary", use_container_width=True
    )

    if st.session_state.generated:
        if st.button("Start Over", use_container_width=True):
            st.session_state.messages = []
            st.session_state.resume_text = ""
            st.session_state.jd_text = ""
            st.session_state.generated = False
            st.rerun()

# --- Generate Cover Letter ---
if generate_clicked:
    if not resume_text.strip() or not job_description.strip():
        st.error("Please provide both your resume and the job description.")
    else:
        # Reset conversation and kick off generation
        user_content = (
            f"Here is my resume:\n\n{resume_text.strip()}\n\n"
            f"Here is the job description:\n\n{job_description.strip()}\n\n"
            "Please write me a personalized cover letter for this role."
        )
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        st.session_state.generated = True
        st.rerun()

# --- Main Chat Area ---
st.header("Cover Letter Generator")

if not st.session_state.generated:
    st.info("Upload your resume and paste the job description in the sidebar, then click **Generate Cover Letter**.")
else:
    # Display conversation (skip system message)
    for msg in st.session_state.messages:
        if msg["role"] == "system":
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # If the last message is from the user, we need to generate a response
    if st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            for token in stream_ollama_response(st.session_state.messages):
                full_response += token
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Download button for the latest assistant response
    latest_letter = ""
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            latest_letter = msg["content"]
            break
    if latest_letter:
        st.download_button(
            "Download Cover Letter",
            data=latest_letter,
            file_name="cover_letter.txt",
            mime="text/plain",
        )

    # Chat input for refining
    if prompt := st.chat_input("Ask to refine (e.g. 'make it shorter', 'add more about my leadership')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()
