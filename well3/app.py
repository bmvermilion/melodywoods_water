import sensaphone


def lambda_handler(event, context):

    if sensaphone.check_valid_session():
        # Well #3
        device_id = 45275
        # Sentinel Output
        zone_id = 26

        if event['pump'] == 'off':
            pump_value = 0
        elif event['pump'] == 'on':
            pump_value = 1
        else:
            pump_value = None
            data = 'Invalid Pump Value!'

        # Set Well#3 Output
        data = sensaphone.change_device_output(device_id, zone_id, pump_value)

    else:
        data = 'Auth failed to Sensaphone!'

    return {
        "statusCode": 200,
        "body": {
            "message": "Well#3 Output Change: " + event['pump'],
            "data": data
        },
    }
