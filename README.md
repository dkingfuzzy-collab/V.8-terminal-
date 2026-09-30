# Dickson Bot V8 — Paper/Research Terminal

Mobile-first SMC/ICT research scanner. This release is **paper/research only** and contains no live order execution or broker-order API.

## What is included
- TraderDNA-style scanner cards: Daily → 4H → 1H → 15M
- Five-bot confluence: Structure, Liquidity Sweep, FVG, Displacement, ICT/SMC Context
- Order Block / POI analysis
- Entry / invalidation / TP1 / TP2 / TP3 model for paper simulation
- Empirical historical paper statistics with 95% Wilson interval when sample >= 10
- Multi-provider market data: Yahoo chart fallback, Coinbase public BTC data, optional Twelve Data
- Lazy historical bootstrap so the scanner does not remain at 0 candles
- Built-in diagnostics endpoint
- Render Blueprint at repository root
- Automated compile/test check during Render build
- Private authentication using PBKDF2 + HttpOnly session cookie

## Render
Connect this repository to Render as a Blueprint. The root `render.yaml` points `rootDir` to `backend`, installs requirements, compiles the application, starts FastAPI on `$PORT`, and checks `/api/health`.

Set `ADMIN_PASSWORD` in Render. Do not commit secrets.

## Local
From `backend/`:
`pip install -r requirements.txt`
`ADMIN_PASSWORD=change_me uvicorn main:app --reload`

## Important
All setup generation, outcome tracking and execution controls are paper/research simulations. No live broker order execution is included.
