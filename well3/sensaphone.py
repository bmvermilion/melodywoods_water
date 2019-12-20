import requests
from requests.exceptions import HTTPError
import json
import datetime
import boto3
from base64 import b64decode
from urllib.parse import urlparse

account_id = None
session = None


def login():
    """
    Login to Sensaphone and collect session, acctid and session_expiration
    Should handle username and password storage better in the future for AWS
    """

    global account_id, session

    username = 'controls@melodywoods.awsapps.com'
    password = decrypt_password()
    login_data = {"request_type": "create", "resource": "login", "user_name": username, "password": password}
    url = 'https://rest.sensaphone.net/api/v1/login'

    print('Attempting to Login to Sensaphone')
    r = sensaphone_request(url, login_data)

    if r['result']['success']:
        creds = {'session': r['response']['session'], 'acctid': r['response']['acctid'], 'session_expiration': str(
            datetime.datetime.fromtimestamp(r['response']['session_expiration'] + r['response']['login_timestamp']))}
        #with open('creds.json', 'w') as fp:
        #    json.dump(creds, fp)

        account_id = creds['acctid']
        session = creds['session']
        print('Auth Success')
        return True
    else:
        print('Auth Failure Sensaphone Account ', r['result'])
        return False


def check_valid_session():
    """Check if current session id is valid. If not then login"""

    global account_id, session

    try:
        with open('creds.json', 'r') as fp:
            creds = json.load(fp)
    except FileNotFoundError:
        return login()
    else:
        session_expiration = datetime.datetime.strptime(creds['session_expiration'], '%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.now()
        time_till_expire = session_expiration - now

        if time_till_expire.total_seconds() / 3660 > 1.0:
            account_id = creds['acctid']
            session = creds['session']
            return True
        else:
            print("Sensaphone Creds Expired")
            return login()


def decrypt_password():

    with open('encrypted_controls.pem', 'r') as encrypted_pem:
        pem_file = encrypted_pem.read()

    kms = boto3.client('kms', region_name='us-west-2')
    return kms.decrypt(CiphertextBlob=b64decode(pem_file))['Plaintext'].decode("utf-8")


def sensaphone_request(url, data):
    try:
        response = requests.post(url=url, data=json.dumps(data))
        r = json.loads(response.text)

        if r['result']['success']:
            print('API Request Success! ' + urlparse(url).path)
            return r
        else:
            if r['result']['code'] == 2:
                print('Session Expired! How?', r)
                login()
                return False
            else:
                print(r)
                return False

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')


def get_all_device_id():
    """Get all if of devices connected to account"""

    global account_id, session

    url = 'https://rest.sensaphone.net/api/v1/device'
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": account_id,
        "session": session,
        "device": None
    }

    data = sensaphone_request(url, payload)
    print(json.dumps(data))
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


def device_info(device_id):
    """Get information about specific devices"""

    global account_id, session

    url = 'https://rest.sensaphone.net/api/v1/device'
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": account_id,
        "session": session,
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


def device_sensor_info(device_id, zone_id, pump_value):
    """Get information about a specific sensor on a device"""

    global account_id, session

    url = "https://rest.sensaphone.net/api/v1/device/zone"
    payload = {
        "request_type": "read",
        "resource": "device",
        "acctid": account_id,
        "session": session,
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


def device_history(device_id, zone_ids):
    """Get history of data log of a device"""

    # need to get log point then get history for log point....
    # log_points is an array...

    global account_id, session
    url = "https://rest.sensaphone.net/api/v1/history/data_log_points"

    payload = {
        "request_type": "read",
        "acctid": account_id,
        "session": session,
        "history":
            {
                "data_log_points": {
                    "resource_type": "device",
                    "device_id": device_id
                }
            }
    }

    data = sensaphone_request(url, payload)
    log_points = []
    for z in data['response']['history']['data_log_points']['log_points']:
        if z['zone_id'] in zone_ids:
            log_points.append(z['log_point'])

    # print(json.dumps(data))
    # exit(0)

    ts = sensaphone_timestamp(10)

    url = "https://rest.sensaphone.net/api/v1/history/data_log"

    payload = {
        "request_type": "read",
        "acctid": account_id,
        "session": session,
        "history":
            {
                "data_log": {
                    "log_points": log_points,
                    "start": ts
                }
            }
    }

    data = sensaphone_request(url, payload)
    print(json.dumps(data))
    exit(0)
    return data


def change_device_output(device_id, zone_id, pump_value):
    global account_id, session

    url = "https://rest.sensaphone.net/api/v1/device/zone"
    payload = {
        "request_type": "update",
        "resource": "device",
        "acctid": account_id,
        "session": session,
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


def sensaphone_timestamp(hours):
    delta = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    print(delta)

    ts = (delta.second % 60) + ((delta.minute * 60) % 3600) + ((delta.hour * 3600) % 86400) + (
                (delta.day * 86400) % 2678400) + ((delta.month * 2678400) % 32140800) + ((delta.year % 100 * 32140800))
    print(ts)
    return ts


"""
https://wiki.sensaphone.net/index.php/Sensaphone.net_API
Need automation account! Melody Woods email domain?

What devices?
What is current values?
What is the history?
Change values?
"""

"""
if check_valid_session():

    # Well #3
    device_id = 45275
    # Output
    zone_id = 26
    # log_point = 124369675

    # Set Well#3 Output
    data = device_sensor_info(device_id, zone_id)
    print(json.dumps(data))
    # data = get_all_device_id()
    # print(json.dumps(data))
    # exit(0)
    # data = device_info(device_id)
    # print(json.dumps(data))

    # device_history(device_id, zone_ids)

    # url = 'https://rest.sensaphone.net/api/v1/user'
    
    payload = {
        "request_type": "read",
        "resource": "user",
        "acctid": account_id,
        "session": session,
        "user": None
    }
    
    # print(account_id)
    # data = sensaphone_request(url, payload)
    # print(json.dumps(data))
    # exit(0)

else:
    print('Unable to login!')
"""
