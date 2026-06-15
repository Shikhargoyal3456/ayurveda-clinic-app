from app import logging_config


def test_redact_text_skips_redaction_during_python_shutdown(monkeypatch):
    monkeypatch.setattr(logging_config.sys, "meta_path", None)
    original = "email doctor@example.com token=secret-value"

    assert logging_config._redact_text(original) == original
