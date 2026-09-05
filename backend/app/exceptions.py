class MetrixSenseError(Exception):
    pass


class OzonAPIError(MetrixSenseError):
    pass


class OzonAPIIntegratyError(OzonAPIError):
    pass


class OzonAPITimeOut(OzonAPIError):
    pass


class OzonAPIToManyRequests(OzonAPIError):
    pass


class OzonAPICompileReportError(OzonAPIError):
    pass


class SettingsError(MetrixSenseError):
    pass


class SecretsError(MetrixSenseError):
    pass


class CircuitOpenError(MetrixSenseError):
    """Предохранитель разомкнут: Ozon API недоступен"""
