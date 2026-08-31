# Google Cloud Deployment Guide

## Prerequisites
- Google Cloud account and active billing
- A Google Cloud project
- `gcloud` CLI installed locally
- SSH key configured for your account
- Optional GPU quota if you want Ollama acceleration

## 1. Create a VM
- Open Google Cloud Console
- Go to `Compute Engine > VM instances`
- Create an instance with Ubuntu 22.04 LTS
- Suggested size for CPU-only: `e2-standard-4`
- Suggested GPU option for Ollama: `n1-standard-4` with NVIDIA T4
- Add network tag: `ayurveda-app`
- Allow HTTP/HTTPS traffic

## 2. Connect over SSH
```bash
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE
```

## 3. Transfer the Code
SCP:
```bash
gcloud compute scp --recurse ./ayurveda_project YOUR_VM_NAME:~/ --zone YOUR_ZONE
```

rsync:
```bash
rsync -avz ./ayurveda_project USER@VM_IP:~/
```

## 4. Install the App
- SSH into the VM
- Copy `.env.example` to `.env`
- Edit `.env` with production values
- Run:
```bash
chmod +x scripts/deploy_linux.sh
./scripts/deploy_linux.sh
```

## 5. Systemd Service
The Linux deployment script creates `ayurveda-clinic.service`.
Useful commands:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ayurveda-clinic
sudo systemctl start ayurveda-clinic
sudo systemctl status ayurveda-clinic
sudo journalctl -u ayurveda-clinic -f
```

## 6. Firewall Configuration
Local GCP CLI:
```bash
gcloud compute firewall-rules create allow-ayurveda-app --allow tcp:8000 --source-ranges 0.0.0.0/0 --target-tags ayurveda-app
```

Windows helper:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcp_firewall.ps1
```

## 7. SSL / HTTPS
- Install nginx
- Install certbot
- Point DNS to the VM external IP
- Run:
```bash
sudo apt-get install nginx certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

## 8. Backup Strategy
- Keep SQLite backups in `backups/`
- Schedule `scripts/backup_db.py`
- Sync backups to Cloud Storage:
```bash
gsutil cp backups/*.zip gs://YOUR_BUCKET/backups/
```

## 9. Monitoring
- Use `scripts/monitor.ps1` on Windows
- On Linux use:
```bash
curl http://localhost:8000/healthz
sudo journalctl -u ayurveda-clinic -n 50
```

## 10. Troubleshooting
- If external access fails, verify firewall rules and VM tags
- If you see invalid HTTP warnings, confirm the app listens on `0.0.0.0`
- If Ollama is unavailable, the fallback engine still serves AI responses
- If the app crashes, inspect `logs/app.log` and systemd logs

## Quick Reference
```bash
gcloud compute instances list
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE
gcloud compute firewall-rules list
curl http://localhost:8000/healthz
sudo systemctl restart ayurveda-clinic
sudo journalctl -u ayurveda-clinic -f
```
