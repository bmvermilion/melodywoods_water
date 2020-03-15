from pysensaphone import sensaphone_auth
from pysensaphone import set_sensaphone
from pysensaphone import get_sensaphone
#import json
import datetime
import dateutil.tz

def lambda_handler(event, context):

    shutoff_level = 23.3
    shutoff_noon_level = 23.0
    turnon_level = 20

    # Get current Pacific time. AWS Lambda event triggers operate in UTC.
    pacific = dateutil.tz.gettz('US/Pacific')
    current_pacific_time = datetime.datetime.now(tz=pacific)
    utc = dateutil.tz.gettz('UTC')
    current_utc_time = datetime.datetime.now(tz=utc)

    # Login to sensaphone.net
    creds = sensaphone_auth.check_valid_session()

    # Current System Status
    devices = get_sensaphone.system_status(creds)

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

    # Process Lambda Event Payload
    msg = None
    if event['pump'] == 'off':
        pump_value = 0
        msg = event
    elif event['pump'] == 'on':
        # 9PM turn the pump On, or after power has been restored (future Lambda).
        # PDT - 9PM / 4 UTC
        # PST - 9PM / 5 UTC
        if current_pacific_time.hour == 21:
            pump_value = 1
            msg = event
        else:
            pump_value = None
            msg = 'Currently ' + current_pacific_time.strftime("%I%p %Z") + ' / '\
                  + current_utc_time.strftime("%I%p %Z") + ' - Pump will turn On at 9PM Pacific'
    else:
        if level_88k > shutoff_level:
            # Turn Off pump as 88k is full
            pump_value = 0
            msg = '88k Level at High Limit ' + str(level_88k)
        elif level_88k > shutoff_noon_level and current_pacific_time.hour >= 12:
            # If it is after 12PM/Noon and 88k tank is > 23ft shutoff 5hp
            # Attempt to even out, pumping during lower $/kW when water usage is higher
            pump_value = 0
            msg = '88k Level at Noon High Limit ' + str(level_88k)
        elif level_88k < turnon_level:
            # Turn on pump 88k is low, likely have a leak or very very high usage.
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
    # In the future when power Off/On email received could shut pumps Off/On
    # To avoid tripped breakers when power comes back On
    elif tp_power == "Off":
        msg = 'TP Power Out'
        data = None
        status_code = 503
    else:
        if not msg:
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
    #print(json.dumps(result))
    return result
