class SensaphoneError(Exception):
    """Base exception for Sensaphone project"""
    pass

class SensaphoneAuthError(SensaphoneError):
    """Raised when authentication fails"""
    pass

class SensaphoneAPIError(SensaphoneError):
    """Raised when the API returns a failure or malformed data"""
    def __init__(self, message, code=None, response=None):
        super().__init__(message)
        self.code = code
        self.response = response

class WaterLogicError(SensaphoneError):
    """Raised when water logic discovery or parsing fails"""
    pass
