from app.services.discovery_source_service import DiscoverySourceService


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = []

    def get(self, url: str):
        self.calls.append(url)
        return _FakeResponse(self._text)


class _MappingFakeClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.calls = []

    def get(self, url: str):
        self.calls.append(url)
        return _FakeResponse(self._responses[url])


def test_collect_candidates_filters_feed_entries_to_target_market() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "North Star Health",
    "feed_url": "https://northstar.example/jobs.xml",
    "website_url": "https://northstar.example",
    "source_type": "careers_feed",
    "company_country": "Germany",
    "campaign": "Saudi and UAE expansion",
    "watch_keywords": ["payroll", "people"],
    "target_countries": ["Saudi Arabia", "United Arab Emirates"]
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>Payroll Operations Manager - Riyadh</title>
      <link>https://northstar.example/jobs/payroll-riyadh</link>
      <description>Build payroll operations for our Saudi Arabia team.</description>
      <pubDate>Sat, 22 Mar 2026 07:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Senior Engineer - Austin</title>
      <link>https://northstar.example/jobs/engineer-austin</link>
      <description>General software role in the US.</description>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        sources, candidates = service.collect_candidates(
            campaign="Saudi and UAE expansion",
        )

        assert len(sources) == 1
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.company_name == "North Star Health"
        assert candidate.target_country_hint == "Saudi Arabia"
        assert candidate.source_url == "https://northstar.example/jobs/payroll-riyadh"
        assert "Riyadh" in candidate.evidence
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_greenhouse_json_sources() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "WillowTree",
    "agent_label": "Payroll Complexity Agent",
    "feed_url": "https://boards-api.greenhouse.io/v1/boards/willowtree/jobs?content=true",
    "website_url": "https://boards.greenhouse.io/embed/job_board?for=willowtree",
    "source_type": "greenhouse_json",
    "company_country": "United Kingdom",
    "campaign": "UK/EU companies hiring into UAE, Saudi Arabia, and Egypt",
    "watch_keywords": ["payroll", "people operations", "country manager"],
    "service_focus": "payroll",
    "target_countries": ["United Arab Emirates"]
  }
]
""".strip()
        )
    feed_text = """
{
  "jobs": [
    {
      "title": "Country Manager, UAE",
      "absolute_url": "https://boards.greenhouse.io/willowtree/jobs/123",
      "updated_at": "2026-03-22T08:00:00Z",
      "location": {"name": "Dubai, United Arab Emirates"},
      "content": "<p>Build payroll operations and people operations capability for our UAE launch.</p>"
    },
    {
      "title": "Backend Engineer",
      "absolute_url": "https://boards.greenhouse.io/willowtree/jobs/124",
      "updated_at": "2026-03-22T08:00:00Z",
      "location": {"name": "Berlin, Germany"},
      "content": "<p>Platform engineering role.</p>"
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        sources, candidates = service.collect_candidates()

        assert len(sources) == 1
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.company_name == "WillowTree"
        assert candidate.agent_label == "Payroll Complexity Agent"
        assert candidate.target_country_hint == "United Arab Emirates"
        assert candidate.source_url == "https://boards.greenhouse.io/willowtree/jobs/123"
        assert "Country Manager, UAE" in candidate.evidence
        assert "Sourcing agent: Payroll Complexity Agent" in (candidate.notes or "")
        assert "Buyer hypothesis:" in (candidate.notes or "")
        assert "Commercial trigger:" in (candidate.notes or "")
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_skips_service_focused_roles_without_matching_service_signal() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Guidepoint",
    "feed_url": "https://boards-api.greenhouse.io/v1/boards/guidepoint/jobs?content=true",
    "website_url": "https://boards.greenhouse.io/embed/job_board?for=guidepoint",
    "source_type": "greenhouse_json",
    "company_country": "United Kingdom",
    "campaign": "UK/EU companies hiring across the Gulf",
    "service_focus": "payroll",
    "lead_type_hint": "direct_payroll",
    "watch_keywords": ["people", "payroll", "operations"],
    "target_countries": ["United Arab Emirates"]
  }
]
""".strip()
        )
    feed_text = """
{
  "jobs": [
    {
      "title": "Associate, Client Growth Dubai",
      "absolute_url": "https://boards.greenhouse.io/guidepoint/jobs/123",
      "updated_at": "2026-03-22T08:00:00Z",
      "location": {"name": "Dubai, United Arab Emirates"},
      "content": "<p>Build commercial relationships in Dubai and support client growth.</p>"
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert candidates == []
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_does_not_match_hr_inside_unrelated_words() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Guidepoint",
    "feed_url": "https://boards-api.greenhouse.io/v1/boards/guidepoint/jobs?content=true",
    "website_url": "https://boards.greenhouse.io/embed/job_board?for=guidepoint",
    "source_type": "greenhouse_json",
    "company_country": "United Kingdom",
    "campaign": "UK/EU companies hiring across the Gulf",
    "watch_keywords": ["hr"],
    "target_countries": ["United Arab Emirates"]
  }
]
""".strip()
        )
    feed_text = """
{
  "jobs": [
    {
      "title": "Associate, Business Development Dubai",
      "absolute_url": "https://boards.greenhouse.io/guidepoint/jobs/456",
      "updated_at": "2026-03-22T08:00:00Z",
      "location": {"name": "Dubai, United Arab Emirates"},
      "content": "<p>Build relationships with new and existing clients in Dubai.</p>"
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert candidates == []
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_secondary_markets() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Atlas Expansion Group",
    "feed_url": "https://atlas.example/jobs.xml",
    "website_url": "https://atlas.example",
    "source_type": "careers_feed",
    "company_country": "United Kingdom",
    "campaign": "Regional payroll expansion",
    "watch_keywords": ["payroll", "operations"],
    "target_countries": ["Qatar", "Jordan"]
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>Regional Payroll Lead - Doha</title>
      <link>https://atlas.example/jobs/payroll-doha</link>
      <description>Build payroll operations for our Qatar team.</description>
      <pubDate>Sat, 22 Mar 2026 07:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates(campaign="Regional payroll expansion")

        assert len(candidates) == 1
        assert candidates[0].target_country_hint == "Qatar"
        assert "Doha" in candidates[0].evidence
        assert "Commercial trigger:" in (candidates[0].notes or "")
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_allows_hris_signals_without_supported_market_match() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "People Systems Group",
    "feed_url": "https://people.example/jobs.xml",
    "website_url": "https://people.example",
    "source_type": "careers_feed",
    "company_country": "Canada",
    "campaign": "Global HRIS expansion",
    "watch_keywords": ["hris"],
    "lead_type_hint": "hris",
    "target_countries": ["United Arab Emirates", "Saudi Arabia", "Egypt"]
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>Senior HRIS Manager - Toronto</title>
      <link>https://people.example/jobs/hris-toronto</link>
      <description>Own global HRIS design and people systems operations.</description>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates(campaign="Global HRIS expansion")

        assert len(candidates) == 1
        assert candidates[0].target_country_hint is None
        assert "HRIS" in candidates[0].evidence
        assert "Buyer hypothesis:" in (candidates[0].notes or "")
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_workable_json_sources() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Global Freight Group",
    "feed_url": "https://apply.workable.com/api/v3/accounts/global-freight/jobs",
    "website_url": "https://apply.workable.com/global-freight/",
    "source_type": "workable_json",
    "company_country": "United Kingdom",
    "campaign": "Regional payroll expansion",
    "watch_keywords": ["payroll", "operations"],
    "service_focus": "payroll",
    "target_countries": ["Qatar", "Saudi Arabia"]
  }
]
""".strip()
        )
    feed_text = """
{
  "results": [
    {
      "title": "Regional Payroll Manager",
      "url": "https://apply.workable.com/global-freight/j/123",
      "published": "2026-03-22T08:00:00Z",
      "location": {"city": "Doha", "country": "Qatar"},
      "description": "Lead payroll operations for our Qatar launch."
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates(campaign="Regional payroll expansion")

        assert len(candidates) == 1
        assert candidates[0].target_country_hint == "Qatar"
        assert candidates[0].source_type == "workable_json"
        assert candidates[0].service_focus == "payroll"
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_deduplicates_by_discovery_key_and_keeps_higher_trust() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "North Star Health",
    "feed_url": "https://northstar.example/jobs.xml",
    "website_url": "https://northstar.example",
    "source_type": "careers_feed",
    "company_country": "Germany",
    "campaign": "Saudi expansion",
    "watch_keywords": ["payroll"],
    "target_countries": ["Saudi Arabia"],
    "source_priority": 8,
    "trust_score": 9
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>Payroll Operations Manager - Riyadh</title>
      <link>https://northstar.example/jobs/payroll-riyadh</link>
      <description>Build payroll operations for our Saudi Arabia team.</description>
    </item>
    <item>
      <title>Payroll Operations Manager - Riyadh</title>
      <link>https://northstar.example/jobs/payroll-riyadh</link>
      <description>Build payroll operations for our Saudi Arabia team.</description>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates(campaign="Saudi expansion")

        assert len(candidates) == 1
        assert candidates[0].source_priority == 8
        assert candidates[0].source_trust_score == 9
        assert candidates[0].discovery_key
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_rejects_generic_sales_role_without_buyer_or_product_signal() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Broad Market Co",
    "feed_url": "https://boards-api.greenhouse.io/v1/boards/broad-market/jobs?content=true",
    "website_url": "https://boards.greenhouse.io/embed/job_board?for=broad-market",
    "source_type": "greenhouse_json",
    "company_country": "United Kingdom",
    "campaign": "Regional sales expansion",
    "watch_keywords": ["sales", "operations"],
    "target_countries": ["United Arab Emirates"]
  }
]
""".strip()
        )
    feed_text = """
{
  "jobs": [
    {
      "title": "Senior Account Executive",
      "absolute_url": "https://boards.greenhouse.io/broad-market/jobs/123",
      "updated_at": "2026-03-22T08:00:00Z",
      "location": {"name": "Dubai, United Arab Emirates"},
      "content": "<p>Build customer relationships and win net-new logos in Dubai.</p>"
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert candidates == []
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_load_sources_supports_lane_grouped_payload() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
{
  "lanes": [
    {
      "lane_label": "Expansion Signals",
      "agent_label": "EOR Expansion Agent",
      "campaign": "Broad MENA employment infrastructure discovery",
      "sources": [
        {
          "company_name": "North Star Health",
          "feed_url": "https://northstar.example/jobs.xml",
          "source_type": "careers_feed",
          "watch_keywords": ["country manager", "entity"],
          "target_countries": ["Saudi Arabia"]
        }
      ]
    }
  ]
}
""".strip()
        )
    try:
        service = DiscoverySourceService(
            client=_FakeClient("<rss><channel></channel></rss>"),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        sources = service.load_sources()

        assert len(sources) == 1
        assert sources[0].lane_label == "Expansion Signals"
        assert sources[0].agent_label == "EOR Expansion Agent"
        assert sources[0].campaign == "Broad MENA employment infrastructure discovery"
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_manual_signal_entries() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
{
  "lanes": [
    {
      "lane_label": "Manual Strategic Accounts",
      "agent_label": "Manual Strategic Account Agent",
      "campaign": "Broad MENA employment infrastructure discovery",
      "sources": [
        {
          "company_name": "Atlas Ops",
          "source_type": "manual_signals",
          "service_focus": "eor",
          "lead_type_hint": "direct_eor",
          "target_countries": ["United Arab Emirates", "Saudi Arabia"],
          "watch_keywords": ["entity", "country manager", "market entry"],
          "entries": [
            {
              "company_name": "Atlas Ops",
              "title": "Atlas Ops preparing UAE launch",
              "summary": "Leadership note indicates market entry planning and entity setup in the UAE.",
              "source_url": "https://atlas.example/uae-launch",
              "target_country_hint": "United Arab Emirates",
              "contact_name": "Mina Yusuf",
              "contact_role": "COO",
              "notes": "Manual strategic-account note from operator research."
            }
          ]
        }
      ]
    }
  ]
}
""".strip()
        )
    try:
        service = DiscoverySourceService(
            client=_FakeClient(""),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        sources, candidates = service.collect_candidates()

        assert len(sources) == 1
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.company_name == "Atlas Ops"
        assert candidate.agent_label == "Manual Strategic Account Agent"
        assert candidate.contact_name == "Mina Yusuf"
        assert candidate.contact_role == "COO"
        assert candidate.target_country_hint == "United Arab Emirates"
        assert "Manual strategic-account note" in (candidate.notes or "")
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_json_feed_sources() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "North Star Health",
    "feed_url": "https://northstar.example/feed.json",
    "website_url": "https://northstar.example",
    "source_type": "json_feed",
    "company_country": "Germany",
    "campaign": "Saudi payroll expansion",
    "watch_keywords": ["payroll", "entity", "expansion"],
    "service_focus": "payroll",
    "target_countries": ["Saudi Arabia"],
    "default_target_country": "Saudi Arabia"
  }
]
""".strip()
        )
    feed_text = """
{
  "items": [
    {
      "title": "North Star Health announces Saudi payroll expansion",
      "url": "https://northstar.example/news/saudi-payroll-expansion",
      "summary": "The company is expanding payroll operations and entity support in Saudi Arabia.",
      "date_published": "2026-03-22T08:00:00Z"
    }
  ]
}
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.source_type == "json_feed"
        assert candidate.target_country_hint == "Saudi Arabia"
        assert "Saudi payroll expansion" in candidate.evidence
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_webpage_html_sources_with_detail_fetch() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "North Star Health",
    "feed_url": "https://northstar.example/news",
    "website_url": "https://northstar.example",
    "source_type": "webpage_html",
    "service_focus": "eor",
    "watch_keywords": ["expansion", "entity", "mobility"],
    "target_countries": ["United Arab Emirates"],
    "default_target_country": "United Arab Emirates",
    "fetch_detail_pages": true
  }
]
""".strip()
        )
    listing_html = """
<html><body>
  <a href="/news/uae-launch">North Star Health launches UAE entity support</a>
</body></html>
""".strip()
    detail_html = """
<html>
  <head>
    <title>North Star Health launches UAE entity support</title>
    <meta name="description" content="North Star Health is launching entity support and mobility operations in the United Arab Emirates." />
    <meta property="article:published_time" content="2026-03-22T08:00:00Z" />
  </head>
  <body>
    <p>North Star Health is expanding into the United Arab Emirates with new entity support and mobility operations.</p>
  </body>
</html>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_MappingFakeClient(
                {
                    "https://northstar.example/news": listing_html,
                    "https://northstar.example/news/uae-launch": detail_html,
                }
            ),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.source_url == "https://northstar.example/news/uae-launch"
        assert candidate.target_country_hint == "United Arab Emirates"
        assert "entity support" in candidate.evidence.lower()
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_supports_generic_market_intelligence_with_company_derivation() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "Regional Expansion Radar",
    "feed_url": "https://news.example/rss.xml",
    "source_type": "careers_feed",
    "watch_keywords": ["expansion", "launch", "entity", "regional"],
    "target_countries": ["Saudi Arabia"],
    "default_target_country": "Saudi Arabia",
    "derive_company_name_from_title": true
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>Acme Corp launches regional headquarters in Saudi Arabia</title>
      <link>https://news.example/acme-saudi-launch</link>
      <description>Acme Corp is expanding regional operations and entity support in Saudi Arabia.</description>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert len(candidates) == 1
        assert candidates[0].company_name == "Acme Corp"
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_normalizes_rss_pubdate_for_notion_safe_dates() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "North Star Health",
    "feed_url": "https://news.example/rss.xml",
    "source_type": "rss_news_feed",
    "watch_keywords": ["expansion", "entity"],
    "service_focus": "eor",
    "target_countries": ["United Arab Emirates"],
    "default_target_country": "United Arab Emirates"
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>North Star Health announces UAE entity expansion</title>
      <link>https://news.example/north-star-uae</link>
      <description>North Star Health is expanding its entity support into the UAE.</description>
      <pubDate>Mon, 24 Mar 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert len(candidates) == 1
        assert candidates[0].published_at == "2026-03-24T08:00:00Z"
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)


def test_collect_candidates_skips_generic_radar_entry_when_company_cannot_be_derived() -> None:
    sources_file = "tests/_tmp_discovery_sources.json"
    with open(sources_file, "w", encoding="utf-8") as handle:
        handle.write(
            """
[
  {
    "company_name": "MENA HRIS Radar",
    "feed_url": "https://news.example/rss.xml",
    "source_type": "rss_news_feed",
    "derive_company_name_from_title": true,
    "watch_keywords": ["hris", "people operations"],
    "service_focus": "hris",
    "target_countries": ["Saudi Arabia"],
    "default_target_country": "Saudi Arabia"
  }
]
""".strip()
        )
    feed_text = """
<rss>
  <channel>
    <item>
      <title>A challenge to banks</title>
      <link>https://news.example/challenge-banks</link>
      <description>General commentary about HRIS adoption and people operations.</description>
      <pubDate>Mon, 24 Mar 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".strip()
    try:
        service = DiscoverySourceService(
            client=_FakeClient(feed_text),
            sources_file=sources_file,
            max_items_per_source=10,
        )

        _, candidates = service.collect_candidates()

        assert candidates == []
    finally:
        import os

        if os.path.exists(sources_file):
            os.remove(sources_file)
