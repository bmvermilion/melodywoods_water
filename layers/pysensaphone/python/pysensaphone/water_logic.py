import datetime
import dateutil.tz
import boto3
import logging
import re
import os
import json
from typing import List, Dict, Any, Union, Optional
from .exceptions import WaterLogicError

logger = logging.getLogger(__name__)

# Global flag to prevent actual API writes
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

def get_pacific_time() -> datetime.datetime:
    """Returns the current time in US/Pacific timezone."""
    pacific = dateutil.tz.gettz('US/Pacific')
    return datetime.datetime.now(tz=pacific)

def find_device(devices: List[Dict[str, Any]], device_name: str) -> Optional[Dict[str, Any]]:
    """Finds a device by name in the system status list."""
    for device in devices:
        if device['name'] == device_name:
            return device
    return None

def find_zone(device: Optional[Dict[str, Any]], zone_name: str) -> Optional[Dict[str, Any]]:
    """Finds a zone (sensor/output) by name within a device."""
    if not device or 'zone' not in device:
        return None
    for zone in device['zone']:
        if zone['name'] == zone_name:
            return zone
    return None

def get_ssm_param(param_name: str, default_value: Optional[Union[str, float]] = None) -> Optional[str]:
    """
    Retrieves a parameter from AWS SSM Parameter Store.
    If missing, returns default_value and logs a CRITICAL warning.
    """
    ssm = boto3.client('ssm')
    try:
        parameter = ssm.get_parameter(Name=param_name)
        return parameter['Parameter']['Value']
    except Exception as e:
        if default_value is not None:
            logger.critical(f"!!! MISSING SSM PARAMETER: {param_name} !!! "
                            f"Using hardcoded fallback: {default_value}. "
                            f"Please restore this parameter in the AWS SSM Console. Error: {e}")
            return str(default_value)
        else:
            logger.error(f"Error retrieving SSM parameter {param_name} and no fallback provided: {e}")
            return None

def is_within_window(timer_str: str, current_time: datetime.datetime, window_minutes: int = 15) -> bool:
    """
    Checks if the current time is within a window (default 15 mins) of the target timer.
    timer_str: "HH:MM" format.
    """
    if not timer_str:
        return False
        
    try:
        hour, minute = map(int, timer_str.split(':'))
        target_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Difference in minutes
        diff_minutes = (target_time - current_time).total_seconds() / 60
        
        # Logic from supply/app.py: 15 > on_mins >= -1
        return window_minutes > diff_minutes >= -1
    except ValueError:
        logger.error(f"Invalid timer format: {timer_str}")
        return False

def is_within_daily_window(
    on_str: Optional[str],
    off_str: Optional[str],
    current_time: datetime.datetime,
) -> bool:
    """
    Checks if current_time falls inside a broad daily window that may wrap past midnight.

    on_str/off_str: "HH:MM" format. Bounds are inclusive.
    Example: on "21:30", off "10:30" is True at 22:00 and 09:00, False at 21:15 and 11:00.

    Minute precision matters: a naive hour-only comparison treats 21:15 as inside a
    21:30 window, so this is the authoritative check for Well#3 email triggers.
    """
    if not on_str or not off_str:
        logger.error(f"Missing daily window bounds: on={on_str!r} off={off_str!r}")
        return False

    try:
        on_hour, on_minute = map(int, on_str.split(':'))
        off_hour, off_minute = map(int, off_str.split(':'))
    except ValueError:
        logger.error(f"Invalid daily window format: on={on_str!r} off={off_str!r}")
        return False

    if not (0 <= on_hour <= 23 and 0 <= on_minute <= 59
            and 0 <= off_hour <= 23 and 0 <= off_minute <= 59):
        logger.error(f"Daily window out of range: on={on_str!r} off={off_str!r}")
        return False

    now = current_time.hour * 60 + current_time.minute
    start = on_hour * 60 + on_minute
    end = off_hour * 60 + off_minute

    if start <= end:
        return start <= now <= end
    # Window wraps midnight, e.g. 21:30 -> 10:30
    return now >= start or now <= end

def parse_tank_level(value_str: str) -> float:
    """Parses a tank level string like '22.555 Ft' into a float."""
    if not value_str:
        return 0.0
    # Strip 'Ft', ' Feet', etc.
    clean_val = re.sub(r'[^\d.]', '', value_str)
    try:
        return float(clean_val)
    except ValueError:
        logger.error(f"Could not parse tank level: {value_str}")
        return 0.0

def format_lambda_result(status_code: int, summary: str, msg: str, data: Optional[Dict[str, Any]], 
                         system_status: List[Dict[str, Any]], requested_change: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standardizes the result dictionary returned by Lambda functions."""
    if DRY_RUN:
        msg = f"[DRY RUN] {msg}"
        logger.info(f"DRY RUN ENABLED: Skipping actual Sensaphone output change for {summary}")

    result = {
        "statusCode": status_code,
        "body": {
            "summary": summary,
            "msg": msg,
            "data": data,
            "system_status": system_status
        }
    }
    if requested_change:
        result["body"]["requested_change"] = requested_change
    
    # CloudWatch logging
    logger.info(json.dumps(result))
    return result
