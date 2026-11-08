"""Device backends. Only this package may talk to adb, ldconsole or win32 (see docs/CONSTRAINTS.md)."""

from cob.device.base import Device, DeviceError, ResolutionMismatch

__all__ = ["Device", "DeviceError", "ResolutionMismatch"]
