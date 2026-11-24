from pysensaphone import sensaphone_auth, get_sensaphone, set_sensaphone, water_logic
from pysensaphone.email_parser import SensaphoneEmailParser
import boto3
import email
import os
import json
import logging

# quiet boto3 message
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_email_body(event):
    """Detects event type (SES or WorkMail) and extracts email body."""
    if 'Records' in event and event['Records'][0].get('eventSource') == 'aws:ses':
        ses_record = event['Records'][0]['ses']
        message_id = ses_record['mail']['messageId']
        bucket = f"melody-woods-water-emails-{boto3.client('sts').get_caller_identity()['Account']}"
        
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=bucket, Key=message_id)
        raw_content = response['Body'].read()
        parsed_msg = email.message_from_bytes(raw_content)

    elif 'messageId' in event:
        workmail = boto3.client('workmailmessageflow', region_name=os.environ["AWS_REGION"])
        raw_msg = workmail.get_raw_message_content(messageId=event['messageId'])
        parsed_msg = email.message_from_bytes(raw_msg['messageContent'].read())
    else:
        return None

    body = b""
    if parsed_msg.is_multipart():
        for part in parsed_msg.walk():
            if part.get_content_type() == 'text/plain' and 'attachment' not in str(part.get('Content-Disposition')):
                body = part.get_payload(decode=True)
                break
    else:
        body = parsed_msg.get_payload(decode=True)

    return body.decode('UTF-8')

def invoke_supply_lambda(payload):
    """Triggers the supply lambda asynchronously."""
    lambda_client = boto3.client('lambda')
    supply_lambda = os.environ.get("SUPPLY_LAMBDA_NAME")
    
    if not supply_lambda:
        return {'success': False, 'msg': 'Configuration error: SUPPLY_LAMBDA_NAME not set'}

    invoke_response = lambda_client.invoke(
        FunctionName=supply_lambda,
        InvocationType='Event',
        Payload=json.dumps(payload))

    return {'success': True if invoke_response['StatusCode'] == 202 else False,
            'HTTPStatusCode': invoke_response['StatusCode'], 'pump': payload['pump_name']}

def lambda_handler(event, context):
    body_text = get_email_body(event)
    if not body_text:
        return {'statusCode': 400, 'body': 'Could not parse email body'}

    parser = SensaphoneEmailParser(body_text)
    sentinel = parser.get_sentinel_name()
    
    well3_payload = {
        "sentinel_name": "Well#3", "pump_name": "#3 Well Pump", "pump": "off",
        "reason": {"type": "email_alarm", "value": True}
    }
    
    actions = []

    # 1. Check for Chlorine Alarms. Only the Treatment Plant barrel is in use;
    # Well #3 chlorine alarms are intentionally ignored.
    # Zero and negative readings indicate a wiring fault or a power-loss
    # artifact, not a real low-chlorine alarm, so they are ignored.
    cl_level = parser.find_chlorine_alarm()
    if cl_level is not None and cl_level > 0:
        if sentinel == 'TreatmentPlant':
            logger.info(f"TP Chlorine Low ({cl_level} Gal). Shutting off Well #3.")
            actions.append(invoke_supply_lambda(well3_payload))

    # 2. Check for Power Status
    power_status = parser.get_power_status()
    if power_status == 'OFF':
        if sentinel in ['TreatmentPlant', 'Well#3']:
            logger.info(f"Power outage at {sentinel}. Shutting off Well #3.")
            actions.append(invoke_supply_lambda(well3_payload))
    
    elif power_status == 'NORMAL':
        if sentinel in ['TreatmentPlant', 'Well#3']:
            logger.info(f"Power restored at {sentinel}. Instructing Well #3 to Resume.")
            well3_payload['pump'] = 'on'
            actions.append(invoke_supply_lambda(well3_payload))

    result_msg = actions if actions else "Email parsed: No action required."
    logger.info(result_msg)
    return {'statusCode': 200, 'body': json.dumps(result_msg)}
