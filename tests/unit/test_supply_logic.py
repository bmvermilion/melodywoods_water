import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
from datetime import datetime
import dateutil.tz

# Resolve paths relative to this file so the tests work from any cwd.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
# Supply handler must win over other lambdas' app.py modules
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'supply'))
# In the workspace the vendored layer wins; standalone checkouts use the
# installed pysensaphone package.
LAYER_DIR = os.path.join(WORKSPACE_ROOT, 'layers', 'pysensaphone', 'python')
if os.path.isdir(LAYER_DIR):
    sys.path.insert(0, LAYER_DIR)

import app as supply_app

class TestSupplyLogic(unittest.TestCase):

    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_well3_timer_on(self, mock_set, mock_status, mock_auth, mock_ssm):
        """Test Well 3 turns ON if within the 15min window of the 'on' timer"""
        
        # 1. Mock Event (Well 3 timer trigger)
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "",
            "reason": {"type": "well3"}
        }

        # 2. Mock SSM Timers
        pacific = dateutil.tz.gettz('US/Pacific')
        # Use a fixed reference time
        base_time = datetime(2024, 11, 15, 12, 0, 0, tzinfo=pacific)
        
        # We need timer_minutes to be between -1 and 15
        # app.py: timer_minutes = (timestamp - current_pacific_time).total_seconds() / 60
        # So timestamp (timer) needs to be slightly AFTER current_pacific_time (base_time)
        # OR exactly current_pacific_time.
        # Let's set timer to 12:05 (5 minutes after base_time)
        on_time = "12:05"
        off_time = "14:00"
        
        mock_ssm.side_effect = lambda name, default_value=None: on_time if "on" in name else off_time

        # 3. Mock System Status
        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'On',
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]
        
        mock_set.return_value = {'result': {'success': True}}

        # 4. Run handler with mocked time
        with patch('datetime.datetime') as mock_date:
            mock_date.now.return_value = base_time
            # Keep original datetime behavior for other calls
            mock_date.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_date.strptime = datetime.strptime
            
            supply_app.lambda_handler(event, None)

        # 5. Verify the pump was actually turned ON
        mock_set.assert_called_with(unittest.mock.ANY, 100, 1, 1)

    @patch('app.water_logic.get_pacific_time')
    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_power_out_logic(self, mock_set, mock_status, mock_auth, mock_ssm, mock_time):
        """Test that if power is Off, change_pump is blocked or returns 409"""
        
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "on", # Email attempt to turn it on
            "reason": {"type": "email_alarm"}
        }

        # Pin an open window so the request reaches the power check
        pacific = dateutil.tz.gettz('US/Pacific')
        mock_time.return_value = datetime(2024, 11, 15, 22, 0, 0, tzinfo=pacific)
        mock_ssm.side_effect = lambda name, default_value=None: "21:00" if "_on" in name else "10:00"

        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'Off', # POWER IS OUT
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]

        # Run handler
        result = supply_app.lambda_handler(event, None)
        self.assertIn("Power is Off", json.dumps(result, default=str))
        
        # Verify set_sensaphone was NEVER called because power is off
        mock_set.assert_not_called()

    @patch('app.water_logic.get_pacific_time')
    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_well3_email_alarm_on_within_hours(self, mock_set, mock_status, mock_auth, mock_ssm, mock_time):
        """email_alarm ON for Well#3 inside the allowed daily window turns the pump ON.

        Regression test: this branch previously shipped with broken indentation
        and never ran in production.
        """
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "on",
            "reason": {"type": "email_alarm"}
        }

        pacific = dateutil.tz.gettz('US/Pacific')
        # 22:00 is inside the 21:00 -> 10:00 allowed window
        mock_time.return_value = datetime(2024, 11, 15, 22, 0, 0, tzinfo=pacific)
        mock_ssm.side_effect = lambda name, default_value=None: "21:00" if "_on" in name else "10:00"

        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'On',
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]
        mock_set.return_value = {'result': {'success': True}}

        supply_app.lambda_handler(event, None)

        mock_set.assert_called_with(unittest.mock.ANY, 100, 1, 1)

    @patch('app.water_logic.get_pacific_time')
    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_well3_email_alarm_on_outside_hours(self, mock_set, mock_status, mock_auth, mock_ssm, mock_time):
        """email_alarm ON for Well#3 outside the allowed window must NOT touch the pump."""
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "on",
            "reason": {"type": "email_alarm"}
        }

        pacific = dateutil.tz.gettz('US/Pacific')
        # 15:00 is between 10:00 and 21:00 -> outside allowed hours
        mock_time.return_value = datetime(2024, 11, 15, 15, 0, 0, tzinfo=pacific)
        mock_ssm.side_effect = lambda name, default_value=None: "21:00" if "_on" in name else "10:00"

        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'On',
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]
        mock_set.return_value = {'result': {'success': True}}

        result = supply_app.lambda_handler(event, None)

        mock_set.assert_not_called()
        self.assertIn("Outside allowed hours", json.dumps(result, default=str))

    @patch('app.water_logic.get_pacific_time')
    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_well3_email_alarm_respects_minutes(self, mock_set, mock_status, mock_auth, mock_ssm, mock_time):
        """The daily window is minute-aware: 21:15 is NOT inside a 21:30 -> 10:30 window.

        An hour-only comparison would wrongly allow this and turn the pump on.
        """
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "on",
            "reason": {"type": "email_alarm"}
        }

        pacific = dateutil.tz.gettz('US/Pacific')
        mock_time.return_value = datetime(2024, 11, 15, 21, 15, 0, tzinfo=pacific)
        mock_ssm.side_effect = lambda name, default_value=None: "21:30" if "_on" in name else "10:30"

        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'On',
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]
        mock_set.return_value = {'result': {'success': True}}

        supply_app.lambda_handler(event, None)

        mock_set.assert_not_called()


class TestDailyWindow(unittest.TestCase):
    """Direct coverage for water_logic.is_within_daily_window."""

    def _at(self, hour, minute):
        return datetime(2024, 11, 15, hour, minute, tzinfo=dateutil.tz.gettz('US/Pacific'))

    def test_inside_after_midnight(self):
        self.assertTrue(supply_app.water_logic.is_within_daily_window("21:00", "10:00", self._at(2, 0)))

    def test_inside_evening(self):
        self.assertTrue(supply_app.water_logic.is_within_daily_window("21:00", "10:00", self._at(22, 0)))

    def test_outside_midday(self):
        self.assertFalse(supply_app.water_logic.is_within_daily_window("21:00", "10:00", self._at(15, 0)))

    def test_minute_precision_before_on(self):
        self.assertFalse(supply_app.water_logic.is_within_daily_window("21:30", "10:30", self._at(21, 15)))

    def test_minute_precision_after_off(self):
        self.assertFalse(supply_app.water_logic.is_within_daily_window("21:30", "10:30", self._at(10, 45)))

    def test_bounds_are_inclusive(self):
        self.assertTrue(supply_app.water_logic.is_within_daily_window("21:30", "10:30", self._at(21, 30)))
        self.assertTrue(supply_app.water_logic.is_within_daily_window("21:30", "10:30", self._at(10, 30)))

    def test_non_wrapping_window(self):
        self.assertTrue(supply_app.water_logic.is_within_daily_window("08:00", "17:00", self._at(12, 0)))
        self.assertFalse(supply_app.water_logic.is_within_daily_window("08:00", "17:00", self._at(18, 0)))

    def test_missing_bounds(self):
        self.assertFalse(supply_app.water_logic.is_within_daily_window(None, "10:00", self._at(12, 0)))

    def test_invalid_bounds(self):
        self.assertFalse(supply_app.water_logic.is_within_daily_window("nope", "10:00", self._at(12, 0)))


if __name__ == '__main__':
    unittest.main()
