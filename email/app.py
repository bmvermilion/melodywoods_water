import boto3
import email
import os
import re
import json


def lambda_handler(event, context):
    msg = []
    # event['messageId'] contains id to retrieve complete email from WorkMail
    print(json.dumps(event))
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

    # parse body of email
    email_lines = body.splitlines()
    for idx, l in enumerate(email_lines):
        # from which Sentinel
        if 'From:' in str(l):
            sentinel = email_lines[idx + 1].decode('utf-8')
            # Well#3 / TreatmentPlant

        # what alerted? looking for CL Barrel Low Alarm
        elif 'alarm' in str(l):
            alert_details = str(l).split('. ')
            cl_alert = re.search(r"Low level alarm .+ Chlorine Barrel Level", str(alert_details[0]), re.I)
            cl_level = re.search(r"\d+\.\d+", alert_details[2])[0]

            # valid alert? if reading is > 0. If we lost power value will be negative.
            if cl_alert and float(cl_level) > 0:
                spring = {"sentinel_name": "TreatmentPlant", "pump_name": "Spring Pump", "pump": "off",
                          "reason": {"type": "email_alarm", "value": True}}
                well3 = {"sentinel_name": "Well#3", "pump_name": "#3 Well Pump", "pump": "off",
                         "reason": {"type": "email_alarm", "value": True}}

                # if CL Barrel in TP is low all the wells and spring need to be shutoff
                if sentinel == 'TreatmentPlant':
                    msg.append(invoke_supply_lambda(spring))
                    msg.append(invoke_supply_lambda(well3))
                # if Well3 CL Barrel is low then turn off Well3
                elif sentinel == 'Well#3':
                    msg.append(invoke_supply_lambda(well3))
                else:
                    msg = 'Unknown Sentinel, no mapping of pumps to turn off'

    # This is to record what happens in CloudWatch logs. For some reason return value is not logged.
    if not msg:
        msg = 'Email Alert did not match Low CL Barrel Alarm'

    print(json.dumps(msg))
    return msg


def invoke_supply_lambda(payload):
    # run supply lambda to turn off wells or spring
    lambda_client = boto3.client('lambda')
    invoke_response = lambda_client.invoke(
        FunctionName="arn:aws:lambda:us-west-2:421269454553:function:melody-woods-water-supply-1FM312GZMYD3X",
        InvocationType='Event',
        Payload=json.dumps(payload))

    return {'success': True if invoke_response['StatusCode'] == 202 else False,
            'HTTPStatusCode': invoke_response['StatusCode'], 'pump': payload['pump_name'], "executed": payload}
