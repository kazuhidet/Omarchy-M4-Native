# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Audrey Tang
"""Exercise the standalone J715 backlight packaging files in a scratch root."""
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_j715_display_profile import ROOT, environment, load

BASE = "usr/lib/omarchy-m4/backlight/j715/"


class BacklightPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name) / "root"
        cls.env = environment()
        targets = {
            "usr/bin/m4-j715-backlight": ("packaging/j715-backlight/m4-j715-backlight", 0o755),
            "usr/lib/systemd/system/m4-j715-backlight.service":
                ("packaging/j715-backlight/m4-j715-backlight.service", 0o644),
            "usr/lib/udev/rules.d/90-j715-backlight.rules":
                ("packaging/j715-backlight/90-j715-backlight.rules", 0o644),
            BASE + "display/j715/profile.schema.json": ("display/j715/profile.schema.json", 0o644),
        }
        for helper in ("m4-j715-backlight.py", "m4-backlight.py", "j715_sources.py", "j715_display_profile.py"):
            targets[BASE + "tools/" + helper] = ("tools/" + helper, 0o644)
        for rel, (source, mode) in targets.items():
            dest = cls.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, dest)
            dest.chmod(mode)

    def test_installed_layout_imports_and_board_gate_work_without_host_writes(self):
        helper = self.root / BASE / "tools/m4-j715-backlight.py"
        compatible = self.root / "sys/firmware/devicetree/base/compatible"
        compatible.parent.mkdir(parents=True)
        for board, code in ((b"apple,j713\0apple,t8132\0", 1),
                            (b"apple,j715\0apple,t8112\0", 1),
                            (b"apple,j715\0apple,j713\0apple,t8132\0", 1),
                            (b"apple,j715\0apple,t8132\0", 0)):
            compatible.write_bytes(board)
            result = subprocess.run([sys.executable, "-B", str(helper), "--supported",
                                     "--root", str(self.root)], env=self.env, capture_output=True,
                                    text=True, check=False)
            self.assertEqual(result.returncode, code, result.stderr)
        self.assertFalse((self.root / "var/lib/omarchy-m4").exists())
        sys.path.insert(0, str(helper.parent))
        self.addCleanup(sys.path.remove, str(helper.parent))
        profile = load("j715_installed_profile", str(self.root / BASE / "tools/j715_display_profile.py"))
        self.assertTrue(profile.parse(ROOT / "tests/fixtures/j715-display-synthetic.json").synthetic)

    def test_installed_permissions_and_absent_private_assets(self):
        for path in self.root.rglob("*"):
            if not path.is_file() or not path.relative_to(self.root).as_posix().startswith("usr/"):
                continue
            with self.subTest(path=path.relative_to(self.root).as_posix()):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o7022, 0)
        self.assertFalse((self.root / BASE / "profile.json").exists())
        self.assertFalse((self.root / BASE / "j715_dcp_backlight.ko").exists())

    def test_shipped_j713_backlight_package_is_unchanged(self):
        pkgbuild = (ROOT / "packaging/omarchy-m4/omarchy-m4-backlight/PKGBUILD").read_text()
        self.assertIn("pkgrel=1", pkgbuild)
        self.assertNotIn("j715", pkgbuild)
        channel = json.loads((ROOT / "packaging/omarchy-m4/channel.json").read_bytes())
        self.assertFalse(any("j715" in path for path in channel["allowed_paths"]["omarchy-m4-backlight"]))

    def test_service_gates_assets_before_activation_and_keys(self):
        unit = self.root / "usr/lib/systemd/system/m4-j715-backlight.service"
        directives = {}
        for line in unit.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                directives.setdefault(key, []).append(value)
        self.assertEqual(set(directives["ConditionPathExists"]), {
            "/" + BASE + name for name in ("j715_dcp_backlight.ko", "module.json", "profile.json")})
        self.assertEqual(directives["ExecCondition"], ["/usr/bin/m4-j715-backlight --supported"])
        self.assertEqual(directives["ExecStart"], ["/usr/bin/m4-j715-backlight --boot"])
        self.assertEqual(directives["ExecStartPost"], ["/usr/bin/m4-j715-backlight --keys-hook"])
        self.assertEqual(directives["TimeoutStartSec"], ["30"])

    def test_udev_rule_targets_only_native_panel_brightness(self):
        rule = (self.root / "usr/lib/udev/rules.d/90-j715-backlight.rules").read_text()
        active = [line for line in rule.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(active), 1)
        fields = [part.strip() for part in active[0].split(", ")]
        self.assertEqual(fields, ['ACTION=="add|change"', 'SUBSYSTEM=="backlight"', 'KERNEL=="j715-dcp"',
                                 'RUN+="/usr/bin/chgrp video /sys%p/brightness"',
                                 'RUN+="/usr/bin/chmod 0664 /sys%p/brightness"'])


if __name__ == "__main__":
    unittest.main()
