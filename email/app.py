import boto3
import email
import os
import re
import json
import logging

# quiet boto3 message, "Found credentials in environment variables."
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

''' How to test/debug
    https://docs.aws.amazon.com/workmail/latest/adminguide/lambda-content.html
    1. Generate recent alert (needs to be in last 24hrs), by changing Alarm Low or High within
        Sensaphone 'Configure Device' screen for a Zone/Sensor.
    2. Look at AWS CloudWatch logs and grab the JSON with the 'messageId' and place in events test JSON files.
        Ex. ../events/email_test_well3.json
    3. Make your code changes, if needed.
    4. Make local build to test with, run:  sam build --use-container --template ../template.yaml
    5. Run Lambda locally with test event:  sam local invoke email -e ../events/email_test_well3.json
'''


def get_email(event):
    """
        Takes event payload and uses messageId to extract email body.
        Parameters:
            event (dict): Contains event payload from Lambda.

        Returns:
            str: email body.
        """
    # event['messageId'] contains id to retrieve complete email from WorkMail (only for emails in last 24hrs)
    workmail = boto3.client('workmailmessageflow', region_name=os.environ["AWS_REGION"])

    # get email
    raw_msg = workmail.get_raw_message_content(messageId=event['messageId'])
    parsed_msg = email.message_from_bytes(raw_msg['messageContent'].read())

    # get body of email
    if parsed_msg.is_multipart():
        for part in parsed_msg.walk():
            content_type = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            # skip any text/plain (txt) attachments
            if content_type == 'text/plain' and 'attachment' not in cdispo:
                body = part.get_payload(decode=True)  # decode
                break
    # not multipart - i.e. plain text, no attachments
    else:
        body = parsed_msg.get_payload(decode=True)

    # log email body
    logger.info(json.dumps({'email_body': body.decode('UTF-8')}))
    return body


def lambda_handler(event, context):
    msg = []

    spring = {"sentinel_name": "TreatmentPlant", "pump_name": "Spring Pump", "pump": "off",
              "reason": {"type": "email_alarm", "value": True}}
    well3 = {"sentinel_name": "Well#3", "pump_name": "#3 Well Pump", "pump": "off",
             "reason": {"type": "email_alarm", "value": True}}
    """
    well5 = {"sentinel_name": "Well#5", "pump_name": "#5 Well Pump", "pump": "off",
             "reason": {"type": "email_alarm", "value": True}}
    """
    logger.info(json.dumps(event))
    email_body = get_email(event)

    # parse body of email
    email_lines = email_body.splitlines()
    for idx, l in enumerate(email_lines):
        # from which Sentinel
        if 'From:' in str(l):
            sentinel = email_lines[idx + 1].decode('utf-8')
            # Well#3 / TreatmentPlant etc

        # what alerted?
        # looking for CL Barrel Low Alarm
        elif 'alarm' in str(l):
            alert_details = str(l).split('. ')
            cl_alert = re.search(r"Low level alarm .+ Chlorine Barrel Level", str(alert_details[0]), re.I)
            cl_level = re.search(r"-?\d+\.\d+", alert_details[2])[0]

            logger.info("Valid alert to take action? " + str(cl_alert and float(cl_level) > 0))

            # valid alert? if reading is > 0. If we lost power value will be negative.
            if cl_alert and float(cl_level) > 0:
                # if CL Barrel in TP is low all the wells and spring need to be shutoff
                if sentinel == 'TreatmentPlant':
                    msg.append(invoke_supply_lambda(spring))
                    msg.append(invoke_supply_lambda(well3))
                    # msg.append(invoke_supply_lambda(well5))
                # if Well3 CL Barrel is low then turn off Well3
                elif sentinel == 'Well#3':
                    msg.append(invoke_supply_lambda(well3))
                else:
                    msg = 'Unknown Sentinel, no mapping of pumps to turn off'
                    logger.error(msg)

        elif 'power' in str(l):
            alert_details = str(l).split('. ')
            power_off = re.search(r"The power is OFF", str(alert_details[0]), re.I)
            power_on = re.search(r"The power has returned to normal", str(alert_details[0]), re.I)

            if power_off:
                if sentinel == 'TreatmentPlant':
                    msg.append(invoke_supply_lambda(spring))
                    msg.append(invoke_supply_lambda(well3))
                    # msg.append(invoke_supply_lambda(well5))
                elif sentinel == 'Well#3':
                    msg.append(invoke_supply_lambda(well3))
                else:
                    msg = 'Unknown Sentinel, no mapping of pumps to turn off'
                    logger.error(msg)
            elif power_on:
                spring['pump'] = 'on'
                # Well3 turns on if it is currently in between its On/Off times based on Supply Lambda.
                well3['pump'] = 'on'
                # well5['pump'] = 'on'
                if sentinel == 'TreatmentPlant':
                    msg.append(invoke_supply_lambda(spring))
                    msg.append(invoke_supply_lambda(well3))
                    # msg.append(invoke_supply_lambda(well5))
                elif sentinel == 'Well#3':
                    msg.append(invoke_supply_lambda(well3))
                else:
                    msg = 'Unknown Sentinel, no mapping of pumps to turn on'
                    logger.error(msg)

    if not msg:
        msg = 'Email Alert body has no match - no-op'

    # This is to record what happens in CloudWatch logs. For some reason return value is not logged.
    logger.info(json.dumps(msg))
    return msg


def invoke_supply_lambda(payload):
    # run supply lambda to turn on/off wells or spring
    lambda_client = boto3.client('lambda')
    invoke_response = lambda_client.invoke(
        FunctionName="arn:aws:lambda:us-east-1:222492554563:function:melody-woods-water-supply-SacqPDTlGjRU",
        InvocationType='Event',
        Payload=json.dumps(payload))

    return {'success': True if invoke_response['StatusCode'] == 202 else False,
            'HTTPStatusCode': invoke_response['StatusCode'], 'pump': payload['pump_name'], "executed": payload}
