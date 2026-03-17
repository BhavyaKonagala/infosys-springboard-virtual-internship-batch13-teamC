# 🧠 AI Career Assistant

### (Cover Letter Generator + Interview Preparation Bot)

An interactive **Streamlit-based AI application** that helps users:

* ✉️ Generate personalized cover letters
* 🎯 Prepare for interviews with questions & quizzes
* 📂 Upload and analyze resumes / documents
* 🤖 Chat with an AI assistant powered by **Ollama (LLaMA 3)**

---

## 🚀 Features

### ✉️ Cover Letter Assistant

* Upload resume, job description (TXT, DOCX, images)
* Extract text using **PaddleOCR**
* Generate personalized cover letters using AI
* Save multiple chats with history
* Export chats as **TXT / PDF**

---

### 🎯 Interview Preparation Bot

* Upload study materials (notes, docs, images)
* Generate:

  * 🧠 Interview Questions (with answers)
  * 📝 MCQ Quizzes
* Chat-based Q&A system
* Multi-chat support with pin, delete, rename

---

### 💬 Smart Chat System

* Persistent chat storage using JSON
* Multi-session chat handling
* Per-chat data isolation
* Auto-title generation

---

### 📂 File Processing

* Supports:

  * `.txt`
  * `.docx`
  * `.jpg / .png / .jpeg`
* OCR support via **PaddleOCR**
* Handles multiple files per session

---

## 🛠️ Tech Stack

* **Frontend/UI:** Streamlit
* **Backend Logic:** Python
* **AI Model:** Ollama (LLaMA 3)
* **OCR:** PaddleOCR
* **File Processing:** python-docx
* **PDF Export:** reportlab

---

## 📁 Project Structure

```
project/
│
├── app.py                          # Interview Preparation Bot
├── pages/
│   └── 2_Interview_Prep_Bot.py     # Cover Letter Assistant
│
├── interview_chats.json            # Stored interview chats
├── coverletter_chats.json          # Stored cover letter chats
│
├── README.md
└── requirements.txt
```

---

## ⚙️ Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

---

### 2️⃣ Create virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

---

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4️⃣ Install & run Ollama

Download Ollama from: https://ollama.com

Then run:

```bash
ollama run llama3
```

---

### 5️⃣ Run the app

```bash
streamlit run app.py
```

---

## 📌 Usage

1. Upload your resume or study material
2. Choose a chat or create a new one
3. Generate:

   * Cover letter
   * Interview questions
   * Quiz
4. Interact with AI assistant
5. Export results if needed

---

## 💡 Key Highlights

* 🔄 Multi-chat support with persistence
* 🧠 AI-powered content generation
* 📄 OCR-enabled document understanding
* 🎯 Focused on job preparation workflow
* 💻 Clean UI with custom styling

---

## ⚠️ Requirements

* Python 3.8+
* Ollama running locally
* Internet (for initial setup)

---

## 📈 Future Improvements

* 🌐 Deploy online (Streamlit Cloud)
* 📊 Resume scoring system
* 🎙️ Voice-based interaction
* 🔗 LinkedIn job integration

---

## 👩‍💻 Author

**Bhavya Konagala**

---

## ⭐ If you like this project

Give it a ⭐ on GitHub and share it!

---
