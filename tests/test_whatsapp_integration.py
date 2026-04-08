from app.health import build_health_report


def test_whatsapp_health_report_exposes_status_not_secrets(monkeypatch):
    monkeypatch.setattr(
        "services.whatsapp._meta_whatsapp_config",
        lambda: {
            "access_token": "super-secret-token",
            "phone_number_id": "1234567890",
            "api_version": "v23.0",
            "template_name": "prescription_ready",
            "template_language_code": "en_US",
        },
    )

    report = build_health_report()
    whatsapp = report["whatsapp_detail"]

    assert report["whatsapp"] == "ok"
    assert whatsapp["cloud_api_configured"] is True
    assert whatsapp["template_configured"] is True
    assert whatsapp["delivery_mode"] == "meta_cloud_api"
    assert "super-secret-token" not in str(report)
    assert "1234567890" not in str(report)
