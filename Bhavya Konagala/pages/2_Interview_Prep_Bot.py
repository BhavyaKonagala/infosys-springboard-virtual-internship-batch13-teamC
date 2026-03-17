import streamlit as st
import json
from docx import Document
import tempfile
from paddleocr import PaddleOCR
import requests
import uuid
from datetime import datetime
import os

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Interview Preparation Bot",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #1a1a2e;
        padding: 1rem 0.75rem;
    }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    /* General sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
        background-color: #16213e;
        color: #e0e0e0 !important;
        border: 1px solid #0f3460;
        border-radius: 8px;
        padding: 0.4rem 0.6rem;
        font-size: 0.85rem;
        margin-bottom: 4px;
        transition: background 0.2s;
    }
    [data-testid="stSidebar"] .stButton > button:hover { background-color: #0f3460; }
    /* Remove Streamlit default column gap that causes the box effect */
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
        gap: 4px !important;
        align-items: center !important;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; }

    .stButton > button { border-radius: 8px; font-weight: 500; }

    /* Remove box around pin/delete column wrappers */
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(2),
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(3) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-width: 0 !important;
        overflow: visible !important;
    }
    /* Pin & delete buttons — no border, no background, emoji centered */
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button,
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(3) button {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        font-size: 1rem !important;
        padding: 0 !important;
        margin: 0 !important;
        height: 2.1rem !important;
        min-height: 2.1rem !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: hidden !important;
    }
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button:hover,
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(3) button:hover {
        background-color: rgba(255,255,255,0.1) !important;
        border-radius: 6px !important;
    }

    .stChatMessage { border-radius: 10px; margin-bottom: 0.5rem; }
    hr { margin: 0.75rem 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────
@st.cache_resource
def load_ocr():
    return PaddleOCR(lang='en')

ocr = load_ocr()


# ─────────────────────────────────────────────
# PERSISTENCE — single file stores everything
# ─────────────────────────────────────────────
CHATS_FILE = "interview_chats.json"

def save_all(chats: dict, current_id: str):
    with open(CHATS_FILE, "w") as f:
        json.dump({"chats": chats, "current_id": current_id}, f)

def load_all() -> tuple:
    try:
        with open(CHATS_FILE, "r") as f:
            data = json.load(f)
            return data.get("chats", {}), data.get("current_id", None)
    except Exception:
        return {}, None


# ─────────────────────────────────────────────
# OLLAMA STREAMING
# ─────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

def ask_ollama_stream(prompt: str):
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": True
        }, stream=True, timeout=180)
        full = ""
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    token = data.get("response", "")
                    if token:
                        full += token
                        yield full
                    if data.get("done", False):
                        break
                except Exception:
                    pass
    except Exception as e:
        yield f"❌ Error: {e}"


# ─────────────────────────────────────────────
# CHAT SCHEMA
# Every chat stores ALL its own data:
#   title, pinned, created_at
#   docs       : {filename: text}
#   active_doc : filename | None
#   questions  : generated text | ""
#   quiz       : generated text | ""
#   messages   : [{role, content}]
# ─────────────────────────────────────────────
def new_chat_obj(title="New Chat"):
    return {
        "title":      title,
        "pinned":     False,
        "created_at": datetime.now().strftime("%b %d, %H:%M"),
        "docs":       {},
        "active_doc": None,
        "questions":  "",
        "quiz":       "",
        "messages":   []
    }


# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
# Always load both together so current_id is never missing
if "chats" not in st.session_state or "current_id" not in st.session_state:
    saved_chats, saved_id = load_all()
    st.session_state.chats      = saved_chats if saved_chats else {}
    st.session_state.current_id = saved_id

# First ever run — create default chat
if not st.session_state.chats:
    cid = str(uuid.uuid4())
    st.session_state.chats[cid]  = new_chat_obj()
    st.session_state.current_id  = cid
    save_all(st.session_state.chats, st.session_state.current_id)

# Safety: if current_id is None or no longer exists, pick first available
if not st.session_state.current_id or \
        st.session_state.current_id not in st.session_state.chats:
    st.session_state.current_id = list(st.session_state.chats.keys())[0]

# Migrate old chat objects that are missing new fields (from previous saved versions)
_defaults = {"docs": {}, "active_doc": None, "questions": "", "quiz": "", "messages": []}
for _cid, _chat in st.session_state.chats.items():
    for _key, _val in _defaults.items():
        if _key not in _chat:
            _chat[_key] = type(_val)() if isinstance(_val, (dict, list)) else _val

# Per-chat upload tracking (in-memory only, intentionally resets on reload)
if "processed_files" not in st.session_state:
    st.session_state.processed_files = {}   # {chat_id: set()}


# ─────────────────────────────────────────────
# EXPORT HELPERS
# ─────────────────────────────────────────────
def export_txt(chat: dict) -> str:
    lines = []
    for m in chat["messages"]:
        role = "You" if m["role"] == "user" else "Assistant"
        lines.append(f"[{role}]\n{m['content']}\n")
    return "\n".join(lines)

def export_pdf(chat: dict):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        import io
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=50, rightMargin=50,
                                topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        u_style = ParagraphStyle("u", parent=styles["Normal"],
                                 textColor=colors.HexColor("#0f3460"),
                                 fontName="Helvetica-Bold", fontSize=10)
        b_style = ParagraphStyle("b", parent=styles["Normal"],
                                 textColor=colors.HexColor("#333333"), fontSize=10)
        story = [Paragraph("Interview Chat History", styles["Title"]), Spacer(1, 12)]
        for m in chat["messages"]:
            label = "You:" if m["role"] == "user" else "Assistant:"
            story.append(Paragraph(f"<b>{label}</b>",
                                   u_style if m["role"] == "user" else b_style))
            safe = (m["content"].replace("&", "&amp;")
                                .replace("<", "&lt;")
                                .replace(">", "&gt;"))
            story.append(Paragraph(safe, b_style))
            story.append(Spacer(1, 8))
        doc.build(story)
        return buf.getvalue()
    except ImportError:
        return None


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 Interview Bot")
    st.markdown("---")

    # ── New Chat ─────────────────────────────
    if st.button("➕  New Chat", use_container_width=True):
        cid = str(uuid.uuid4())
        st.session_state.chats[cid] = new_chat_obj()
        st.session_state.current_id = cid
        save_all(st.session_state.chats, st.session_state.current_id)
        st.rerun()

    st.markdown("### 💬 Chats")

    sorted_chats = sorted(
        st.session_state.chats.items(),
        key=lambda x: (not x[1]["pinned"], x[1].get("created_at", "")),
    )

    for cid, cdata in sorted_chats:
        is_active = (cid == st.session_state.current_id)
        pin_icon  = "📌" if cdata["pinned"] else "💬"
        label     = f"{'▶ ' if is_active else ''}{pin_icon} {cdata['title'][:18]}"

        col1, col2, col3 = st.columns([7, 1, 1])
        with col1:
            if st.button(label, key=f"open_{cid}", use_container_width=True):
                st.session_state.current_id = cid
                save_all(st.session_state.chats, st.session_state.current_id)
                st.rerun()
        with col2:
            if st.button("📍", key=f"pin_{cid}", help="Pin/Unpin"):
                cdata["pinned"] = not cdata["pinned"]
                save_all(st.session_state.chats, st.session_state.current_id)
                st.rerun()
        with col3:
            if st.button("🗑", key=f"del_{cid}", help="Delete"):
                del st.session_state.chats[cid]
                if st.session_state.chats:
                    st.session_state.current_id = list(st.session_state.chats.keys())[0]
                else:
                    ncid = str(uuid.uuid4())
                    st.session_state.chats[ncid] = new_chat_obj()
                    st.session_state.current_id  = ncid
                save_all(st.session_state.chats, st.session_state.current_id)
                st.rerun()

    # ── Rename ───────────────────────────────
    st.markdown("---")
    with st.expander("✏️ Rename Current Chat"):
        new_title = st.text_input("New name", label_visibility="collapsed",
                                  placeholder="Enter new chat name…")
        if st.button("Rename", use_container_width=True) and new_title:
            st.session_state.chats[st.session_state.current_id]["title"] = new_title
            save_all(st.session_state.chats, st.session_state.current_id)
            st.rerun()

    # ── Export ───────────────────────────────
    st.markdown("---")
    st.markdown("### 📤 Export Chat")
    cur  = st.session_state.chats[st.session_state.current_id]
    msgs = cur["messages"]

    st.download_button(
        "⬇️ Download as TXT", data=export_txt(cur),
        file_name="chat_history.txt", mime="text/plain",
        use_container_width=True, disabled=(len(msgs) == 0)
    )
    pdf_bytes = export_pdf(cur)
    if pdf_bytes:
        st.download_button(
            "⬇️ Download as PDF", data=pdf_bytes,
            file_name="chat_history.pdf", mime="application/pdf",
            use_container_width=True, disabled=(len(msgs) == 0)
        )
    else:
        st.caption("💡 Install `reportlab` for PDF export")

    # ── Docs for current chat ─────────────────
    st.markdown("---")
    st.markdown("### 📂 This Chat's Documents")
    chat_docs = cur["docs"]
    if chat_docs:
        for fname in list(chat_docs.keys()):
            is_active_doc = (fname == cur["active_doc"])
            dc1, dc2 = st.columns([4, 1])
            with dc1:
                dlabel = f"✅ {fname[:18]}" if is_active_doc else f"📄 {fname[:18]}"
                if st.button(dlabel, key=f"setdoc_{fname}_{st.session_state.current_id}",
                             use_container_width=True):
                    cur["active_doc"] = fname
                    cur["questions"]  = ""
                    cur["quiz"]       = ""
                    save_all(st.session_state.chats, st.session_state.current_id)
                    st.rerun()
            with dc2:
                if st.button("✖", key=f"rmdoc_{fname}_{st.session_state.current_id}",
                             help="Remove"):
                    del chat_docs[fname]
                    keys = list(chat_docs.keys())
                    cur["active_doc"] = keys[0] if keys else None
                    cur["questions"]  = ""
                    cur["quiz"]       = ""
                    save_all(st.session_state.chats, st.session_state.current_id)
                    st.rerun()
    else:
        st.caption("No documents in this chat yet.")


# ─────────────────────────────────────────────
# MAIN AREA  — all data read from current chat
# ─────────────────────────────────────────────
chat = st.session_state.chats[st.session_state.current_id]

st.markdown(f"""
<div class="main-header">
    <span style="font-size:2.2rem">🎯</span>
    <div>
        <h1>Interview Preparation Bot</h1>
        <p style="margin:0;opacity:0.8;font-size:0.9rem">
            Chat: <b>{chat['title']}</b> &nbsp;|&nbsp;
            Upload → Generate Questions → Practice
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── File Upload (per chat) ───────────────────
with st.expander("📘 Upload Study Material", expanded=(not chat["docs"])):
    uploaded_files = st.file_uploader(
        "Upload files for THIS chat (TXT, DOCX, JPG, PNG)",
        type=["txt", "docx", "jpg", "png", "jpeg"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.current_id}"   # unique widget per chat
    )

    if uploaded_files:
        cid = st.session_state.current_id
        if cid not in st.session_state.processed_files:
            st.session_state.processed_files[cid] = set()

        for uploaded_file in uploaded_files:
            fname = uploaded_file.name
            if fname in st.session_state.processed_files[cid]:
                continue   # already handled this session

            text = ""
            ext  = fname.split(".")[-1].lower()

            with st.spinner(f"Processing {fname}…"):
                if ext == "txt":
                    text = uploaded_file.read().decode("utf-8")
                elif ext == "docx":
                    doc  = Document(uploaded_file)
                    text = "\n".join([p.text for p in doc.paragraphs])
                elif ext in ["jpg", "png", "jpeg"]:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                        tmp.write(uploaded_file.read())
                        path = tmp.name
                    result = ocr.ocr(path)
                    for page in result:
                        for line in page:
                            text += line[1][0] + "\n"
                    os.unlink(path)

            if text.strip():
                chat["docs"][fname] = text
                chat["active_doc"]  = fname
                chat["questions"]   = ""    # clear stale outputs for new doc
                chat["quiz"]        = ""
                st.session_state.processed_files[cid].add(fname)
                save_all(st.session_state.chats, st.session_state.current_id)
                st.success(f"✅ '{fname}' uploaded and set as active!")
            else:
                st.warning(f"⚠️ No readable text found in '{fname}'")


# ─── Active Doc Selector + Preview ───────────
content = ""
if chat["docs"]:
    doc_names = list(chat["docs"].keys())

    if chat["active_doc"] not in doc_names:
        chat["active_doc"] = doc_names[0]

    selected = st.selectbox(
        "📄 Active document for Q&A / Quiz",
        options=doc_names,
        index=doc_names.index(chat["active_doc"]),
        key=f"docselect_{st.session_state.current_id}"
    )

    if selected != chat["active_doc"]:
        chat["active_doc"] = selected
        chat["questions"]  = ""
        chat["quiz"]       = ""
        save_all(st.session_state.chats, st.session_state.current_id)

    content = chat["docs"][chat["active_doc"]]

    with st.expander("📖 Preview Content", expanded=True):
        st.caption(f"Showing: **{chat['active_doc']}** ({len(content)} chars total)")
        st.text_area("", content[:2000], height=180, label_visibility="collapsed",
                     key=f"preview_{st.session_state.current_id}_{chat['active_doc']}")
else:
    st.info("📂 Upload a document above to get started with this chat.")


# ─── Generate Questions / Quiz ────────────────
col_q, col_quiz = st.columns(2)

q_trigger_key  = f"gen_q_{st.session_state.current_id}"
qz_trigger_key = f"gen_qz_{st.session_state.current_id}"

with col_q:
    if st.button("🧠 Generate Interview Questions", use_container_width=True):
        if not content:
            st.warning("⚠️ Please upload a document first.")
        else:
            st.session_state[q_trigger_key] = True

with col_quiz:
    if st.button("📝 Generate Quiz (MCQ)", use_container_width=True):
        if not content:
            st.warning("⚠️ Please upload a document first.")
        else:
            st.session_state[qz_trigger_key] = True

# ── Questions — generate or show saved ────────
if st.session_state.get(q_trigger_key):
    st.markdown("#### 📋 Interview Questions")
    status_q = st.empty()
    status_q.caption("⏳ Generating questions… please wait")
    ph_q = st.empty()
    prompt = ("Based on the following content, generate 10 interview questions "
              "with detailed answers. Number each question clearly.\n\n"
              + content[:3000])
    last = ""
    for partial in ask_ollama_stream(prompt):
        ph_q.markdown(partial + " ▌")
        last = partial
    ph_q.markdown(last)
    status_q.caption("✅ Questions ready!")
    chat["questions"] = last
    save_all(st.session_state.chats, st.session_state.current_id)
    st.session_state[q_trigger_key] = False

elif chat.get("questions"):
    st.markdown("#### 📋 Interview Questions")
    st.markdown(chat["questions"])

# ── Quiz — generate or show saved ─────────────
if st.session_state.get(qz_trigger_key):
    st.markdown("#### 📝 Quiz")
    status_qz = st.empty()
    status_qz.caption("⏳ Generating quiz… please wait")
    ph_qz = st.empty()
    prompt = ("Create 5 multiple-choice questions with 4 options each (A, B, C, D). "
              "Mark the correct answer clearly after each question.\n\n"
              + content[:3000])
    last = ""
    for partial in ask_ollama_stream(prompt):
        ph_qz.markdown(partial + " ▌")
        last = partial
    ph_qz.markdown(last)
    status_qz.caption("✅ Quiz ready!")
    chat["quiz"] = last
    save_all(st.session_state.chats, st.session_state.current_id)
    st.session_state[qz_trigger_key] = False

elif chat.get("quiz"):
    st.markdown("#### 📝 Quiz")
    st.markdown(chat["quiz"])


# ─── Chat Messages ────────────────────────────
st.markdown("---")
st.subheader(f"💬 {chat['title']}")

for msg in chat["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_query = st.chat_input("Ask an interview question or type anything…")

if user_query:
    chat["messages"].append({"role": "user", "content": user_query})

    with st.chat_message("user"):
        st.write(user_query)

    # Auto-title from first message
    if len(chat["messages"]) == 1:
        chat["title"] = user_query[:30]

    if content:
        prompt = (f"You are an expert interview assistant.\n\n"
                  f"Reference material:\n{content[:2000]}\n\n"
                  f"User: {user_query}\nAssistant:")
    else:
        prompt = f"You are an expert interview assistant.\nUser: {user_query}\nAssistant:"

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⏳ _Thinking…_")
        response_text = ""
        for partial in ask_ollama_stream(prompt):
            placeholder.markdown(partial + " ▌")
            response_text = partial
        placeholder.markdown(response_text)

    chat["messages"].append({"role": "assistant", "content": response_text})
    save_all(st.session_state.chats, st.session_state.current_id)