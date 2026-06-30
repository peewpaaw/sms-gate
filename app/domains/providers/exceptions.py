class ProviderNotFoundError(Exception):
    """Provider code is not in catalog."""


class ProviderDisabledError(Exception):
    """Provider exists but is not enabled for new mailings."""


class ProviderNotImplementedError(Exception):
    """Provider is in catalog but has no runtime adapter."""
