# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Kazuhide Takahashi
"""The J715 speaker routing is the J713 routing with six lanes and the J715's names only."""
import json
import math
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
J713 = ROOT / 'audio/j713/policy'
J715 = ROOT / 'audio/j715/policy'
FILTERS = ROOT / 'audio/j715/filters'
GAIN = 0.336
L1_BOUND = 0.976  # the J713 graph's gain x largest filter L1 (0.38 x 2.567)

# J715 file -> (J713 file, the exact replacements, each with its count).
WIREPLUMBER = [('"api.alsa.path": "hw:AppleJ713,0"', '"api.alsa.path": "hw:AppleJ715,0"', 2),
               ('"node.name": "alsa_output.j713.RawSpeakers"', '"node.name": "alsa_output.j715.RawSpeakers"', 1),
               ('"node.description": "J713 raw speakers (do not use)"', '"node.description": "J715 raw speakers (do not use)"', 1),
               ('"audio.channels": 4,', '"audio.channels": 6,', 1),
               ('"AUX3"\n', '"AUX3",\n          "AUX4",\n          "AUX5"\n', 1),
               ('/usr/share/asahi-audio/j713/graph.json', '/usr/share/asahi-audio/j715/graph.json', 1)]
UCM_USE_CASE = [('J713 protected speakers', 'J715 protected speakers', 1), ('File "J713-HiFi.conf"', 'File "J715-HiFi.conf"', 1)]
UCM_HIFI = [('J713 protected speakers', 'J715 protected speakers', 1), ('"hw:AppleJ713,0"', '"hw:AppleJ715,0"', 1),
            ('PlaybackChannels 4', 'PlaybackChannels 6', 1)]
DERIVED = {
    'etc/wireplumber/wireplumber.conf.d/80-j715-protected.conf':
        ('etc/wireplumber/wireplumber.conf.d/80-j713-protected.conf', WIREPLUMBER),
    'usr/share/asahi-audio/j715/80-j715-protected.conf.in':
        ('usr/share/asahi-audio/j713/80-j713-protected.conf.in', WIREPLUMBER),
    'etc/wireplumber/wireplumber.conf.d/81-j715-busy-discovery.conf':
        ('etc/wireplumber/wireplumber.conf.d/81-j713-busy-discovery.conf', []),
    'etc/wireplumber/wireplumber.conf.d/82-j715-protected-default.conf':
        ('etc/wireplumber/wireplumber.conf.d/82-j713-protected-default.conf',
         [('default-nodes/j713-protected.lua', 'default-nodes/j715-protected.lua', 1),
          ('hooks.default-nodes.j713-protected', 'hooks.default-nodes.j715-protected', 2)]),
    'usr/share/wireplumber/scripts/default-nodes/j715-protected.lua':
        ('usr/share/wireplumber/scripts/default-nodes/j713-protected.lua',
         [('"default-nodes/j713-protected"', '"default-nodes/j715-protected"', 1),
          ('"alsa_output.j713.RawSpeakers"', '"alsa_output.j715.RawSpeakers"', 1)]),
    'usr/share/alsa/ucm2/conf.d/macaudio/Apple J715.conf': ('usr/share/alsa/ucm2/conf.d/macaudio/Apple J713.conf', UCM_USE_CASE),
    'usr/share/asahi-audio/j715/ucm/Apple J715.conf.in': ('usr/share/asahi-audio/j713/ucm/Apple J713.conf.in', UCM_USE_CASE),
    'usr/share/alsa/ucm2/conf.d/macaudio/J715-HiFi.conf': ('usr/share/alsa/ucm2/conf.d/macaudio/J713-HiFi.conf', UCM_HIFI),
    'usr/share/asahi-audio/j715/ucm/J715-HiFi.conf.in': ('usr/share/asahi-audio/j713/ucm/J713-HiFi.conf.in', UCM_HIFI),
}


def l1(path):
    data = path.read_bytes()
    start = data.index(b'data')
    size, = struct.unpack_from('<I', data, start + 4)
    return math.fsum(abs(x) for x in struct.unpack_from('<%df' % (size // 4), data, start + 8))


def board(name):
    text = (ROOT / 'audio/j713/kernel/m4-audio-board.h').read_text()
    j715 = text.split('#ifdef M4_AUDIO_J715', 1)[1].split('#else', 1)[0]
    return re.search(r'^#define %s (.+)$' % name, j715, re.M).group(1)


class Derived(unittest.TestCase):
    def test_every_file_is_listed(self):
        files = {p.relative_to(J715).as_posix() for p in J715.rglob('*') if p.is_file()}
        self.assertEqual(files, set(DERIVED) | {'usr/share/asahi-audio/j715/graph.json',
                                                'usr/share/asahi-audio/j715/contract.json'})

    def test_text_files_are_the_j713_ones_with_the_listed_replacements(self):
        for name, (source, replacements) in DERIVED.items():
            with self.subTest(name=name):
                text = (J713 / source).read_text()
                for old, new, count in replacements:
                    self.assertEqual(text.count(old), count, old)
                    text = text.replace(old, new)
                self.assertEqual((J715 / name).read_text(), text)
                self.assertNotIn('j713', text.lower())


class Graph(unittest.TestCase):
    def setUp(self):
        self.j713 = json.loads((J713 / 'usr/share/asahi-audio/j713/graph.json').read_text())
        self.j715 = json.loads((J715 / 'usr/share/asahi-audio/j715/graph.json').read_text())
        self.nodes = {node['name']: node for node in self.j715['filter.graph']['nodes']}

    def test_same_input_clamps_and_six_convolvers(self):
        clamps = [n for n in self.j713['filter.graph']['nodes'] if n['label'] == 'clamp']
        self.assertEqual([n for n in self.j715['filter.graph']['nodes'] if n['label'] == 'clamp'], clamps)
        self.assertEqual(self.j715['filter.graph']['inputs'], self.j713['filter.graph']['inputs'])
        template = next(n for n in self.j713['filter.graph']['nodes'] if n['label'] == 'convolver')
        for lane in range(6):
            with self.subTest(lane=lane):
                node = self.nodes['lane%d' % lane]
                self.assertEqual({**node, 'name': template['name'],
                                  'config': {**node['config'], 'filename': template['config']['filename'], 'gain': 0.38}},
                                 template)
                self.assertEqual(node['config']['filename'],
                                 '/usr/share/asahi-audio/j715/j715-spk3-static-minimal-lane%d-48000.wav' % lane)
                self.assertEqual(node['config']['gain'], GAIN)
        self.assertEqual(len(self.nodes), 8)

    def test_left_feeds_even_lanes_and_right_odd_lanes(self):
        self.assertEqual(self.j715['filter.graph']['links'],
                         [{'output': ('inputL' if lane % 2 == 0 else 'inputR') + ':Out', 'input': 'lane%d:In' % lane}
                          for lane in range(6)])
        self.assertEqual(self.j715['filter.graph']['outputs'], ['lane%d:Out' % lane for lane in range(6)])

    def test_gain_keeps_every_lane_within_the_j713_bound(self):
        for lane in range(6):
            name = Path(self.nodes['lane%d' % lane]['config']['filename']).name
            with self.subTest(lane=lane):
                self.assertLessEqual(GAIN * l1(FILTERS / name), L1_BOUND)

    def test_stream_properties(self):
        expected = json.loads(json.dumps(self.j713))
        for key in ('filter.graph',):
            expected[key] = self.j715[key]
        expected['node.description'] = expected['media.name'] = 'J715 protected speakers'
        expected['capture.props']['node.name'] = 'audio_effect.j715-protected'
        expected['playback.props'].update({'node.name': 'effect_output.j715-protected',
                                           'target.object': 'alsa_output.j715.RawSpeakers',
                                           'audio.channels': 6, 'audio.position': ['AUX%d' % i for i in range(6)]})
        self.assertEqual(self.j715, expected)


class Contract(unittest.TestCase):
    def test_contract_matches_the_board_build_and_graph(self):
        contract = json.loads((J715 / 'usr/share/asahi-audio/j715/contract.json').read_text())
        graph = json.loads((J715 / 'usr/share/asahi-audio/j715/graph.json').read_text())
        self.assertEqual(contract['card'], {'id': board('M4_CARD_ID').strip('"'),
                                            'longname': board('M4_CARD_NAME').strip('"'), 'driver': 'macaudio'})
        self.assertEqual((contract['pcm']['playback']['channels'], contract['pcm']['feedback']['channels']), (6, 12))
        addresses = [int(x, 16) for x in re.findall(r'0x[0-9a-f]+', board('M4_ADDRESSES'))]
        self.assertEqual([int(entry['i2c'], 16) for entry in contract['lane_order']], addresses)
        self.assertEqual([entry['slot'] for entry in contract['lane_order']], list(range(6)))
        self.assertEqual(contract['graph_gain'], GAIN)
        self.assertEqual({n['config']['gain'] for n in graph['filter.graph']['nodes'] if n['label'] == 'convolver'}, {GAIN})
        largest = max(l1(FILTERS / ('j715-spk3-static-minimal-lane%d-48000.wav' % lane)) for lane in range(6))
        self.assertAlmostEqual(contract['max_finite_fir_l1'], largest, places=9)
        self.assertEqual((contract['activated'], contract['profile_accepted'], contract['speaker_id']), (False, False, 3))


if __name__ == '__main__':
    unittest.main()
