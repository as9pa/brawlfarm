"""CI guard: importing config must work with NO .env file and NO BRAWL_*/DISCORD_* env.

The CI runner has no .env and never will — no secrets in CI is an absolute rail.
config.py tolerates a missing .env today (``load_dotenv`` on a missing path is a
no-op, every ``os.environ.get`` has a default); this test pins that property so an
import-time hard requirement can't sneak in and break every PR.

Deliberately runner-independent: instead of trusting that the checkout has no .env
(a dev machine running the suite usually HAS one), the test points BRAWLFARM_HOME at
an empty temp dir — so config looks for .env somewhere guaranteed empty — and imports
it in a clean subprocess with the farm/Discord env vars stripped.
"""

import os
import subprocess
import sys


def test_config_imports_with_no_env_file(tmp_path):
    # Strip every project env var; keep the rest (PATH/SYSTEMROOT etc. — Python
    # itself needs those on Windows).
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("BRAWL_", "DISCORD_"))
    }
    env["BRAWLFARM_HOME"] = str(tmp_path)

    proc = subprocess.run(
        [sys.executable, "-c", "from brawlfarm.core import config; print(config.ADB_SERIAL)"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"config failed to import without .env:\n{proc.stderr}"
    # Defaults survived the stripped env (ADB host:port falls back to 127.0.0.1:5555).
    assert proc.stdout.strip() == "127.0.0.1:5555"
