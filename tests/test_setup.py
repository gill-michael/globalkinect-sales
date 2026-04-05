from app.models.lead import Lead


def test_lead_model() -> None:
    lead = Lead(
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder"
    )

    assert lead.company_name == "Example Ltd"
    assert lead.status == "new"