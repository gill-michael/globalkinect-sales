import argparse

from app.orchestrators.integration_check import (
    IntegrationCheckRunner,
    format_cleanup_report,
    format_integration_check_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a safe end-to-end integration check for Supabase and Notion.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help=(
            "Delete only Supabase records that contain the integration-test marker "
            "and then exit. Notion cleanup remains manual."
        ),
    )
    parser.add_argument(
        "--run-marker",
        help=(
            "Optional marker suffix or full marker to trace a specific test run. "
            "If omitted, a unique INTEGRATION_TEST timestamp marker is generated."
        ),
    )
    args = parser.parse_args()

    runner = IntegrationCheckRunner()

    if args.cleanup:
        cleanup_result = runner.cleanup(run_marker=args.run_marker)
        print(format_cleanup_report(cleanup_result))
        return 0 if cleanup_result.success else 1

    result = runner.run(run_marker=args.run_marker)
    print(format_integration_check_report(result))
    return 0 if result.is_fully_integration_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
