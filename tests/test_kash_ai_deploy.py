from __future__ import annotations

from pathlib import Path


def test_kash_ai_deploy_targets_domain_and_service():
    # KASH-AI-DEPLOY-FINAL: deploy.sh should target Kash AI service/domain.
    deploy = Path("deploy.sh").read_text(encoding="utf-8")
    assert 'SERVICE_NAME="${SERVICE_NAME:-kash-ai}"' in deploy
    assert 'DOMAIN="${DOMAIN:-kashai.in}"' in deploy
    assert "gcloud builds submit" in deploy
    assert "python scripts/smoke.py --base-url" in deploy


def test_kash_ai_production_env_template_present():
    # KASH-AI-DEPLOY-FINAL: production env file is ready to fill before live deploy.
    env_text = Path(".env.production").read_text(encoding="utf-8")
    assert "APP_NAME=kash-ai" in env_text
    assert "TRUSTED_HOSTS=kashai.in,www.kashai.in,*.run.app" in env_text
    assert "RAZORPAY_MODE=test" in env_text


def test_kash_ai_domain_helper_targets_kashai():
    # KASH-AI-DEPLOY-FINAL: domain helper maps kashai.in to kash-ai.
    domain_script = Path("domains/cloud-run-domains.sh").read_text(encoding="utf-8")
    assert 'SERVICE="${SERVICE:-kash-ai}"' in domain_script
    assert 'DOMAIN="${DOMAIN:-kashai.in}"' in domain_script
