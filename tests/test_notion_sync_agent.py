from unittest.mock import MagicMock

from app.agents.notion_sync_agent import NotionSyncAgent
from app.models.account import Account
from app.models.buyer import Buyer
from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation


def _sample_sync_payload():
    accounts = [
        Account(
            account_name="Example Ltd",
            account_canonical="example ltd",
            primary_target_country="Saudi Arabia",
        )
    ]
    buyers = [
        Buyer(
            buyer_key="Jane Smith | Example Ltd",
            buyer_name="Jane Smith",
            buyer_canonical="jane smith",
            account_name="Example Ltd",
            account_canonical="example ltd",
            contact_role="Founder",
            target_country="Saudi Arabia",
        )
    ]
    leads = [
        Lead(
            company_name="Example Ltd",
            contact_name="Jane Smith",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=8,
            priority="high",
        )
    ]
    pipeline_records = [
        PipelineRecord(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            score=8,
            priority="high",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            recommended_modules=["Payroll", "HRIS"],
            stage="proposal",
            outreach_status="sent",
            next_action="follow_up_proposal",
        )
    ]
    solution_recommendations = [
        SolutionRecommendation(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            target_country="Saudi Arabia",
            sales_motion="direct_client",
            recommended_modules=["Payroll", "HRIS"],
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            commercial_strategy="Position a payroll-led platform entry point for Saudi Arabia with added operational visibility and control.",
            rationale="The current fit is payroll-led with stronger control.",
        )
    ]
    execution_tasks = [
        ExecutionTask(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            task_type="follow_up",
            description="Follow up on the Payroll + HRIS proposal.",
            priority="high",
            due_in_days=2,
        )
    ]
    deal_support_packages = [
        DealSupportPackage(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            recommended_modules=["Payroll", "HRIS"],
            stage="proposal",
            call_prep_summary="Prep summary",
            recap_email_subject="Recap subject",
            recap_email_body="Recap body",
            proposal_summary="Proposal summary",
            next_steps_message="Next steps",
            objection_response="Objection response",
        )
    ]
    return (
        accounts,
        buyers,
        leads,
        pipeline_records,
        solution_recommendations,
        execution_tasks,
        deal_support_packages,
    )


def test_sync_operating_views_skips_cleanly_when_notion_is_not_configured() -> None:
    fake_service = MagicMock()
    fake_service.is_configured.return_value = False
    agent = NotionSyncAgent(fake_service)

    (
        accounts,
        buyers,
        leads,
        pipeline_records,
        solution_recommendations,
        execution_tasks,
        deal_support_packages,
    ) = _sample_sync_payload()

    result = agent.sync_operating_views(
        leads=leads,
        pipeline_records=pipeline_records,
        solution_recommendations=solution_recommendations,
        execution_tasks=execution_tasks,
        deal_support_packages=deal_support_packages,
        accounts=accounts,
        buyers=buyers,
    )

    assert result == {
        "accounts": [],
        "buyers": [],
        "leads": [],
        "pipeline_records": [],
        "solution_recommendations": [],
        "execution_tasks": [],
        "deal_support_packages": [],
    }
    fake_service.upsert_lead_pages.assert_not_called()
    fake_service.upsert_pipeline_pages.assert_not_called()
    fake_service.upsert_solution_pages.assert_not_called()
    fake_service.upsert_execution_task_pages.assert_not_called()
    fake_service.upsert_deal_support_pages.assert_not_called()


def test_sync_operating_views_calls_service_methods_when_configured() -> None:
    fake_service = MagicMock()
    fake_service.is_configured.return_value = True
    fake_service.is_accounts_configured.return_value = True
    fake_service.is_buyers_configured.return_value = True
    fake_service.upsert_account_pages.return_value = [{"id": "account-page"}]
    fake_service.upsert_buyer_pages.return_value = [{"id": "buyer-page"}]
    fake_service.upsert_lead_pages.return_value = [{"id": "lead-page"}]
    fake_service.upsert_pipeline_pages.return_value = [{"id": "pipeline-page"}]
    fake_service.upsert_solution_pages.return_value = [{"id": "solution-page"}]
    fake_service.upsert_execution_task_pages.return_value = [{"id": "task-page"}]
    fake_service.upsert_deal_support_pages.return_value = [{"id": "deal-page"}]
    agent = NotionSyncAgent(fake_service)

    (
        accounts,
        buyers,
        leads,
        pipeline_records,
        solution_recommendations,
        execution_tasks,
        deal_support_packages,
    ) = _sample_sync_payload()

    result = agent.sync_operating_views(
        leads=leads,
        pipeline_records=pipeline_records,
        solution_recommendations=solution_recommendations,
        execution_tasks=execution_tasks,
        deal_support_packages=deal_support_packages,
        accounts=accounts,
        buyers=buyers,
    )

    assert result == {
        "accounts": [{"id": "account-page"}],
        "buyers": [{"id": "buyer-page"}],
        "leads": [{"id": "lead-page"}],
        "pipeline_records": [{"id": "pipeline-page"}],
        "solution_recommendations": [{"id": "solution-page"}],
        "execution_tasks": [{"id": "task-page"}],
        "deal_support_packages": [{"id": "deal-page"}],
    }
    fake_service.upsert_account_pages.assert_called_once_with(accounts)
    fake_service.upsert_buyer_pages.assert_called_once_with(buyers)
    fake_service.upsert_lead_pages.assert_called_once_with(leads)
    fake_service.upsert_pipeline_pages.assert_called_once_with(pipeline_records)
    fake_service.upsert_solution_pages.assert_called_once_with(solution_recommendations)
    fake_service.upsert_execution_task_pages.assert_called_once_with(execution_tasks)
    fake_service.upsert_deal_support_pages.assert_called_once_with(deal_support_packages)
