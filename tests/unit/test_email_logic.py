import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'email'))
LAYER_DIR = os.path.join(PROJECT_ROOT, 'layers', 'pysensaphone', 'python')
if os.path.isdir(LAYER_DIR):
    sys.path.insert(0, LAYER_DIR)

import app as email_app


CHLORINE_ALARM = """From:
{sentinel}
Low level alarm 0.5 Gal. Chlorine Barrel Level
"""

POWER_OFF = """From:
{sentinel}
The power is OFF
"""


class TestEmailAlerts(unittest.TestCase):
    """Verifies which alerts do and do not invoke the supply function."""

    @patch('app.invoke_supply_lambda')
    @patch('app.get_email_body')
    def test_tp_chlorine_turns_off_well3(self, mock_body, mock_invoke):
        mock_body.return_value = CHLORINE_ALARM.format(sentinel='TreatmentPlant')
        mock_invoke.return_value = {'success': True}

        email_app.lambda_handler({'messageId': 'test'}, None)

        mock_invoke.assert_called_once()
        payload = mock_invoke.call_args.args[0]
        self.assertEqual(payload['sentinel_name'], 'Well#3')
        self.assertEqual(payload['pump'], 'off')

    @patch('app.invoke_supply_lambda')
    @patch('app.get_email_body')
    def test_well3_chlorine_is_ignored(self, mock_body, mock_invoke):
        mock_body.return_value = CHLORINE_ALARM.format(sentinel='Well#3')

        email_app.lambda_handler({'messageId': 'test'}, None)

        mock_invoke.assert_not_called()

    @patch('app.invoke_supply_lambda')
    @patch('app.get_email_body')
    def test_tp_zero_chlorine_is_ignored(self, mock_body, mock_invoke):
        """A zero or negative reading is a wiring/power artifact, not an alarm."""
        for level in ('0.0', '-0.5'):
            with self.subTest(level=level):
                mock_body.return_value = (
                    f"From:\nTreatmentPlant\n"
                    f"Low level alarm {level} Gal. Chlorine Barrel Level\n"
                )
                email_app.lambda_handler({'messageId': 'test'}, None)

        mock_invoke.assert_not_called()

    @patch('app.invoke_supply_lambda')
    @patch('app.get_email_body')
    def test_tp_power_off_turns_off_well3(self, mock_body, mock_invoke):
        mock_body.return_value = POWER_OFF.format(sentinel='TreatmentPlant')
        mock_invoke.return_value = {'success': True}

        email_app.lambda_handler({'messageId': 'test'}, None)

        mock_invoke.assert_called_once()
        payload = mock_invoke.call_args.args[0]
        self.assertEqual(payload['sentinel_name'], 'Well#3')
        self.assertEqual(payload['pump'], 'off')

    @patch('app.invoke_supply_lambda')
    @patch('app.get_email_body')
    def test_well3_power_off_turns_off_well3(self, mock_body, mock_invoke):
        mock_body.return_value = POWER_OFF.format(sentinel='Well#3')
        mock_invoke.return_value = {'success': True}

        email_app.lambda_handler({'messageId': 'test'}, None)

        mock_invoke.assert_called_once()
        payload = mock_invoke.call_args.args[0]
        self.assertEqual(payload['sentinel_name'], 'Well#3')
        self.assertEqual(payload['pump'], 'off')


if __name__ == '__main__':
    unittest.main()
