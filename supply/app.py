from pysensaphone import sensaphone_auth
from pysensaphone import get_sensaphone
from pysensaphone import set_sensaphone
import json
import datetime
import dateutil.tz
import re
import boto3
import logging

# quiet boto3 message, "Found credentials in environment variables."
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_ssm_param(param_name):
    """
    Retrieve adjustable parameters for Well ON/OFF times which are stored in AWS Systems Manager - Parameter Store
    https://us-west-2.console.aws.amazon.com/systems-manager/parameters/?region=us-west-2&tab=Table

    Parameters:
        param_name (str): name of AWS Systems Manager Parameter to retrieve

    Returns:
        str: Returning value of AWS Systems Manager Parameter
    """

    ssm = boto3.client('ssm')
    parameter = ssm.get_parameter(Name=param_name)
    param = parameter['Parameter']['Value']

    # Check that parameter format is 'HH:MM'
    if re.match(r'^\d+\:\d+$', param):
        logger.info('{a} {b}'.format(a=param_name, b=parameter))
    else:
        logger.error('Invalid {a} parameter format \n {b}'.format(a=param, b=parameter))
        param = None

    return param


def timer_offset(timer):
    """
    Takes pump timer (HH:MM) and returns the minutes until timer from current time.
    Parameters:
        timer (str): Time in HH:MM for the pump change.

    Returns:
        float: Minutes until or since the timer from current time.
    """

    # Get current Pacific time. AWS Lambda event triggers operate in UTC.
    pacific = dateutil.tz.gettz('US/Pacific')
    current_pacific_time = datetime.datetime.now(tz=pacific)

    timestamp = current_pacific_time.replace(hour=int(timer.split(":")[0]),
                                             minute=int(timer.split(":")[1]),
                                             second=0, microsecond=0)

    # Difference in between timer and current time
    timer_minutes = (timestamp - current_pacific_time).total_seconds() / 60

    logger.info('Current Pacific Time: {a} \n Timer Change Timestamp: {b}'.format(a=current_pacific_time
                                                                                  , b=timestamp))
    logger.info('Minutes until Change: {a:.2f}'.format(a=timer_minutes))

    return timer_minutes


def change_pump(event, creds, device_id, zone_id, power, current_pump_value, requested_pump_value):
    """
        Change pump output.

        Parameters:
            event (dict): Lambda event payload
            creds (dict): Sensaphone.net credentials
            device_id (int): Sentinel Device ID to change output
            zone_id (int): Output Zone ID to change output
            power (str): Power On or Off
            current_pump_value (str): Current output value of Sentinel (on/off)
            requested_pump_value (str): Requested change of output value based on Lambda cron or email

        Returns:
            list: status_code (int) - HTTP Status Code,
                    msg (str) - message of what occurred during the run,
                    data (dict) - request data from changing Sentinel Output
        """

    data = None
    event['pump'] = None
    if requested_pump_value.lower() == current_pump_value.lower():
        status_code = 200
        msg = 'Requested Pump Value Change Not Required, Value Already Set'
    elif power == "On":
        if requested_pump_value.lower() == 'on':
            pump_value = 1
        else:
            pump_value = 0
        data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
        if data['result']['success']:
            status_code = 200
            msg = 'Success'
            event['pump'] = requested_pump_value
        else:
            status_code = data['result']['code']
            msg = 'Failure'
    else:
        # Power is out
        status_code = 409
        msg = 'Power is ' + power

    return status_code, msg, data


def log_result(status_code, event, msg, data, devices):
    """
    Log what happened during the Lambda execution to CloudWatch
    https://us-west-2.console.aws.amazon.com/cloudwatch/home?region=us-west-2#
        Parameters:
            status_code (int): HTTP Status Code from Sentinel Output change
            event (dict): event details from Lambda cron or email
            msg (str): message of what occurred during the run
            data (dict): request data from changing Sentinel Output
            devices (dict): Sentinel data of system status

        Returns:
            dict: dictionary of what happened during the Lambda execution
    """
    if not event['pump']:
        event['pump'] = 'None'

    result = {
        "statusCode": status_code,
        "body": {
            "summary": event['sentinel_name'] + ' - ' + event['pump_name'] + ' Change - ' + event['pump'],
            "msg": msg,
            "requested_change": event,
            "response_data": data,
            "system_status": devices
        },
    }
    # This is to record what happens in CloudWatch logs.
    print(json.dumps(result))
    return result


def lambda_handler(event, context):
    params = {'well3': ['well3_on', 'well3_off'], 'well5': ['well5_on', 'well5_off'],
              'spring': ['spring_on', 'spring_off']}
    # Login to sensaphone.net
    creds = sensaphone_auth.check_valid_session()
    # Get Current System Status
    devices = get_sensaphone.system_status(creds)

    for d in devices:
        # Sentinel Device Name
        if d['name'] == event['sentinel_name']:
            device_id = d['device_id']
            is_online = d['is_online']
            power = d['power_value']
            # Sentinel Output
            for z in d['zone']:
                if z['name'] == event['pump_name']:
                    # Output Id
                    zone_id = z['zone_id']
                    current_pump_value = z['value']

    if event['reason']['type'].lower() in ('well3', 'well5', 'spring'):
        reason = event['reason']['type'].lower()

        # Get Timer Settings from AWS Systems Manger Parameter Store
        on = get_ssm_param(params[reason][0])
        off = get_ssm_param(params[reason][1])
        # Minutes until or since timer
        on_mins = timer_offset(on)
        off_mins = timer_offset(off)

        # Timer in last 15 mins take action.
        # AWS Lambda cron is set to run every 15 mins.
        if 15 > on_mins >= -1:
            poutput = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
        elif 15 > off_mins >= -1:
            poutput = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'off')
        else:
            status_code = 200
            msg = reason + ' - Not time to change pump output'

    # Pump change based on content of email alert from Sensaphone.
    elif event['reason']['type'].lower() == 'email_alarm':
        if event['pump'] == 'on':
            if event['pump_name'] == '#3 Well Pump':
                # Get Timer Settings from AWS Systems Manger Parameter Store
                well3_on_hour = int(get_ssm_param('well3_on').split(":")[0])
                well3_off_hour = int(get_ssm_param('well3_off').split(":")[0])

                # Get current Pacific time. AWS Lambda event triggers operate in UTC.
                pacific = dateutil.tz.gettz('US/Pacific')
                current_pacific_hour = datetime.datetime.now(tz=pacific).hour

                # it is currently between turn on and turn off times.
                if (current_pacific_hour >= well3_on_hour) or (current_pacific_hour <= well3_off_hour):
                    poutput = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
                else:
                    status_code = 200
                    msg = event['reason']['type'].lower() + ' Well#3 - Not time to change pump output'
            # tend to run #5 / Spring 24/7.
            else:
                poutput = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
        elif event['pump'] == 'off':
            poutput = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'off')
        else:
            status_code = 400
            msg = 'Invalid Pump Value! Check Template Payload'
    else:
        status_code = 400
        msg = 'Invalid \'Reason Type\'! Check Template Payload'

    if 'poutput' not in locals():
        poutput = [status_code, msg, None]
    log_result(poutput[0], event, poutput[1], poutput[2], devices)
