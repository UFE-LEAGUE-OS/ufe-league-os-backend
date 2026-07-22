from unittest.mock import patch

from django.test import SimpleTestCase

from dashboards.management.commands.seed_league_os_test_environment import (
    COVERAGE_SEED_STEPS,
    TEST_PASSWORD,
    Command,
)


class SeedLeagueOsTestEnvironmentTests(SimpleTestCase):
    def test_sponsor_seed_step_receives_required_password(self):
        sponsor_steps = [
            options
            for command_name, options in COVERAGE_SEED_STEPS
            if command_name == "seed_sponsor_demo_data"
        ]

        self.assertEqual(
            sponsor_steps,
            [
                {
                    "password": TEST_PASSWORD,
                }
            ],
        )

    @patch(
        "dashboards.management.commands." "seed_league_os_test_environment.call_command"
    )
    def test_required_command_forwards_command_options(
        self,
        mocked_call_command,
    ):
        command = Command()

        command._run_required_command(
            command_name="seed_sponsor_demo_data",
            command_options={
                "password": TEST_PASSWORD,
            },
            available_commands={
                "seed_sponsor_demo_data": ("sponsorships"),
            },
        )

        mocked_call_command.assert_called_once_with(
            "seed_sponsor_demo_data",
            password=TEST_PASSWORD,
        )
