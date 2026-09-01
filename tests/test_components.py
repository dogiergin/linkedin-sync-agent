import json
import pytest
from pathlib import Path
from src.extractor import PostExtractor
from src.state_manager import StateManager
from src.webhook import WebhookDispatcher


def test_hashtag_extraction():
    text = "Bugün #AI ve #Python ile otonom sistemler kuruyoruz! #YapayZeka #SoftwareEngineering"
    tags = PostExtractor.extract_hashtags(text)
    assert "AI" in tags
    assert "Python" in tags
    assert "YapayZeka" in tags
    assert "SoftwareEngineering" in tags
    assert len(tags) == 4


def test_clean_content():
    raw = "Yeni bir proje başlattık! Detaylar için profilime göz atın.\n\n...see more"
    cleaned = PostExtractor.clean_content(raw)
    assert not cleaned.endswith("see more")
    assert "Yeni bir proje başlattık!" in cleaned


def test_standardize_url():
    raw = "/feed/update/urn:li:activity:7234567890123456789?updateEntityUrn=..."
    url = PostExtractor.standardize_url(raw)
    assert url == "https://www.linkedin.com/feed/update/urn:li:activity:7234567890123456789"

    urn_only = "7234567890123456789"
    url_from_urn = PostExtractor.standardize_url("", urn=urn_only)
    assert url_from_urn == "https://www.linkedin.com/feed/update/urn:li:activity:7234567890123456789/"


def test_post_parsing():
    content = "Harika bir çalışma oldu! #Geliştirici #WebDev"
    url = "https://www.linkedin.com/feed/update/urn:li:activity:123456"
    date = "1 gün önce"

    parsed = PostExtractor.parse_post(content, url, date)
    assert parsed["content"] == content
    assert parsed["url"] == url
    assert parsed["date"] == date
    assert "Geliştirici" in parsed["hashtags"]
    assert "WebDev" in parsed["hashtags"]
    assert "synced_at" in parsed


def test_state_manager(tmp_path):
    test_state_file = tmp_path / "test_state.json"
    mgr = StateManager(state_file=test_state_file)

    post_data = {
        "content": "Test content",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:9999",
        "date": "Just now",
        "hashtags": ["Test"],
    }

    # Before sync
    assert not mgr.is_already_synced(post_data["url"], post_data["content"])

    # Record sync
    mgr.record_sync(post_data)

    # After sync
    assert mgr.is_already_synced(post_data["url"], post_data["content"])
    assert mgr.is_already_synced("https://www.linkedin.com/feed/update/urn:li:activity:9999", "Different text")
    assert mgr.is_already_synced("different_url", "Test content")
    assert not mgr.is_already_synced("https://other-url.com", "Completely different")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
