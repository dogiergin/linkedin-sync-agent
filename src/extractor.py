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
        """
        Cleans and auto-formats post text according to 8 readability rules:
        1. Line 1: Single, clean title sentence without trailing period.
        2. Line 2: Bold subtitle (**...**) if present.
        3. Numbered items (1️⃣, 2️⃣, etc.): Prefixed with '### ' and blank lines around.
        4. Critical highlights: Bolded ('**✅ Neden Kritik?**', '**📌 Not:**', '**💡 Özet:**').
        5. Bullet points: Standardized to '- '.
        """
        if not raw_text:
            return ""

        text = raw_text.strip()
        # Remove LinkedIn accessibility artifacts & 'see more' buttons
        text = re.sub(r"\bhashtag\s*\n\s*#", "#", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhashtag\s+#", "#", text, flags=re.IGNORECASE)
        text = re.sub(r"\.\.\.\s*(see more|daha fazla gör|daha fazla göster|see less|daha az gör)\s*$", "", text, flags=re.IGNORECASE)

        lines = [l.rstrip() for l in text.splitlines()]
        non_empty_indices = [i for i, l in enumerate(lines) if l.strip()]
        if not non_empty_indices:
            return text

        # Rule 1: First line no trailing period
        first_idx = non_empty_indices[0]
        lines[first_idx] = re.sub(r"\.+$", "", lines[first_idx].strip())

        # Rule 2: Second non-empty line bold subtitle if applicable
        if len(non_empty_indices) > 1:
            second_idx = non_empty_indices[1]
            sub = lines[second_idx].strip()
            if not re.match(r"^(###|[1-9]️⃣|🔟|•|-|\*)", sub) and len(sub) < 140:
                if not (sub.startswith("**") and sub.endswith("**")):
                    clean_sub = sub.strip("*").strip()
                    lines[second_idx] = f"**{clean_sub}**"

        joined = "\n".join(lines)

        # Rule 3: Numbered items get ### and blank lines around
        joined = re.sub(r"(?m)^(?!###\s*)([1-9]️⃣|🔟)\s*(.+)$", r"\n\n### \1 \2\n", joined)

        # Rule 4: Critical phrases bolded
        joined = re.sub(r"(?i)(?:^|\n)\s*(?:\*{0,2})(?:✅\s*)?Neden Kritik\??(?:\*{0,2})\s*", r"\n\n**✅ Neden Kritik?**\n", joined)
        joined = re.sub(r"(?i)(?:^|\n)\s*(?:\*{0,2})(?:📌\s*)?Not:(?:\*{0,2})\s*", r"\n\n**📌 Not:** ", joined)
        joined = re.sub(r"(?i)(?:^|\n)\s*(?:\*{0,2})(?:💡\s*)?Özet:(?:\*{0,2})\s*", r"\n\n**💡 Özet:** ", joined)

        # Rule 5: Bullet items standardize to - (do not match bold **)
        joined = re.sub(r"(?m)^[•✔]\s*|^\*(?!\*)\s*", "- ", joined)

        # Normalize multiple blank lines to max 2
        joined = re.sub(r"\n{3,}", "\n\n", joined).strip()
        return joined

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
