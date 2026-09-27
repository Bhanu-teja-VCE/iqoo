"""
Sentinel Chaos Failure Injection Package.
"""

from sentinel.chaos.faults import FaultClass
from sentinel.chaos.injector import FailureInjector

__all__ = [
    "FaultClass",
    "FailureInjector",
]
