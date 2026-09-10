"""The supervisor: one tick a minute launches, watches, stops and kills one worker per
instance (ported from the legacy PowerShell watchdog)."""

from brawlfarm.supervisor.loop import Supervisor
from brawlfarm.supervisor.state import Health, InstanceState, InstanceView

__all__ = ["Health", "InstanceState", "InstanceView", "Supervisor"]
