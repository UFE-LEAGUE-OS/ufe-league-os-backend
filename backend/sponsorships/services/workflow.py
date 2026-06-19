from ..models import SponsorWorkflowEvent


def create_sponsor_workflow_event(
    *,
    actor,
    event_type,
    sponsor_package=None,
    agreement=None,
    payment=None,
    from_status="",
    to_status="",
    note="",
):
    return SponsorWorkflowEvent.objects.create(
        sponsor_package=sponsor_package,
        agreement=agreement,
        payment=payment,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )


def create_sponsor_package_workflow_event(
    *,
    sponsor_package,
    actor,
    event_type,
    from_status="",
    to_status="",
    note="",
):
    return create_sponsor_workflow_event(
        sponsor_package=sponsor_package,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
