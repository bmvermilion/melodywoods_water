import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SensaphoneEmailParser:
    """
    Parses Sensaphone alert emails to extract Sentinel names, 
    alarm types, and power status.
    """
    
    def __init__(self, email_body: str):
        self.body = email_body
        self.lines = email_body.splitlines()

    def get_sentinel_name(self) -> Optional[str]:
        """Extracts the Sentinel device name from the 'From:' line area."""
        for idx, line in enumerate(self.lines):
            if 'From:' in str(line):
                try:
                    # The name is usually on the line immediately following 'From:'
                    return self.lines[idx + 1].strip()
                except IndexError:
                    return None
        return None

    def find_chlorine_alarm(self) -> Optional[float]:
        """
        Looks for Chlorine Barrel Low alerts.
        Returns the level as a float if found, else None.
        """
        for line in self.lines:
            if 'alarm' in line.lower():
                # Regex for "Low level alarm ... Chlorine Barrel Level"
                if re.search(r"Low level alarm .+ Chlorine Barrel Level", line, re.I):
                    # Extract the numeric level (handles negative and decimals)
                    match = re.search(r"(-?\d+\.\d+)", line)
                    if match:
                        return float(match.group(1))
        return None

    def get_power_status(self) -> Optional[str]:
        """
        Detects power status changes.
        Returns 'OFF', 'NORMAL', or None.
        """
        for line in self.lines:
            if 'power' in line.lower():
                if re.search(r"The power is OFF", line, re.I):
                    return 'OFF'
                if re.search(r"The power has returned to normal", line, re.I):
                    return 'NORMAL'
        return None
