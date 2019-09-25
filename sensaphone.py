import requests
from requests.exceptions import HTTPError
import json
import datetime


# defining the api-endpoint
LOGIN_ENDPOINT = "https://rest.sensaphone.net/api/v1/login"
DEVICE_ENDPOINT = "https://rest.sensaphone.net/api/v1/device"
DASHBOARD_ENDPOINT = "https://rest.sensaphone.net/api/v1/dashboard"
DEVICE_ZONE_ENDPOINT = "https://rest.sensaphone.net/api/v2/device/zone"
DATA_LOG_ENDPOINT = "https://rest.sensaphone.net/api/v1/history/data_log_points"
DATA2_LOG_ENDPOINT = "https://rest.sensaphone.net/api/v1/history/event_log"

device_data = {
    "request_type": "read",
    "resource": "device",
    "acctid": 100010835,
    "session": "c568645fca022fec2f12c483cef938ade0de",
"device": {
      "device_id":45275
     }
}

device_zone_data =  {
   "request_type": "read",
    "resource": "device",
    "acctid": 100010835,
    "session": "c568645fca022fec2f12c483cef938ade0de",
   "device":[
    {
      "device_id": 45275,
      "zone":[
       {
         "zone_id": 26,
         "output_zone": {
             "value": None
         }
       }
      ]
    }
   ]
 }


dashboard_data = {
    "request_type": "read",
    "resource": "dashboard",
    "acctid": 100010835,
    "session": "c568645fca022fec2f12c483cef938ade0de",
"dashboard": {
       "online_count": None,
       "device": [{
           "name": None
       }]
}}

data_log = {
 "request_type": "read",
 "acctid": 100010835,
 "session": "c568645fca022fec2f12c483cef938ade0de",
 "history":
   {
     "data_log_points": {
       "resource_type": "device",
       "device_id": 45275
     }
   }
 }

data2_log = {
 "request_type": "read",
 "acctid": 100010835,
 "session": "c568645fca022fec2f12c483cef938ade0de",
 "history":
   {
     "data_log": {
       "log_points" : [124369675],
       "begin_offset": 0,
       "record_offset": 150
     }
   }
 }


def sensaphone_request(url, data):

    try:
        response = requests.post(url=url, data=json.dumps(data))
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')
    else:
        print('Success!')
        return json.loads(response.content)


def login():
    """Login to sensaphone and collected session, acctind and session_experation
    Should handle username and password storage better in the future
    """

    username = 'brian.vermilion@gmail.com'
    password = '5z6DbBjTZKK2'
    login_data = {"request_type": "create", "resource": "login", "user_name": username, "password": password}
    url = 'https://rest.sensaphone.net/api/v1/login'
    r = sensaphone_request(url, login_data)
    print(r, type(r))
    if r['result']['success']:
        creds = {'session': r['response']['session'], 'acctid': r['response']['acctid'], 'session_expiration': str(datetime.datetime.fromtimestamp(r['response']['session_expiration'] + r['response']['login_timestamp']))}
        with open('creds.json', 'w') as fp:
            json.dump(creds, fp)
        return True
    else:
        print('Login Failure', r['result'])
        return False



def check_valid_session():
    """Check if current session id is valid. If not login"""

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
            return True
        else:
            return login()

"""
https://wiki.sensaphone.net/index.php/Sensaphone.net_API
Need automation account

What devices?
What is current values?
What is the history?
Change values?
"""

#login()
print(check_valid_session())