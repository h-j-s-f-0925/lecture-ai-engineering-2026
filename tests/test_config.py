"""アプリ共通設定のテスト。外部APIは呼び出さない。"""

import pytest

from app.config import get_api_key


def test_get_api_key_uses_free_key_by_default(monkeypatch):
    """AIE_API_TIER を省略した場合は無料用キーを使う。"""
    monkeypatch.setenv("GEMINI_API_KEY", "free-key")
    monkeypatch.setenv("GEMINI_API_KEY_PAID", "paid-key")
    monkeypatch.delenv("AIE_API_TIER", raising=False)

    assert get_api_key() == "free-key"


def test_get_api_key_uses_selected_paid_key(monkeypatch):
    """AIE_API_TIER=paid の場合は有料用キーを使う。"""
    monkeypatch.setenv("GEMINI_API_KEY", "free-key")
    monkeypatch.setenv("GEMINI_API_KEY_PAID", "paid-key")
    monkeypatch.setenv("AIE_API_TIER", "paid")

    assert get_api_key() == "paid-key"


def test_get_api_key_fails_when_selected_key_is_missing(monkeypatch):
    """選択したtierのキーがない場合は、別tierへ切り替えず終了する。"""
    monkeypatch.setenv("GEMINI_API_KEY", "free-key")
    monkeypatch.delenv("GEMINI_API_KEY_PAID", raising=False)
    monkeypatch.setenv("AIE_API_TIER", "paid")

    with pytest.raises(SystemExit, match="GEMINI_API_KEY_PAID"):
        get_api_key()


def test_get_api_key_rejects_unknown_tier(monkeypatch):
    """未対応の AIE_API_TIER は設定ミスとして終了する。"""
    monkeypatch.setenv("AIE_API_TIER", "premium")

    with pytest.raises(SystemExit, match="AIE_API_TIER は free または paid"):
        get_api_key()


def test_get_api_key_fails_when_free_key_is_missing(monkeypatch):
    """無料が既定でも無料用キーがなければ設定方法を示して終了する。"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_PAID", "paid-key")
    monkeypatch.delenv("AIE_API_TIER", raising=False)

    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        get_api_key()
