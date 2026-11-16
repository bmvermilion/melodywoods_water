from pysensaphone import sensaphone_auth, get_sensaphone, set_sensaphone, water_logic
import json
import logging
import datetime

# quiet boto3 message
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def change_pump(event, creds, device_id, zone_id, power, current_pump_value, requested_pump_value):
    """Change pump output with safety checks."""
    data = None
    event['pump'] = None
    
    if requested_pump_value.lower() == str(current_pump_value).lower():
        return 200, 'Requested Pump Value Change Not Required, Value Already Set', None

    if power == "On":
        pump_value = 1 if requested_pump_value.lower() == 'on' else 0
        
        if water_logic.DRY_RUN:
            logger.info(f"DRY RUN: Would have set Device {device_id} Zone {zone_id} to {pump_value}")
            data = {'result': {'success': True}, 'dry_run': True}
        else:
            data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
            
        if data['result']['success']:
            event['pump'] = requested_pump_value
            return 200, 'Success', data
        return data['result']['code'], 'Failure', data
    
    return 409, f'Power is {power}', None

def lambda_handler(event, context):
    params = {
        'well3': ['well3_on', 'well3_off'], 
        'well5': ['well5_on', 'well5_off'],
        'spring': ['spring_on', 'spring_off']
    }
    
    # Initialization
    creds = sensaphone_auth.check_valid_session()
    devices = get_sensaphone.system_status(creds)
    current_time = water_logic.get_pacific_time()

    # Find target device and zone
    device = water_logic.find_device(devices, event['sentinel_name'])
    zone = water_logic.find_zone(device, event['pump_name'])
    
    if not device or not zone:
        return water_logic.format_lambda_result(404, "Target Not Found", f"Device {event['sentinel_name']} or Zone {event['pump_name']} not found", None, devices, event)

    device_id = device['device_id']
    power = device['power_value']
    zone_id = zone['zone_id']
    current_pump_value = zone['value']

    status_code, msg, pdata = 200, "No action taken", None
    reason_type = event['reason']['type'].lower()

    # 1. Scheduled Timer Logic
    if reason_type in params:
        # Defaults based on standard operating documentation
        on_timer = water_logic.get_ssm_param(params[reason_type][0], default_value="21:00")
        off_timer = water_logic.get_ssm_param(params[reason_type][1], default_value="10:00")

        if water_logic.is_within_window(on_timer, current_time):
            status_code, msg, pdata = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
        elif water_logic.is_within_window(off_timer, current_time):
            status_code, msg, pdata = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'off')
        else:
            msg = f"{reason_type} - Not time to change pump output"

    # 2. Email/Intermittent Alert Logic
    elif reason_type in ['email_alarm', 'intermittent_pumping']:
        if event['pump'] == 'on':
            # Specific logic for Well #3: only turn on if within the broad daily window
            if event['pump_name'] == '#3 Well Pump':
    well3_on_hour_param = water_logic.get_ssm_param('well3_on', default_value="21:00")
                well3_off_hour_param = water_logic.get_ssm_param('well3_off', default_value="10:00")
                on_hour = int(well3_on_hour_param.split(":")[0])
                off_hour = int(well3_off_hour_param.split(":")[0])
                current_hour = current_time.hour
                
                if (current_hour >= on_hour) or (current_hour <= off_hour):
                    status_code, msg, pdata = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
                else:
                    msg = f"{reason_type} Well#3 - Outside allowed hours"
            else:
                # Default behavior for others is to turn on
                status_code, msg, pdata = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'on')
        elif event['pump'] == 'off':
            status_code, msg, pdata = change_pump(event, creds, device_id, zone_id, power, current_pump_value, 'off')

    # Result Formatting
    summary = f"{event['sentinel_name']} - {event['pump_name']} Change - {event.get('pump', 'None')}"
    return water_logic.format_lambda_result(status_code, summary, msg, pdata, devices, event)
