import argparse
import sys

from app.services.anthropic_service import AnthropicService
from app.services.notion_service import NotionService
from app.services.supabase_service import SupabaseService
from app.services.config import settings
from app.agents.discovery_source_collector_agent import DiscoverySourceCollectorAgent
from app.agents.opportunities_outreach_agent import OpportunitiesOutreachAgent
from app.agents.response_handler_agent import ResponseHandlerAgent
from app.agents.autonomous_lane_agent import AutonomousLaneAgent
from app.agents.lead_discovery_agent import LeadDiscoveryAgent
from app.agents.lead_feedback_agent import LeadFeedbackAgent
from app.agents.outreach_review_agent import OutreachReviewAgent
from app.agents.lead_research_agent import LeadResearchAgent
from app.agents.lead_scoring_agent import LeadScoringAgent
from app.agents.message_writer_agent import MessageWriterAgent
from app.agents.crm_updater_agent import CRMUpdaterAgent
from app.agents.solution_design_agent import SolutionDesignAgent
from app.agents.proposal_support_agent import ProposalSupportAgent
from app.agents.pipeline_intelligence_agent import PipelineIntelligenceAgent
from app.agents.lifecycle_agent import LifecycleAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.entity_mapper_agent import EntityMapperAgent
from app.agents.notion_sync_agent import NotionSyncAgent
from app.models.outreach_queue_item import OutreachQueueItem
from app.models.sales_engine_run import SalesEngineRun
from app.utils.logger import get_logger
from app.utils.time import utc_now, utc_now_iso

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting Global Kinect sales engine...")
    started_at = utc_now_iso()
    run_marker = _build_run_marker()
    campaign = "UK/EU companies hiring across the Gulf, Egypt, Lebanon, and Jordan"
    run_mode = _normalized_run_mode()
    triggered_by = settings.SALES_ENGINE_TRIGGERED_BY.strip() or "manual"

    anthropic_service = AnthropicService()
    supabase_service = SupabaseService()
    notion_service = NotionService()
    discovery_source_collector_agent = DiscoverySourceCollectorAgent(
        notion_service=notion_service,
    )
    autonomous_lane_agent = AutonomousLaneAgent(notion_service=notion_service)
    lead_discovery_agent = LeadDiscoveryAgent(
        notion_service=notion_service,
        anthropic_service=anthropic_service,
    )
    crm_updater_agent = CRMUpdaterAgent()
    pipeline_intelligence_agent = PipelineIntelligenceAgent()
    lead_feedback_agent = LeadFeedbackAgent(notion_service=notion_service)
    outreach_review_agent = OutreachReviewAgent(
        notion_service=notion_service,
        supabase_service=supabase_service,
        crm_updater_agent=crm_updater_agent,
        pipeline_intelligence_agent=pipeline_intelligence_agent,
    )
    lead_research_agent = LeadResearchAgent(
        notion_service=notion_service,
        anthropic_service=anthropic_service,
    )
    lead_scoring_agent = LeadScoringAgent()
    message_writer_agent = MessageWriterAgent()
    solution_design_agent = SolutionDesignAgent()
    proposal_support_agent = ProposalSupportAgent()
    lifecycle_agent = LifecycleAgent()
    execution_agent = ExecutionAgent()
    entity_mapper_agent = EntityMapperAgent()
    notion_sync_agent = NotionSyncAgent(notion_service)
    response_handler_agent = ResponseHandlerAgent(
        notion_service=notion_service,
        anthropic_service=anthropic_service,
        supabase_service=supabase_service,
        crm_updater_agent=crm_updater_agent,
    )

    logger.info(f"Anthropic configured: {anthropic_service.is_configured()}")
    logger.info(f"Sales engine run mode: {run_mode}")
    logger.info(
        f"Discovery source collection configured: {discovery_source_collector_agent.is_configured()}"
    )
    logger.info(f"Lead discovery configured: {lead_discovery_agent.is_configured()}")
    logger.info(f"Outreach review sync configured: {outreach_review_agent.is_configured()}")
    logger.info(
        f"Lead intake configured: {lead_research_agent.is_real_intake_configured()}"
    )
    logger.info(f"Supabase configured: {supabase_service.is_configured()}")
    logger.info(f"Notion configured: {notion_sync_agent.is_configured()}")

    run_record = SalesEngineRun(
        run_marker=run_marker,
        status="running",
        started_at=started_at,
        run_mode=run_mode,
        triggered_by=triggered_by,
        notes=f"Sales engine run started in {run_mode} mode.",
    )
    _sync_run_record(notion_service, run_record)

    leads = []
    scored_leads = []
    solution_recommendations = []
    pipeline_records = []
    outreach_messages = []
    outreach_queue_items = []
    execution_tasks = []
    deal_support_packages = []
    high_value_deals = []
    accounts = []
    buyers = []
    source_collection_result = None
    autonomous_lane_result = None
    discovery_result = None
    outreach_review_result = None
    feedback_index = None

    try:
        if run_mode == "live" and outreach_review_agent.is_configured():
            outreach_review_result = outreach_review_agent.sync_queue_decisions(limit=300)
            if outreach_review_result.reviewed_count:
                logger.info(
                    "Outreach review sync result: %s",
                    outreach_review_result.summary(),
                )
        elif run_mode != "live" and outreach_review_agent.is_configured():
            logger.info(
                "Shadow mode is active. Skipping outreach review sync because it updates live pipeline state."
            )

        feedback_index = lead_feedback_agent.collect_feedback_index(limit=300)

        if response_handler_agent.is_configured():
            response_result = response_handler_agent.process_replies(
                limit=50,
                shadow_mode=run_mode != "live",
            )
            if response_result.reviewed_count:
                logger.info("Response handler result: %s", response_result.summary())

        if discovery_source_collector_agent.is_configured():
            source_collection_result = (
                discovery_source_collector_agent.collect_into_discovery(
                    campaign=campaign,
                )
            )
            if source_collection_result.source_count:
                logger.info(
                    "Discovery source collection result: %s",
                    source_collection_result.summary(),
                )

        if autonomous_lane_agent.is_configured():
            autonomous_lane_result = autonomous_lane_agent.seed_internal_lanes(limit=100)
            if autonomous_lane_result.candidate_count:
                logger.info(
                    "Autonomous lane seeding result: %s",
                    autonomous_lane_result.summary(),
                )

        if lead_discovery_agent.is_configured():
            discovery_result = lead_discovery_agent.promote_discovery_records(
                campaign=campaign,
                max_records=25,
                feedback_index=feedback_index,
            )
            if discovery_result.fetched_count:
                logger.info(
                    "Discovery promotion result: %s",
                    discovery_result.summary(),
                )

        leads = lead_research_agent.collect_leads(
            campaign=campaign,
            max_records=25,
            mark_processed=run_mode != "shadow",
        )
        if not leads:
            logger.info("No leads were collected. Exiting without downstream processing.")
            completed_run = run_record.model_copy(
                update={
                    "status": "completed",
                    "completed_at": utc_now_iso(),
                    "notes": _build_run_notes(
                        (
                            "No ready lead intake records found."
                            if run_mode == "live"
                            else "Shadow mode found no ready lead intake records."
                        ),
                        outreach_review_result,
                        source_collection_result,
                        autonomous_lane_result,
                        discovery_result,
                    ),
                }
            )
            _sync_run_record(notion_service, completed_run)
            return

        scored_leads = lead_scoring_agent.score_leads(
            leads,
            feedback_index=feedback_index,
        )
        accounts = entity_mapper_agent.build_accounts(scored_leads)
        buyers = entity_mapper_agent.build_buyers(scored_leads)
        solution_recommendations = solution_design_agent.create_solution_recommendations(
            scored_leads,
        )
        pipeline_records = crm_updater_agent.create_pipeline_records_with_solution(
            scored_leads,
            solution_recommendations,
        )
        outreach_messages = message_writer_agent.generate_messages_with_solution(
            scored_leads,
            solution_recommendations,
        )
        pipeline_records = [
            crm_updater_agent.update_outreach_status(record, "drafted")
            for record in pipeline_records
        ]
        pipeline_records = pipeline_intelligence_agent.evaluate_pipeline(pipeline_records)
        pipeline_records = lifecycle_agent.evaluate_lifecycle(pipeline_records)
        high_value_deals = pipeline_intelligence_agent.flag_high_value_deals(
            pipeline_records,
        )
        execution_tasks = execution_agent.generate_tasks(pipeline_records)
        deal_support_packages = proposal_support_agent.create_deal_support_packages_with_solution(
            scored_leads,
            pipeline_records,
            solution_recommendations,
        )
        outreach_queue_items = _build_outreach_queue_items(
            scored_leads,
            outreach_messages,
            run_marker,
        )
        if run_mode == "live":
            _persist_generated_data(
                supabase_service,
                scored_leads,
                outreach_messages,
                pipeline_records,
                solution_recommendations,
                deal_support_packages,
                execution_tasks,
            )
            _sync_operating_views(
                notion_sync_agent,
                accounts,
                buyers,
                scored_leads,
                pipeline_records,
                solution_recommendations,
                execution_tasks,
                deal_support_packages,
            )
            _sync_outreach_queue(notion_service, outreach_queue_items)
        else:
            logger.info(
                "Shadow mode is active. Skipping Supabase persistence, Outreach Queue sync, and operating-view sync."
            )

        logger.info("Lead, outreach, pipeline, execution, solution, and deal-support output:")
        _print_demo_output(
            scored_leads,
            outreach_messages,
            pipeline_records,
            solution_recommendations,
            deal_support_packages,
            execution_tasks,
            high_value_deals,
        )

        completed_run = run_record.model_copy(
            update={
                "status": "completed",
                "completed_at": utc_now_iso(),
                "lead_count": len(scored_leads),
                "outreach_count": len(outreach_queue_items),
                "pipeline_count": len(pipeline_records),
                "task_count": len(execution_tasks),
                "notes": _build_run_notes(
                    (
                        "Run completed successfully and packaged outreach in Outreach Queue."
                        if run_mode == "live"
                        else "Shadow mode completed successfully. Discovery, qualification, and packaging logic ran without live sync."
                    ),
                    outreach_review_result,
                    source_collection_result,
                    autonomous_lane_result,
                    discovery_result,
                ),
            }
        )
        _sync_run_record(notion_service, completed_run)

        logger.info(
            "Lead research, scoring, messaging, pipeline tracking, solution design, "
            "pipeline intelligence, lifecycle evaluation, execution tasks, deal support, "
            "outreach packaging, and run logging ran successfully."
        )
    except Exception as exc:
        failed_run = run_record.model_copy(
            update={
                "status": "failed",
                "completed_at": utc_now_iso(),
                "lead_count": len(scored_leads),
                "outreach_count": len(outreach_queue_items),
                "pipeline_count": len(pipeline_records),
                "task_count": len(execution_tasks),
                "error_summary": str(exc),
                "notes": _build_run_notes(
                    "Run failed before completion.",
                    outreach_review_result,
                    source_collection_result,
                    autonomous_lane_result,
                    discovery_result,
                ),
            }
        )
        _sync_run_record(notion_service, failed_run)
        raise


def _persist_generated_data(
    supabase_service: SupabaseService,
    scored_leads,
    outreach_messages,
    pipeline_records,
    solution_recommendations,
    deal_support_packages,
    execution_tasks,
) -> None:
    if not supabase_service.is_configured():
        logger.info("Supabase is not configured. Skipping persistence.")
        return

    logger.info("Persisting generated records to Supabase.")
    supabase_service.insert_leads(scored_leads)
    supabase_service.insert_outreach_messages(outreach_messages)
    supabase_service.upsert_pipeline_records(pipeline_records)
    supabase_service.upsert_solution_recommendations(solution_recommendations)
    supabase_service.insert_deal_support_packages(deal_support_packages)
    supabase_service.insert_execution_tasks(execution_tasks)


def _sync_operating_views(
    notion_sync_agent: NotionSyncAgent,
    accounts,
    buyers,
    scored_leads,
    pipeline_records,
    solution_recommendations,
    execution_tasks,
    deal_support_packages,
) -> None:
    notion_sync_agent.sync_operating_views(
        accounts=accounts,
        buyers=buyers,
        leads=scored_leads,
        pipeline_records=pipeline_records,
        solution_recommendations=solution_recommendations,
        execution_tasks=execution_tasks,
        deal_support_packages=deal_support_packages,
    )


def _sync_outreach_queue(
    notion_service: NotionService,
    outreach_queue_items: list[OutreachQueueItem],
) -> None:
    if not notion_service.is_outreach_queue_configured():
        logger.info("Outreach Queue is not configured. Skipping outreach packaging sync.")
        return

    notion_service.upsert_outreach_queue_pages(outreach_queue_items)


def _sync_run_record(
    notion_service: NotionService,
    run_record: SalesEngineRun,
) -> None:
    if not notion_service.is_run_logging_configured():
        return

    try:
        notion_service.upsert_sales_engine_run_page(run_record)
    except Exception:
        logger.warning(
            "Failed to sync Sales Engine Runs record for %s.",
            run_record.run_marker,
        )


def _build_outreach_queue_items(
    scored_leads,
    outreach_messages,
    run_marker: str,
) -> list[OutreachQueueItem]:
    generated_at = utc_now_iso()
    return [
        OutreachQueueItem(
            lead_reference=message.lead_reference,
            company_name=message.company_name,
            company_canonical=lead.company_canonical,
            contact_name=message.contact_name,
            contact_role=message.contact_role,
            priority=lead.priority or "medium",
            target_country=message.target_country,
            sales_motion=message.sales_motion,
            primary_module=message.primary_module,
            bundle_label=message.bundle_label,
            email_subject=message.email_subject,
            email_message=message.email_message,
            linkedin_message=message.linkedin_message,
            follow_up_message=message.follow_up_message,
            generated_at=generated_at,
            run_marker=run_marker,
            notes=_compose_queue_notes(lead.feedback_summary),
        )
        for lead, message in zip(scored_leads, outreach_messages)
    ]


def _build_run_marker() -> str:
    return f"RUN_{utc_now().strftime('%Y%m%d%H%M%S')}"


def _normalized_run_mode() -> str:
    configured_mode = settings.SALES_ENGINE_RUN_MODE.strip().lower()
    if configured_mode in {"shadow", "live"}:
        return configured_mode
    return "live"


def _build_run_notes(
    base_note: str,
    outreach_review_result,
    source_collection_result,
    autonomous_lane_result,
    discovery_result,
) -> str:
    notes = [base_note]
    if outreach_review_result is not None:
        notes.append(f"Outreach review sync: {outreach_review_result.summary()}.")
    if source_collection_result is not None:
        notes.append(f"Source collection: {source_collection_result.summary()}.")
    if autonomous_lane_result is not None:
        notes.append(f"Autonomous lanes: {autonomous_lane_result.summary()}.")
    if discovery_result is not None:
        notes.append(f"Discovery: {discovery_result.summary()}.")
    return " ".join(notes)


def _compose_queue_notes(feedback_summary: str | None) -> str:
    notes = ["Packaged by the daily sales engine run and ready for operator review."]
    if feedback_summary:
        notes.append(feedback_summary)
    return "\n".join(notes)


def _print_demo_output(
    scored_leads,
    outreach_messages,
    pipeline_records,
    solution_recommendations,
    deal_support_packages,
    execution_tasks,
    high_value_deals,
) -> None:
    tasks_by_reference = {
        task.lead_reference: task
        for task in execution_tasks
    }
    high_value_references = {
        record.lead_reference
        for record in high_value_deals
    }

    for idx, (lead, message, record, recommendation, package) in enumerate(
        zip(
            scored_leads,
            outreach_messages,
            pipeline_records,
            solution_recommendations,
            deal_support_packages,
        ),
        start=1,
    ):
        print(f"\nLead {idx}")
        print(f"Reference: {message.lead_reference}")
        print(f"Company: {lead.company_name}")
        print(f"Contact: {lead.contact_name}")
        print(f"Role: {lead.contact_role}")
        print(f"Target Country: {lead.target_country}")
        print(f"Lead Type: {lead.lead_type}")
        print(f"Score: {lead.score}")
        print(f"Priority: {lead.priority}")
        print("Messaging:")
        print(f"Email Subject: {message.email_subject}")
        print(f"Follow-Up: {message.follow_up_message}")
        print("Pipeline:")
        print(f"Stage: {record.stage}")
        print(f"Outreach Status: {record.outreach_status}")
        print(f"Next Action: {record.next_action}")
        print(f"Sales Motion: {record.sales_motion}")
        print(f"Primary Module: {record.primary_module}")
        print(f"Bundle Label: {record.bundle_label}")
        print(
            f"Recommended Modules: {', '.join(record.recommended_modules or [])}"
        )
        print(f"High Value Deal: {record.lead_reference in high_value_references}")
        print("Solution Design:")
        print(f"Lead Reference: {recommendation.lead_reference}")
        print(f"Sales Motion: {recommendation.sales_motion}")
        print(
            f"Recommended Modules: {', '.join(recommendation.recommended_modules)}"
        )
        print(f"Primary Module: {recommendation.primary_module}")
        print(f"Bundle Label: {recommendation.bundle_label}")
        print(f"Commercial Strategy: {recommendation.commercial_strategy}")
        print(f"Rationale: {recommendation.rationale}")
        print("Deal Support:")
        print(f"Call Prep Summary: {package.call_prep_summary}")
        print(f"Recap Email Subject: {package.recap_email_subject}")
        print(f"Proposal Summary: {package.proposal_summary}")
        print(f"Next Steps Message: {package.next_steps_message}")
        print(f"Objection Response: {package.objection_response}")
        task = tasks_by_reference.get(record.lead_reference)
        if task is not None:
            print("Execution Task:")
            print(f"Task Type: {task.task_type}")
            print(f"Description: {task.description}")
            print(f"Task Priority: {task.priority}")
            print(f"Due In Days: {task.due_in_days}")
            print(f"Task Status: {task.status}")


def generate_opportunities_outreach(limit: int, icp_filter: str | None) -> int:
    notion_service = NotionService()
    anthropic_service = AnthropicService()
    supabase_service = SupabaseService()

    agent = OpportunitiesOutreachAgent(
        notion_service=notion_service,
        anthropic_service=anthropic_service,
        supabase_service=supabase_service,
    )
    if not agent.is_configured():
        logger.error(
            "OpportunitiesOutreachAgent is not configured. "
            "Ensure NOTION_API_KEY, NOTION_OPPORTUNITIES_DATABASE_ID, "
            "NOTION_OUTREACH_QUEUE_DATABASE_ID, and ANTHROPIC_API_KEY are set."
        )
        return 1

    print(
        f"About to generate outreach for up to {limit} prospects"
        + (f" with ICP filter '{icp_filter}'" if icp_filter else "")
        + ". Shadow mode is always on — messages queue for review only. "
          "Proceed? (y/n): ",
        end="",
    )
    answer = input().strip().lower()
    if answer not in {"y", "yes"}:
        print("Cancelled.")
        return 0

    result = agent.generate_outreach(limit=limit, icp_filter=icp_filter)
    print("\nOutreach generation summary:")
    print(f"  {result.summary()}")
    if result.failures:
        print("Failures:")
        for prospect_label, reason in result.failures:
            print(f"  - {prospect_label}: {reason}")
    return 0


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="globalkinect-sales",
        description="GlobalKinect sales engine entry point.",
    )
    parser.add_argument(
        "--generate-outreach",
        action="store_true",
        help="Generate outreach for prospects in the Notion Opportunities database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of prospects to process (default: 50).",
    )
    parser.add_argument(
        "--icp",
        type=str,
        default=None,
        help="Optional ICP filter, e.g. 'A1 - Frustrated GCC Operator'.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_cli_args(sys.argv[1:])
    if args.generate_outreach:
        sys.exit(generate_opportunities_outreach(args.limit, args.icp))
    main()
