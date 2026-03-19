# VerifyFlow – AI-Powered Document Fraud Detection

VerifyFlow is a full-stack web application that uses AI to detect document fraud. Upload any PDF or image document and get a detailed trust score, red flags, and a verdict powered by 5 specialized AI agents.

---

## 🏗️ Architecture

```
frontend (React + Vite + Tailwind)
    │  POST /upload
    │  GET  /stream/:jobId  (SSE)
    │  GET  /result/:jobId
    ▼
backend (FastAPI)
    │
    └── LangGraph Pipeline
            ├── 1. OCR Agent        (PyMuPDF + Tesseract)
            ├── 2. NER Agent        (spaCy – companies, PAN, GSTIN, dates)
            ├── 3. Web Checker      (Tavily API – company verification)
            ├── 4. Anomaly Scorer   (font diversity, metadata, OCR confidence)
            └── 5. Vision Agent     (Gemini 2.5 Pro – visual fraud signals)
                        │
                        └── Aggregator → Trust Score 0–100 + Verdict
```

## 🤖 AI Caller – 5-Layer Fallback

All agents share a central `ai_caller.py` with automatic key rotation and fallback:

| Layer | Provider | Model |
|-------|----------|-------|
| 1–3 | Gemini (key rotation) | gemini-2.5-pro-latest |
| 4 | Groq | llama-3.3-70b-versatile |
| 5 | OpenRouter | openai/gpt-4o-mini |
| 6 | Safe default | Pre-defined JSON response |

## 📊 Trust Score Calculation

| Agent | Weight | Description |
|-------|--------|-------------|
| OCR Confidence | 20% | Average Tesseract confidence |
| NER Completeness | 10% | Key entities extracted |
| Web Verification | 25% | Companies verified online |
| Anomaly Score | 25% | Inverted anomaly (low anomaly = high score) |
| Vision Analysis | 20% | Gemini visual fraud detection |

**Verdicts:** `AUTHENTIC` (75–100) · `SUSPICIOUS` (40–74) · `FRAUDULENT` (0–39)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Tesseract OCR installed (`apt install tesseract-ocr` or `brew install tesseract`)

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev
```

Open http://localhost:5173

---

## 🔑 Environment Variables

Create `backend/.env` from `backend/.env.example`:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY_1` | Recommended | Google Gemini API key (primary) |
| `GEMINI_API_KEY_2` | Optional | Gemini key 2 (rotation) |
| `GEMINI_API_KEY_3` | Optional | Gemini key 3 (rotation) |
| `GROQ_API_KEY` | Optional | Groq API key (fallback layer 4) |
| `OPENROUTER_API_KEY` | Optional | OpenRouter key (fallback layer 5) |
| `TAVILY_API_KEY` | Optional | Tavily search key (web verification) |

> **Note:** The app works without any API keys using safe default responses, but AI analysis will be limited.

---

## 🌐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload document (PDF/image), returns `job_id` |
| `GET` | `/status/{job_id}` | Get job status and agent progress |
| `GET` | `/result/{job_id}` | Get final analysis result |
| `GET` | `/stream/{job_id}` | Server-Sent Events stream for live updates |
| `GET` | `/health` | Health check |

### POST /upload

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@document.pdf"
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Document uploaded. Processing started."
}
```

### GET /result/{job_id}

```json
{
  "job_id": "550e8400...",
  "trust_score": 82,
  "verdict": "AUTHENTIC",
  "red_flags": [],
  "summary": "Document appears authentic...",
  "agent_results": { ... }
}
```

---

## 🚢 Deployment

### Backend → Render

1. Fork this repository
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Set environment variables in Render dashboard

### Frontend → Vercel

1. Create a new project on [Vercel](https://vercel.com)
2. Import your GitHub repo, set **Root Directory** to `frontend`
3. Set `VITE_API_URL` environment variable to your Render backend URL
4. Deploy – `vercel.json` handles SPA routing and API proxy

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, LangGraph |
| AI Agents | spaCy, PyMuPDF, Tesseract, Gemini 2.5 Pro |
| Search | Tavily API |
| Frontend | React 18, Vite, Tailwind CSS, Framer Motion |
| Deployment | Render (backend), Vercel (frontend) |

---

## 📁 Project Structure

```
XENOTHON/
├── backend/
│   ├── main.py              # FastAPI app (upload, status, result, SSE)
│   ├── graph.py             # LangGraph pipeline
│   ├── ai_caller.py         # 6-layer fallback AI caller
│   ├── models.py            # Pydantic models
│   ├── requirements.txt
│   ├── .env.example
│   └── agents/
│       ├── ocr_agent.py     # PyMuPDF + Tesseract
│       ├── ner_agent.py     # spaCy NER + PAN/GSTIN regex
│       ├── web_checker_agent.py  # Tavily company verification
│       ├── anomaly_scorer.py     # Font/metadata anomaly detection
│       └── vision_agent.py      # Gemini 2.5 Pro vision
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx   # Drag & drop upload
│   │   │   └── ResultPage.jsx   # Results dashboard
│   │   └── components/
│   │       ├── AgentProgress.jsx # Live SSE progress tracker
│   │       ├── TrustScore.jsx    # Animated circular gauge
│   │       └── RedFlags.jsx      # Severity-colored flags list
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── vercel.json
└── render.yaml              # Render deployment config
```

## License

MIT
