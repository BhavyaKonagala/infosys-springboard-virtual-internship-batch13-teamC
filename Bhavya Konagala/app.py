import streamlit as st
import uuid
import requests
import tempfile
import json
from docx import Document
from paddleocr import PaddleOCR


# ----------------------------
# LOAD OCR ONLY ONCE
# ----------------------------
@st.cache_resource
def load_ocr():
    return PaddleOCR(lang='en')

ocr = load_ocr()


# ----------------------------
# OLLAMA STREAM FUNCTION (BUFFERED)
# ----------------------------
def ask_ollama_stream(prompt):

    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": True
    }

    response = requests.post(url, json=payload, stream=True)

    full_response = ""
    buffer = ""

    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line.decode("utf-8"))
                token = data.get("response", "")

                buffer += token

                # update UI less frequently for smoother streaming
                if len(buffer) > 25:
                    full_response += buffer
                    buffer = ""
                    yield full_response

            except:
                pass

    if buffer:
        full_response += buffer
        yield full_response


# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="Personalized Cover Letter Assistant",
    layout="wide"
)


# ----------------------------
# SESSION STATE INIT
# ----------------------------
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None


def create_new_chat():
    chat_id = str(uuid.uuid4())

    st.session_state.chats[chat_id] = {
        "title": "New Chat",
        "messages": [],
        "resume_text": "",
        "resume_processed": False,
        "role": "",
        "company": "",
        "pinned": False
    }

    st.session_state.current_chat_id = chat_id


if st.session_state.current_chat_id is None:
    create_new_chat()


# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:

    st.title("💬 Chat History")

    if st.button("➕ New Chat"):
        create_new_chat()
        st.rerun()

    st.write("---")

    sorted_chats = sorted(
        st.session_state.chats.items(),
        key=lambda x: x[1]["pinned"],
        reverse=True
    )

    for chat_id, chat_data in sorted_chats:

        col1, col2, col3 = st.columns([3,1,1])

        with col1:

            label = f"📌 {chat_data['title']}" if chat_data["pinned"] else chat_data["title"]

            if st.button(label, key=f"open_{chat_id}"):
                st.session_state.current_chat_id = chat_id
                st.rerun()

        with col2:

            if st.button("📍", key=f"pin_{chat_id}"):
                chat_data["pinned"] = not chat_data["pinned"]
                st.rerun()

        with col3:

            if st.button("🗑", key=f"delete_{chat_id}"):

                del st.session_state.chats[chat_id]

                if st.session_state.chats:
                    st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
                else:
                    create_new_chat()

                st.rerun()

    st.write("---")

    new_title = st.text_input("✏ Rename Current Chat")

    if st.button("Update Title"):

        if new_title:

            st.session_state.chats[st.session_state.current_chat_id]["title"] = new_title
            st.rerun()


# ----------------------------
# MAIN CHAT
# ----------------------------
current_chat = st.session_state.chats[st.session_state.current_chat_id]

st.title("🤖 Personalized Cover Letter Assistant")


# ----------------------------
# RESUME UPLOAD
# ----------------------------
uploaded_files = st.file_uploader(
    "📂 Upload Resume (TXT, DOCX, JPG, PNG, JPEG)",
    type=["txt","docx","jpg","png","jpeg"],
    accept_multiple_files=True
)


# ----------------------------
# PROCESS RESUME
# ----------------------------
if uploaded_files and not current_chat["resume_processed"]:

    if st.button("⚡ Process Resume"):

        combined_text = ""

        for uploaded_file in uploaded_files:

            file_extension = uploaded_file.name.split(".")[-1].lower()

            try:

                if file_extension == "txt":

                    text = uploaded_file.read().decode("utf-8")
                    combined_text += text + "\n"


                elif file_extension == "docx":

                    doc = Document(uploaded_file)

                    resume_text = "\n".join(
                        [para.text for para in doc.paragraphs]
                    )

                    combined_text += resume_text + "\n"


                elif file_extension in ["jpg","png","jpeg"]:

                    st.info(f"🔎 OCR Processing {uploaded_file.name}")

                    with tempfile.NamedTemporaryFile(delete=False) as tmp:

                        tmp.write(uploaded_file.read())
                        temp_path = tmp.name

                    result = ocr.ocr(temp_path)

                    if result:

                        for page in result:

                            for line in page:

                                combined_text += line[1][0] + "\n"


                else:

                    st.warning(f"{uploaded_file.name} unsupported")


            except Exception as e:

                st.error(f"Error processing {uploaded_file.name}: {str(e)}")


        if combined_text.strip() == "":
            combined_text = "⚠️ No readable text detected."


        current_chat["resume_text"] = combined_text
        current_chat["resume_processed"] = True


# ----------------------------
# SHOW EXTRACTED TEXT
# ----------------------------
if current_chat["resume_text"]:

    if current_chat["resume_processed"]:
        st.success("✅ Resume processed successfully!")

    st.text_area(
        "Extracted Resume Text",
        current_chat["resume_text"],
        height=300
    )


# ----------------------------
# DISPLAY CHAT HISTORY
# ----------------------------
for msg in current_chat["messages"]:

    with st.chat_message(msg["role"]):

        st.write(msg["content"])


# ----------------------------
# CHAT INPUT
# ----------------------------
user_input = st.chat_input("Ask anything...")


if user_input:

    current_chat["messages"].append({
        "role":"user",
        "content":user_input
    })

    with st.chat_message("user"):
        st.write(user_input)

    if len(current_chat["messages"]) == 1:
        current_chat["title"] = user_input[:30]

    lower_input = user_input.lower()

    if " at " in lower_input:

        parts = user_input.split(" at ")

        current_chat["role"] = parts[0]
        current_chat["company"] = parts[1]


    if "cover letter" in lower_input and current_chat["resume_text"]:

        prompt = f"""
Write a highly personalized professional cover letter.

Role: {current_chat['role']}
Company: {current_chat['company']}

Resume Content:
{current_chat['resume_text']}
"""

    else:

        conversation = ""

        for msg in current_chat["messages"]:
            conversation += f"{msg['role']}: {msg['content']}\n"

        prompt = conversation


    # ----------------------------
    # STREAM RESPONSE WITH SPINNER
    # ----------------------------
    with st.chat_message("assistant"):

        placeholder = st.empty()

        with st.spinner("Generating response..."):

            response_text = ""

            for partial in ask_ollama_stream(prompt):

                placeholder.markdown(partial)
                response_text = partial


    current_chat["messages"].append({
        "role":"assistant",
        "content":response_text
    })