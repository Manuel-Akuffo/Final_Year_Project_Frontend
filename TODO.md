# TODO — AI-Powered Predictive Cardiovascular Risk Monitoring System

## Step 1 — Backend hardening & trend support
- [ ] Update `app.py` to remove hardcoded Groq API key; read from `GROQ_API_KEY` env var.
- [ ] Add risk probability output (`risk_score`) and map to risk_level (Low/Medium/High) based on model probability.
- [ ] Add new endpoint `GET /trend/<user_id>` returning time-series of BP/HR and predicted risk.

## Step 2 — Improve chatbot explanation
- [ ] Update `POST /chat` system prompt to include recent trend summary (computed from DB records).
- [ ] Ensure chatbot message includes clear, non-diagnostic safety disclaimer.

## Step 3 — Frontend enhancements
- [ ] Update `venv/Script.js` to display `risk_score` and risk level.
- [ ] Add charts (client-side) for BP/HR/risk trend using existing records.

## Step 4 — Reports (optional but defense-friendly)
- [ ] Implement PDF report generation endpoint and “Download PDF” button (server-side `reportlab`).

## Step 5 — Testing
- [ ] Re-run `train_model.py` (if model changes).
- [ ] Test endpoints: `/predict`, `/records/<user_id>`, `/trend/<user_id>`, `/chat`.

