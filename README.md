# 🚀 JobGenAI – AI-Powered Job Recommendation System

JobGenAI is a Generative AI-powered job recommendation system that analyzes user resumes and provides intelligent, relevant job suggestions using semantic understanding instead of traditional keyword matching and helps to improve job opportunites.

---

## 📌 Overview

With the rapid growth of job platforms like LinkedIn and Naukri, job seekers face information overload and inefficient search processes. Most platforms rely on keyword matching, which fails to understand real skills and experience.

JobGenAI addresses this problem by leveraging AI and Large Language Models to understand resumes contextually and recommend meaningful job opportunities.

---

## 🧠 Key Features

- 📄 Resume Upload (PDF)
- 🤖 AI-based Resume Analysis (LLM)
- 🧩 Skill Extraction (Technical + Soft Skills)
- 📊 Skill Gap Detection
- 🛠️ Career Roadmap Suggestions
- 🔍 Job Keyword Generation
- 🌐 Multi-platform Job Fetching (LinkedIn, Naukri)
- 📈 Ranked Job Recommendations
- 🧾 Explainable Outputs

---

## 🏗️ System Architecture

The system follows a modular pipeline:

1. Resume Upload  
2. Resume Text Extraction  
3. LLM-Based Analysis  
4. Job Keyword Generation  
5. Job Fetching via APIs  
6. Job Ranking & Recommendation  

---

## 🖼️ Architecture Diagram

<img width="623" height="438" alt="image" src="https://github.com/user-attachments/assets/13e411bf-bc03-41d2-8b54-395806f8a367" />


---

## ⚙️ Technology Stack

- **Programming Language:** Python  
- **Frontend:** Streamlit  
- **Backend:** Python-based APIs  
- **AI/LLM:** Groq / LLaMA Models  
- **Resume Processing:** PyMuPDF  
- **Job Data Sources:** Apify APIs (LinkedIn, Naukri)  
- **Environment Management:** python-dotenv  

---

## 🔄 Workflow

1. User uploads resume (PDF)  
2. Resume text is extracted using PyMuPDF  
3. LLM analyzes:
   - Skills  
   - Experience  
   - Summary  
   - Skill gaps  
4. Job-related keywords are generated  
5. Jobs are fetched from APIs  
6. Jobs are filtered, ranked, and displayed  

---

## 📊 Project Scope

- Resume understanding  
- Skill gap identification  
- AI-based career roadmap  
- Multi-platform job recommendations  

---

## ⚠️ Limitations

- Dependency on third-party APIs  
- API rate limits  
- Job availability controlled by external platforms  

---

## 🚀 Future Enhancements

- User authentication and profiles  
- Job alerts and notifications  
- Resume ATS score analysis  
- React-based frontend  
- Job tracking dashboard  
- Fine-tuned AI models  

---

## 🛠️ Setup & Run

```bash
# Clone repository
git clone https://github.com/yourusername/JobGenAI.git

# Go to project folder
cd JobGenAI

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run app.py
