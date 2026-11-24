from .get_sensaphone import sensaphone_request, system_status
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def get_history(creds: dict, hours: int, device_name: str, zone_names: list) -> pd.DataFrame:
    """Get Sentinel Sensor History

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    hours : int
        Data window specified in hours (int)
    device_name : str
        Sentinel device name for which you want sensor history from.
    zone_names : list
        List of sensor names for which you want data.

    Returns
    -------
    DataFrame
        a DataFrame with sensor data from Sentinel for specified window.

    TODO
    -------
    Change 'hours' to a more flexible window variable taking a number and units.
    Example 5D (5 days), 2W (2 weeks), 1M (1 month).
    """

    # Get device_id and zone_id/s, this is needed to get log points
    id_data = get_ids(creds, device_name, zone_names)
    # Get log_points (sensor id)
    log_points = get_device_log_points(creds, id_data)

    begin_offset = 0
    # hours * 4 data point every hour  * number of sensors data requested for.
    # (data point every 15 mins - configurable in Sensaphone)
    record_offset = ((hours * 4) + 1) * len(log_points[0])
    data_log = get_data_log(creds, begin_offset, record_offset, log_points[0])

    # merge the sensor data with metadata details about Sentinel and sensors
    data = pd.merge(data_log, log_points[1], left_on='variable', right_on='log_point')
    return data


def get_ids(creds: dict, device_name: str, zone_names: list) -> pd.DataFrame:
    """Get id for Sentinel (device_name) and Sensors (zone_name)

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    device_name : str
        Sentinel device name for which you want sensor history from.
    zone_names : list
        List of sensor names for which you want data.

    Returns
    -------
    DataFrame
        a DataFrame with pairs of name and id for device and zone.
    """

    devices = system_status(creds)

    df = pd.DataFrame(columns=['device_name', 'device_id', 'zone_name', 'zone_id', 'log_point'])
    for d in devices:
        if d['name'] == device_name:
            for z in d['zone']:
                if z['name'] in zone_names:
                    df = df.append({'device_name': d['name'], 'device_id': d['device_id'], 'zone_name': z['name'],
                                    'zone_id': z['zone_id']}, ignore_index=True)
    return df


def get_device_log_points(creds: dict, df: pd.DataFrame) -> list:
    """Obtain log_point ids (sensor data id) for Sensaphone device

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    df : pd.DataFrame
        Dataframe to append log_point (id for sensor data) to Sentinel and Sensor id.

    Returns
    -------
    list
        list of log point ids.
    DataFrame
        a DataFrame with pairs of name and id for device and zone. Log point is the data id for the sensor.
    """

    if len(df.device_id.unique()) == 1:
        device_id = df.device_id.unique()[0]
    else:
        logger.error('Error, why do we have more than one device id?')
        logger.error(df)
        logger.error(df.device_id.unique())
        device_id = None

    url = "https://rest.sensaphone.net/api/v1/history/data_log_points"

    payload = {
        "request_type": "read",
        "acctid": creds['acctid'],
        "session": creds['session'],
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
        if z['zone_id'] in df.zone_id.unique():
            df['log_point'][df['zone_id'] == z['zone_id']] = z['log_point']
            log_points.append(z['log_point'])

    return log_points, df


def get_data_log(creds: dict, begin_offset: int, record_offset: int, log_points: list) -> pd.DataFrame:
    """ Get the data for specified sensors.
    Specified by position from latest data point (begin_offset) and number of data points (record_offset).

    Parameters
    ----------
    creds : dict
        Sensaphone credentials returned from sensaphone_auth.sensaphone_login()
    begin_offset : int
        Offset from most recent record (0 is most recent record). 'Start'
    record_offset : int
        Number of records to retrieve, offset from the beginning record. 'End'
    log_points : list
        list of log points (sensor data id) to pull data for.

    Returns
    -------
    DataFrame
        a DataFrame with sensor data that was requested.
    """

    url = "https://rest.sensaphone.net/api/v1/history/data_log"

    payload = {
        "request_type": "read",
        "acctid": creds['acctid'],
        "session": creds['session'],
        "history":
            {
                "data_log": {
                    "log_points": log_points,
                    "begin_offset": begin_offset,
                    "record_offset": record_offset,
                }
            }
    }

    data = sensaphone_request(url, payload)

    if data['result']['success'] and len(data['response']['history']['data_log']) > 0:
        # create dataframe from response
        df_data = pd.DataFrame(data['response']['history']['data_log'])
    else:
        logger.error('ERROR Datalog - No data returned')
        logger.error(json.dumps(data['result']))
        df_data = None

    return df_data
