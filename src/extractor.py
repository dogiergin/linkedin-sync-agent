import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from loguru import logger


class PostExtractor:
    """Extracts structured post information (content, URL, date, hashtags) from LinkedIn elements/HTML."""

    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extracts hashtags without the '#' prefix."""
        if not text:
            return []
        # Support alphanumeric and unicode hashtags (e.g. Turkish characters)
        raw_tags = re.findall(r"#([^\s!@#$%^&*()+=\[\]{};:'\",.<>?/\\|]+)", text)
        # Deduplicate while maintaining order
        seen = set()
        deduped = []
        for tag in raw_tags:
            tag_clean = tag.strip()
            if tag_clean and tag_clean.lower() not in seen:
                seen.add(tag_clean.lower())
                deduped.append(tag_clean)
        return deduped

    @staticmethod
    def clean_content(raw_text: str) -> str:
        """Cleans post text, removes '...see more' artifacts and standardizes whitespace."""
        if not raw_text:
            return ""

        text = raw_text.strip()
        # Remove LinkedIn accessibility 'hashtag\n#' prefix artifacts
        text = re.sub(r"\bhashtag\s*\n\s*#", "#", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhashtag\s+#", "#", text, flags=re.IGNORECASE)
        # Remove "...see more" or "...daha fazla göster" buttons text
        text = re.sub(r"\.\.\.\s*(see more|daha fazla gör|daha fazla göster|see less|daha az gör)\s*$", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(\r?\n){3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def standardize_url(raw_url: str, urn: Optional[str] = None) -> str:
        """Standardizes a LinkedIn post URL into a permanent direct feed link."""
        if raw_url:
            # If already full URL
            if raw_url.startswith("https://www.linkedin.com/feed/update/"):
                # Strip query params
                return raw_url.split("?")[0]
            if raw_url.startswith("/feed/update/"):
                return f"https://www.linkedin.com{raw_url.split('?')[0]}"
            if "linkedin.com/posts/" in raw_url:
                return raw_url.split("?")[0]

        if urn:
            # Construct direct canonical feed link from URN
            clean_urn = urn.strip()
            if not clean_urn.startswith("urn:li:"):
                clean_urn = f"urn:li:activity:{clean_urn}"
            return f"https://www.linkedin.com/feed/update/{clean_urn}/"

        if raw_url:
            return raw_url.split("?")[0]

        return ""

    @classmethod
    def parse_post(
        cls,
        raw_content: str,
        raw_url: str = "",
        raw_date: str = "",
        urn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parses all extracted fields into the canonical webhook payload format.
        """
        content = cls.clean_content(raw_content)
        url = cls.standardize_url(raw_url, urn)
        hashtags = cls.extract_hashtags(content)
        date = raw_date.strip() if raw_date else datetime.now(timezone.utc).isoformat()

        logger.info(f"Parsed post: URL={url} | Date={date} | Tags={len(hashtags)} | Content length={len(content)}")

        return {
            "content": content,
            "url": url,
            "date": date,
            "hashtags": hashtags,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
