# Qonnect Tool - Deployment Guide

## Quick Deploy Options

### Option 1: Render.com (Recommended - Easiest)

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Add deployment files"
   git push origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com)
   - Sign up with GitHub
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file

3. **Set Environment Variables**:
   - In Render dashboard, go to Environment
   - Add `GOOGLE_SERVICE_ACCOUNT_JSON` as a secret
   - Copy your entire `credentials.json` content as the value

### Option 2: Railway.app

1. **Deploy**:
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub
   - Click "Deploy from GitHub repo"
   - Select your repository

2. **Set Environment Variables**:
   - Add `GOOGLE_SERVICE_ACCOUNT_JSON` in Variables tab
   - Copy your `credentials.json` content as the value

### Option 3: Fly.io

1. **Install Fly CLI**:
   ```bash
   brew install flyctl  # macOS
   ```

2. **Deploy**:
   ```bash
   fly auth login
   fly launch  # This will use the fly.toml file
   fly secrets set GOOGLE_SERVICE_ACCOUNT_JSON="$(cat credentials.json)"
   fly deploy
   ```

## Security Notes

⚠️ **Important**: Never commit `credentials.json` to a public repository. Always use environment variables for sensitive data.

## Post-Deployment

After deployment, your app will be available at:
- Render: `https://your-app-name.onrender.com`
- Railway: `https://your-app-name.up.railway.app`
- Fly.io: `https://your-app-name.fly.dev`

## Environment Variables Required

- `PORT`: Set automatically by most platforms
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Your Google Service Account credentials as JSON string