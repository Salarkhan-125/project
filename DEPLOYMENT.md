# ctfWithAi — Deployment Guide

## What goes where

```
Vercel  →  web/frontend/         (React app)
Ubuntu  →  everything else       (FastAPI, core engine, MySQL, Docker)
```

---

## Part 1 — Ubuntu/AWS Backend

### 1. Server Requirements

- Ubuntu 22.04 LTS
- Open ports: **22** (SSH), **8000** (API), **3306** (MySQL, local only), **40000-50000** (Docker lab containers)
- Docker + Docker Compose installed
- Python 3.11+, Node.js (only needed if running start.py on the same box)

### 2. Upload your project

```bash
# From your local machine — exclude frontend build artifacts and node_modules
rsync -avz --exclude='node_modules' --exclude='web/frontend/build' \
  c:/deploy/Project/ ubuntu@YOUR_IP:/home/ubuntu/ctfWithAi/
```

### 3. Set up Python environment

```bash
cd /home/ubuntu/ctfWithAi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure .env

```bash
cp .env.example .env
nano .env
```

**Critical values to set for production:**

```ini
# Your server's public IP or domain (with http/https)
SERVER_HOST=http://YOUR_PUBLIC_IP

# Your Vercel frontend URL
FRONTEND_URL=https://your-app.vercel.app

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_secure_password
DB_NAME=ctfWithAi
DATABASE_URL=mysql+pymysql://root:your_secure_password@localhost:3306/ctfWithAi

# Security — generate strong values:
# python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=<generate_strong_value>
SECRET_KEY=<generate_strong_value>
INTERNAL_API_KEY=<generate_strong_value>
FLAG_HMAC_KEY=<generate_strong_value>   # ⚠️ NEVER change after first run

# Email (get from resend.com)
RESEND_API_KEY=re_your_key_here
EMAIL_FROM_ADDRESS=noreply@yourdomain.com   # Must be verified in Resend
EMAIL_FROM_NAME=ctfWithAi

# Groq AI
GROQ_API_KEY=gsk_your_groq_key_here

# Turn off debug in production
DEBUG=False
SKIP_EMAIL_VERIFICATION=false
```

### 5. Set up MySQL

```bash
sudo apt install mysql-server -y
sudo mysql -u root -p
```

```sql
CREATE DATABASE ctfWithAi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ctfWithAi'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON ctfWithAi.* TO 'ctfWithAi'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 6. Run database migrations

```bash
source venv/bin/activate
python migrate_enterprise.py
python migrate_rbac.py
```

### 7. Start the backend

```bash
# Option A: use the start script (also starts frontend if needed)
source venv/bin/activate
python start.py

# Option B: start API only (production-recommended — use systemd or screen)
source venv/bin/activate
uvicorn web.api.main:app --host 0.0.0.0 --port 8000
```

### 8. (Optional) Run as a systemd service

```bash
sudo nano /etc/systemd/system/ctfWithAi.service
```

```ini
[Unit]
Description=ctfWithAi API
After=network.target mysql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/ctfWithAi
ExecStart=/home/ubuntu/ctfWithAi/venv/bin/uvicorn web.api.main:app --host 0.0.0.0 --port 8000
Restart=always
EnvironmentFile=/home/ubuntu/ctfWithAi/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ctfWithAi
sudo systemctl start ctfWithAi
sudo systemctl status ctfWithAi
```

### 9. Verify the API is running

```bash
curl http://localhost:8000/api/docs
# Should return the FastAPI docs HTML
```

---

## Part 2 — Vercel Frontend

### 1. Push `web/frontend/` to a Git repo

Vercel deploys from Git. Either:

- Push the whole project (Vercel will pick the frontend subfolder), **or**
- Push only `web/frontend/` as a separate repo

### 2. Connect to Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → import your repo
2. Set **Root Directory** → `web/frontend`
3. Framework preset → **Create React App**
4. Build command → `npm run build` (auto-detected)
5. Output directory → `build` (auto-detected)

### 3. Set Environment Variables in Vercel dashboard

Go to **Project → Settings → Environment Variables** and add:

| Variable                | Value                                   |
| ----------------------- | --------------------------------------- |
| `REACT_APP_API_URL`     | `http://YOUR_AWS_IP:8000`               |
| `REACT_APP_SERVER_HOST` | `YOUR_AWS_IP` (just the IP, no http://) |

> **Note:** Use `https://` if you set up SSL on your backend. For plain HTTP AWS, use `http://`.

### 4. Deploy

Click **Deploy** — Vercel will build and give you a URL like `https://ctfWithAi-abc123.vercel.app`.

### 5. Update your backend's .env

Set `FRONTEND_URL` to your Vercel URL so CORS and password reset emails work:

```ini
FRONTEND_URL=https://ctfWithAi-abc123.vercel.app
```

Then restart the backend.

---

## Part 3 — Email Setup (Future)

When you're ready to use email (OTP + password reset):

1. Sign up at [resend.com](https://resend.com)
2. Add and verify your domain (e.g., `ctfWithAi.io`)
3. Create an API key
4. Update `.env` on Ubuntu:
   ```ini
   RESEND_API_KEY=re_your_real_key
   EMAIL_FROM_ADDRESS=noreply@ctfWithAi.io
   EMAIL_FROM_NAME=ctfWithAi
   SKIP_EMAIL_VERIFICATION=false
   ```
5. Restart the backend — email is live.

---

## Quick Checklist

### Backend (Ubuntu)

- [ ] `.env` has real values (not `changeme_*`)
- [ ] `SERVER_HOST` = `http://YOUR_PUBLIC_IP`
- [ ] `FRONTEND_URL` = your Vercel URL
- [ ] MySQL running and `ctfWithAi` database created
- [ ] Migrations run
- [ ] API responding at `http://YOUR_IP:8000/api/docs`
- [ ] Docker installed and accessible by the app user
- [ ] Ports 8000 and 40000-50000 open in AWS Security Group

### Frontend (Vercel)

- [ ] `REACT_APP_API_URL` = `http://YOUR_AWS_IP:8000`
- [ ] `REACT_APP_SERVER_HOST` = `YOUR_AWS_IP`
- [ ] Deploy successful
- [ ] Login page loads and can reach the backend
