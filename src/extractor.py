import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from loguru import logger


class PostExtractor:
    """Extracts structured post information (content, URL, date, hashtags) from LinkedIn elements/HTML."""

    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extracts hashtags without the '#' prefix, uppercase with underscores."""
        if not text:
            return []
        raw_tags = re.findall(r"#([^\s!@#$%^&*()+=\[\]{};:'\",.<>?/\\|]+)", text)
        seen = set()
        deduped = []
        for tag in raw_tags:
            clean = re.sub(r"[^\w\d_]", "_", tag.strip()).upper().strip("_")
            if clean and clean not in seen:
                seen.add(clean)
                deduped.append(clean)
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

    @staticmethod
    def normalize_date(raw_date: str) -> str:
        """Normalizes date according to rule 6: 'Bugün', '1 gün'-'6 gün', or '1 hafta'."""
        if not raw_date:
            return "Bugün"
        str_val = raw_date.strip().lower()
        if any(m in str_val for m in ["eylül", "september", "ağustos", "august", "temmuz", "july", "haziran", "june", "mayıs", "may", "nisan", "april", "mart", "march", "şubat", "february", "ocak", "january"]):
            return "1 hafta"
        if str_val in ["bugün", "today"] or any(w in str_val for w in ["dakika", "saat", "hour", "min", "just now", "şimdi", "az önce"]):
            return "Bugün"
        m = re.search(r"(\d+)\s*(gün|g|d|day)", str_val)
        if m:
            days = int(m.group(1))
            return f"{days} gün" if days <= 6 else "1 hafta"
        if any(w in str_val for w in ["hafta", "week", "ay", "month", "yıl", "year"]):
            return "1 hafta"
        return "Bugün"

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
        date = cls.normalize_date(raw_date)

        logger.info(f"Parsed post: URL={url} | Date={date} | Tags={len(hashtags)} | Content length={len(content)}")

        return {
            "content": content,
            "url": url,
            "date": date,
            "hashtags": hashtags,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
