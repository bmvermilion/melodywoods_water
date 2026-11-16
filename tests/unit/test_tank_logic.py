import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
from datetime import datetime
import dateutil.tz

# Add paths
sys.path.append(os.path.abspath('layers/pysensaphone/python'))
sys.path.append(os.path.abspath('melodywoods_water/88k_tank'))

import app as tank_app

class TestTankLogic(unittest.TestCase):

    @patch('app.water_logic.get_ssm_param')
    @patch('app.sensaphone_auth.check_valid_session')
    @patch('app.get_sensaphone.system_status')
    @patch('app.set_sensaphone.change_device_output')
    def test_88k_tank_full_shutoff(self, mock_set, mock_status, mock_auth, mock_ssm):
        """Test that if tank level > shutoff_level, pump is turned OFF"""
        
        # Mock SSM Parameters
        mock_ssm.side_effect = lambda Name: '23.3' if Name == 'shutoff_level_88k' else '22.8'

        # Mock Event (Hourly check)
        event = {"pump": "", "reason": "Hourly"}

        # Mock System Status: Tank is at 24.0 ft (OVER LIMIT)
        mock_status.return_value = [
            {
                'name': 'TreatmentPlant',
                'device_id': 200,
                'is_online': True,
                'power_value': 'On',
                'zone': [{'name': '88k Pump', 'zone_id': 10, 'value': 'on'}]
            },
            {
                'name': '88kTank',
                'is_online': True,
                'power_value': 'On',
                'zone': [{'name': '88k Level', 'value': '24.0Ft'}]
            }
        ]
        
        mock_set.return_value = {'result': {'success': True}}

        tank_app.lambda_handler(event, None)

        # Verify pump was set to 0 (OFF)
        mock_set.assert_called_with(unittest.mock.ANY, 200, 10, 0)

if __name__ == '__main__':
    unittest.main()
