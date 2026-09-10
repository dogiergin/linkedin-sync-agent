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
    assert "PYTHON" in tags
    assert "YAPAYZEKA" in tags
    assert "SOFTWAREENGINEERING" in tags
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
    assert parsed["date"] == "1 gün"
    assert "WEBDEV" in parsed["hashtags"]
    assert any("GEL" in tag for tag in parsed["hashtags"])
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


def test_linkedin_8_rules_enforcement():
    """Verifies that raw, unstructured LinkedIn post text is automatically transformed according to the 8 rules."""
    raw_post = (
        "🚀 Yapay Zeka Çağının Teknik Sözlüğü | Bölüm 3/3.\n"
        "Geliştiriciler & Teknoloji Profesyonelleri İçin 5 Kritik Kavram (5 & Bonus)\n\n"
        "Yapay zeka modellerinin yeni çağını inceliyoruz.\n\n"
        "5️⃣ Ajanssal (Agentic) Modeller: Otonom Karar Vericiler\n"
        "Geleneksel modeller sadece soruya yanıt üretirken, ajanssal modeller hedefe ulaşmak için araçları kullanır.\n"
        "Neden Kritik?\n"
        "• Kendi kendine hata ayıklama yapabilir.\n"
        "• Çok adımlı iş akışlarını sıfır insan müdahalesiyle tamamlar.\n\n"
        "Not: Harika bir seri oldu!\n"
        "#YapayZeka #AgenticAI #MachineLearning #DogukanErgin\n...see more"
    )
    url = "https://www.linkedin.com/feed/update/urn:li:activity:7509999999999999999"
    date_raw = "12 dakika önce"

    parsed = PostExtractor.parse_post(raw_post, url, date_raw)
    content = parsed["content"]
    lines = content.split("\n")

    # Rule 1: First line no trailing dot
    assert lines[0] == "🚀 Yapay Zeka Çağının Teknik Sözlüğü | Bölüm 3/3"
    assert not lines[0].endswith(".")

    # Rule 2: Second line bold subtitle
    assert lines[1] == "**Geliştiriciler & Teknoloji Profesyonelleri İçin 5 Kritik Kavram (5 & Bonus)**"

    # Rule 3: Numbered items get ### and blank lines
    assert "### 5️⃣ Ajanssal (Agentic) Modeller: Otonom Karar Vericiler" in content

    # Rule 4: Critical highlights bolded
    assert "**✅ Neden Kritik?**" in content
    assert "**📌 Not:** Harika bir seri oldu!" in content

    # Rule 5: Bullet items standardize to '-'
    assert "- Kendi kendine hata ayıklama yapabilir." in content
    assert "•" not in content

    # Rule 6: Date normalized to 'Bugün'
    assert parsed["date"] == "Bugün"

    # Rule 8: Uppercase tags with underscores and no '#'
    assert "YAPAYZEKA" in parsed["hashtags"]
    assert "AGENTICAI" in parsed["hashtags"]
    assert "MACHINELEARNING" in parsed["hashtags"]
    assert all(not t.startswith("#") for t in parsed["hashtags"])
    assert all(t == t.upper() for t in parsed["hashtags"])


if __name__ == "__main__":
    pytest.main(["-v", __file__])
