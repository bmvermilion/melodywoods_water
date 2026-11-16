import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
from datetime import datetime
import dateutil.tz

# Add layers path to sys.path
sys.path.append(os.path.abspath('layers/pysensaphone/python'))
# Add supply path
sys.path.append(os.path.abspath('melodywoods_water/supply'))

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
        
        mock_ssm.side_effect = lambda name: on_time if "on" in name else off_time

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

    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_power_out_logic(self, mock_set, mock_status, mock_auth, mock_ssm):
        """Test that if power is Off, change_pump is blocked or returns 409"""
        
        event = {
            "sentinel_name": "Well#3",
            "pump_name": "#3 Well Pump",
            "pump": "on", # Email attempt to turn it on
            "reason": {"type": "email_alarm"}
        }

        mock_status.return_value = [{
            'name': 'Well#3',
            'device_id': 100,
            'is_online': True,
            'power_value': 'Off', # POWER IS OUT
            'zone': [{'name': '#3 Well Pump', 'zone_id': 1, 'value': 'off'}]
        }]

        # Run handler
        result = supply_app.lambda_handler(event, None)
        
        # Verify set_sensaphone was NEVER called because power is off
        mock_set.assert_not_called()

if __name__ == '__main__':
    unittest.main()
