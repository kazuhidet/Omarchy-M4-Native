# SPDX-License-Identifier: MIT
"""m4-wq-cpumask keeps unbound workqueues off CPU 0 on an M4 only (#132)."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/m4-wq-cpumask.sh'
SPEAKER = ROOT / 'packaging/omarchy-m4/omarchy-m4-speaker'
UNIT = SPEAKER / 'm4-wq-cpumask.service'
J713 = b'apple,j713\0apple,t8132\0apple,arm-platform\0'


class WorkqueueCpumaskTest(unittest.TestCase):
    def tree(self, compatible=J713, possible='0-9\n', mask='3ff\n'):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        if compatible is not None:
            (root / 'proc/device-tree').mkdir(parents=True)
            (root / 'proc/device-tree/compatible').write_bytes(compatible)
        if possible is not None:
            (root / 'sys/devices/system/cpu').mkdir(parents=True)
            (root / 'sys/devices/system/cpu/possible').write_text(possible)
        (root / 'sys/devices/virtual/workqueue').mkdir(parents=True)
        (root / 'sys/devices/virtual/workqueue/cpumask').write_text(mask)
        return root

    def run_tool(self, root):
        env = {**os.environ, 'M4_WQ_CPUMASK_ROOT': str(root)}
        return subprocess.run(['sh', str(TOOL)], env=env, capture_output=True, text=True, check=False)

    def mask(self, root):
        return (root / 'sys/devices/virtual/workqueue/cpumask').read_text()

    def test_m4_gets_every_possible_cpu_but_0(self):
        for possible, expected in (('0-9\n', '3fe'), ('0-3,6-7\n', 'ce'), ('0-1\n', '2'), ('0,4\n', '10')):
            with self.subTest(possible=possible):
                root = self.tree(possible=possible)
                result = self.run_tool(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.mask(root), expected + '\n')
                self.assertIn(f'workqueue cpumask 3ff -> {expected} (CPU 0 excluded)', result.stdout)

    def test_other_boards_and_unreadable_input_are_left_alone(self):
        cases = {'not an M4': dict(compatible=b'apple,j313\0apple,t8103\0apple,arm-platform\0'),
                 'no device tree': dict(compatible=None),
                 'a name that only contains t8132': dict(compatible=b'apple,t8132x\0'),
                 'only CPU 0': dict(possible='0\n'),
                 'no possible list': dict(possible=None),
                 'a malformed possible list': dict(possible='0-9 junk\n'),
                 'more than 63 CPUs': dict(possible='0-63\n')}
        for name, kwargs in cases.items():
            with self.subTest(name):
                root = self.tree(**kwargs)
                result = self.run_tool(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.mask(root), '3ff\n')
                self.assertIn('left unchanged', result.stdout)

    @unittest.skipIf(hasattr(os, 'geteuid') and os.geteuid() == 0, 'root can write a read-only file')
    def test_an_unwritable_mask_is_left_alone(self):
        root = self.tree()
        target = root / 'sys/devices/virtual/workqueue/cpumask'
        target.chmod(0o444)
        result = self.run_tool(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.mask(root), '3ff\n')
        self.assertIn('is not writable; left unchanged', result.stdout)

    def test_unit_runs_early_once_and_before_protection(self):
        text = UNIT.read_text()
        self.assertIn('DefaultDependencies=no\n', text)
        self.assertIn('Type=oneshot\n', text)
        self.assertIn('RemainAfterExit=yes\n', text)
        self.assertIn('Before=sysinit.target shutdown.target\n', text)
        self.assertIn('Before=m4-j713-audio-register.service speakersafetyd-j713.service\n', text)
        self.assertIn('WantedBy=sysinit.target\n', text)
        self.assertIsNone(re.search(r'^(After|Requires|Wants)=', text, re.M))
        exec_start = re.search(r'^ExecStart=(.*)$', text, re.M).group(1)
        self.assertEqual(exec_start, '/usr/lib/omarchy-m4/m4-wq-cpumask')

    def test_package_installs_the_tool_where_the_unit_runs_it(self):
        recipe = (SPEAKER / 'PKGBUILD').read_text()
        self.assertIn('install -Dm755 m4-wq-cpumask.sh "$pkgdir/usr/lib/omarchy-m4/m4-wq-cpumask"', recipe)
        self.assertIn('install -Dm644 m4-wq-cpumask.service "$pkgdir/usr/lib/systemd/system/m4-wq-cpumask.service"',
                      recipe)
        self.assertIn('install=omarchy-m4-speaker.install', recipe)
        scriptlet = (SPEAKER / 'omarchy-m4-speaker.install').read_text()
        self.assertIn('systemctl enable m4-wq-cpumask.service', scriptlet)
        self.assertIn('systemctl disable m4-wq-cpumask.service', scriptlet)


if __name__ == '__main__':
    unittest.main()
