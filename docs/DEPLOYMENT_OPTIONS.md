# Deployment Options

## DigitalOcean
1. Create an Ubuntu 22.04 droplet.
2. Install Docker and Docker Compose.
3. Clone the repository and copy `.env.production` to `.env`.
4. Run:
   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh
   ```
5. Add SSL with Let's Encrypt or place Cloudflare in front.

## Railway
1. Install the Railway CLI.
2. Run `railway init`.
3. Add PostgreSQL and Redis plugins.
4. Set variables from `.env.production`.
5. Deploy with `railway up`.

## AWS Elastic Beanstalk
1. Install `awsebcli`.
2. Run:
   ```bash
   eb init -p docker ayurveda-app
   eb create ayurveda-prod
   eb setenv DATABASE_URL=... SECRET_KEY=... ADMIN_API_TOKEN=...
   eb deploy
   ```

## Production Notes
- Ensure `SESSION_HTTPS_ONLY=true`
- Set a real `ADMIN_API_TOKEN`
- Set `SENDER_EMAIL` and `SENDER_PASSWORD`
- Point Nginx or your cloud ingress at port `8000`
- Run `python scripts/final_test_suite.py` after deploy
