# Deployment Guide — Vercel (Frontend) + Railway (Backend)

This guide walks through deploying the Crypto Fraud Intelligence platform:
- **Frontend** (React/Vite SPA) → **Vercel**
- **Backend** (FastAPI + PostgreSQL + Neo4j) → **Railway**

---

## Prerequisites

- GitHub account with this repository pushed
- [Vercel account](https://vercel.com) (free)
- [Railway account](https://railway.app) (free — $5/mo credit, no credit card required)
- [Neo4j Aura account](https://neo4j.com/cloud/platform/aura-graph-database/) (free tier)

---

## Step 1 — Push to GitHub

Make sure the repo is on GitHub:

```bash
git add .
git commit -m "chore: add Vercel and Railway deployment config"
git push origin main
```

> ⚠️ The `.env` file is in `.gitignore` — your credentials will NOT be committed.

---

## Step 2 — Deploy Backend on Railway

### 2a. Create Railway Project

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"Deploy from GitHub repo"**
3. Select your `CRYPTO FRAUD INTELLIGENCE` repo
4. Railway will auto-detect the `railway.toml` at the root and use the Dockerfile

### 2b. Add PostgreSQL Database

1. In your Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway auto-injects `DATABASE_URL` into your service — no manual configuration needed

### 2c. Set Environment Variables

In your Railway service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `ALCHEMY_API_KEY` | `alch_N2npkDETokS1WG7MEoN4q` |
| `ALCHEMY_NETWORK` | `eth-mainnet` |
| `BLOCKCHAIN_DATA_MODE` | `LIVE` |
| `DATABASE_AUTO_MIGRATE` | `true` |
| `AUTH_REQUIRED` | `false` |
| `TRACE_DEFAULT_HOPS` | `2` |
| `TRACE_DEFAULT_MAX_NODES` | `100` |
| `NEO4J_URI` | *(see Step 3 — add after Neo4j Aura setup)* |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | *(your Aura password)* |
| `CORS_EXTRA_ORIGINS` | *(add after Vercel deploy — see Step 4c)* |
| `API_ORIGIN` | *(your Railway public URL — auto-set after first deploy)* |

### 2d. Get Your Railway Backend URL

After deploy succeeds:
1. Go to **Settings** → **Networking** → **Generate Domain**
2. Copy the URL: `https://your-app-name.up.railway.app`

### 2e. Verify Backend Health

```bash
curl https://your-app-name.up.railway.app/health
# Should return: {"status": "ok"}

curl https://your-app-name.up.railway.app/api/v1/system/status
```

---

## Step 3 — Set Up Neo4j Aura (Free)

1. Go to [console.neo4j.io](https://console.neo4j.io) → **Create Free Instance**
2. Copy the connection URI: `neo4j+s://xxxxxxxx.databases.neo4j.io`
3. Copy the generated password
4. Back in Railway, add these variables:
   - `NEO4J_URI` = `neo4j+s://xxxxxxxx.databases.neo4j.io`
   - `NEO4J_USERNAME` = `neo4j`
   - `NEO4J_PASSWORD` = *(Aura password)*
   - `NEO4J_DATABASE` = `neo4j`

> **Note**: If you skip this, the app will show `NOT_CONFIGURED` for graph features but will otherwise work normally.

---

## Step 4 — Deploy Frontend on Vercel

### 4a. Import to Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click **"Import Git Repository"**
3. Select your repo
4. Vercel will auto-detect the root `vercel.json`

### 4b. Configure Build Settings

In the Vercel import wizard, verify:
- **Framework Preset**: Other (or Vite)
- **Root Directory**: *(leave as repo root — `vercel.json` handles this)*
- **Build Command**: `cd apps/investigator-web && npm install && npm run build`
- **Output Directory**: `apps/investigator-web/dist`

### 4c. Add Environment Variables

In Vercel → **Environment Variables**, add:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://your-app-name.up.railway.app` |

### 4d. Deploy

Click **Deploy**. Your frontend will be live at `https://your-app.vercel.app`.

### 4e. Add Vercel URL to Railway CORS

Back in Railway → Variables, update:
- `CORS_EXTRA_ORIGINS` = `https://your-app.vercel.app`
- `API_ORIGIN` = `https://your-app-name.up.railway.app`

Railway will redeploy automatically.

---

## Step 5 — Verify End-to-End

1. Open `https://your-app.vercel.app`
2. The dashboard should load without API errors
3. Go to **Cases** → **New Case** → fill in a test case
4. The case should appear in the list (confirms PostgreSQL works)
5. Try a **Wallet Intelligence Lookup** with a real Ethereum address (confirms Alchemy works)

---

## Environment Variables Reference

### Frontend (Vercel)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | ✅ | Full Railway backend URL |

### Backend (Railway)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Auto-injected by Railway PostgreSQL plugin |
| `ALCHEMY_API_KEY` | ✅ | Your Alchemy API key |
| `ALCHEMY_NETWORK` | ✅ | `eth-mainnet` |
| `BLOCKCHAIN_DATA_MODE` | ✅ | `LIVE` for real data |
| `DATABASE_AUTO_MIGRATE` | ✅ | `true` — runs SQL migrations on startup |
| `API_ORIGIN` | ✅ | Railway backend public URL |
| `CORS_EXTRA_ORIGINS` | ✅ | Vercel frontend URL (space-separated) |
| `AUTH_REQUIRED` | ✅ | `false` unless you configure JWT |
| `NEO4J_URI` | ⚪ | Neo4j Aura URI (optional) |
| `NEO4J_USERNAME` | ⚪ | `neo4j` |
| `NEO4J_PASSWORD` | ⚪ | Aura password |
| `REDIS_URL` | ⚪ | Optional — only for realtime webhook queue |
| `TRONGRID_API_KEY` | ⚪ | Optional — Tron chain support |

---

## Updating Deployments

Both Vercel and Railway auto-deploy on every push to `main`. No manual steps needed after initial setup.

```bash
git add .
git commit -m "feat: your change"
git push origin main
# Both platforms deploy automatically
```

---

## Troubleshooting

### Frontend shows "API OFFLINE"
- Check `VITE_API_BASE_URL` in Vercel — must be the full Railway URL including `https://`
- Check Railway logs for startup errors
- Verify `/health` returns `{"status": "ok"}` at the Railway URL

### "CORS error" in browser console
- Make sure `CORS_EXTRA_ORIGINS` in Railway includes your exact Vercel URL (no trailing slash)
- Redeploy Railway after changing environment variables

### Database migration errors on Railway startup
- Check Railway PostgreSQL plugin is connected
- `DATABASE_URL` should be auto-injected — verify in Variables tab
- Check startup logs for migration errors

### Neo4j shows NOT_CONFIGURED
- This is expected if `NEO4J_URI` is not set — graph features will be disabled
- Add Aura credentials to Railway Variables to enable graph features
