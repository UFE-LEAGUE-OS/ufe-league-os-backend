# This migration is a no-op on the feature/fan-egagement branch because all
# models (SponsorPackage, SponsorBenefit, SponsorAgreement, etc.) are already
# created in 0001_initial which was squashed/consolidated on this branch.
# On develop, these models exist in a separate 0002 migration.
# We keep this file so that migration dependency chains remain intact.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sponsorships", "0001_initial"),
    ]

    operations = []
