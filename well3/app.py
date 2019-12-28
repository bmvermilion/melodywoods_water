from pysensaphone import sensaphone_auth
from pysensaphone import get_sensaphone
from pysensaphone import set_sensaphone
import json


def lambda_handler(event, context):

    creds = sensaphone_auth.check_valid_session()

    devices = get_sensaphone.system_status(creds)
    # Current System Status
    for d in devices:
        if d['name'] == 'Well#3':
            # Well#3 Sentinel
            device_id = d['device_id']
            is_online = d['is_online']
            power = d['power_value']
            for z in d['zone']:
                if z['name'] == '#3 Well Pump':
                    pump_well3 = z['value']
                    # Output #1 - Well#3 Pump
                    zone_id = z['zone_id']

    if event['pump'] == 'off':
        pump_value = 0
    elif event['pump'] == 'on':
        pump_value = 1
    else:
        pump_value = None
        data = 'Invalid Pump Value!'

    # Set Well#3 Output
    if power == "On" and pump_value is not None:
        data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
        if data['result']['success']:
            status_code = 200
        else:
            status_code = data['result']['code']
    else:
        status_code = 400
        data = None

    result = {
        "statusCode": status_code,
        "body": {
            "zone": "Well#3 Output Change - " + event['pump'],
            "summary": event,
            "data": data,
            "system_status": devices
        },
    }
    print(json.dumps(result))
    return result

