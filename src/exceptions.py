class EarlyResponseException(Exception):
    status = 200
    body = None


class Error(Exception):
    pass


class BeforeRecordError(Error):
    status = 500


class ForbiddenError(BeforeRecordError):
    status = 403
