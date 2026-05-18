@echo off
echo ========================================
echo Deploying Kash AI to Google Cloud Run
echo ========================================
echo.

echo Step 1: Setting project...
gcloud config set project %1

echo Step 2: Enabling APIs...
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo Step 3: Deploying to Cloud Run...
gcloud run deploy kash-ai --source . --platform managed --region us-central1 --allow-unauthenticated --memory 1Gi --cpu 1 --timeout 300

echo.
echo ========================================
echo Deployment complete!
echo Get your URL from the output above
echo ========================================
pause
