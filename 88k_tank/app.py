from pysensaphone import sensaphone_auth
from pysensaphone import set_sensaphone
from pysensaphone import get_sensaphone
import json


def lambda_handler(event, context):

    shutoff_level = 23.4
    turnon_level = 20

    creds = sensaphone_auth.check_valid_session()

    devices = get_sensaphone.system_status(creds)
    # Current System Status
    for d in devices:
        if d['name'] == 'TreatmentPlant':
            # TP Sentinel
            device_id = d['device_id']
            tp_is_online = d['is_online']
            tp_power = d['power_value']
            for z in d['zone']:
                if z['name'] == '88k Pump':
                    pump_88k = z['value']
                    # Output #1 - 88k 5hp
                    zone_id = z['zone_id']
        elif d['name'] == '88kTank':
            # 88k Sentinel
            for z in d['zone']:
                if z['name'] == '88k Level':
                    level_88k = float(z['value'].strip('Ft'))

    # Lambda Event Payload
    if event['pump'] == 'off':
        pump_value = 0
        msg = event
    elif event['pump'] == 'on':
        # 9PM turn the pump on, or after power has been restored (future Lambda).
        pump_value = 1
        msg = event
    else:
        if level_88k > shutoff_level:
            # Turn off pump as 88k is full
            pump_value = 0
            msg = '88k Level High ' + str(level_88k)
        elif level_88k < turnon_level:
            # Turn on pump 88k is low, likely have a leak or high usage.
            pump_value = 1
            msg = '88k Level Low ' + str(level_88k)
        else:
            # No Output Changes needed
            pump_value = None


    # Set 88k Output
    if tp_power == "On" and pump_value is not None:
        data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
        if data['result']['success']:
            status_code = 200
        else:
            status_code = data['result']['code']
    elif tp_power == "Off":
        msg = 'TP Power Out'
        data = None
        status_code = 503
    else:
        msg = "No Output Change Needed"
        data = None
        status_code = 200

    result = {
        "statusCode": status_code,
        "body": {
            "zone": "TP 88k 5hp Pump Output",
            "summary": msg,
            "data": data,
            "system_status": devices
        },
    }
    print(json.dumps(result))
    return result
