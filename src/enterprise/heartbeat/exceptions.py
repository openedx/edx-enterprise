"""
Exceptions for use by enterprise heartbeat module.
"""


class ServiceNotAvailable(Exception):
    """
    All heartbeat service status exception inherit from this excepton.
    """
    message = ''
    service_name = ''

    def __init__(self, message, service_name, *args):
        super().__init__(*args)
        self.message = message
        self.service_name = service_name


class EcommerceNotAvailable(ServiceNotAvailable):
    """
    Raised when E-Commerce service is not available.
    """
    service_name = 'E-Commerce'

    def __init__(self, message, *args):
        super().__init__(message, self.service_name, *args)


class DiscoveryNotAvailable(ServiceNotAvailable):
    """
    Raised when Course Discovery service is not available.
    """
    service_name = 'Course Discovery'

    def __init__(self, message, *args):
        super().__init__(message, self.service_name, *args)


class LMSNotAvailable(ServiceNotAvailable):
    """
    Raised when Learning Management System (LMS) service is not available.
    """
    service_name = 'Learning Management System (LMS)'

    def __init__(self, message, *args):
        super().__init__(message, self.service_name, *args)


class EnterpriseCatalogNotAvailable(ServiceNotAvailable):
    """
    Raised when Enterprise Catalog service is not available.
    """
    service_name = 'Enterprise Catalog'

    def __init__(self, message, *args):
        super().__init__(message, self.service_name, *args)
