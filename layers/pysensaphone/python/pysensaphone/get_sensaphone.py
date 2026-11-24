import requests
from requests.exceptions import HTTPError
import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def sensaphone_request(url: str, data: dict) -> dict:
    """
    Sensaphone Sentinel POST Request

    Parameters
    ----------
    url : str
        Expects the full URL for the Sensaphone REST API endpoint.
        See - https://wiki.sensaphone.net/index.php/Sensaphone.net_API
    data : dict
        payload for the request as specified by API docs.

    Returns
    -------
    dict
        return response as dict from Sensaphone REST API.
    """

    try:
        response = requests.post(url=url, data=json.dumps(data))
        r = json.loads(response.text)

        if r['result']['success']:
            if "password" in data:
                data['password'] = 'HIDDEN'
            logger.debug(f'sensaphone_request() data: \n{data}')
            logger.info(f'API Request Success! {urlparse(url).path}')
            return r
        else:
            if r['result']['code'] == 2:
                logger.warning(f'Session Expired! {r}')
                return False
            else:
                logger.error(f"sensaphone_request() failure, code: {r['result']['code']}")
                logger.error(json.dumps(r))
                return False

    except HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')
    except Exception as err:
        logger.error(f'Other error occurred: {err}')


def system_status(creds: dict) -> list:
    """
    Get all info of devices connected to account and gather high level system status

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()

    Returns
    -------
    list
        list of dictionaries that contains the device and zone (sensors) id, values and current status.
    """

    url = 'https://rest.sensaphone.net/api/v1/device'
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": creds['acctid'],
        "session": creds['session'],
        "device": None
    }

    data = sensaphone_request(url, payload)

    devices = []
    for d in data['response']['device']:
        sensors = []
        for z in d['zone']:
            if z['enable']:
                sensors.append(
                    {"name": z['name'], "zone_id": z['zone_id'], "sensor_type": z['type'], "units": z['units'],
                     "value": z['value']})
        devices.append({"name": d['name'], "device_id": d['device_id'], "description": d['description'],
                        "is_online": d['is_online'], "power_value": d['power_value'], "power_status": d['power_status'],
                        "battery_value": d['battery_value'], "battery_status": d['battery_status'], "zone": sensors})

    return devices


def device_info(creds: dict, device_id: int) -> list:
    """
    Get information about a specific Sensaphone device

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    device_id : int
        This the Sensaphone device id for which you want data for.

    Returns
    -------
    list
        list of dictionaries that contains the device and zone (sensors) id, values and current status.
    """

    url = 'https://rest.sensaphone.net/api/v1/device'
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": creds['acctid'],
        "session": creds['session'],
        "device": [
            {
                "device_id": device_id
            }
        ]
    }

    data = sensaphone_request(url, payload)

    devices = []
    for d in data['response']['device']:
        sensors = []
        for z in d['zone']:
            if z['enable']:
                sensors.append(
                    {"name": z['name'], "zone_id": z['zone_id'], "sensor_type": z['type'], "units": z['units'],
                     "value": z['value']})
        devices.append(
            {"name": d['name'], "device_id": d['device_id'], "description": d['description'], "zone": sensors})

    return devices


def device_zone_info(creds: dict, device_id: int, zone_id: int) -> list:
    """
    Get information about a specific zone (sensor/output) on a device

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    device_id : int
        This the Sensaphone device id for which you want data for.
    zone_id: int
        This is the id for the sensor (zone) you want data for.

    Returns
    -------
    list
        list of dictionaries that contains the device and zone (sensors) id, values and current status.
    """

    url = "https://rest.sensaphone.net/api/v1/device/zone"
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": creds['acctid'],
        "session": creds['session'],
        "device": [
            {
                "device_id": device_id,
                "zone": [
                    {
                        "zone_id": zone_id
                    }
                ]
            }
        ]
    }

    data = sensaphone_request(url, payload)

    return data
