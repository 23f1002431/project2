# Deployment Guide: GitHub + Hugging Face Spaces

This guide will help you deploy your Quiz Solver application to GitHub and Hugging Face Spaces.

---

## Part 1: Prepare Your Code for GitHub

### Step 1: Update .gitignore (Already Done ✓)

Your `.gitignore` should exclude:
- `venv/` - Virtual environment
- `.env` - Environment variables (sensitive!)
- `__pycache__/` - Python cache files
- `.playwright/` - Playwright browsers

✅ Your `.gitignore` already has these.

### Step 2: Create .env.example Template

Create a template file for environment variables (without actual secrets):

```bash
# Create .env.example file
```

**Content for `.env.example`:**
```env
# Student Information
STUDENT_EMAIL=your-email@example.com
STUDENT_SECRET=your-secret-string

# LLM Configuration
DEFAULT_LLM_PROVIDER=aipipe
AIPIPE_API_KEY=your-aipipe-api-key-here
AIPIPE_BASE_URL=https://api.aipipe.ai/v1
AIPIPE_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.3
LLM_REQUEST_TIMEOUT=60

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Prompts (optional)
SYSTEM_PROMPT=Your system prompt here
USER_PROMPT=Your user prompt here

# Timeouts
QUIZ_TIMEOUT=180
```

### Step 3: Update README.md

Make sure your README has:
- Clear description
- Installation instructions
- Environment variables setup
- Deployment instructions
- MIT License mentioned (required by project)

### Step 4: Initialize Git Repository

```bash
# Navigate to your project directory
cd C:\Users\Admin\Desktop\TDS\project2

# Initialize git (if not already done)
git init

# Check status
git status

# Add all files
git add .

# Make first commit
git commit -m "Initial commit: Quiz Solver API"
```

### Step 5: Create GitHub Repository

1. **Go to GitHub**: https://github.com
2. **Click "New Repository"** (top right → green button)
3. **Repository settings:**
   - Name: `quiz-solver` (or your preferred name)
   - Description: "Intelligent quiz solver using LLMs for data analysis tasks"
   - Visibility: **Public** (required for evaluation)
   - ✅ Add README: No (we already have one)
   - ✅ Add .gitignore: No (we already have one)
   - License: **MIT License** (required!)
4. **Click "Create repository"**

### Step 6: Push Code to GitHub

```bash
# Add remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/quiz-solver.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

**If asked for credentials:**
- Use GitHub Personal Access Token (not password)
- Create token: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- Permissions needed: `repo` (full control)

---

## Part 2: Deploy to Hugging Face Spaces

Hugging Face Spaces can host FastAPI applications. Here's how:

### Step 1: Create Hugging Face Account

1. Go to: https://huggingface.co
2. Sign up for a free account
3. Verify your email

### Step 2: Create a New Space

1. Go to: https://huggingface.co/spaces
2. Click **"Create new Space"**
3. **Settings:**
   - Space name: `quiz-solver` (or your preferred name)
   - SDK: Select **Docker**
   - Visibility: **Public** or **Private**
4. Click **"Create Space"**

### Step 3: Prepare Files for Hugging Face

Hugging Face Spaces needs specific files. Create these:

#### File 1: `Dockerfile`

Create a file named `Dockerfile` in your project root:

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Expose port (Hugging Face uses port 7860 by default)
EXPOSE 7860

# Set environment variable
ENV PORT=7860

# Run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
```

#### File 2: Update `main.py` for Hugging Face Port

Your `main.py` should read port from environment variable. Check line 289:

```python
# In main.py, the port should be configurable:
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", config.API_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

#### File 3: `.dockerignore`

Create `.dockerignore`:

```
venv/
__pycache__/
*.pyc
.env
.git/
.gitignore
*.log
.pytest_cache/
.coverage
htmlcov/
```

#### File 4: `README.md` for Space

Create or update `README.md` with Space-specific content at the top:

```markdown
---
title: Quiz Solver API
emoji: 🎯
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: 3.0.0
app_file: Dockerfile
pinned: false
license: mit
---

# Quiz Solver API

An intelligent application that solves data-related quizzes using LLMs.
```

### Step 4: Push Code to Hugging Face

#### Option A: Using Git (Recommended)

```bash
# Add Hugging Face remote
git remote add huggingface https://huggingface.co/spaces/YOUR_USERNAME/quiz-solver

# Push to Hugging Face
git push huggingface main
```

#### Option B: Using Web Interface

1. Go to your Space page
2. Click **"Files and versions"** tab
3. Click **"Add file"** → **"Upload files"**
4. Upload all your files (drag and drop)
5. Click **"Commit changes"**

### Step 5: Set Environment Variables

1. Go to your Space settings
2. Navigate to **"Variables and secrets"**
3. Add all your environment variables:
   - `STUDENT_EMAIL`
   - `STUDENT_SECRET`
   - `AIPIPE_API_KEY`
   - `AIPIPE_BASE_URL`
   - `AIPIPE_MODEL`
   - `DEFAULT_LLM_PROVIDER`
   - `API_PORT` (set to `7860` for Hugging Face)
   - All other variables from your `.env` file

4. Click **"Save"**

### Step 6: Wait for Build

1. Go to your Space page
2. Click **"Logs"** tab to see build progress
3. Wait for status to change to **"Running"** (usually 5-10 minutes first time)

### Step 7: Get Your API URL

Once deployed, your API will be available at:
```
https://YOUR_USERNAME-quiz-solver.hf.space
```

Health check:
```
https://YOUR_USERNAME-quiz-solver.hf.space/health
```

Quiz endpoint:
```
https://YOUR_USERNAME-quiz-solver.hf.space/quiz
```

---

## Part 3: Testing Deployment

### Test GitHub Repository

```bash
# Clone your repo to verify
git clone https://github.com/YOUR_USERNAME/quiz-solver.git
cd quiz-solver

# Verify all files are there
ls -la

# Check .env.example exists (not .env!)
```

### Test Hugging Face Space

1. **Health Check:**
```bash
curl https://YOUR_USERNAME-quiz-solver.hf.space/health
```

Expected response:
```json
{"status":"healthy","timestamp":"2025-11-28T..."}
```

2. **Test Quiz Endpoint:**
```bash
curl -X POST https://YOUR_USERNAME-quiz-solver.hf.space/quiz \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

Expected response:
```json
{"status":"accepted","message":"Quiz task received and processing started"}
```

---

## Part 4: Troubleshooting

### GitHub Issues

**Problem: Can't push to GitHub**
- Solution: Use Personal Access Token instead of password
- Create token: Settings → Developer settings → Personal access tokens

**Problem: Repository not showing all files**
- Solution: Make sure `.gitignore` isn't excluding important files
- Check: `git status` shows all files you want to include

### Hugging Face Issues

**Problem: Build failing**
- Check: `Dockerfile` syntax is correct
- Check: All files are uploaded
- Check: `requirements.txt` has all dependencies

**Problem: App not starting**
- Check: Port is set to 7860 or uses `PORT` env variable
- Check: Environment variables are set correctly
- Check: Logs tab for error messages

**Problem: Playwright not working**
- Solution: Make sure `Dockerfile` installs Playwright dependencies
- Check: `playwright install chromium` is in Dockerfile

**Problem: API not accessible**
- Check: Space is set to Public (if testing externally)
- Check: API endpoint URL is correct
- Check: CORS settings if needed

---

## Part 5: Quick Checklist

Before deploying, ensure:

- [ ] ✅ `.gitignore` excludes sensitive files (`.env`, `venv/`)
- [ ] ✅ `.env.example` exists (template without secrets)
- [ ] ✅ `LICENSE` file exists (MIT License)
- [ ] ✅ `README.md` is complete
- [ ] ✅ All code is committed to git
- [ ] ✅ GitHub repository is public
- [ ] ✅ `Dockerfile` is created for Hugging Face
- [ ] ✅ Environment variables are set in Hugging Face
- [ ] ✅ Health endpoint works
- [ ] ✅ Quiz endpoint works

---

## Part 6: Important Notes

### Security

1. **Never commit `.env` file** - It contains secrets!
2. **Use `.env.example`** - Template without actual values
3. **Set secrets in Hugging Face** - Use Variables and secrets section
4. **GitHub is public** - Don't put secrets in code comments

### URLs for Submission

When submitting to the Google Form, use:
- **GitHub Repo URL**: `https://github.com/YOUR_USERNAME/quiz-solver`
- **API Endpoint URL**: `https://YOUR_USERNAME-quiz-solver.hf.space` (or your Hugging Face URL)

### Hugging Face Space Requirements

- Docker SDK selected when creating space
- Port must be 7860 or use `PORT` env variable
- Environment variables must be set in Space settings
- First build takes 5-10 minutes

### Cost

- GitHub: Free for public repositories ✅
- Hugging Face Spaces: Free tier available ✅
- API calls: Depends on your LLM provider usage

---

## Part 7: Commands Summary

### GitHub Commands

```bash
# Initialize and push
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/quiz-solver.git
git branch -M main
git push -u origin main

# Subsequent updates
git add .
git commit -m "Update description"
git push
```

### Hugging Face Commands

```bash
# Add remote and push
git remote add huggingface https://huggingface.co/spaces/YOUR_USERNAME/quiz-solver
git push huggingface main

# Update space
git add .
git commit -m "Update description"
git push huggingface main
```

---

## Need Help?

- **GitHub Docs**: https://docs.github.com
- **Hugging Face Spaces Docs**: https://huggingface.co/docs/hub/spaces
- **Docker Docs**: https://docs.docker.com

---

**Ready to deploy?** Follow the steps above and your Quiz Solver will be live! 🚀

