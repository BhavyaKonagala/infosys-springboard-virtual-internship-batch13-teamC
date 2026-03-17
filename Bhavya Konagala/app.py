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
    page_title="Cover Letter Assistant",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CUSTOM CSS  (same design as Interview Bot)
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

    /* Remove gap/box effect on horizontal block */
    [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
        gap: 4px !important;
        align-items: center !important;
    }

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

    /* Pin & delete buttons — no border, centered emoji */
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

    .main-header {
        background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
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
    .stChatMessage { border-radius: 10px; margin-bottom: 0.5rem; }
    hr { margin: 0.75rem 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# OCR  (shared cache — loads only once globally)
# ─────────────────────────────────────────────
@st.cache_resource
def load_ocr():
    return PaddleOCR(lang='en')

ocr = load_ocr()


# ─────────────────────────────────────────────
# PERSISTENCE
# NOTE: uses "coverletter_chats.json" — completely
#       separate from interview_chats.json
# ─────────────────────────────────────────────
CHATS_FILE = "coverletter_chats.json"

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
# Each chat owns ALL its own data:
#   title, pinned, created_at
#   resume_text  : extracted resume content
#   role         : target job role
#   company      : target company
#   cover_letter : generated cover letter text
#   messages     : [{role, content}]
# ─────────────────────────────────────────────
def new_chat_obj(title="New Chat"):
    return {
        "title":        title,
        "pinned":       False,
        "created_at":   datetime.now().strftime("%b %d, %H:%M"),
        "docs":         {},    # {filename: text} — stores ALL uploaded files separately
        "role":         "",
        "company":      "",
        "cover_letter": "",
        "messages":     []
    }


# ─────────────────────────────────────────────
# SESSION STATE INIT
# Uses "cl_chats" and "cl_current_id" keys —
# completely separate from interview bot's
# "chats" and "current_id" keys
# ─────────────────────────────────────────────
if "cl_chats" not in st.session_state or "cl_current_id" not in st.session_state:
    saved_chats, saved_id = load_all()
    st.session_state.cl_chats      = saved_chats if saved_chats else {}
    st.session_state.cl_current_id = saved_id

if not st.session_state.cl_chats:
    cid = str(uuid.uuid4())
    st.session_state.cl_chats[cid]  = new_chat_obj()
    st.session_state.cl_current_id  = cid
    save_all(st.session_state.cl_chats, st.session_state.cl_current_id)

if not st.session_state.cl_current_id or \
        st.session_state.cl_current_id not in st.session_state.cl_chats:
    st.session_state.cl_current_id = list(st.session_state.cl_chats.keys())[0]

# Migrate old chat objects missing new fields
_defaults = {"docs": {}, "role": "", "company": "",
             "cover_letter": "", "messages": []}
for _chat in st.session_state.cl_chats.values():
    for _key, _val in _defaults.items():
        if _key not in _chat:
            _chat[_key] = type(_val)() if isinstance(_val, (dict, list)) else _val

# Per-chat upload tracking (in-memory, resets on reload intentionally)
if "cl_processed_files" not in st.session_state:
    st.session_state.cl_processed_files = {}   # {chat_id: set()}


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
        story = [Paragraph("Cover Letter Chat History", styles["Title"]), Spacer(1, 12)]
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
    st.markdown("## 📝 Cover Letter Bot")
    st.markdown("---")

    # ── New Chat ─────────────────────────────
    if st.button("➕  New Chat", use_container_width=True):
        cid = str(uuid.uuid4())
        st.session_state.cl_chats[cid] = new_chat_obj()
        st.session_state.cl_current_id = cid
        save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
        st.rerun()

    st.markdown("### 💬 Chats")

    sorted_chats = sorted(
        st.session_state.cl_chats.items(),
        key=lambda x: (not x[1]["pinned"], x[1].get("created_at", ""))
    )

    for cid, cdata in sorted_chats:
        is_active = (cid == st.session_state.cl_current_id)
        pin_icon  = "📌" if cdata["pinned"] else "💬"
        label     = f"{'▶ ' if is_active else ''}{pin_icon} {cdata['title'][:18]}"

        col1, col2, col3 = st.columns([7, 1, 1])
        with col1:
            if st.button(label, key=f"cl_open_{cid}", use_container_width=True):
                st.session_state.cl_current_id = cid
                save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
                st.rerun()
        with col2:
            if st.button("📍", key=f"cl_pin_{cid}", help="Pin/Unpin"):
                cdata["pinned"] = not cdata["pinned"]
                save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
                st.rerun()
        with col3:
            if st.button("🗑", key=f"cl_del_{cid}", help="Delete"):
                del st.session_state.cl_chats[cid]
                if st.session_state.cl_chats:
                    st.session_state.cl_current_id = \
                        list(st.session_state.cl_chats.keys())[0]
                else:
                    ncid = str(uuid.uuid4())
                    st.session_state.cl_chats[ncid] = new_chat_obj()
                    st.session_state.cl_current_id  = ncid
                save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
                st.rerun()

    # ── Rename ───────────────────────────────
    st.markdown("---")
    with st.expander("✏️ Rename Current Chat"):
        new_title = st.text_input("New name", label_visibility="collapsed",
                                  placeholder="Enter new chat name…")
        if st.button("Rename", use_container_width=True) and new_title:
            st.session_state.cl_chats[st.session_state.cl_current_id]["title"] = new_title
            save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
            st.rerun()

    # ── Export ───────────────────────────────
    st.markdown("---")
    st.markdown("### 📤 Export Chat")
    cur  = st.session_state.cl_chats[st.session_state.cl_current_id]
    msgs = cur["messages"]

    st.download_button(
        "⬇️ Download as TXT", data=export_txt(cur),
        file_name="cover_letter_chat.txt", mime="text/plain",
        use_container_width=True, disabled=(len(msgs) == 0)
    )
    pdf_bytes = export_pdf(cur)
    if pdf_bytes:
        st.download_button(
            "⬇️ Download as PDF", data=pdf_bytes,
            file_name="cover_letter_chat.pdf", mime="application/pdf",
            use_container_width=True, disabled=(len(msgs) == 0)
        )
    else:
        st.caption("💡 Install `reportlab` for PDF export")


# ─────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────
chat = st.session_state.cl_chats[st.session_state.cl_current_id]

st.markdown(f"""
<div class="main-header">
    <span style="font-size:2.2rem">📝</span>
    <div>
        <h1>Cover Letter Assistant</h1>
        <p style="margin:0;opacity:0.8;font-size:0.9rem">
            Chat: <b>{chat['title']}</b> &nbsp;|&nbsp;
            Upload Resume → Set Role & Company → Generate Cover Letter
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── File Upload (resume + job description) ──
with st.expander("📂 Upload Files", expanded=(not chat["docs"])):
    st.caption("Upload your **resume** and/or **job description** — all files are combined when generating the cover letter.")
    uploaded_files = st.file_uploader(
        "Upload files for THIS chat (TXT, DOCX, JPG, PNG, JPEG)",
        type=["txt", "docx", "jpg", "png", "jpeg"],
        accept_multiple_files=True,
        key=f"cl_uploader_{st.session_state.cl_current_id}"
    )

    if uploaded_files:
        cid = st.session_state.cl_current_id
        if cid not in st.session_state.cl_processed_files:
            st.session_state.cl_processed_files[cid] = set()

        if st.button("⚡ Process Files", use_container_width=True):
            any_new = False

            for uploaded_file in uploaded_files:
                fname = uploaded_file.name
                if fname in st.session_state.cl_processed_files[cid]:
                    continue   # already processed this session

                ext  = fname.split(".")[-1].lower()
                text = ""

                try:
                    if ext == "txt":
                        text = uploaded_file.read().decode("utf-8")

                    elif ext == "docx":
                        doc  = Document(uploaded_file)
                        text = "\n".join([p.text for p in doc.paragraphs])

                    elif ext in ["jpg", "png", "jpeg"]:
                        st.info(f"🔎 OCR processing {fname}…")
                        with tempfile.NamedTemporaryFile(
                                delete=False, suffix=f".{ext}") as tmp:
                            tmp.write(uploaded_file.read())
                            path = tmp.name
                        result = ocr.ocr(path)
                        if result:
                            for page in result:
                                for line in page:
                                    text += line[1][0] + "\n"
                        os.unlink(path)
                    else:
                        st.warning(f"⚠️ '{fname}' format not supported")

                except Exception as e:
                    st.error(f"Error processing {fname}: {e}")

                if text.strip():
                    chat["docs"][fname] = text
                    chat["cover_letter"] = ""   # clear stale output
                    st.session_state.cl_processed_files[cid].add(fname)
                    any_new = True
                    st.success(f"✅ '{fname}' processed!")
                elif text == "":
                    pass  # unsupported format already warned
                else:
                    st.warning(f"⚠️ No readable text found in '{fname}'")

            if any_new:
                save_all(st.session_state.cl_chats, st.session_state.cl_current_id)

    # Show already-stored files with remove option
    if chat["docs"]:
        st.markdown("**Stored files in this chat:**")
        for fname in list(chat["docs"].keys()):
            fc1, fc2 = st.columns([5, 1])
            with fc1:
                st.caption(f"📄 {fname}  ({len(chat['docs'][fname])} chars)")
            with fc2:
                if st.button("✖", key=f"cl_rmdoc_{fname}_{st.session_state.cl_current_id}"):
                    del chat["docs"][fname]
                    chat["cover_letter"] = ""
                    save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
                    st.rerun()


# ─── Preview each uploaded file separately ────
if chat["docs"]:
    with st.expander("📄 Uploaded Content Preview", expanded=False):
        for fname, ftext in chat["docs"].items():
            st.markdown(f"**{fname}** — {len(ftext)} chars")
            st.text_area("", ftext[:1500], height=150,
                         label_visibility="collapsed",
                         key=f"cl_prev_{st.session_state.cl_current_id}_{fname}")
            st.markdown("---")


# ─── Role & Company fields ────────────────────
st.markdown("#### 🎯 Target Role & Company")
col_r, col_c = st.columns(2)
with col_r:
    role_input = st.text_input(
        "Job Role", value=chat["role"], placeholder="e.g. Software Engineer",
        key=f"cl_role_{st.session_state.cl_current_id}"
    )
with col_c:
    company_input = st.text_input(
        "Company", value=chat["company"], placeholder="e.g. Google",
        key=f"cl_company_{st.session_state.cl_current_id}"
    )

# Save if changed
if role_input != chat["role"] or company_input != chat["company"]:
    chat["role"]    = role_input
    chat["company"] = company_input
    save_all(st.session_state.cl_chats, st.session_state.cl_current_id)


# ─── Generate Cover Letter button ─────────────
gen_key = f"cl_gen_{st.session_state.cl_current_id}"

if st.button("✉️ Generate Cover Letter", use_container_width=True):
    if not chat["docs"]:
        st.warning("⚠️ Please upload and process your resume/job description first.")
    elif not chat["role"] or not chat["company"]:
        st.warning("⚠️ Please enter both a Job Role and Company name.")
    else:
        st.session_state[gen_key] = True

# Build combined context from all uploaded files with clear labels
def build_docs_context(docs: dict, max_chars: int = 4000) -> str:
    parts = []
    remaining = max_chars
    for fname, ftext in docs.items():
        chunk = ftext[:remaining]
        parts.append(f"--- {fname} ---\n{chunk}")
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "\n\n".join(parts)

# Generate or show saved cover letter
if st.session_state.get(gen_key):
    st.markdown("#### ✉️ Your Cover Letter")
    status = st.empty()
    status.caption("⏳ Generating cover letter… please wait")
    ph = st.empty()
    docs_context = build_docs_context(chat["docs"])
    prompt = (
        f"Write a highly personalized, professional cover letter.\n\n"
        f"Role: {chat['role']}\n"
        f"Company: {chat['company']}\n\n"
        f"Uploaded Documents (resume, job description, etc.):\n{docs_context}"
    )
    last = ""
    for partial in ask_ollama_stream(prompt):
        ph.markdown(partial + " ▌")
        last = partial
    ph.markdown(last)
    status.caption("✅ Cover letter ready!")
    chat["cover_letter"] = last
    save_all(st.session_state.cl_chats, st.session_state.cl_current_id)
    st.session_state[gen_key] = False

elif chat.get("cover_letter"):
    st.markdown("#### ✉️ Your Cover Letter")
    st.markdown(chat["cover_letter"])


# ─── Chat Interface ───────────────────────────
st.markdown("---")
st.subheader(f"💬 {chat['title']}")

for msg in chat["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Ask anything about your cover letter or resume…")

if user_input:
    chat["messages"].append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    # Auto-title from first message
    if len(chat["messages"]) == 1:
        chat["title"] = user_input[:30]

    # Parse "role at company" from message
    lower = user_input.lower()
    if " at " in lower:
        parts = user_input.split(" at ", 1)
        chat["role"]    = parts[0].strip()
        chat["company"] = parts[1].strip()

    # Build prompt
    docs_ctx = build_docs_context(chat["docs"], max_chars=3000) if chat["docs"] else ""
    if "cover letter" in lower and chat["docs"]:
        prompt = (
            f"Write a highly personalized professional cover letter.\n\n"
            f"Role: {chat['role']}\n"
            f"Company: {chat['company']}\n\n"
            f"Uploaded Documents:\n{docs_ctx}"
        )
    else:
        history = "\n".join(
            [f"{m['role']}: {m['content']}" for m in chat["messages"]])
        if docs_ctx:
            prompt = (
                f"You are a professional cover letter and resume assistant.\n\n"
                f"Uploaded Documents:\n{docs_ctx}\n\n"
                f"Conversation:\n{history}\nAssistant:"
            )
        else:
            prompt = (
                f"You are a professional cover letter and resume assistant.\n\n"
                f"Conversation:\n{history}\nAssistant:"
            )

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⏳ _Thinking…_")
        response_text = ""
        for partial in ask_ollama_stream(prompt):
            placeholder.markdown(partial + " ▌")
            response_text = partial
        placeholder.markdown(response_text)

    chat["messages"].append({"role": "assistant", "content": response_text})
    save_all(st.session_state.cl_chats, st.session_state.cl_current_id)