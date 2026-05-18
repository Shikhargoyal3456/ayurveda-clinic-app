@echo off
echo ========================================
echo Deploying Kash AI to Railway
echo ========================================
echo.

echo Installing Railway CLI...
npm install -g @railway/cli

echo Logging in...
railway login

echo Initializing...
railway init

echo Deploying...
railway up

echo Getting URL...
railway domain

echo.
echo ========================================
echo Deployment complete!
echo ========================================
pause
