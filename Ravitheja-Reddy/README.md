# Cover Letter Generator

An AI-powered document intelligence tool that generates personalized cover letters using OCR and local LLMs. This application operates entirely offline, ensuring maximum data privacy and zero API costs.

## Features

- **OCR Integration**: Extracts text from scanned PDFs and images using PaddleOCR and Tesseract.
- **Local LLM**: Utilizes Meta Llama 3 (via Ollama) for context-aware cover letter generation.
- **Privacy First**: All data remains on your local machine; no cloud APIs are used.
- **Streamlit UI**: Easy-to-use interface for uploading resumes and job descriptions.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Ollama**: Install [Ollama](https://ollama.com/) and download the Llama 3 model:
    ```bash
    ollama run llama3.2
    ```
3.  **Tesseract OCR**: (Optional) Install Tesseract for OCR support.
4.  **Run the App**:
    ```bash
    streamlit run app.py
    ```

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Ravitheja Reddy
