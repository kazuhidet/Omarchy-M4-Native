# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Kazuhide Takahashi
"""The speaker sources build for the J713 or the 15-inch Air (J715), and the J713 build is unchanged.

audio/j713/kernel builds for the J713 by default and for the J715 with
M4_BOARD=j715; m4-audio-board.h holds every per-board value. The J713 overlay
loaders in audio/j713/bootstrap and audio/j713/topology stay as released (the
release source joins pin them at the alpha.1 tag); audio/j715 carries their
J715 copies, which differ only where they use the board header.
"""
import configparser
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
J713 = ROOT / 'audio/j713'
J715 = ROOT / 'audio/j715'
HEADER = 'm4-audio-board.h'
ALPHA1 = 'ee98743a860437ad5797bf5db080c04e0128528d'
LOADERS = (('bootstrap', 'j713_audio_bootstrap.c', 'j713_bootstrap_blob.h', 'j715_bootstrap_blob.h'),
           ('topology', 'j713_audio_dt3.c', 'j713_audio_blob.h', 'j715_audio_blob.h'))


def branches():
    """The J715 and J713 halves of the board header, as name -> text."""
    text = (J713 / 'kernel' / HEADER).read_text()
    j715 = text.split('#ifdef M4_AUDIO_J715', 1)[1].split('#else', 1)[0]
    j713 = text.split('#else', 1)[1].split('#endif', 1)[0]
    return {'j715': defines(j715), 'j713': defines(j713)}


def defines(text):
    text = text.replace('\\\n', ' ')
    return {m.group(1): ' '.join(m.group(2).split()) for m in re.finditer(r'^#define (\w+) (.+)$', text, re.M)}


def blob(path):
    text = path.read_text()
    return bytes(int(x, 16) for x in re.findall(r'0x([0-9a-f]{2})', text.split('{', 1)[1].split('}', 1)[0]))


def git_tree(revision, path):
    result = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--verify', '--quiet', f'{revision}:{path}'],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


class BoardHeader(unittest.TestCase):
    def test_one_header_and_how_each_component_selects_its_board(self):
        header = (J713 / 'kernel' / HEADER).read_bytes()
        kernel = (J713 / 'kernel/Makefile').read_text()
        self.assertIn('ccflags-y += -include $(src)/m4-audio-board.h\nifeq ($(M4_BOARD),j715)\n'
                      'ccflags-y += -DM4_AUDIO_J715\nendif', kernel)
        for component, *_ in LOADERS:
            with self.subTest(component=component):
                self.assertEqual((J715 / component / HEADER).read_bytes(), header)
                self.assertTrue((J715 / component / 'Makefile').read_text().endswith(
                    'ccflags-y += -include $(src)/m4-audio-board.h\nccflags-y += -DM4_AUDIO_J715\n'))
                self.assertFalse((J713 / component / HEADER).exists())

    def test_j713_branch_is_the_qualified_literals(self):
        j713 = branches()['j713']
        self.assertEqual(j713['M4_BOARD'], '"apple,j713"')
        self.assertEqual(j713['M4_NAMP'], '4')
        self.assertEqual(j713['M4_ADDRESSES'], '{ 0x38, 0x3b, 0x39, 0x3c }')
        self.assertEqual(j713['M4_TX_ZD_MASKS'], '{{0xf0,0xf0,0,0},{0x0f,0x0f,0,0},{0},{0}}')
        self.assertEqual(j713['M4_CARD_NAME'], '"Apple J713"')
        self.assertEqual(j713['M4_CARD_ID'], '"AppleJ713"')
        self.assertEqual(j713['M4_GROUP_COMPAT'], '"apple,j713-speaker-group"')
        self.assertEqual(j713['M4_CARD_COMPAT'], '"apple,j713-audio"')

    def test_j715_branch_is_the_adt_layout(self):
        j715 = branches()['j715']
        self.assertEqual(j715['M4_BOARD'], '"apple,j715"')
        self.assertEqual(j715['M4_NAMP'], '6')
        # ADT speaker order: amplifiers 0-3 as on the J713, then the second woofers.
        self.assertEqual(j715['M4_ADDRESSES'], '{ 0x38, 0x3b, 0x39, 0x3c, 0x3a, 0x3d }')
        # amp-tx-zd-config f0 f0 f0 ff / 0f 0f 0f ff, cut to the 24 byte-slots of 12 x S16 feedback.
        self.assertEqual(j715['M4_TX_ZD_MASKS'], '{ {0xf0,0xf0,0xf0,0}, {0x0f,0x0f,0x0f,0}, {0}, {0}, {0}, {0} }')
        self.assertEqual(j715['M4_CARD_NAME'], '"Apple J715"')

    def test_frame_words_reduce_to_the_j713_values(self):
        # j713_frame_unlocked() checked 0x17503, 0x1b047, ~0xf and ~0xff for four amplifiers.
        for amps, tx, rx, tx_inv, rx_inv in ((4, 0x17503, 0x1b047, 0xfffffff0, 0xffffff00),
                                             (6, 0x17505, 0x1b04b, 0xffffffc0, 0xfffff000)):
            with self.subTest(amps=amps):
                tx_ch, rx_ch = amps, 2 * amps
                self.assertEqual(0x17500 | (tx_ch - 1), tx)
                self.assertEqual(0x1b040 | (rx_ch - 1), rx)
                self.assertEqual(~((1 << tx_ch) - 1) & 0xffffffff, tx_inv)
                self.assertEqual(~((1 << rx_ch) - 1) & 0xffffffff, rx_inv)
        shared = (J713 / 'kernel' / HEADER).read_text().split('#endif', 1)[1]
        self.assertIn('#define M4_TX_SERDES_WORD (0x17500U | (M4_TX_CH - 1))', shared)
        self.assertIn('#define M4_RX_CONFIG_WORD (0x1b040U | (M4_RX_CH - 1))', shared)

    def test_no_board_literal_left_in_the_switched_sources(self):
        sources = [p for p in sorted((J713 / 'kernel').glob('*.[ch]')) if p.name != HEADER]
        sources += [J715 / component / source for component, source, *_ in LOADERS]
        for path in sources:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertNotRegex(path.read_text(), r'"apple,j71[35]')

    def test_kernel_sources_are_pinned(self):
        pins = dict(reversed(line.split('  ', 1)) for line in (J713 / 'imported-source.sha256').read_text().splitlines())
        for path in sorted((J713 / 'kernel').iterdir()):
            rel = path.relative_to(J713).as_posix()
            with self.subTest(path=rel):
                self.assertEqual(pins.get(rel), hashlib.sha256(path.read_bytes()).hexdigest())


class Loaders(unittest.TestCase):
    @unittest.skipUnless(shutil.which('git') and git_tree('HEAD', 'audio/j713/bootstrap'), 'not a git checkout')
    def test_j713_loaders_are_the_alpha1_trees(self):
        # packaging/release-source-joins.json joins both J713 loaders to these trees at the tag.
        for component, *_ in LOADERS:
            with self.subTest(component=component):
                pinned = git_tree(ALPHA1, 'audio/j713/' + component)
                if pinned is None:
                    self.skipTest('alpha.1 tag commit not in this clone')
                self.assertEqual(git_tree('HEAD', 'audio/j713/' + component), pinned)

    def test_j715_loaders_differ_only_through_the_header(self):
        for component, source, j713_blob, j715_blob in LOADERS:
            with self.subTest(component=component):
                old = (J713 / component / source).read_text().splitlines()
                new = (J715 / component / source).read_text().splitlines()
                self.assertEqual(len(old), len(new))
                for a, b in zip(old, new):
                    if a == b:
                        continue
                    if a == f'#include "{j713_blob}"':
                        self.assertEqual(b, f'#include "{j715_blob}"')
                    else:
                        self.assertIn('M4_', b, b)

    def test_j715_cold_transport_adds_only_the_i2c3_clock(self):
        j713 = (J713 / 'bootstrap/j713-cold-transport.dtso').read_text().splitlines()
        j715 = (J715 / 'bootstrap/j715-cold-transport.dtso').read_text().splitlines()
        self.assertEqual(len(j713), len(j715))
        changed = [b.strip() for a, b in zip(j713, j715) if a != b]
        self.assertEqual(changed, ['__overlay__ { status = "okay"; clock-frequency = <400000>; };'])

    def test_j715_topology_adds_two_woofers(self):
        text = (J715 / 'topology/j715-audio.dtso').read_text()
        self.assertIn('apple,codecs = <&amp0 &amp1 &amp2 &amp3 &amp4 &amp5>;', text)
        self.assertEqual(re.findall(r'amplifier@([0-9a-f]+)', text), ['38', '3b', '39', '3c', '3a', '3d'])
        self.assertIn('compatible = "apple,j715-speaker-group";', text)
        self.assertIn('compatible = "apple,j715-audio";', text)

    @unittest.skipUnless(shutil.which('dtc'), 'dtc is not installed')
    def test_blobs_are_the_overlay_sources(self):
        for header, source in ((J713 / 'bootstrap/j713_bootstrap_blob.h', J713 / 'bootstrap/j713-cold-transport.dtso'),
                               (J715 / 'bootstrap/j715_bootstrap_blob.h', J715 / 'bootstrap/j715-cold-transport.dtso'),
                               (J713 / 'topology/j713_audio_blob.h', J713 / 'topology/j713-audio.dtso'),
                               (J715 / 'topology/j715_audio_blob.h', J715 / 'topology/j715-audio.dtso')):
            with self.subTest(header=header.relative_to(ROOT).as_posix()), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / 'overlay.dtbo'
                subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', str(out), str(source)], check=True)
                self.assertEqual(blob(header), out.read_bytes())



class Daemon(unittest.TestCase):
    SSD = J713 / 'speakersafetyd'

    def test_feature_selects_channels_and_machine(self):
        self.assertIn('[features]\n# Build for the 15-inch Air (J715): twelve feedback channels, apple,j715 only.\nj715 = []\n',
                      (self.SSD / 'Cargo.toml').read_text())
        source = (self.SSD / 'src/j713.rs').read_text()
        self.assertIn('pub const CHANNELS: usize = if cfg!(feature = "j715") { 12 } else { 8 }; '
                      'pub const MACHINE: &str = if cfg!(feature = "j715") { "apple,j715" } else { "apple,j713" };', source)
        self.assertIn('let j713 = machine == j713::MACHINE;', (self.SSD / 'src/main.rs').read_text())
        helpers = (self.SSD / 'src/helpers.rs').read_text()
        self.assertEqual(helpers.count('crate::j713::CHANNELS as u32'), 2)
        self.assertNotRegex(helpers, r'set_channels\(8\)|get_channels\(\)\.unwrap\(\), 8\)')

    def test_j715_model(self):
        j713, j715 = configparser.ConfigParser(), configparser.ConfigParser()
        j713.read(J713 / 'j713.conf')
        j715.read(J715 / 'j715.conf')
        self.assertEqual(j715['Globals']['channels'], '12')
        for key in ('visense_pcm', 'period', 't_ambient', 't_window', 't_hysteresis'):
            self.assertEqual(j715['Globals'][key], j713['Globals'][key])
        self.assertEqual(dict(j715['Controls']), dict(j713['Controls']))
        speakers = [s for s in j715.sections() if s.startswith('Speaker/')]
        self.assertEqual(speakers, ['Speaker/Left Woofer 1', 'Speaker/Right Woofer 1', 'Speaker/Left Tweeter',
                                    'Speaker/Right Tweeter', 'Speaker/Left Woofer 2', 'Speaker/Right Woofer 2'])
        tweeter = j713['Speaker/Left Tweeter']
        for index, name in enumerate(speakers):
            s = j715[name]
            with self.subTest(speaker=name):
                self.assertEqual((int(s['vs_chan']), int(s['is_chan'])), (2 * index, 2 * index + 1))
                self.assertEqual(int(s['group']), 1 if 'Tweeter' in name else 0)
                self.assertEqual((float(s['t_limit']), float(s['t_headroom'])), (120.0, 5.0))
                self.assertEqual((float(s['vs_scale']), float(s['is_scale'])), (14.0, 3.75))
                # AID38's lowest Reb per channel; every one is below one unit's 3.696 ohm calibration.
                self.assertLess(float(s['z_nominal']), 3.696)
                if 'Tweeter' in name:
                    self.assertEqual((s['tr_coil'], s['tr_magnet']), (tweeter['tr_coil'], tweeter['tr_magnet']))

if __name__ == '__main__':
    unittest.main()
