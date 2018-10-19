# -*- coding: utf-8 -*-


class PyGoBGPBaseError(Exception):
    """Base exception class for this module"""

    def __init__(self, msg, cause=None):
        super(Exception, self).__init__(msg)
        self._cause = cause

    @property
    def cause(self):
        """The underlying exception causing the error, if any."""
        return self._cause


class PeerNotFound(PyGoBGPBaseError):
    """
        BGP Peer not found
    """
    pass
