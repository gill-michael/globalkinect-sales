from html import escape
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import make_server

from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import OutreachQueueRecord, SalesEngineRunRecord
from app.services.config import settings
from app.services.operator_console_service import OperatorConsoleService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OperatorConsoleApp:
    def __init__(
        self,
        service: OperatorConsoleService | None = None,
    ) -> None:
        self.service = service or OperatorConsoleService()

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/") or "/"
        query = parse_qs(environ.get("QUERY_STRING", ""))

        try:
            if method == "GET" and path == "/":
                return self._respond_html(
                    start_response,
                    self._render_dashboard(query),
                )
            if method == "GET" and path == "/discovery":
                return self._respond_html(
                    start_response,
                    self._render_discovery(query),
                )
            if method == "GET" and path == "/intake":
                return self._respond_html(
                    start_response,
                    self._render_intake(query),
                )
            if method == "GET" and path == "/accounts":
                return self._respond_html(
                    start_response,
                    self._render_accounts(query),
                )
            if method == "GET" and path == "/queue":
                return self._respond_html(
                    start_response,
                    self._render_queue(query),
                )
            if method == "POST" and path == "/queue/status":
                return self._handle_queue_status(start_response, environ)
            if method == "GET" and path == "/runs":
                return self._respond_html(
                    start_response,
                    self._render_runs(query),
                )
            if method == "GET" and path == "/help":
                return self._respond_html(
                    start_response,
                    self._render_help(query),
                )
            if method == "GET" and path == "/health":
                return self._respond_text(start_response, "ok")
            return self._respond_html(
                start_response,
                self._layout(
                    title="Not Found",
                    active="",
                    body="<section class='panel'><h2>Page not found</h2></section>",
                ),
                status="404 Not Found",
            )
        except Exception as exc:
            logger.exception("Operator console request failed.")
            return self._respond_html(
                start_response,
                self._layout(
                    title="Console Error",
                    active="",
                    body=(
                        "<section class='panel'>"
                        "<h2>Operator console error</h2>"
                        f"<p>{escape(str(exc))}</p>"
                        "</section>"
                    ),
                ),
                status="500 Internal Server Error",
            )

    def _render_dashboard(self, query: dict[str, list[str]]) -> str:
        snapshot = self.service.dashboard_snapshot()
        flash = self._flash_message(query)

        ready_discovery = self._count_statuses(
            [record.status for record in snapshot.discovery_records],
            {"new", "approved", "ready"},
        )
        ready_intake = self._count_statuses(
            [record.status for record in snapshot.intake_records],
            {"new", "approved", "ready"},
        )
        ready_queue = self._count_statuses(
            [record.status for record in snapshot.outreach_queue_records],
            {"readytosend"},
        )
        approved_queue = self._count_statuses(
            [record.status for record in snapshot.outreach_queue_records],
            {"approved"},
        )
        hold_queue = self._count_statuses(
            [record.status for record in snapshot.outreach_queue_records],
            {"hold"},
        )
        failed_runs = self._count_statuses(
            [record.status for record in snapshot.run_records],
            {"failed"},
        )

        latest_run = snapshot.run_records[0] if snapshot.run_records else None
        latest_run_html = (
            self._run_row(latest_run, compact=True)
            if latest_run is not None
            else "<p class='muted'>No run history available yet.</p>"
        )
        queue_focus = self._focus_row(
            "Outreach Queue",
            ready_queue,
            "Drafts need operator decisions before any send action happens.",
            "/queue",
            "Open queue",
        )
        discovery_focus = self._focus_row(
            "Lead Discovery",
            ready_discovery,
            "Fresh signals waiting for qualification and buyer review.",
            "/discovery",
            "Review discovery",
        )
        intake_focus = self._focus_row(
            "Lead Intake",
            ready_intake,
            "Normalized rows that can move into scoring and packaging.",
            "/intake",
            "Open intake",
        )

        body = (
            self._warning_banner()
            + self._flash_banner(flash)
            + "<section class='hero'>"
            "<div><p class='eyebrow'>Global Kinect Sales Engine</p>"
            "<h1>Daily operator console</h1>"
            "<p class='hero-copy'>Review live discovery, intake, queue decisions, and run health from one local control surface.</p>"
            "<div class='hero-actions'>"
            "<a class='hero-link' href='/queue?status=Ready+to+send'>Review ready drafts</a>"
            "<a class='hero-link ghost' href='/discovery?status=Review'>Review discovery backlog</a>"
            "</div></div>"
            "<div class='hero-accent'>"
            f"<span class='metric-pill'>Discovery {len(snapshot.discovery_records)}</span>"
            f"<span class='metric-pill'>Queue {len(snapshot.outreach_queue_records)}</span>"
            f"<span class='metric-pill'>Runs {len(snapshot.run_records)}</span>"
            "</div></section>"
            "<section class='metrics'>"
            f"{self._metric_card('Ready Discovery', ready_discovery, 'Promotable or awaiting review in Lead Discovery.')}"
            f"{self._metric_card('Ready Intake', ready_intake, 'Normalized rows ready for scoring and packaging.')}"
            f"{self._metric_card('Ready To Send', ready_queue, 'Drafts waiting for manual approval or send.')}"
            f"{self._metric_card('Approved', approved_queue, 'Rows explicitly selected for send readiness.')}"
            f"{self._metric_card('Hold', hold_queue, 'Rows intentionally kept out of the current send cycle.')}"
            f"{self._metric_card('Failed Runs', failed_runs, 'Recent run records marked failed.')}"
            "</section>"
            "<section class='focus-grid'>"
            f"{queue_focus}{discovery_focus}{intake_focus}"
            "</section>"
            "<section class='panel-grid'>"
            "<section class='panel'><div class='panel-head'><h2>Latest Run</h2><a href='/runs'>Open run monitor</a></div>"
            f"{latest_run_html}</section>"
            "<section class='panel'><div class='panel-head'><h2>Immediate Next Steps</h2></div>"
            "<ul class='action-list'>"
            "<li>Review promoted records in <a href='/discovery'>Lead Discovery</a>.</li>"
            "<li>Check current normalization backlog in <a href='/intake'>Lead Intake</a>.</li>"
            "<li>Use <a href='/queue'>Outreach Queue</a> to approve, hold, or mark drafts sent.</li>"
            "</ul></section>"
            "</section>"
        )
        return self._layout("Operator Dashboard", "dashboard", body)

    def _render_discovery(self, query: dict[str, list[str]]) -> str:
        records = self.service.list_discovery_records(limit=100)
        requested_status = self._selected_filter(query, "status")
        requested_search = self._selected_filter(query, "q")
        filtered = self._apply_record_filters(
            records,
            requested_status,
            requested_search,
            lambda record: [
                record.company_name,
                record.contact_name,
                record.contact_role,
                record.target_country_hint,
                record.service_focus,
                record.lane_label,
                record.agent_label,
                record.notes,
                record.evidence,
            ],
        )
        ordered = sorted(
            filtered,
            key=lambda record: (
                self._status_rank(
                    record.status,
                    ["Review", "Ready", "Approved", "Promoted", "Rejected", "Archived"],
                ),
                -(record.buyer_confidence or 0),
                -(record.source_trust_score or 0),
                -(record.source_priority or 0),
                record.company_name.lower(),
            ),
        )
        rows = "".join(self._discovery_card(record) for record in ordered) or (
            "<p class='muted'>No Lead Discovery rows match the current filters.</p>"
        )
        status_counts = self._summarize_statuses(records)
        body = (
            self._warning_banner()
            + self._flash_banner(self._flash_message(query))
            + self._page_header(
                "Lead Discovery",
                "Raw source-backed candidates and qualification status.",
                len(filtered),
                len(records),
            )
            + self._filter_toolbar(
                "/discovery",
                requested_status,
                requested_search,
                status_counts,
                "Search company, buyer, lane, service, or evidence",
            )
            + "<section class='panel'><div class='panel-head'><h2>Lead Discovery</h2>"
            "<span class='muted'>Work from the freshest and strongest signals first. Filter down to review-ready rows when triaging the backlog.</span></div>"
            f"<div class='stack'>{rows}</div></section>"
        )
        return self._layout("Lead Discovery", "discovery", body)

    def _render_intake(self, query: dict[str, list[str]]) -> str:
        records = self.service.list_intake_records(limit=100)
        requested_status = self._selected_filter(query, "status")
        requested_search = self._selected_filter(query, "q")
        filtered = self._apply_record_filters(
            records,
            requested_status,
            requested_search,
            lambda record: [
                record.company_name,
                record.contact_name,
                record.contact_role,
                record.target_country,
                record.lead_type_hint,
                record.lane_label,
                record.notes,
                record.campaign,
            ],
        )
        ordered = sorted(
            filtered,
            key=lambda record: (
                self._status_rank(
                    record.status,
                    ["Ready", "Approved", "New", "Processed", "Archived", "Rejected"],
                ),
                -(record.buyer_confidence or 0),
                record.company_name.lower(),
            ),
        )
        rows = "".join(self._intake_card(record) for record in ordered) or (
            "<p class='muted'>No Lead Intake rows match the current filters.</p>"
        )
        status_counts = self._summarize_statuses(records)
        body = (
            self._warning_banner()
            + self._flash_banner(self._flash_message(query))
            + self._page_header(
                "Lead Intake",
                "Normalized leads waiting for or recently completed packaging.",
                len(filtered),
                len(records),
            )
            + self._filter_toolbar(
                "/intake",
                requested_status,
                requested_search,
                status_counts,
                "Search company, buyer, country, lead type, or campaign",
            )
            + "<section class='panel'><div class='panel-head'><h2>Lead Intake</h2>"
            "<span class='muted'>Use this queue to confirm packaged rows still look commercially credible before they reach downstream actions.</span></div>"
            f"<div class='stack'>{rows}</div></section>"
        )
        return self._layout("Lead Intake", "intake", body)

    def _render_queue(self, query: dict[str, list[str]]) -> str:
        records = self.service.list_outreach_queue_records(limit=100)
        requested_status = self._selected_filter(query, "status")
        requested_search = self._selected_filter(query, "q")
        filtered = self._apply_record_filters(
            records,
            requested_status,
            requested_search,
            lambda record: [
                record.company_name,
                record.contact_name,
                record.contact_role,
                record.target_country,
                record.sales_motion,
                record.primary_module,
                record.bundle_label,
                record.lead_reference,
                record.notes,
            ],
        )
        ordered = sorted(
            filtered,
            key=lambda record: (
                self._status_rank(
                    record.status,
                    ["Ready to send", "Approved", "Hold", "Sent"],
                ),
                self._priority_rank(record.priority),
                (record.company_name or record.lead_reference).lower(),
            ),
        )
        rows = "".join(self._queue_card(record) for record in ordered) or (
            "<p class='muted'>No Outreach Queue rows match the current filters.</p>"
        )
        status_counts = self._summarize_statuses(records)
        body = (
            self._warning_banner()
            + self._flash_banner(self._flash_message(query))
            + self._page_header(
                "Outreach Queue",
                "Approve the drafts you want to send, hold the rest, and mark sent after execution.",
                len(filtered),
                len(records),
            )
            + self._filter_toolbar(
                "/queue",
                requested_status,
                requested_search,
                status_counts,
                "Search company, buyer, country, module, or lead reference",
            )
            + "<section class='panel'><div class='panel-head'><h2>Outreach Queue</h2>"
            "<span class='muted'>Prioritize ready-to-send rows first. Keep weak or unclear drafts on hold instead of letting them drift into send actions.</span></div>"
            f"<div class='stack'>{rows}</div></section>"
        )
        return self._layout("Outreach Queue", "queue", body)

    def _render_runs(self, query: dict[str, list[str]]) -> str:
        records = self.service.list_sales_engine_runs(limit=50)
        requested_status = self._selected_filter(query, "status")
        requested_search = self._selected_filter(query, "q")
        filtered = self._apply_record_filters(
            records,
            requested_status,
            requested_search,
            lambda record: [
                record.run_marker,
                record.status,
                record.run_mode,
                record.triggered_by,
                record.error_summary,
                record.notes,
            ],
        )
        ordered = sorted(
            filtered,
            key=lambda record: (
                self._status_rank(record.status, ["Failed", "Running", "Completed"]),
                record.started_at,
            ),
            reverse=True,
        )
        rows = "".join(self._run_row(record) for record in ordered) or (
            "<p class='muted'>No Sales Engine Runs rows match the current filters.</p>"
        )
        status_counts = self._summarize_statuses(records)
        body = (
            self._warning_banner()
            + self._flash_banner(self._flash_message(query))
            + self._page_header(
                "Sales Engine Runs",
                "Track daily health, counts, and failure signals.",
                len(filtered),
                len(records),
            )
            + self._filter_toolbar(
                "/runs",
                requested_status,
                requested_search,
                status_counts,
                "Search run marker, mode, trigger, or error summary",
            )
            + "<section class='panel'><div class='panel-head'><h2>Sales Engine Runs</h2>"
            "<span class='muted'>Use failures and low-output runs as the main operational signals, not just total counts.</span></div>"
            f"<div class='stack'>{rows}</div></section>"
        )
        return self._layout("Run Monitor", "runs", body)

    def _render_accounts(self, query: dict[str, list[str]]) -> str:
        """Render aggregated account/buyer view across discovery, intake, and queue."""
        discovery_records = self.service.list_discovery_records(limit=200)
        intake_records = self.service.list_intake_records(limit=200)
        queue_records = self.service.list_outreach_queue_records(limit=200)
        
        # Aggregate by company name
        accounts: dict[str, dict] = {}
        
        for record in discovery_records:
            company = record.company_name or "Unknown Company"
            if company not in accounts:
                accounts[company] = {
                    "company": company,
                    "country": record.company_country or record.target_country_hint,
                    "discovery_count": 0,
                    "intake_count": 0,
                    "queue_count": 0,
                    "buyers": set(),
                    "statuses": set(),
                }
            accounts[company]["discovery_count"] += 1
            if record.contact_name:
                accounts[company]["buyers"].add(f"{record.contact_name} ({record.contact_role or 'Unknown'})")
            if record.status:
                accounts[company]["statuses"].add(record.status)
        
        for record in intake_records:
            company = record.company_name or "Unknown Company"
            if company not in accounts:
                accounts[company] = {
                    "company": company,
                    "country": record.target_country or record.company_country,
                    "discovery_count": 0,
                    "intake_count": 0,
                    "queue_count": 0,
                    "buyers": set(),
                    "statuses": set(),
                }
            accounts[company]["intake_count"] += 1
            if record.contact_name:
                accounts[company]["buyers"].add(f"{record.contact_name} ({record.contact_role or 'Unknown'})")
        
        for record in queue_records:
            company = record.company_name or "Unknown Company"
            if company not in accounts:
                accounts[company] = {
                    "company": company,
                    "country": record.target_country,
                    "discovery_count": 0,
                    "intake_count": 0,
                    "queue_count": 0,
                    "buyers": set(),
                    "statuses": set(),
                }
            accounts[company]["queue_count"] += 1
            if record.contact_name:
                accounts[company]["buyers"].add(f"{record.contact_name} ({record.contact_role or 'Unknown'})")
        
        # Sort by activity
        sorted_accounts = sorted(
            accounts.values(),
            key=lambda a: (-(a["discovery_count"] + a["intake_count"] + a["queue_count"]), a["company"].lower()),
        )
        
        # Render as dense table or cards
        rows = "".join(self._account_card(account) for account in sorted_accounts) or (
            "<p class='muted'>No account records found.</p>"
        )
        
        body = (
            self._warning_banner()
            + self._flash_banner(self._flash_message(query))
            + self._page_header(
                "Accounts & Buyers",
                "Aggregated view of companies, contacts, and activity across discovery, intake, and outreach.",
                len(sorted_accounts),
                len(sorted_accounts),
            )
            + "<section class='panel'><div class='panel-head'><h2>Active Accounts</h2>"
            "<span class='muted'>Companies with identified buyers and cross-pipeline activity.</span></div>"
            f"<div class='stack'>{rows}</div></section>"
        )
        return self._layout("Accounts & Buyers", "accounts", body)

    def _render_help(self, query: dict[str, list[str]]) -> str:
        """Render keyboard shortcuts and help documentation."""
        body = (
            self._warning_banner()
            + "<section class='page-intro'>"
            "<div><p class='eyebrow'>Operator Help</p><h1>Keyboard Shortcuts & Guide</h1>"
            "<p>Use keyboard shortcuts to move faster through the operator console.</p></div>"
            "</section>"
            "<section class='keyboard-help'>"
            "<div class='kb-section'>"
            "<h3>Navigation</h3>"
            "<ul class='kb-list'>"
            "<li><span class='kb-key'>G</span><span class='kb-description'>Dashboard</span></li>"
            "<li><span class='kb-key'>D</span><span class='kb-description'>Lead Discovery</span></li>"
            "<li><span class='kb-key'>I</span><span class='kb-description'>Lead Intake</span></li>"
            "<li><span class='kb-key'>A</span><span class='kb-description'>Accounts & Buyers</span></li>"
            "<li><span class='kb-key'>Q</span><span class='kb-description'>Outreach Queue (Approval)</span></li>"
            "<li><span class='kb-key'>R</span><span class='kb-description'>Run Monitor</span></li>"
            "<li><span class='kb-key'>?</span><span class='kb-description'>This Help Page</span></li>"
            "</ul>"
            "</div>"
            "<div class='kb-section'>"
            "<h3>Queue Actions (Shift + Letter)</h3>"
            "<ul class='kb-list'>"
            "<li><span class='kb-key'>Shift+A</span><span class='kb-description'>Approve outreach draft</span></li>"
            "<li><span class='kb-key'>Shift+H</span><span class='kb-description'>Hold (keep out of send)</span></li>"
            "<li><span class='kb-key'>Shift+S</span><span class='kb-description'>Mark Sent</span></li>"
            "<li><span class='kb-key'>Shift+G</span><span class='kb-description'>Regenerate draft</span></li>"
            "</ul>"
            "</div>"
            "<div class='kb-section'>"
            "<h3>Filtering & Search</h3>"
            "<ul class='kb-list'>"
            "<li><span class='kb-key'>Ctrl/Cmd+K</span><span class='kb-description'>Focus search box</span></li>"
            "<li>Click status chips to filter</li>"
            "<li>Type multiple words to AND them together</li>"
            "<li>Use 'Reset' to clear all filters</li>"
            "</ul>"
            "</div>"
            "<div class='kb-section'>"
            "<h3>View Modes</h3>"
            "<ul class='kb-list'>"
            "<li><strong>Card View</strong> – Full details for each record</li>"
            "<li><strong>Table View</strong> – Dense, compact view for power users</li>"
            "<li>Preference is saved in browser</li>"
            "</ul>"
            "</div>"
            "<div class='kb-section'>"
            "<h3>Tips for Power Users</h3>"
            "<ul class='kb-list'>"
            "<li>Use keyboard navigation to move through queues faster</li>"
            "<li>Switch to table view for high-volume review sessions</li>"
            "<li>Use Accounts view to spot patterns across pipeline</li>"
            "<li>Check Run Monitor for system health signals</li>"
            "</ul>"
            "</div>"
            "</section>"
        )
        return self._layout("Help & Shortcuts", "help", body)

    def _handle_queue_status(self, start_response, environ):
        size = int(environ.get("CONTENT_LENGTH") or "0")
        payload = environ["wsgi.input"].read(size).decode("utf-8")
        form = parse_qs(payload)
        lead_reference = form.get("lead_reference", [""])[0]
        status = form.get("status", [""])[0]

        if not lead_reference or not status:
            location = "/queue?" + urlencode(
                {"flash": "Missing lead reference or queue status."}
            )
            start_response("303 See Other", [("Location", location)])
            return [b""]

        self.service.update_outreach_queue_status(lead_reference, status)
        location = "/queue?" + urlencode(
            {"flash": f"Updated {lead_reference} to {status}."}
        )
        start_response("303 See Other", [("Location", location)])
        return [b""]

    def _layout(self, title: str, active: str, body: str) -> str:
        nav_items = [
            ("dashboard", "/", "Dashboard"),
            ("discovery", "/discovery", "Discovery"),
            ("intake", "/intake", "Intake"),
            ("accounts", "/accounts", "Accounts"),
            ("queue", "/queue", "Outreach Queue"),
            ("runs", "/runs", "Run Monitor"),
        ]
        nav_html = "".join(
            f"<a class='nav-link{' active' if key == active else ''}' href='{href}'>{label}</a>"
            for key, href, label in nav_items
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | Global Kinect Sales Console</title>
  <style>
    :root {{
      --bg: #f4efe3;
      --bg-panel: rgba(255,255,255,0.78);
      --ink: #1c2b2d;
      --muted: #66766e;
      --accent: #0f6b5b;
      --accent-soft: #d9efe5;
      --warm: #b45f2d;
      --line: rgba(28,43,45,0.12);
      --shadow: 0 18px 45px rgba(40,50,45,0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(180,95,45,0.18), transparent 28rem),
        radial-gradient(circle at top right, rgba(15,107,91,0.16), transparent 24rem),
        linear-gradient(180deg, #f7f1e7 0%, #efe6d6 100%);
      min-height: 100vh;
    }}
    .shell {{ max-width: 1240px; margin: 0 auto; padding: 24px 18px 48px; }}
    a {{ color: inherit; }}
    .topbar {{
      display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between;
      margin-bottom: 20px;
    }}
    .brand-wrap {{ display: grid; gap: 4px; }}
    .brand {{ font-family: Georgia, "Times New Roman", serif; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.03em; }}
    .brand-note {{ color: var(--muted); font-size: 0.95rem; }}
    .nav {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .nav-link {{
      text-decoration: none; color: var(--ink); padding: 10px 14px; border-radius: 999px;
      background: rgba(255,255,255,0.6); border: 1px solid var(--line);
    }}
    .nav-link.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .hero, .panel, .metric-card {{
      background: var(--bg-panel);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255,255,255,0.55);
      box-shadow: var(--shadow);
    }}
    .hero {{ border-radius: 30px; padding: 24px; display: grid; grid-template-columns: 1.4fr 1fr; gap: 22px; margin-bottom: 18px; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.16em; color: var(--warm); font-size: 0.77rem; margin: 0 0 8px; }}
    h1, h2, h3 {{ margin: 0; font-family: Georgia, "Times New Roman", serif; }}
    h1 {{ font-size: clamp(2rem, 3.4vw, 3.1rem); line-height: 1.04; }}
    h2 {{ font-size: 1.55rem; }}
    h3 {{ font-size: 1.1rem; }}
    .hero-copy, .muted, .flash, .warning {{ color: var(--muted); }}
    .hero-copy {{ max-width: 46rem; line-height: 1.6; }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .hero-link {{
      display: inline-flex; align-items: center; justify-content: center; text-decoration: none;
      color: #fff; background: var(--accent); padding: 11px 16px; border-radius: 999px;
      font-weight: 700; border: 1px solid var(--accent);
    }}
    .hero-link.ghost {{ background: rgba(255,255,255,0.7); color: var(--ink); border-color: var(--line); }}
    .hero-accent {{ display: flex; flex-wrap: wrap; gap: 10px; align-content: start; justify-content: flex-start; }}
    .metric-pill {{
      background: rgba(15,107,91,0.08);
      color: var(--accent);
      border: 1px solid rgba(15,107,91,0.18);
      padding: 10px 12px;
      border-radius: 999px;
      font-weight: 600;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .metric-card {{ border-radius: var(--radius); padding: 18px; }}
    .metric-card .value {{ font-size: 2rem; font-weight: 700; margin: 10px 0 4px; }}
    .metric-card p {{ margin: 0; line-height: 1.45; color: var(--muted); }}
    .focus-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .focus-card {{
      background: rgba(255,255,255,0.74);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .focus-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 8px; }}
    .focus-value {{ font-size: 2rem; font-weight: 700; }}
    .focus-card p {{ margin: 0 0 14px; color: var(--muted); line-height: 1.45; }}
    .focus-link {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    .panel-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .panel {{ border-radius: var(--radius); padding: 18px; margin-bottom: 16px; }}
    .panel-head {{ display: flex; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; }}
    .panel-head a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
    .page-intro {{
      display: flex; gap: 18px; align-items: flex-end; justify-content: space-between;
      margin-bottom: 14px; flex-wrap: wrap;
    }}
    .page-intro p {{ margin: 6px 0 0; color: var(--muted); max-width: 44rem; line-height: 1.55; }}
    .page-kpi {{
      min-width: 170px; padding: 14px 16px; border-radius: 18px; background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
    }}
    .page-kpi .label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .page-kpi .value {{ font-size: 1.7rem; font-weight: 700; margin-top: 6px; }}
    .toolbar {{
      display: grid; gap: 12px; padding: 16px; border-radius: 18px; margin-bottom: 16px;
      background: rgba(255,255,255,0.74); border: 1px solid var(--line); box-shadow: var(--shadow);
    }}
    .toolbar-row {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }}
    .toolbar-form {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .toolbar input, .toolbar select {{
      border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; min-height: 42px;
      background: rgba(255,255,255,0.85); color: var(--ink); min-width: 200px;
    }}
    .chip-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      display: inline-flex; align-items: center; gap: 8px;
      text-decoration: none; color: var(--ink); padding: 8px 12px; border-radius: 999px;
      border: 1px solid var(--line); background: rgba(255,255,255,0.7); font-weight: 600; font-size: 0.92rem;
    }}
    .chip.active {{ background: rgba(15,107,91,0.12); color: var(--accent); border-color: rgba(15,107,91,0.2); }}
    .chip-count {{ color: var(--muted); font-weight: 700; }}
    .stack {{ display: grid; gap: 12px; }}
    .row-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: rgba(255,255,255,0.68);
    }}
    .row-top {{
      display: flex; gap: 10px; align-items: start; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap;
    }}
    .row-title {{ display: grid; gap: 6px; }}
    .subtle {{ color: var(--muted); font-size: 0.94rem; }}
    .section-label {{
      color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; margin: 12px 0 8px;
    }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 12px; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 10px; border-radius: 999px; font-size: 0.86rem; font-weight: 600;
      border: 1px solid rgba(28,43,45,0.08); background: rgba(255,255,255,0.72);
    }}
    .badge.status {{ background: rgba(15,107,91,0.09); color: var(--accent); }}
    .badge.warn {{ background: rgba(180,95,45,0.1); color: var(--warm); }}
    .badge.dark {{ background: rgba(28,43,45,0.08); color: var(--ink); }}
    .pair-grid {{
      display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      margin: 10px 0 12px;
    }}
    .pair {{ padding: 10px 12px; border-radius: 14px; background: rgba(15,107,91,0.04); }}
    .pair dt {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }}
    .pair dd {{ margin: 0; font-weight: 600; }}
    details {{ border-top: 1px solid var(--line); padding-top: 12px; }}
    summary {{ cursor: pointer; font-weight: 600; color: var(--accent); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .btn {{
      appearance: none; border: none; cursor: pointer; border-radius: 999px;
      padding: 10px 14px; font-weight: 700;
    }}
    .btn-primary {{ background: var(--accent); color: #fff; }}
    .btn-secondary {{ background: rgba(28,43,45,0.08); color: var(--ink); }}
    .btn-warm {{ background: rgba(180,95,45,0.12); color: var(--warm); }}
    .flash, .warning {{
      border-radius: 16px; padding: 14px 16px; margin-bottom: 16px;
      border: 1px solid var(--line); background: rgba(255,255,255,0.64);
    }}
    .warning {{ color: #7b3d1e; background: rgba(180,95,45,0.1); }}
    .action-list {{ margin: 0; padding-left: 20px; line-height: 1.7; }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 840px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .toolbar-form {{ width: 100%; }}
      .toolbar input, .toolbar select {{ width: 100%; min-width: 0; }}
    }}
    .view-toggle {{
      display: flex; gap: 6px; align-items: center;
    }}
    .view-toggle button {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--line);
      background: rgba(255,255,255,0.7); color: var(--ink); cursor: pointer;
      font-weight: 600; font-size: 0.85rem; transition: background 0.2s;
    }}
    .view-toggle button.active {{
      background: rgba(15,107,91,0.12); color: var(--accent); border-color: rgba(15,107,91,0.2);
    }}
    .view-toggle button:hover {{
      background: rgba(255,255,255,0.85);
    }}
    .compact-table {{
      width: 100%; border-collapse: collapse; font-size: 0.92rem;
    }}
    .compact-table thead {{
      background: rgba(15,107,91,0.06); border-bottom: 2px solid var(--line);
    }}
    .compact-table th {{
      text-align: left; padding: 12px; font-weight: 700; color: var(--ink);
    }}
    .compact-table td {{
      padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.5);
    }}
    .compact-table tbody tr:hover {{
      background: rgba(15,107,91,0.04);
    }}
    .compact-table .status {{ font-weight: 600; }}
    .compact-table .actions {{
      display: flex; gap: 4px; flex-wrap: nowrap;
    }}
    .compact-table .actions form {{
      display: inline;
    }}
    .compact-table .btn {{
      padding: 6px 8px; font-size: 0.8rem;
    }}
    .keyboard-hint {{
      display: inline-block; margin-left: 6px; padding: 2px 6px;
      background: rgba(28,43,45,0.08); border-radius: 4px; font-size: 0.75rem;
      color: var(--muted); font-family: monospace;
    }}
    .keyboard-help {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;
    }}
    .kb-section {{
      background: rgba(255,255,255,0.72); border: 1px solid var(--line);
      border-radius: 14px; padding: 16px;
    }}
    .kb-section h3 {{ margin-top: 0; }}
    .kb-list {{
      margin: 0; padding: 0; list-style: none;
    }}
    .kb-list li {{
      display: flex; justify-content: space-between; gap: 12px; padding: 8px 0;
      border-bottom: 1px solid rgba(255,255,255,0.4);
    }}
    .kb-list li:last-child {{
      border-bottom: none;
    }}
    .kb-key {{
      display: inline-block; padding: 2px 8px; background: rgba(28,43,45,0.12);
      border-radius: 4px; font-family: monospace; white-space: nowrap; font-weight: 600;
    }}
    .kb-description {{
      color: var(--muted); flex: 1;
    }}
  </style>
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
      // Navigation shortcuts
      const shortcuts = {{
        'g': '/',
        'd': '/discovery',
        'i': '/intake',
        'a': '/accounts',
        'q': '/queue',
        'r': '/runs',
        '?': '/help',
      }};
      
      const actionShortcuts = {{
        'A': 'approve',
        'H': 'hold',
        'S': 'sent',
        'G': 'regenerate',
      }};
      
      document.addEventListener('keydown', function(e) {{
        // Ignore if user is typing in input
        if (e.target.matches('input, textarea, select')) return;
        
        const char = e.key.toLowerCase();
        
        // Navigation shortcuts (Ctrl/Cmd + optional)
        if (e.ctrlKey || e.metaKey) {{
          if (char === 'k') {{ e.preventDefault(); event_show_search(); }}
        }}
        
        // Direct navigation
        if (shortcuts[char]) {{
          e.preventDefault();
          window.location.href = shortcuts[char];
        }}
        
        // Action shortcuts  (Shift + letter)
        if (e.shiftKey && actionShortcuts[e.key]) {{
          e.preventDefault();
          trigger_action(actionShortcuts[e.key]);
        }}
      }});
      
      // Add view toggle listener if available
      const cardViewBtn = document.getElementById('view-card');
      const tableViewBtn = document.getElementById('view-table');
      
      if (cardViewBtn && tableViewBtn) {{
        const savedView = localStorage.getItem('preferred-view') || 'card';
        apply_view(savedView);
        
        cardViewBtn.addEventListener('click', () => {{ apply_view('card'); }});
        tableViewBtn.addEventListener('click', () => {{ apply_view('table'); }});
      }}
    }});
    
    function apply_view(view_type) {{
      localStorage.setItem('preferred-view', view_type);
      document.querySelectorAll('[data-view]').forEach(el => {{
        el.style.display = el.getAttribute('data-view') === view_type ? '' : 'none';
      }});
      
      const cardViewBtn = document.getElementById('view-card');
      const tableViewBtn = document.getElementById('view-table');
      if (cardViewBtn && tableViewBtn) {{
        if (view_type === 'card') {{
          cardViewBtn.classList.add('active');
          tableViewBtn.classList.remove('active');
        }} else {{
          tableViewBtn.classList.add('active');
          cardViewBtn.classList.remove('active');
        }}
      }}
    }}
    
    function trigger_action(action) {{
      // Find the first visible button matching the action
      const buttons = document.querySelectorAll('button');
      for (let btn of buttons) {{
        if (btn.textContent.toLowerCase().includes(action.toLowerCase()) && btn.offsetParent !== null) {{
          btn.click();
          return;
        }}
      }}
    }}
    
    function event_show_search() {{
      const searchInput = document.querySelector('input[type="search"]');
      if (searchInput) {{
        searchInput.focus();
        searchInput.select();
      }}
    }}
  </script>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand-wrap">
        <div class="brand">Global Kinect Operator Console</div>
        <div class="brand-note">Decision-first workspace for discovery, outreach, and run monitoring.</div>
      </div>
      <nav class="nav">{nav_html}</nav>
    </header>
    {body}
  </div>
</body>
</html>"""

    def _metric_card(self, label: str, value: int, caption: str) -> str:
        return (
            "<article class='metric-card'>"
            f"<div class='muted'>{escape(label)}</div>"
            f"<div class='value'>{value}</div>"
            f"<p>{escape(caption)}</p>"
            "</article>"
        )

    def _focus_row(
        self,
        label: str,
        value: int,
        caption: str,
        href: str,
        action_label: str,
    ) -> str:
        return (
            "<article class='focus-card'>"
            "<div class='focus-top'>"
            f"<div><div class='subtle'>{escape(label)}</div><div class='focus-value'>{value}</div></div>"
            f"{self._status_badge('Needs review' if value else 'Clear')}"
            "</div>"
            f"<p>{escape(caption)}</p>"
            f"<a class='focus-link' href='{escape(href, quote=True)}'>{escape(action_label)}</a>"
            "</article>"
        )

    def _page_header(
        self,
        title: str,
        description: str,
        visible_count: int,
        total_count: int,
    ) -> str:
        return (
            "<section class='page-intro'>"
            "<div>"
            f"<p class='eyebrow'>Operator Workspace</p><h1>{escape(title)}</h1>"
            f"<p>{escape(description)}</p>"
            "</div>"
            "<div class='page-kpi'>"
            "<div class='label'>Visible Rows</div>"
            f"<div class='value'>{visible_count}</div>"
            f"<div class='subtle'>of {total_count} total</div>"
            "</div>"
            "</section>"
        )

    def _filter_toolbar(
        self,
        path: str,
        selected_status: str | None,
        search_text: str | None,
        status_counts: list[tuple[str, int]],
        search_placeholder: str,
    ) -> str:
        normalized_selected = self._normalize(selected_status)
        search_value = escape(search_text or "", quote=True)
        chips = [
            self._filter_chip(path, None, search_text, "All statuses", sum(count for _, count in status_counts), not normalized_selected)
        ]
        chips.extend(
            self._filter_chip(
                path,
                status,
                search_text,
                status,
                count,
                self._normalize(status) == normalized_selected,
            )
            for status, count in status_counts
        )
        reset_href = escape(path, quote=True)
        return (
            "<section class='toolbar'>"
            "<div class='toolbar-row'>"
            "<form class='toolbar-form' method='get'>"
            f"<input type='search' name='q' placeholder='{escape(search_placeholder, quote=True)}' value='{search_value}'>"
            "<button class='btn btn-primary' type='submit'>Apply</button>"
            f"<a class='chip' href='{reset_href}'>Reset</a>"
            "</form>"
            "<div class='view-toggle'>"
            "<button id='view-card' type='button' title='Card view (Ctrl+1)' class='active'>Cards</button>"
            "<button id='view-table' type='button' title='Table view (Ctrl+2)'>Table</button>"
            "</div>"
            f"<a class='chip' href='/help' title='Keyboard shortcuts (Press ?)'>Help</a>"
            "</div>"
            f"<div class='chip-row'>{''.join(chips)}</div>"
            "</section>"
        )

    def _filter_chip(
        self,
        path: str,
        status: str | None,
        search_text: str | None,
        label: str,
        count: int,
        active: bool,
    ) -> str:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if search_text:
            params["q"] = search_text
        href = path if not params else f"{path}?{urlencode(params)}"
        return (
            f"<a class='chip{' active' if active else ''}' href='{escape(href, quote=True)}'>"
            f"{escape(label)} <span class='chip-count'>{count}</span>"
            "</a>"
        )

    def _discovery_card(self, record: LeadDiscoveryRecord) -> str:
        return (
            "<article class='row-card'>"
            "<div class='row-top'>"
            f"<div class='row-title'><h3>{escape(record.company_name)}</h3><p class='muted'>{escape(record.contact_name or 'Unknown contact')}</p></div>"
            f"{self._status_badge(record.status)}"
            "</div>"
            f"{self._meta_badges([record.lane_label, record.agent_label, record.service_focus, record.target_country_hint, record.source_type])}"
            f"{self._pair_grid([('Role', record.contact_role), ('Buyer Confidence', self._display_value(record.buyer_confidence)), ('Company Country', record.company_country), ('Trust Score', self._display_value(record.source_trust_score)), ('Source Priority', self._display_value(record.source_priority))])}"
            f"{self._text_block('Account Fit', record.account_fit_summary)}"
            f"{self._text_block('Evidence', record.evidence)}"
            f"{self._text_block('Notes', record.notes)}"
            f"{self._link_row(record.source_url, record.website_url)}"
            "</article>"
        )

    def _intake_card(self, record: LeadIntakeRecord) -> str:
        return (
            "<article class='row-card'>"
            "<div class='row-top'>"
            f"<div class='row-title'><h3>{escape(record.company_name)}</h3><p class='muted'>{escape(record.contact_name or 'Unknown contact')}</p></div>"
            f"{self._status_badge(record.status)}"
            "</div>"
            f"{self._meta_badges([record.lane_label, record.target_country, record.lead_type_hint, record.company_country])}"
            f"{self._pair_grid([('Role', record.contact_role), ('Buyer Confidence', self._display_value(record.buyer_confidence)), ('Email', record.email), ('LinkedIn', record.linkedin_url)])}"
            f"{self._text_block('Account Fit', record.account_fit_summary)}"
            f"{self._text_block('Campaign', record.campaign)}"
            f"{self._text_block('Notes', record.notes)}"
            "</article>"
        )

    def _queue_card(self, record: OutreachQueueRecord) -> str:
        actions = "".join(
            self._queue_action_button(record.lead_reference, status, label, button_class)
            for status, label, button_class in [
                ("Approved", "Approve", "btn-primary"),
                ("Hold", "Hold", "btn-secondary"),
                ("Regenerate", "Regenerate", "btn-warm"),
                ("Sent", "Mark Sent", "btn-primary"),
            ]
        )
        return (
            "<article class='row-card'>"
            "<div class='row-top'>"
            f"<div class='row-title'><h3>{escape(record.company_name or record.lead_reference)}</h3><p class='muted'>{escape(record.contact_name or 'Unknown contact')}</p></div>"
            f"{self._status_badge(record.status)}"
            "</div>"
            f"{self._meta_badges([record.priority, record.target_country, record.sales_motion, record.primary_module, record.bundle_label])}"
            f"{self._pair_grid([('Lead Reference', record.lead_reference), ('Role', record.contact_role), ('Run Marker', record.run_marker), ('Generated At', record.generated_at)])}"
            f"{self._details_block('Prospect reply', record.reply)}"
            f"{self._text_block('Email Subject', record.email_subject)}"
            f"{self._details_block('Email Message', record.email_message)}"
            f"{self._details_block('LinkedIn Message', record.linkedin_message)}"
            f"{self._details_block('Follow-Up Message', record.follow_up_message)}"
            f"{self._text_block('Notes', record.notes)}"
            f"<div class='actions'>{actions}</div>"
            "</article>"
        )

    def _account_card(self, account: dict) -> str:
        """Render a summary card for an account with aggregated activity."""
        total_activity = account["discovery_count"] + account["intake_count"] + account["queue_count"]
        buyers_html = "<ul class='action-list'>" + "".join(
            f"<li>{escape(buyer)}</li>"
            for buyer in sorted(account["buyers"])
        ) + "</ul>" if account["buyers"] else "<p class='muted'>No buyers identified yet.</p>"
        
        return (
            "<article class='row-card'>"
            "<div class='row-top'>"
            f"<div class='row-title'><h3>{escape(account['company'])}</h3><p class='muted'>{escape(account['country'] or 'Unknown country')}</p></div>"
            "</div>"
            f"{self._pair_grid([('Total Activity', total_activity), ('Discovery', account['discovery_count']), ('Intake', account['intake_count']), ('Queue', account['queue_count'])])}"
            f"<div class='pair'><dt>Identified Buyers</dt><dd>{buyers_html}</dd></div>"
            f"{self._meta_badges(sorted(account['statuses']))}"
            "<div class='actions'>"
            f"<a class='nav-link' href='/discovery?q={escape(account['company'], quote=True)}'>View Discovery</a>"
            f"<a class='nav-link' href='/intake?q={escape(account['company'], quote=True)}'>View Intake</a>"
            f"<a class='nav-link' href='/queue?q={escape(account['company'], quote=True)}'>View Queue</a>"
            "</div>"
            "</article>"
        )

    def _run_row(self, record: SalesEngineRunRecord, compact: bool = False) -> str:
        body = (
            "<article class='row-card'>"
            "<div class='row-top'>"
            f"<div class='row-title'><h3>{escape(record.run_marker)}</h3><p class='muted'>{escape(record.started_at)}</p></div>"
            f"{self._status_badge(record.status)}"
            "</div>"
            f"{self._meta_badges([record.run_mode, record.triggered_by])}"
            f"{self._pair_grid([('Completed At', record.completed_at), ('Leads', self._display_value(record.lead_count)), ('Outreach', self._display_value(record.outreach_count)), ('Pipeline', self._display_value(record.pipeline_count)), ('Tasks', self._display_value(record.task_count))])}"
        )
        if not compact:
            body += self._text_block("Error Summary", record.error_summary)
            body += self._text_block("Notes", record.notes)
        return body + "</article>"

    def _queue_action_button(
        self,
        lead_reference: str,
        status: str,
        label: str,
        button_class: str,
    ) -> str:
        shortcut_hints = {
            "Approve": "(Shift+A)",
            "Hold": "(Shift+H)",
            "Mark Sent": "(Shift+S)",
            "Regenerate": "(Shift+G)",
        }
        hint = shortcut_hints.get(label, "")
        return (
            "<form method='post' action='/queue/status'>"
            f"<input type='hidden' name='lead_reference' value='{escape(lead_reference, quote=True)}'>"
            f"<input type='hidden' name='status' value='{escape(status, quote=True)}'>"
            f"<button class='btn {button_class}' type='submit' title='{hint}'>"
            f"{escape(label)}"
            f"{f'<span class=\"keyboard-hint\">{hint}</span>' if hint else ''}"
            "</button>"
            "</form>"
        )

    def _status_badge(self, status: str | None) -> str:
        normalized = self._normalize(status)
        badge_class = "status"
        if normalized in {"failed", "error", "hold", "rejected"}:
            badge_class = "warn"
        elif normalized in {"sent", "completed", "promoted"}:
            badge_class = "dark"
        label = status or "Unknown"
        return f"<span class='badge {badge_class}'>{escape(label)}</span>"

    def _meta_badges(self, values: list[str | None]) -> str:
        items = [value for value in values if value]
        if not items:
            return ""
        return "<div class='meta'>" + "".join(
            f"<span class='badge'>{escape(value)}</span>"
            for value in items
        ) + "</div>"

    def _pair_grid(self, items: list[tuple[str, str | int | None]]) -> str:
        usable = [(label, value) for label, value in items if value not in (None, "")]
        if not usable:
            return ""
        return "<dl class='pair-grid'>" + "".join(
            f"<div class='pair'><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd></div>"
            for label, value in usable
        ) + "</dl>"

    def _text_block(self, label: str, value: str | None) -> str:
        if not value:
            return ""
        return (
            f"<div class='pair'><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        )

    def _details_block(self, label: str, value: str | None) -> str:
        if not value:
            return ""
        return (
            "<details>"
            f"<summary>{escape(label)}</summary>"
            f"<p>{escape(value)}</p>"
            "</details>"
        )

    def _link_row(self, source_url: str | None, website_url: str | None) -> str:
        links = []
        if source_url:
            links.append(
                f"<a class='nav-link' href='{escape(source_url, quote=True)}' target='_blank' rel='noreferrer'>Source URL</a>"
            )
        if website_url:
            links.append(
                f"<a class='nav-link' href='{escape(website_url, quote=True)}' target='_blank' rel='noreferrer'>Website</a>"
            )
        if not links:
            return ""
        return "<div class='actions'>" + "".join(links) + "</div>"

    def _warning_banner(self) -> str:
        if self.service.is_configured():
            return ""
        return (
            "<div class='warning'>"
            f"{escape(self.service.configuration_error())}"
            "</div>"
        )

    def _flash_banner(self, flash: str | None) -> str:
        if not flash:
            return ""
        return f"<div class='flash'>{escape(flash)}</div>"

    def _flash_message(self, query: dict[str, list[str]]) -> str | None:
        values = query.get("flash")
        if not values:
            return None
        return values[0]

    def _respond_html(self, start_response, html: str, status: str = "200 OK"):
        start_response(status, [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]

    def _respond_text(self, start_response, text: str, status: str = "200 OK"):
        start_response(status, [("Content-Type", "text/plain; charset=utf-8")])
        return [text.encode("utf-8")]

    def _count_statuses(self, statuses: list[str | None], wanted: set[str]) -> int:
        return sum(1 for status in statuses if self._normalize(status) in wanted)

    def _selected_filter(self, query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key)
        if not values:
            return None
        selected = values[0].strip()
        return selected or None

    def _apply_record_filters(
        self,
        records: list,
        selected_status: str | None,
        search_text: str | None,
        value_getter,
    ) -> list:
        normalized_status = self._normalize(selected_status)
        search_terms = [term.lower() for term in (search_text or "").split() if term.strip()]
        filtered = []
        for record in records:
            if normalized_status and self._normalize(getattr(record, "status", None)) != normalized_status:
                continue
            if search_terms:
                haystack = " ".join(
                    str(value).lower()
                    for value in value_getter(record)
                    if value not in (None, "")
                )
                if not all(term in haystack for term in search_terms):
                    continue
            filtered.append(record)
        return filtered

    def _summarize_statuses(self, records: list) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        labels: dict[str, str] = {}
        for record in records:
            label = getattr(record, "status", None) or "Unknown"
            normalized = self._normalize(label)
            counts[normalized] = counts.get(normalized, 0) + 1
            labels.setdefault(normalized, label)
        return sorted(
            ((labels[key], count) for key, count in counts.items()),
            key=lambda item: (-item[1], item[0].lower()),
        )

    def _status_rank(self, status: str | None, ordered_labels: list[str]) -> int:
        normalized = self._normalize(status)
        ordered = {self._normalize(label): index for index, label in enumerate(ordered_labels)}
        return ordered.get(normalized, len(ordered_labels))

    def _priority_rank(self, priority: str | None) -> int:
        ordered = {"high": 0, "medium": 1, "low": 2}
        return ordered.get(self._normalize(priority), 3)

    def _normalize(self, value: str | None) -> str:
        if not value:
            return ""
        return "".join(character for character in value.lower() if character.isalnum())

    def _display_value(self, value) -> str | None:
        if value in (None, ""):
            return None
        return str(value)


def run_operator_console() -> None:
    host = settings.OPERATOR_CONSOLE_HOST
    port = settings.OPERATOR_CONSOLE_PORT
    app = OperatorConsoleApp()
    with make_server(host, port, app) as server:
        logger.info("Operator console running at http://%s:%s", host, port)
        server.serve_forever()
