import boto3
import os
import datetime
import json
import logging
from base64 import b64decode
from pathlib import Path
from botocore.exceptions import ClientError
from .get_sensaphone import sensaphone_request

logger = logging.getLogger(__name__)

# Cache configuration
SSM_PARAMETER_NAME = os.environ.get("SENSAPHONE_CACHE_PARAMETER", "/sensaphone/session")

def store_session_ssm(creds: dict):
    """Store session credentials in AWS SSM Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        ssm.put_parameter(
            Name=SSM_PARAMETER_NAME,
            Value=json.dumps(creds),
            Type='SecureString',
            Overwrite=True
        )
        logger.info(f"Successfully cached session in SSM: {SSM_PARAMETER_NAME}")
    except ClientError as e:
        logger.error(f"Failed to cache session in SSM: {e}")

def get_session_ssm() -> dict:
    """Retrieve session credentials from AWS SSM Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        parameter = ssm.get_parameter(Name=SSM_PARAMETER_NAME, WithDecryption=True)
        return json.loads(parameter['Parameter']['Value'])
    except (ClientError, json.JSONDecodeError, KeyError):
        logger.info("No valid session found in SSM cache")
        return None

def sensaphone_login() -> dict:
    """Login to Sensaphone and collect session, acctid and session_expiration"""
    username = os.environ.get("SENSAPHONE_USERNAME", 'controls@melodywoodscontrols.awsapps.com')
    password = decrypt_password()
    login_data = {"request_type": "create", "resource": "login", "user_name": username, "password": password}
    url = 'https://rest.sensaphone.net/api/v1/login'

    logger.info('Attempting to Login to Sensaphone')
    r = sensaphone_request(url, login_data)

    if r['result']['success']:
        expiration_timestamp = r['response']['session_expiration'] + r['response']['login_timestamp']
        creds = {
            'session': r['response']['session'], 
            'acctid': r['response']['acctid'], 
            'session_expiration': str(datetime.datetime.fromtimestamp(expiration_timestamp))
        }
        
        if os.environ.get("AWS_EXECUTION_ENV"):
            store_session_ssm(creds)
        else:
            with open('creds.json', 'w') as fp:
                json.dump(creds, fp)
        
        logger.info('Auth Success')
        return creds
    else:
        logger.error(f"Auth Failure Sensaphone Account: {json.dumps(r)}")
        return False

def check_valid_session() -> dict:
    """Check if current session id is valid. If not then login using sensaphone_login()"""
    creds = None
    
    if os.environ.get("AWS_EXECUTION_ENV"):
        creds = get_session_ssm()
    else:
        try:
            with open('creds.json', 'r') as fp:
                creds = json.load(fp)
        except FileNotFoundError:
            pass

    if creds:
        try:
            session_expiration = datetime.datetime.strptime(creds['session_expiration'], '%Y-%m-%d %H:%M:%S')
            now = datetime.datetime.now()
            time_till_expire = session_expiration - now

            # If session is valid for more than 1 hour, reuse it
            if time_till_expire.total_seconds() / 3600 > 1.0:
                return creds
            else:
                logger.info("Sensaphone Credentials Expired or near expiration")
        except (ValueError, KeyError):
            logger.warning("Malformed credentials found in cache")

    return sensaphone_login()

def decrypt_password() -> str:
    """Decrypt password stored in .pem file using AWS Key Management Service (KMS)."""
    path = Path(__file__).parent / "encrypted_controls.pem"
    with open(path, 'rb') as encrypted_pem:
        pem_file = encrypted_pem.read()

    kms = boto3.client('kms', region_name='us-east-1')
    return kms.decrypt(CiphertextBlob=pem_file)['Plaintext'].decode("utf-8")
