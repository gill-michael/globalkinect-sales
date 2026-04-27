import json
import hashlib
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from app.models.discovery_candidate import DiscoveryCandidate
from app.models.discovery_source import DiscoverySource
from app.services.config import settings
from app.utils.logger import get_logger
from app.utils.target_markets import (
    SUPPORTED_TARGET_MARKETS,
    TARGET_MARKET_ALIASES,
    normalize_target_country,
)

logger = get_logger(__name__)

try:
    import httpx
except ImportError:
    httpx = None


class DiscoverySourceService:
    COUNTRY_ALIASES = {
        country: [
            alias
            for alias, normalized_country in TARGET_MARKET_ALIASES.items()
            if normalized_country == country
        ]
        for country in SUPPORTED_TARGET_MARKETS
    }
    OPPORTUNITY_KEYWORDS = {
        "payroll",
        "employer of record",
        "eor",
        "hris",
        "hr",
        "human resources",
        "people",
        "talent",
        "recruiter",
        "recruitment",
        "compliance",
        "global mobility",
        "mobility",
        "entity",
        "expansion",
        "country manager",
        "operations",
    }
    ACCOUNT_SIGNAL_KEYWORDS = {
        "expansion",
        "launch",
        "launching",
        "market entry",
        "entity",
        "entity setup",
        "new country",
        "new market",
        "regional",
        "global mobility",
        "mobility",
        "compliance",
        "distributed",
        "remote",
        "cross-border",
        "international",
        "country manager",
        "people operations",
        "people ops",
        "payroll operations",
        "payroll manager",
        "hris",
        "human resources information system",
        "regional headquarters",
        "office opening",
        "funding",
        "series",
        "acquisition",
        "partnership",
        "press release",
    }
    BUYER_SIGNAL_KEYWORDS = {
        "head of people",
        "vp people",
        "people director",
        "people operations",
        "people ops",
        "hr director",
        "hr manager",
        "human resources",
        "payroll manager",
        "payroll lead",
        "global payroll",
        "global mobility",
        "mobility",
        "finance director",
        "cfo",
        "chief financial officer",
        "coo",
        "chief operating officer",
        "operations director",
        "country manager",
        "general manager",
    }
    JOB_TITLE_ROLE_NOISE_KEYWORDS = {
        "software engineer",
        "backend engineer",
        "frontend engineer",
        "full stack engineer",
        "cloud engineer",
        "data engineer",
        "devops",
        "site reliability",
        "product manager",
        "designer",
        "account executive",
        "sales",
        "business development",
        "client growth",
        "customer success",
        "marketing",
    }
    SERVICE_FOCUS_KEYWORDS = {
        "payroll": {
            "payroll",
            "compensation",
            "payroll operations",
            "payroll manager",
            "payroll lead",
            "global payroll",
            "compliance",
        },
        "eor": {
            "employer of record",
            "eor",
            "entity",
            "global mobility",
            "mobility",
            "international expansion",
        },
        "partner": {
            "recruiter",
            "recruitment",
            "staffing",
            "talent acquisition",
            "agency",
            "placement",
        },
        "hris": {
            "hris",
            "people systems",
            "hr systems",
            "workday",
            "people ops",
            "human resources information system",
        },
    }
    DEFAULT_ENTRY_URL_KEYWORDS = {
        "news",
        "press",
        "blog",
        "article",
        "story",
        "insight",
        "update",
        "announcement",
        "launch",
        "expansion",
        "global",
        "mena",
        "middle-east",
        "middleeast",
        "gulf",
        "payroll",
        "hris",
        "mobility",
        "entity",
    }

    def __init__(
        self,
        client: Any | None = None,
        sources_file: str | None = None,
        max_items_per_source: int | None = None,
    ) -> None:
        self.sources_file = Path(sources_file or settings.DISCOVERY_SOURCES_FILE)
        self.max_items_per_source = (
            max_items_per_source
            if max_items_per_source is not None
            else settings.DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE
        )
        self.client = None
        # Set by _parse_feed_entries on recovery; read by collect_candidates
        # to emit the per-source health log.
        self._last_parse_status: str = "success"

        if client is not None:
            self.client = client
            return

        if httpx is None:
            logger.warning(
                "httpx is not installed. Discovery source collection is unavailable."
            )
            return

        self.client = httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            headers={
                # Intentionally one word: HTTP product tokens (RFC 7231) cannot
                # contain spaces. The brand rule "Global Kinect" (two words)
                # applies to copy in client-facing drafts, not to identifiers
                # on the wire.
                "User-Agent": "GlobalKinectSalesEngine/1.0",
            },
        )

    def is_configured(self) -> bool:
        return self.client is not None and self.sources_file.exists()

    def load_sources(self) -> list[DiscoverySource]:
        if not self.sources_file.exists():
            logger.info(
                "Discovery sources file %s was not found. Skipping source collection.",
                self.sources_file,
            )
            return []

        payload = json.loads(self.sources_file.read_text(encoding="utf-8"))
        raw_sources = self._expand_source_payload(payload)
        if not isinstance(raw_sources, list):
            raise ValueError("Discovery sources file must contain a list of sources.")

        return [
            source
            for source in (
                DiscoverySource.model_validate(item)
                for item in raw_sources
            )
            if source.active
        ]

    def _expand_source_payload(self, payload: Any) -> list[dict[str, Any]] | Any:
        if not isinstance(payload, dict):
            return payload

        if "lanes" in payload:
            expanded_sources: list[dict[str, Any]] = []
            for lane in payload.get("lanes", []):
                if not isinstance(lane, dict):
                    continue
                if lane.get("active", True) is False:
                    continue

                lane_label = lane.get("lane_label") or lane.get("name")
                lane_agent_label = lane.get("agent_label")
                lane_campaign = lane.get("campaign")
                lane_sources = lane.get("sources", [])
                for source in lane_sources:
                    if not isinstance(source, dict):
                        continue
                    merged_source = dict(source)
                    if lane_label and "lane_label" not in merged_source:
                        merged_source["lane_label"] = lane_label
                    if lane_agent_label and "agent_label" not in merged_source:
                        merged_source["agent_label"] = lane_agent_label
                    if lane_campaign and "campaign" not in merged_source:
                        merged_source["campaign"] = lane_campaign
                    expanded_sources.append(merged_source)
            return expanded_sources

        return payload.get("sources", payload)

    def collect_candidates(
        self,
        campaign: str | None = None,
    ) -> tuple[list[DiscoverySource], list[DiscoveryCandidate]]:
        if self.client is None:
            logger.info("Discovery source client is not configured. Skipping source collection.")
            return [], []

        sources = self.load_sources()
        if not sources:
            return [], []

        candidates: list[DiscoveryCandidate] = []
        for source in sources:
            # Per-source health tracking. _parse_feed_entries upgrades this
            # to "fallback_success" when it recovers from malformed XML.
            self._last_parse_status = "success"
            items_found = 0
            source_status = "success"
            try:
                entries = self._load_entries_for_source(source)
                items_found = len(entries)
                source_status = self._last_parse_status
                max_items = source.max_items or self.max_items_per_source
                for entry in entries[:max_items]:
                    candidate = self._build_candidate_from_entry(
                        source,
                        entry,
                        campaign=campaign,
                    )
                    if candidate is not None:
                        candidates.append(candidate)
            except Exception as exc:
                source_status = "failed"
                logger.warning(
                    "Discovery source failed: name=%s url=%s error=%s",
                    source.company_name or "unknown",
                    source.feed_url or "",
                    exc,
                )
            finally:
                logger.info(
                    "[source-health] name=%s url=%s items_found=%s status=%s",
                    source.company_name or "unknown",
                    source.feed_url or "",
                    items_found,
                    source_status,
                )

        candidates = self._deduplicate_candidates(candidates)
        candidates.sort(
            key=lambda candidate: (
                -(candidate.source_priority or 0),
                -(candidate.source_trust_score or 0),
                candidate.company_name.lower(),
            )
        )

        logger.info(
            "Collected %s discovery candidates from %s configured source(s).",
            len(candidates),
            len(sources),
        )
        return sources, candidates

    def _load_entries_for_source(
        self,
        source: DiscoverySource,
    ) -> list[dict[str, Any]]:
        normalized_type = (source.source_type or "").strip().lower()
        if source.entries:
            return [self._normalize_manual_entry(entry) for entry in source.entries]
        if normalized_type == "manual_signals":
            return []
        if not source.feed_url:
            raise ValueError("Feed-backed discovery sources require a feed_url.")
        feed_text = self._fetch_feed(source.feed_url)
        if normalized_type == "webpage_html":
            return self._parse_webpage_entries(source, feed_text)
        if normalized_type == "sitemap_xml":
            return self._parse_sitemap_entries(source, feed_text)
        return self._parse_entries(source, feed_text)

    def _normalize_manual_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "company_name": self._clean_text(str(entry.get("company_name") or "")) or None,
            "title": self._clean_text(str(entry.get("title") or "")) or None,
            "link": entry.get("link") or entry.get("source_url"),
            "summary": self._clean_text(str(entry.get("summary") or entry.get("description") or "")) or None,
            "published": entry.get("published") or entry.get("published_at"),
            "raw_text": self._clean_text(
                " ".join(
                    str(value)
                    for value in [
                        entry.get("title"),
                        entry.get("summary") or entry.get("description"),
                        entry.get("raw_text"),
                        entry.get("notes"),
                    ]
                    if value
                )
            ),
            "contact_name": entry.get("contact_name"),
            "contact_role": entry.get("contact_role"),
            "email": entry.get("email"),
            "linkedin_url": entry.get("linkedin_url"),
            "company_country": entry.get("company_country"),
            "target_country_hint": entry.get("target_country_hint"),
            "notes": entry.get("notes"),
        }

    def _parse_entries(
        self,
        source: DiscoverySource,
        raw_text: str,
    ) -> list[dict[str, str | None]]:
        normalized_type = (source.source_type or "").lower()
        stripped = raw_text.lstrip()

        if "greenhouse" in normalized_type or (
            stripped.startswith("{") and "\"jobs\"" in stripped[:200]
        ):
            payload = json.loads(raw_text)
            return self._parse_greenhouse_entries(payload)

        if "workable" in normalized_type or (
            stripped.startswith("{") and "\"results\"" in stripped[:200]
        ):
            payload = json.loads(raw_text)
            if isinstance(payload, dict):
                return self._parse_workable_entries(payload)

        if "json_feed" in normalized_type or (
            stripped.startswith("{") and "\"items\"" in stripped[:400]
        ):
            payload = json.loads(raw_text)
            if isinstance(payload, dict):
                return self._parse_json_feed_entries(payload)

        if "lever" in normalized_type or stripped.startswith("["):
            payload = json.loads(raw_text)
            if isinstance(payload, list):
                return self._parse_lever_entries(payload)

        return self._parse_feed_entries(raw_text)

    def _fetch_feed(self, feed_url: str) -> str:
        response = self.client.get(feed_url)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if hasattr(response, "text"):
            return response.text
        return str(response)

    def _clean_xml_for_parse(self, xml_text: str) -> str:
        """Salvage a mis-formed XML body so feedparsing can retry.

        Two common publisher pathologies:
          * Bytes (BOMs, HTML fragments, error banners) prepended before the
            first XML prolog or root tag.
          * Control characters outside the XML 1.0 permitted range embedded
            in CDATA or text nodes.

        We strip everything before the first recognised XML entry point and
        drop codepoints that XML 1.0 forbids. The goal is best-effort
        recovery — the caller treats a second ParseError as terminal.
        """
        if not isinstance(xml_text, str):
            return ""
        trimmed = xml_text.lstrip("\ufeff\r\n\t ")
        for marker in ("<?xml", "<rss", "<feed"):
            idx = trimmed.find(marker)
            if idx >= 0:
                trimmed = trimmed[idx:]
                break
        # XML 1.0 valid codepoints: 0x09, 0x0A, 0x0D, 0x20-0xD7FF,
        # 0xE000-0xFFFD, 0x10000-0x10FFFF. Anything else (most commonly NULs
        # and vertical tabs) is stripped silently.
        allowed: list[str] = []
        for ch in trimmed:
            cp = ord(ch)
            if (
                cp == 0x09
                or cp == 0x0A
                or cp == 0x0D
                or 0x20 <= cp <= 0xD7FF
                or 0xE000 <= cp <= 0xFFFD
                or 0x10000 <= cp <= 0x10FFFF
            ):
                allowed.append(ch)
        return "".join(allowed)

    def _parse_feed_entries(self, xml_text: str) -> list[dict[str, str | None]]:
        # Some publishers (observed with MEED and Reed) emit RSS with garbage
        # bytes before the XML prolog or with control characters outside the
        # XML 1.0 permitted set. Try a strict parse first, fall back to a
        # cleaned retry. A second failure propagates and is caught at the
        # source-level boundary in collect_candidates.
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.info(
                "XML parse failed on first attempt (%s); retrying with cleaned input.",
                exc,
            )
            cleaned = self._clean_xml_for_parse(xml_text)
            try:
                root = ET.fromstring(cleaned)
            except ET.ParseError as retry_exc:
                logger.warning(
                    "Feed XML unparseable even after cleanup: %s", retry_exc
                )
                raise
            self._last_parse_status = "fallback_success"
        if self._local_name(root.tag) == "rss" or root.find("./channel") is not None:
            nodes = root.findall(".//item")
        else:
            nodes = [node for node in root.iter() if self._local_name(node.tag) == "entry"]

        entries: list[dict[str, str | None]] = []
        for node in nodes:
            title = self._find_text(node, "title")
            link = self._find_link(node)
            summary = self._find_first_text(node, "description", "summary", "content")
            published = self._find_first_text(
                node,
                "pubDate",
                "published",
                "updated",
            )
            raw_text = self._clean_text(" ".join(text for text in node.itertext()))
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": self._normalize_published_at(published),
                    "raw_text": raw_text,
                }
            )
        return entries

    def _parse_greenhouse_entries(
        self,
        payload: dict[str, Any],
    ) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for job in payload.get("jobs", []):
            location = (
                (job.get("location") or {}).get("name")
                if isinstance(job.get("location"), dict)
                else None
            )
            content = self._clean_text(job.get("content", ""))
            summary_parts = [location, self._snippet(content)]
            entries.append(
                {
                    "title": self._clean_text(job.get("title", "")) or None,
                    "link": job.get("absolute_url"),
                    "summary": self._clean_text(
                        " ".join(part for part in summary_parts if part)
                    )
                    or None,
                    "published": self._normalize_published_at(job.get("updated_at")),
                    "raw_text": self._clean_text(
                        " ".join(
                            part
                            for part in [
                                job.get("title", ""),
                                location or "",
                                content,
                            ]
                            if part
                        )
                    ),
                }
            )
        return entries

    def _parse_lever_entries(
        self,
        payload: list[dict[str, Any]],
    ) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for job in payload:
            categories = job.get("categories") or {}
            category_values = [
                value
                for value in [
                    categories.get("location"),
                    categories.get("team"),
                    categories.get("department"),
                    categories.get("commitment"),
                    categories.get("allLocations"),
                ]
                if value
            ]
            description = self._clean_text(
                job.get("descriptionPlain")
                or job.get("description")
                or ""
            )
            summary_parts = category_values + [self._snippet(description)]
            entries.append(
                {
                    "title": self._clean_text(job.get("text", "")) or None,
                    "link": job.get("hostedUrl") or job.get("applyUrl"),
                    "summary": self._clean_text(
                        " ".join(part for part in summary_parts if part)
                    )
                    or None,
                    "published": self._normalize_published_at(job.get("createdAt")),
                    "raw_text": self._clean_text(
                        " ".join(
                            part
                            for part in [
                                job.get("text", ""),
                                " ".join(category_values),
                                description,
                            ]
                            if part
                        )
                    ),
                }
            )
        return entries

    def _parse_workable_entries(
        self,
        payload: dict[str, Any],
    ) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for job in payload.get("results", []):
            location = job.get("location") or {}
            location_values = [
                value
                for value in [
                    location.get("city") if isinstance(location, dict) else None,
                    location.get("country") if isinstance(location, dict) else None,
                    job.get("location") if isinstance(job.get("location"), str) else None,
                ]
                if value
            ]
            description = self._clean_text(
                job.get("description")
                or job.get("full_description")
                or ""
            )
            summary_parts = location_values + [self._snippet(description)]
            entries.append(
                {
                    "title": self._clean_text(job.get("title", "")) or None,
                    "link": (
                        job.get("url")
                        or job.get("application_url")
                        or job.get("shortlink")
                    ),
                    "summary": self._clean_text(
                        " ".join(part for part in summary_parts if part)
                    )
                    or None,
                    "published": (
                        self._normalize_published_at(job.get("published"))
                        or self._normalize_published_at(job.get("updated_at"))
                        or self._normalize_published_at(job.get("created_at"))
                    ),
                    "raw_text": self._clean_text(
                        " ".join(
                            part
                            for part in [
                                job.get("title", ""),
                                " ".join(location_values),
                                description,
                            ]
                            if part
                        )
                    ),
                }
            )
        return entries

    def _parse_json_feed_entries(
        self,
        payload: dict[str, Any],
    ) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            content_text = self._clean_text(
                item.get("content_text")
                or item.get("content_html")
                or item.get("summary")
                or ""
            )
            summary = self._clean_text(
                item.get("summary") or self._snippet(content_text) or ""
            )
            entries.append(
                {
                    "title": self._clean_text(item.get("title", "")) or None,
                    "link": item.get("url") or item.get("external_url"),
                    "summary": summary or None,
                    "published": self._normalize_published_at(
                        item.get("date_published") or item.get("date_modified")
                    ),
                    "raw_text": self._clean_text(
                        " ".join(
                            part
                            for part in [
                                item.get("title", ""),
                                summary or "",
                                content_text,
                            ]
                            if part
                        )
                    ),
                }
            )
        return entries

    def _parse_webpage_entries(
        self,
        source: DiscoverySource,
        html_text: str,
    ) -> list[dict[str, str | None]]:
        base_url = source.feed_url or source.website_url or ""
        entries = self._extract_anchor_entries(base_url, html_text, source)
        if source.fetch_detail_pages:
            return self._enrich_entries_from_detail_pages(source, entries)
        return entries

    def _parse_sitemap_entries(
        self,
        source: DiscoverySource,
        xml_text: str,
    ) -> list[dict[str, str | None]]:
        root = ET.fromstring(xml_text)
        namespace_prefix = ""
        if "}" in root.tag:
            namespace_prefix = root.tag.split("}")[0] + "}"
        url_nodes = root.findall(f".//{namespace_prefix}url")
        entries: list[dict[str, str | None]] = []
        for url_node in url_nodes:
            link = self._find_text(url_node, "loc")
            if not link or not self._is_allowed_entry_url(source, link):
                continue
            title = self._title_from_url(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "summary": title,
                    "published": self._normalize_published_at(
                        self._find_text(url_node, "lastmod")
                    ),
                    "raw_text": self._clean_text(
                        " ".join(part for part in [title or "", link] if part)
                    ),
                }
            )
        if source.fetch_detail_pages:
            return self._enrich_entries_from_detail_pages(source, entries)
        return entries

    def _extract_anchor_entries(
        self,
        base_url: str,
        html_text: str,
        source: DiscoverySource,
    ) -> list[dict[str, str | None]]:
        entries: list[dict[str, str | None]] = []
        seen_links: set[str] = set()
        for match in re.finditer(
            r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<label>.*?)</a>",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = (match.group("href") or "").strip()
            if not href or href.startswith(("mailto:", "javascript:", "#")):
                continue
            link = urljoin(base_url, href)
            if link in seen_links or not self._is_allowed_entry_url(source, link):
                continue
            title = self._clean_text(
                self._strip_html(match.group("label") or "")
            ) or self._title_from_url(link)
            if not title:
                continue
            seen_links.add(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "summary": title,
                    "published": None,
                    "raw_text": self._clean_text(
                        " ".join(part for part in [title, link] if part)
                    ),
                }
            )
        return entries

    def _enrich_entries_from_detail_pages(
        self,
        source: DiscoverySource,
        entries: list[dict[str, str | None]],
    ) -> list[dict[str, str | None]]:
        enriched: list[dict[str, str | None]] = []
        max_items = source.max_items or self.max_items_per_source
        for entry in entries[: max(max_items * 2, max_items)]:
            link = entry.get("link")
            if not link:
                continue
            try:
                page_text = self._fetch_feed(link)
            except Exception:
                logger.debug("Failed to fetch detail page for %s.", link, exc_info=True)
                enriched.append(entry)
                continue
            enriched.append(self._merge_detail_page_entry(entry, page_text))
            if len(enriched) >= max_items:
                break
        return enriched

    def _merge_detail_page_entry(
        self,
        entry: dict[str, str | None],
        html_text: str,
    ) -> dict[str, str | None]:
        title = (
            self._extract_html_title(html_text)
            or entry.get("title")
            or self._title_from_url(entry.get("link") or "")
        )
        description = self._extract_meta_content(
            html_text,
            "description",
            property_name=False,
        ) or self._extract_meta_content(html_text, "og:description")
        published = (
            self._extract_meta_content(html_text, "article:published_time")
            or self._extract_time_datetime(html_text)
            or entry.get("published")
        )
        body_text = self._extract_body_text(html_text)
        summary = self._clean_text(
            description or self._snippet(body_text) or entry.get("summary") or ""
        )
        raw_text = self._clean_text(
            " ".join(
                part
                for part in [
                    title or "",
                    summary or "",
                    body_text,
                ]
                if part
            )
        )
        return {
            "title": title,
            "link": entry.get("link"),
            "summary": summary or None,
                    "published": self._normalize_published_at(published),
            "raw_text": raw_text,
        }

    def _build_candidate_from_entry(
        self,
        source: DiscoverySource,
        entry: dict[str, str | None],
        campaign: str | None = None,
    ) -> DiscoveryCandidate | None:
        explicit_company_name = self._clean_optional_value(entry.get("company_name"))
        derived_company_name = (
            self._derive_company_name_from_title(entry.get("title"))
            if source.derive_company_name_from_title
            else None
        )
        if source.derive_company_name_from_title and not explicit_company_name and not derived_company_name:
            return None
        company_name = explicit_company_name or derived_company_name or source.company_name
        combined_text = self._clean_text(
            " ".join(
                value
                for value in [
                    company_name,
                    entry.get("title"),
                    entry.get("summary"),
                    entry.get("raw_text"),
                ]
                if value
            )
        )
        if not combined_text:
            return None

        normalized_text = combined_text.lower()
        if self._contains_any(normalized_text, source.exclude_keywords):
            return None

        target_country = (
            normalize_target_country(entry.get("target_country_hint"))
            or normalize_target_country(source.default_target_country)
            or self._detect_target_country(
                normalized_text,
                source.target_countries,
            )
        )
        if target_country is None and not self._is_marketless_hris_signal(
            source,
            normalized_text,
        ):
            return None

        matched_watch_keywords = self._matched_keywords(
            normalized_text,
            source.watch_keywords,
        )
        matched_opportunity_keywords = self._matched_keywords(
            normalized_text,
            list(self.OPPORTUNITY_KEYWORDS),
        )
        matched_account_signals = self._matched_keywords(
            normalized_text,
            list(self.ACCOUNT_SIGNAL_KEYWORDS),
        )
        matched_buyer_signals = self._matched_keywords(
            normalized_text,
            list(self.BUYER_SIGNAL_KEYWORDS),
        )
        matched_service_focus_keywords = self._matched_service_focus_keywords(
            normalized_text,
            source.service_focus,
        )
        title_text = self._clean_text(entry.get("title") or "").lower()

        if not self._is_source_entry_relevant(
            source=source,
            title_text=title_text,
            matched_watch_keywords=matched_watch_keywords,
            matched_opportunity_keywords=matched_opportunity_keywords,
            matched_account_signals=matched_account_signals,
            matched_buyer_signals=matched_buyer_signals,
            matched_service_focus_keywords=matched_service_focus_keywords,
        ):
            return None

        buyer_hypothesis = self._buyer_hypothesis(
            self._service_focus_for_source(source),
            matched_buyer_signals,
            title_text,
        )
        commercial_trigger = self._commercial_trigger(
            matched_account_signals,
            matched_service_focus_keywords,
            target_country,
        )
        product_angle = self._product_angle(source, matched_service_focus_keywords)
        buyer_confidence = self._buyer_confidence(
            entry=entry,
            matched_buyer_signals=matched_buyer_signals,
            buyer_hypothesis=buyer_hypothesis,
        )
        account_fit_summary = self._account_fit_summary(
            company_name=company_name,
            lane_label=source.lane_label,
            target_country=target_country,
            commercial_trigger=commercial_trigger,
            product_angle=product_angle,
        )
        evidence = self._compose_evidence(
            entry.get("title"),
            entry.get("summary"),
            target_country,
        )
        notes = self._compose_notes(
            source.agent_label,
            entry.get("published"),
            matched_watch_keywords,
            matched_opportunity_keywords,
            matched_account_signals,
            matched_buyer_signals,
            source.lead_type_hint,
            self._service_focus_for_source(source),
            source.source_priority,
            source.trust_score,
            entry.get("link"),
            buyer_hypothesis,
            commercial_trigger,
            product_angle,
            entry.get("notes"),
        )
        return DiscoveryCandidate(
            company_name=company_name,
            agent_label=source.agent_label,
            lane_label=source.lane_label,
            discovery_key=self._build_discovery_key(
                source,
                entry,
                target_country,
            ),
            website_url=source.website_url,
            source_url=entry.get("link"),
            source_type=source.source_type,
            published_at=entry.get("published"),
            source_priority=source.source_priority,
            source_trust_score=source.trust_score,
            service_focus=self._service_focus_for_source(source),
            evidence=evidence,
            contact_name=self._clean_optional_value(entry.get("contact_name")),
            contact_role=self._clean_optional_value(entry.get("contact_role")),
            email=self._clean_optional_value(entry.get("email")),
            linkedin_url=self._clean_optional_value(entry.get("linkedin_url")),
            company_country=self._clean_optional_value(entry.get("company_country"))
            or source.company_country,
            target_country_hint=target_country,
            buyer_confidence=buyer_confidence,
            account_fit_summary=account_fit_summary,
            campaign=campaign or source.campaign,
            notes=notes,
        )

    def _detect_target_country(
        self,
        normalized_text: str,
        allowed_countries: list[str] | None = None,
    ) -> str | None:
        countries_to_check = [
            normalize_target_country(country)
            for country in (allowed_countries or list(self.COUNTRY_ALIASES.keys()))
        ]
        for country in countries_to_check:
            if not country:
                continue
            aliases = self.COUNTRY_ALIASES.get(country, [country.lower()])
            if any(alias in normalized_text for alias in aliases):
                return country
        return None

    def _is_source_entry_relevant(
        self,
        source: DiscoverySource,
        title_text: str,
        matched_watch_keywords: list[str],
        matched_opportunity_keywords: list[str],
        matched_account_signals: list[str],
        matched_buyer_signals: list[str],
        matched_service_focus_keywords: list[str],
    ) -> bool:
        has_watch_signal = bool(matched_watch_keywords)
        has_account_signal = bool(matched_account_signals)
        has_buyer_signal = bool(matched_buyer_signals)
        has_service_signal = bool(matched_service_focus_keywords)
        normalized_type = (source.source_type or "").lower()
        is_job_like_source = any(
            token in normalized_type
            for token in {"careers", "jobs", "greenhouse", "lever", "workable"}
        )

        if self._contains_any(title_text, list(self.JOB_TITLE_ROLE_NOISE_KEYWORDS)):
            if not (has_account_signal or has_buyer_signal or has_service_signal):
                return False

        normalized_service_focus = (source.service_focus or "").strip().lower()
        if normalized_service_focus and not matched_service_focus_keywords:
            if is_job_like_source:
                return False
            if not (has_account_signal and (has_watch_signal or has_buyer_signal)):
                return False

        if has_service_signal and (has_account_signal or has_buyer_signal or has_watch_signal):
            return True

        if has_account_signal and has_buyer_signal:
            return True

        if not is_job_like_source:
            if has_account_signal and (
                has_watch_signal or has_buyer_signal or bool(matched_opportunity_keywords)
            ):
                return True
            if has_buyer_signal and has_watch_signal:
                return True

        if source.watch_keywords:
            return has_watch_signal and (has_account_signal or has_buyer_signal or has_service_signal)

        if is_job_like_source:
            return bool(matched_opportunity_keywords) and (
                has_account_signal or has_buyer_signal or has_service_signal
            )
        return bool(matched_opportunity_keywords) and (
            has_account_signal or has_buyer_signal or has_service_signal
        )

    def _matched_keywords(
        self,
        normalized_text: str,
        keywords: list[str],
    ) -> list[str]:
        matched: list[str] = []
        for keyword in keywords:
            candidate = keyword.strip().lower()
            if candidate and self._keyword_matches(normalized_text, candidate):
                matched.append(keyword)
        return matched

    def _matched_service_focus_keywords(
        self,
        normalized_text: str,
        service_focus: str | None,
    ) -> list[str]:
        normalized_focus = (service_focus or "").strip().lower()
        keywords = self.SERVICE_FOCUS_KEYWORDS.get(normalized_focus, set())
        return self._matched_keywords(normalized_text, list(keywords))

    def _is_marketless_hris_signal(
        self,
        source: DiscoverySource,
        normalized_text: str,
    ) -> bool:
        lead_type_hint = (source.lead_type_hint or "").strip().lower()
        if lead_type_hint == "hris":
            return True
        return "hris" in normalized_text

    def _compose_evidence(
        self,
        title: str | None,
        summary: str | None,
        target_country: str | None,
    ) -> str:
        parts = [title or "Untitled source signal"]
        if summary:
            parts.append(summary)
        if target_country:
            parts.append(f"Matched target market: {target_country}.")
        return self._clean_text(" ".join(parts))

    def _compose_notes(
        self,
        agent_label: str | None,
        published: str | None,
        matched_watch_keywords: list[str],
        matched_opportunity_keywords: list[str],
        matched_account_signals: list[str],
        matched_buyer_signals: list[str],
        lead_type_hint: str | None,
        service_focus: str | None,
        source_priority: int,
        trust_score: int,
        source_url: str | None,
        buyer_hypothesis: str | None,
        commercial_trigger: str | None,
        product_angle: str | None,
        entry_notes: str | None,
    ) -> str | None:
        notes: list[str] = []
        if agent_label:
            notes.append(f"Sourcing agent: {agent_label}")
        if published:
            notes.append(f"Published: {published}")
        if matched_watch_keywords:
            notes.append(
                f"Matched source keywords: {', '.join(sorted(set(matched_watch_keywords)))}"
            )
        if matched_opportunity_keywords:
            notes.append(
                "Matched opportunity keywords: "
                f"{', '.join(sorted(set(matched_opportunity_keywords)))}"
            )
        if matched_account_signals:
            notes.append(
                "Matched account signals: "
                f"{', '.join(sorted(set(matched_account_signals)))}"
            )
        if matched_buyer_signals:
            notes.append(
                "Matched buyer signals: "
                f"{', '.join(sorted(set(matched_buyer_signals)))}"
            )
        if lead_type_hint:
            notes.append(f"Lead type hint: {lead_type_hint}")
        if service_focus:
            notes.append(f"Service focus: {service_focus}")
        if product_angle:
            notes.append(f"Product angle: {product_angle}")
        if buyer_hypothesis:
            notes.append(f"Buyer hypothesis: {buyer_hypothesis}")
        if commercial_trigger:
            notes.append(f"Commercial trigger: {commercial_trigger}")
        notes.append(f"Source priority: {source_priority}")
        notes.append(f"Source trust score: {trust_score}")
        if source_url:
            notes.append(f"Source URL: {source_url}")
        if entry_notes:
            notes.append(f"Source notes: {entry_notes}")
        if not notes:
            return None
        return "\n".join(notes)

    def _buyer_hypothesis(
        self,
        service_focus: str | None,
        matched_buyer_signals: list[str],
        title_text: str,
    ) -> str | None:
        if matched_buyer_signals:
            return ", ".join(sorted(set(matched_buyer_signals)))

        normalized_focus = (service_focus or "").strip().lower()
        if normalized_focus == "payroll":
            return "Payroll Manager, People Operations Lead, or Finance Director"
        if normalized_focus == "eor":
            return "Head of People, COO, or Regional General Manager"
        if normalized_focus == "hris":
            return "People Operations Lead, HR Director, or HRIS owner"
        if normalized_focus == "partner":
            return "Recruitment leader, Operations Director, or commercial partner owner"

        if "country manager" in title_text:
            return "Country Manager or regional operator"
        return None

    def _commercial_trigger(
        self,
        matched_account_signals: list[str],
        matched_service_focus_keywords: list[str],
        target_country: str | None,
    ) -> str | None:
        signal_parts: list[str] = []
        if matched_account_signals:
            signal_parts.append(", ".join(sorted(set(matched_account_signals))))
        if matched_service_focus_keywords:
            signal_parts.append(", ".join(sorted(set(matched_service_focus_keywords))))
        if target_country:
            signal_parts.append(f"target market={target_country}")
        if not signal_parts:
            return None
        return "; ".join(signal_parts)

    def _product_angle(
        self,
        source: DiscoverySource,
        matched_service_focus_keywords: list[str],
    ) -> str | None:
        normalized_focus = (self._service_focus_for_source(source) or "").strip().lower()
        if normalized_focus == "payroll":
            if any("people" in keyword or "hris" in keyword for keyword in matched_service_focus_keywords):
                return "Payroll-led opportunity with possible HRIS adjacency"
            return "Payroll-led opportunity"
        if normalized_focus == "eor":
            return "EOR-led market entry or employment infrastructure opportunity"
        if normalized_focus == "hris":
            return "HRIS-led people systems standardization opportunity"
        if normalized_focus == "partner":
            return "Partner-led referral or staffing-channel opportunity"
        return None

    def _buyer_confidence(
        self,
        *,
        entry: dict[str, Any],
        matched_buyer_signals: list[str],
        buyer_hypothesis: str | None,
    ) -> int | None:
        if self._clean_optional_value(entry.get("contact_name")) and self._clean_optional_value(
            entry.get("contact_role")
        ):
            return 9
        if self._clean_optional_value(entry.get("contact_role")):
            return 8
        if matched_buyer_signals:
            return 6
        if buyer_hypothesis:
            return 5
        return None

    def _account_fit_summary(
        self,
        *,
        company_name: str,
        lane_label: str | None,
        target_country: str | None,
        commercial_trigger: str | None,
        product_angle: str | None,
    ) -> str | None:
        parts = [
            f"lane={lane_label}" if lane_label else None,
            f"market={target_country}" if target_country else None,
            f"trigger={commercial_trigger}" if commercial_trigger else None,
            f"angle={product_angle}" if product_angle else None,
        ]
        values = [part for part in parts if part]
        if not values:
            return None
        return f"{company_name}: " + "; ".join(values)

    def _deduplicate_candidates(
        self,
        candidates: list[DiscoveryCandidate],
    ) -> list[DiscoveryCandidate]:
        deduplicated: dict[str, DiscoveryCandidate] = {}
        for candidate in candidates:
            key = candidate.discovery_key or self._candidate_fallback_key(candidate)
            existing = deduplicated.get(key)
            if existing is None:
                deduplicated[key] = candidate
                continue

            existing_rank = (
                existing.source_priority or 0,
                existing.source_trust_score or 0,
            )
            candidate_rank = (
                candidate.source_priority or 0,
                candidate.source_trust_score or 0,
            )
            if candidate_rank > existing_rank:
                deduplicated[key] = candidate
        return list(deduplicated.values())

    def _candidate_fallback_key(self, candidate: DiscoveryCandidate) -> str:
        return "|".join(
            [
                candidate.company_name.strip().lower(),
                (candidate.source_url or "").strip().lower(),
                (candidate.target_country_hint or "").strip().lower(),
                (candidate.service_focus or "").strip().lower(),
            ]
        )

    def _build_discovery_key(
        self,
        source: DiscoverySource,
        entry: dict[str, str | None],
        target_country: str | None,
    ) -> str:
        seed = "|".join(
            [
                source.company_name.strip().lower(),
                (entry.get("link") or "").strip().lower(),
                (entry.get("title") or "").strip().lower(),
                (target_country or "").strip().lower(),
                (source.service_focus or source.lead_type_hint or "").strip().lower(),
            ]
        )
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]

    def _service_focus_for_source(self, source: DiscoverySource) -> str | None:
        if source.service_focus:
            return source.service_focus
        if source.lead_type_hint == "direct_payroll":
            return "payroll"
        if source.lead_type_hint == "direct_eor":
            return "eor"
        if source.lead_type_hint == "recruitment_partner":
            return "partner"
        if source.lead_type_hint == "hris":
            return "hris"
        return None

    def _contains_any(self, normalized_text: str, keywords: list[str]) -> bool:
        return any(
            self._keyword_matches(normalized_text, keyword.strip().lower())
            for keyword in keywords
            if keyword.strip()
        )

    def _keyword_matches(self, normalized_text: str, keyword: str) -> bool:
        pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
        return re.search(pattern, normalized_text) is not None

    def _find_text(self, node: ET.Element, tag_name: str) -> str | None:
        for child in node:
            if self._local_name(child.tag) == tag_name:
                return self._clean_text(" ".join(child.itertext()))
        return None

    def _find_first_text(self, node: ET.Element, *tag_names: str) -> str | None:
        for tag_name in tag_names:
            value = self._find_text(node, tag_name)
            if value:
                return value
        return None

    def _find_link(self, node: ET.Element) -> str | None:
        for child in node:
            if self._local_name(child.tag) != "link":
                continue
            href = child.attrib.get("href")
            if href:
                return href.strip()
            text_value = self._clean_text(" ".join(child.itertext()))
            if text_value:
                return text_value
        return None

    def _is_allowed_entry_url(
        self,
        source: DiscoverySource,
        link: str,
    ) -> bool:
        parsed_link = urlparse(link)
        if not parsed_link.scheme or parsed_link.scheme not in {"http", "https"}:
            return False
        base_url = source.feed_url or source.website_url
        if source.same_domain_only and base_url:
            parsed_base = urlparse(base_url)
            if parsed_base.netloc and parsed_link.netloc and parsed_base.netloc != parsed_link.netloc:
                return False

        keywords = [keyword.strip().lower() for keyword in source.entry_url_keywords if keyword.strip()]
        if not keywords:
            normalized_type = (source.source_type or "").strip().lower()
            if normalized_type in {"webpage_html", "sitemap_xml"}:
                keywords = sorted(self.DEFAULT_ENTRY_URL_KEYWORDS)
        if not keywords:
            return True

        searchable = self._clean_text(link).lower()
        return any(keyword in searchable for keyword in keywords)

    def _extract_html_title(self, html_text: str) -> str | None:
        match = re.search(
            r"<title[^>]*>(.*?)</title>",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            title = self._extract_meta_content(html_text, "og:title")
            return self._clean_text(title) if title else None
        return self._clean_text(self._strip_html(match.group(1)))

    def _extract_meta_content(
        self,
        html_text: str,
        name: str,
        *,
        property_name: bool = True,
    ) -> str | None:
        attribute = "property" if property_name else "name"
        pattern = rf"<meta[^>]+{attribute}=[\"']{re.escape(name)}[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>"
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match and property_name:
            pattern = rf"<meta[^>]+name=[\"']{re.escape(name)}[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>"
            match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return self._clean_text(self._strip_html(match.group(1)))

    def _extract_time_datetime(self, html_text: str) -> str | None:
        match = re.search(
            r"<time[^>]+datetime=[\"'](.*?)[\"'][^>]*>",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return self._clean_text(match.group(1))

    def _extract_body_text(self, html_text: str) -> str:
        cleaned = re.sub(
            r"<(script|style|noscript)[^>]*>.*?</\1>",
            " ",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        paragraphs = re.findall(
            r"<p[^>]*>(.*?)</p>",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if paragraphs:
            return self._clean_text(
                " ".join(self._strip_html(paragraph) for paragraph in paragraphs)
            )
        return self._clean_text(self._strip_html(cleaned))

    def _strip_html(self, html_fragment: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", html_fragment)
        return unescape(without_tags)

    def _title_from_url(self, link: str) -> str | None:
        path = urlparse(link).path
        if not path:
            return None
        slug = path.rstrip("/").split("/")[-1]
        slug = re.sub(r"[-_]+", " ", slug)
        return self._clean_text(slug.title())

    def _derive_company_name_from_title(self, title: str | None) -> str | None:
        cleaned = self._clean_text(title or "")
        if not cleaned:
            return None
        first_clause = re.split(r"[:|\-–]", cleaned, maxsplit=1)[0].strip()
        if not first_clause:
            return None
        candidate = re.sub(
            r"^(press release|news|update)\s+",
            "",
            first_clause,
            flags=re.IGNORECASE,
        ).strip()
        if not candidate:
            return None
        if re.match(r"^(a|an|the)\b", candidate, flags=re.IGNORECASE):
            return None
        trigger_match = re.match(
            r"^(?P<company>.+?)\s+(launches|launching|expands|expanding|opens|opening|enters|entering|appoints|appointing|announces|announcing|raises|raising|partners|partnering)\b",
            candidate,
            flags=re.IGNORECASE,
        )
        if trigger_match:
            candidate = trigger_match.group("company").strip()
        if len(candidate.split()) > 6:
            return None
        lowered = candidate.lower()
        if any(alias in lowered for aliases in self.COUNTRY_ALIASES.values() for alias in aliases):
            return None
        return candidate

    def _normalize_published_at(self, value: str | None) -> str | None:
        cleaned = self._clean_optional_value(value)
        if not cleaned:
            return None
        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(cleaned)
            except (TypeError, ValueError, IndexError):
                return cleaned
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _clean_text(self, value: str) -> str:
        unescaped = unescape(value or "")
        no_tags = re.sub(r"<[^>]+>", " ", unescaped)
        normalized = re.sub(r"\s+", " ", no_tags).strip()
        return normalized

    def _clean_optional_value(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = self._clean_text(str(value))
        return cleaned or None

    def _snippet(self, value: str | None, limit: int = 320) -> str | None:
        if not value:
            return None
        cleaned = self._clean_text(value)
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."
