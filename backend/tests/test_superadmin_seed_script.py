import importlib.util
from pathlib import Path

from accounts.models import User
from monitoring.models import (
    Anomaly,
    ComplianceTrail,
    SecurityEvent,
    TransactionReconciliation,
)

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "populate_superadmin_data.py"
)


def load_seed_module():
    spec = importlib.util.spec_from_file_location(
        "populate_superadmin_data", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_populate_monitoring_creates_records_with_current_model_fields(db):
    seed_module = load_seed_module()
    super_admin = User.objects.create_user(
        email="seed-test@example.com",
        password="StrongPass123!",
        first_name="Seed",
        last_name="Tester",
        role=User.Role.SUPER_ADMIN,
    )

    seed_module.populate_monitoring(super_admin)

    assert Anomaly.objects.filter(affected_user=super_admin).count() == 2
    assert SecurityEvent.objects.count() == 2
    assert ComplianceTrail.objects.count() == 2
    assert TransactionReconciliation.objects.count() == 1
