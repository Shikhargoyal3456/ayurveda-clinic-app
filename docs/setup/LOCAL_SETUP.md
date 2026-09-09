# 🚀 COMPLETE LOCAL SETUP GUIDE - Ayurveda Clinic App

This guide will get your app running locally on your machine with ALL errors fixed.

## ✅ Prerequisites

- **Python 3.11+** (Check: `python --version`)
- **Node.js 20+** (for WhatsApp service, optional)
- **Git** installed
- **PostgreSQL 12+** (recommended) OR SQLite (default for local dev)

---

## 📋 Step 1: Clone & Navigate

```bash
git clone https://github.com/Shikhargoyal3456/ayurveda-clinic-app.git
cd ayurveda-clinic-app
```

---

## 🔧 Step 2: Run Automated Setup

### macOS/Linux:
```bash
bash SETUP.sh
```

### Windows (Command Prompt):
```cmd
SETUP.bat
```

### Or Manual Setup (all platforms):

```bash
# Create virtual environment
python -m venv venv

# Activate it
# macOS/Linux:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate.bat

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Step 3: Environment Configuration

```bash
cp .env.example .env
```

### Minimal .env for Local Development:

```env
# App Settings
ENVIRONMENT=development
SECRET_KEY=your-random-secret-key-min-32-characters-here-12345
JWT_SECRET=your-jwt-secret-key-min-32-characters-here-12345
ENCRYPTION_KEY=your-32-byte-encryption-key-string-here

# Database (SQLite for quick start)
DATABASE_URL=sqlite:///./kash_ai.db

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Security
SESSION_HTTPS_ONLY=false
HTTPS_REDIRECT_ENABLED=false
ALLOW_PUBLIC_SIGNUP=true

# Optional AI (uses fallback if not set)
AI_ENABLED=true
STARTUP_RAG_WARMUP=false
STARTUP_LLM_WARMUP=false
```

### Generate Secure Keys:

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_bytes(32).hex())"
```

---

## 🗄️ Step 4: Initialize Database

```bash
alembic upgrade head
```

---

## ▶️ Step 5: Start the Application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Access Your App

Once running, open in browser:

- **Main App:** http://localhost:8000/new
- **API Docs (Swagger):** http://localhost:8000/docs
- **API ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/healthz

---

## 👤 First-Time Setup

1. Go to: `http://localhost:8000/new`
2. Click **Sign Up**
3. Create first doctor account
4. After setup, set `ALLOW_PUBLIC_SIGNUP=false` in `.env`

---

## 🐛 Common Errors & Fixes

### ❌ `ModuleNotFoundError: No module named 'app'`
```bash
# Ensure venv is activated and you're in project root
cd /path/to/ayurveda-clinic-app
source venv/bin/activate
```

### ❌ Database connection errors
```bash
pip install --no-cache-dir --force-reinstall psycopg2-binary
pip install -r requirements.txt
```

### ❌ Alembic migration errors
```bash
rm kash_ai.db
alembic stamp head
alembic upgrade head
```

### ❌ Redis connection errors
```env
# Leave empty to use in-memory fallback
REDIS_URL=
```

### ❌ Missing templates directory
```bash
mkdir -p templates static/images logs
```

### ❌ Import errors
```bash
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

---

## 🧪 Run Tests

```bash
pytest -v
```

---

## 📊 Health Checks

```bash
# Check environment
python verify_environment.py

# Check API
curl http://localhost:8000/api

# Check health
curl http://localhost:8000/healthz
```

---

## 🔐 Security Notes

⚠️ **NEVER commit .env to GitHub!**

For production:
- Set `ENVIRONMENT=production`
- Use strong keys
- Enable HTTPS
- Use PostgreSQL
- Configure Redis
- Set `ALLOW_PUBLIC_SIGNUP=false`

---

## ✨ You're Ready!

Your app should now be running at **http://localhost:8000** 🎉

