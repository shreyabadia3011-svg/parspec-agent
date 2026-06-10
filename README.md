# Parspec Construction Procurement Agent

AI-powered construction spec processing, product matching, and quote generation.

**Built by Shreya Badia**

## Features

- 4-layer pipeline: Inspect → Extract → Match → Quote
- 50-product MEP catalogue (7 categories)
- Substitution Intelligence, Win Probability, Market Trends
- Manufacturer Live Pricing, Batch Processing, Dynamic Pricing
- Spec Compliance Checker, HITL Review Queue
- Submittal Revision Tracker, Engineer Approval Prediction
- O&M Auto-Assembly, Multi-Distributor Collaboration

## Run locally

```bash
pip install -r requirements.txt
python server.py
# → http://localhost:5055
```

## Deploy on Render

1. Push this repo to GitHub
2. Connect repo on [render.com](https://render.com)
3. Render auto-detects `render.yaml` and deploys
