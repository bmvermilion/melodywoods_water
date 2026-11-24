from .get_sensaphone import sensaphone_request


def change_device_output(creds: dict, device_id: int, zone_id: int, pump_value: int) -> list:
    """Change a Sensaphone output on a device

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    device_id : int
        Sentinel device id for which you want to change an output.
    zone_id : int
        List of sensor names for which you want data.
    pump_value : int
        Set Sentinel output on (1) or off (0).

    Returns
    -------
    list
        response from Sensaphone returned as a list of dictionaries.
    """

    url = "https://rest.sensaphone.net/api/v1/device/zone"
    payload = {
        "request_type": "update",
        "resource": "device",
        "acctid": creds['acctid'],
        "session": creds['session'],
        "device": [
            {
                "device_id": device_id,
                "zone": [
                    {
                        "zone_id": zone_id,
                        "output_zone": {
                            "value": pump_value
                        }
                    }
                ]
            }
        ]
    }

    data = sensaphone_request(url, payload)

    return data
