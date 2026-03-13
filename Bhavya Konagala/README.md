# Personalized Cover Letter Assistant with OCR Integration

## Overview
This project is an AI-powered application that generates personalized cover letters based on a user's resume. The system extracts resume content using OCR when necessary and uses a local Large Language Model (Llama3 via Ollama) to generate a professional cover letter tailored to a specific job role and company.

## Features
* Upload resumes in multiple formats (TXT, DOCX, JPG, PNG, JPEG)
* OCR-based text extraction using PaddleOCR
* AI-generated personalized cover letters
* Interactive web interface built with Streamlit
* Chat-style interaction with session management

## Technologies Used
* Python 3.10
* Streamlit
* PaddleOCR
* Ollama (Llama3)
* Virtual Environment (venv)

## How to Run
1. Install dependencies
   ```
   pip install -r requirements.txt
   ```

2. Start the Llama3 model using Ollama
   ```
   ollama run llama3
   ```

3. Run the Streamlit application
   ```
   streamlit run app.py
   ```

## Author
Bhavya Konagala
Infosys Springboard Virtual Internship 6.0 – Batch 13 (Team C)
