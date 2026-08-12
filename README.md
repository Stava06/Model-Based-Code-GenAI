# Model-Based Code GenAI

Capstone work on generating runnable software from **OPL (Object-Process Language)** / **OPM** models. The project treats the model as the source of truth, then uses agentic iterative code generation to produce full-stack applications that stay faithful to those models.

> *The Model Is the System* — full-stack applications via **MOSAIC**.

## Capstones

| Capstone | Focus | Contents |
|----------|--------|----------|
| **[Capstone A](Capstone_A/)** | Foundations & communication | Book and presentation on OPL-to-code |
| **[Capstone B](Capstone_B/)** | Product delivery — **MOSAIC** | Working app, guides, poster, and demo |

```
Model-Based-Code-GenAI/
├── Capstone_A/          # Research & presentation materials
└── Capstone_B/          # MOSAIC product + documentation
    └── MOSAIC/          # Full-stack application source
```

## Capstone A

Early materials that frame the problem and approach:

| Resource | Path |
|----------|------|
| Book | [`Capstone_A/Model-Based Code GenAI - Book.docx`](Capstone_A/Model-Based%20Code%20GenAI%20-%20Book.docx) |
| Presentation | [`Capstone_A/OPL to Code - Presentation.pptx`](Capstone_A/OPL%20to%20Code%20-%20Presentation.pptx) |

## Capstone B — MOSAIC

**MOSAIC** (*Model-driven, OPM-based System with Agentic Iterative Code generation*) is the delivered system: upload an OPL specification, run a Supervisor → Generator → Critic Gemini agent pipeline, download a React + Flask project zip, and inspect automated evaluation scores.

### Application

Source and setup instructions:

- **[Capstone_B/MOSAIC/README.md](Capstone_B/MOSAIC/README.md)** — architecture, quick start, API overview
- [appserver](Capstone_B/MOSAIC/appserver/README.md) — Flask API & agent pipeline
- [web client](Capstone_B/MOSAIC/myapp/my-web/README.md) — React UI

### Deliverables

| Resource | Path |
|----------|------|
| User Guide | [`Capstone_B/User Guide - MOSAIC.docx`](Capstone_B/User%20Guide%20-%20MOSAIC.docx) |
| Maintenance Guide | [`Capstone_B/Maintenance Guide - MOSAIC.docx`](Capstone_B/Maintenance%20Guide%20-%20MOSAIC.docx) |
| Book | [`Capstone_B/The Model Is the System - Book.docx`](Capstone_B/The%20Model%20Is%20the%20System%20-%20Book.docx) |
| Poster | [`Capstone_B/MOSAIC_poster.jpeg`](Capstone_B/MOSAIC_poster.jpeg) |
| Demonstration | [`Capstone_B/MOSAIC_demonstration.mkv`](Capstone_B/MOSAIC_demonstration.mkv) |

## Quick start (MOSAIC)

From the MOSAIC app folder:

```bash
# Server
cd Capstone_B/MOSAIC/appserver
pip install -r requirements.txt
# create .env (see Capstone_B/MOSAIC/README.md), then:
python app.py

# Client (separate terminal)
cd Capstone_B/MOSAIC/myapp/my-web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). You need MongoDB and a Gemini API key — details in the [MOSAIC README](Capstone_B/MOSAIC/README.md).

## Stack (MOSAIC)

- **Frontend:** React + Vite
- **Backend:** Flask + Google ADK / Gemini
- **Data:** MongoDB (users, OPL docs, logic maps, evaluation scores)
