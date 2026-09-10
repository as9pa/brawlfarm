"""Onboarding safety rails: the farm-instance refusal set is DERIVED from
config.INSTANCES, so adding a 4th account automatically protects it — a hardcoded
port tuple (the pre-rail state) would silently leave a new farm signable-over.

Run:  uv run pytest tests/test_onboarding_rails.py -q
"""

from __future__ import annotations

import pytest

from brawlfarm.core import config, onboarding

# The rail is derived, so the registered set is whatever the user registered; these
# stand-ins exist only to give the derivation something to derive from.
INSTANCES = {
    "Pie64": {"port": "5555", "tag": "", "data": "data/Pie64"},
    "Nest32": {"port": "5565", "tag": "", "data": "data/Nest32"},
}


@pytest.fixture(autouse=True)
def _registered():
    config.set_instances(INSTANCES)


def test_farm_ports_derived_from_config_instances():
    # the rail's port set must be exactly the registered farm instances' ports
    assert onboarding.farm_ports() == {inst["port"] for inst in config.INSTANCES.values()}


def test_use_port_refuses_every_farm_instance():
    # the refuse-to-sign-in rail: an account-login flow may never target a farm
    # instance (logging a farm account out would be a serious incident)
    assert config.INSTANCES, "the rail is vacuous with no registered instances"
    for inst in config.INSTANCES.values():
        with pytest.raises(onboarding.OnboardError):
            onboarding._use_port(inst["port"], allow_farm_instance=False)
