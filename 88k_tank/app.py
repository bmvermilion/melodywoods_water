from pysensaphone import sensaphone_auth, get_sensaphone, set_sensaphone, water_logic
import json
import logging

# quiet boto3 message
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    # Initialization
    creds = sensaphone_auth.check_valid_session()
    devices = get_sensaphone.system_status(creds)
    current_time = water_logic.get_pacific_time()

    # Load Dynamic Thresholds
    shutoff_level = float(water_logic.get_ssm_param('shutoff_level_88k', default_value=23.3))
    shutoff_noon_level = float(water_logic.get_ssm_param('shutoff_noon_level_88k', default_value=22.8))

    # Locate Devices
    tp_device = water_logic.find_device(devices, 'TreatmentPlant')
    tank_device = water_logic.find_device(devices, '88kTank')

    if not tp_device or not tank_device:
        return water_logic.format_lambda_result(404, "Device Discovery Failure", "TP or Tank device not found", None, devices, event)

    # TP Data
    pump_zone = water_logic.find_zone(tp_device, '88k Pump')
    device_id = tp_device['device_id']
    tp_power = tp_device['power_value']
    zone_id = pump_zone['zone_id'] if pump_zone else None

    # Tank Data
    level_zone = water_logic.find_zone(tank_device, '88k Level')
    tank_power = tank_device['power_value']
    level_88k = water_logic.parse_tank_level(level_zone['value']) if level_zone else 0.0

    # Logic Engine
    pump_value = None
    msg = "No Output Change Needed"

    if event.get('pump') == 'off':
        pump_value = 0
        msg = "Explicit OFF requested"
    elif event.get('pump') == 'on':
        # Scheduled ON (9PM)
        if current_time.hour == 21:
            pump_value = 1
            msg = "Scheduled 9PM ON triggered"
        else:
            pump_value = None
            msg = f"Currently {current_time.strftime('%I%p %Z')} - Pump will turn on at 9PM"
    else:
        # Autonomous Level Checks
        if level_88k > shutoff_level:
            pump_value = 0
            msg = f'88k Level at High Limit {level_88k}'
        elif level_88k > shutoff_noon_level and (12 <= current_time.hour < 21):
            pump_value = 0
            msg = f'88k Level at Noon High Limit {level_88k}'
        elif level_88k < shutoff_noon_level and current_time.hour <= 7:
            pump_value = 1
            msg = f'88k Level Morning Low Optimization {level_88k}'

    # Execution with Power Safety
    status_code = 200
    data = None
    
    if (tp_power == "On" and tank_power == "On") and pump_value is not None:
        if water_logic.DRY_RUN:
            logger.info(f"DRY RUN: Would have set Device {device_id} Zone {zone_id} to {pump_value}")
            data = {'result': {'success': True}, 'dry_run': True}
            status_code = 200
        else:
            data = set_sensaphone.change_device_output(creds, device_id, zone_id, pump_value)
            status_code = 200 if data['result']['success'] else data['result']['code']
    elif tp_power == "Off" or tank_power == "Off":
        msg = f'Power Out - TP {tp_power} - 88k {tank_power}. Shutting off for safety.'
        data = set_sensaphone.change_device_output(creds, device_id, zone_id, 0)
        status_code = 503

    return water_logic.format_lambda_result(status_code, "88k Pump Control", msg, data, devices, event)
