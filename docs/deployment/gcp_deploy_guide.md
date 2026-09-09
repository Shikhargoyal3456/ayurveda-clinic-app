# One-Command GCP Deployment

## Prerequisites

1. Google Cloud account with billing enabled
2. `gcloud` CLI installed

## Steps

### 1. Login and set project

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Run deployment (ONE COMMAND)

```bash
./deploy_gcp.sh
```

### 3. Get your URL

The URL will be displayed after deployment.

### 4. Test

```bash
curl YOUR_URL/health
```
