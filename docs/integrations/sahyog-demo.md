# SAHYOG-ready integration boundary

RRR includes a government-integration demonstration gateway at `/integration/sahyog-demo`.

This is a simulation only. It is not connected to live SAHYOG or any live government system, does not use government credentials, and does not imply official authorization.

The gateway provides:

- Demo authentication using `RRR_DEMO_USER` and `RRR_DEMO_PASSWORD`.
- A simulated complaint intake package.
- Import into the existing RRR case creation and wallet-registration flow.

Demo access is enabled only when `APP_ENV=development` or `DEMO_MODE=true`. For the Vercel + Railway deployment, set `DEMO_MODE=true`, `RRR_DEMO_USER=RRR@SIH`, and `RRR_DEMO_PASSWORD=SIH@2026` on the Railway/API service. Vercel serves the frontend and forwards login requests to that API; the credentials are not frontend environment variables. The demo session is short-lived and held in application memory; it is not a production identity system.

Claim boundary: SAHYOG-ready integration boundary, simulated intake, demo authentication, not connected to live government systems.
