import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LAYER_DIR = os.path.join(PROJECT_ROOT, 'layers', 'pysensaphone', 'python')
if os.path.isdir(LAYER_DIR):
    sys.path.insert(0, LAYER_DIR)

from pysensaphone import sensaphone_auth

class TestSensaphoneAuth(unittest.TestCase):

    @patch('pysensaphone.sensaphone_auth.boto3.client')
    @patch('os.environ.get')
    def test_check_valid_session_ssm_hit(self, mock_env, mock_ssm_client):
        """Test that auth reuses a valid session from SSM without logging in"""
        mock_env.side_effect = lambda k, default=None: "AWS_LAMBDA" if k == "AWS_EXECUTION_ENV" else default
        
        # Mock SSM returning a valid session
        future_date = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            'Parameter': {
                'Value': json.dumps({
                    'session': 'fake-session-id',
                    'acctid': '12345',
                    'session_expiration': future_date
                })
            }
        }
        mock_ssm_client.return_value = mock_ssm

        # Call check_valid_session
        with patch('pysensaphone.sensaphone_auth.sensaphone_login') as mock_login:
            creds = sensaphone_auth.check_valid_session()
            
            # Assertions
            self.assertEqual(creds['session'], 'fake-session-id')
            mock_login.assert_not_called()
            mock_ssm.get_parameter.assert_called_once()

    @patch('pysensaphone.sensaphone_auth.sensaphone_request')
    @patch('pysensaphone.sensaphone_auth.decrypt_password')
    @patch('pysensaphone.sensaphone_auth.boto3.client')
    @patch('os.environ.get')
    def test_sensaphone_login_success(self, mock_env, mock_ssm_client, mock_decrypt, mock_request):
        """Test a full login flow when cache is empty"""
        mock_env.side_effect = lambda k, default=None: "AWS_LAMBDA" if k == "AWS_EXECUTION_ENV" else default
        mock_decrypt.return_value = "password123"
        
        # Mock API response
        mock_request.return_value = {
            'result': {'success': True},
            'response': {
                'session': 'new-session',
                'acctid': '54321',
                'session_expiration': 3600, # 1 hour
                'login_timestamp': datetime.now().timestamp()
            }
        }
        
        mock_ssm = MagicMock()
        mock_ssm_client.return_value = mock_ssm

        creds = sensaphone_auth.sensaphone_login()
        
        self.assertEqual(creds['session'], 'new-session')
        mock_ssm.put_parameter.assert_called_once()

if __name__ == '__main__':
    unittest.main()
