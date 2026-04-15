import fitz  # PyMuPDF
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def extract_text_from_pdf(uploaded_file):
    uploaded_file.seek(0)
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")

    text = ""
    for page in doc:
        text += page.get_text()

    return text.strip()


def ask_groq(prompt, max_tokens=500):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt[:3000]
                }
            ],
            max_tokens=max_tokens,
            temperature=0.5,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Groq Error: {str(e)}"