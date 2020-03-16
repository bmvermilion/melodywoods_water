from pysensaphone import sensaphone_auth
from pysensaphone import get_sensaphone
from pysensaphone import set_sensaphone
import json


def lambda_handler(event, context):

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

    if event['pump'] == current_pump_value.lower():
        pump_value = None
        status_code = 200
        msg = 'Requested Pump Value Change Not Required, Value Already Set'
        data = None
    elif event['pump'] == 'on':
        pump_value = 1
    elif event['pump'] == 'off':
        pump_value = 0
    else:
        pump_value = None
        status_code = 400
        msg = 'Invalid Pump Value!'
        data = None

    # Set Sentinel Output
    if power == "On" and pump_value is not None:
        data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
        if data['result']['success']:
            status_code = 200
            msg = 'Success'
        else:
            status_code = data['result']['code']
            msg = 'Failure'
    else:
        # Reason or Err Msg should already be set
        event['pump'] = 'None'

    result = {
        "statusCode": status_code,
        "body": {
            "summary": event['sentinel_name'] + ' ' + event['pump_name'] + ' Change - ' + event['pump'],
            "msg": msg,
            "requested_change": event,
            "response_data": data,
            "system_status": devices
        },
    }
    print(json.dumps(result))
    return result
