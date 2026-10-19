# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Kazuhide Takahashi
"""The J715 filter generator, its bundle pins and the static J715 filters agree."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'audio/j715/owner-fir'
FILTERS = ROOT / 'audio/j715/filters'
spec = importlib.util.spec_from_file_location('j715_fir_owner', ROOT / 'tools/m4-j715-fir-owner.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def taps(data):
    """The float32 samples of a static filter WAV."""
    start = data.index(b'data')
    size, = struct.unpack_from('<I', data, start + 4)
    return struct.unpack_from('<%df' % (size // 4), data, start + 8)


class BundleConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((BUNDLE / 'manifest.json').read_bytes())

    def test_schema_board_and_speakers(self):
        self.assertEqual((self.manifest['schema'], self.manifest['board']), (1, 'apple,j715'))
        self.assertEqual(set(self.manifest['speakers']), set(owner.SPEAKER_IDS))
        for speaker_id, speaker in self.manifest['speakers'].items():
            with self.subTest(speaker_id=speaker_id):
                self.assertEqual(speaker['strip'], f'builtin_speaker_out_general_{speaker_id}.austrip')
                self.assertIn(speaker['strip'], self.manifest['owner_inputs'])
                self.assertEqual(set(speaker['presets']), {'Tone1.aupreset', 'Tone2.aupreset', 'analytical.aupreset'})

    def test_retained_sources_and_shared_helper_match_their_pins(self):
        self.assertEqual(set(self.manifest['sources']), owner.SOURCE_NAMES)
        for name, record in self.manifest['sources'].items():
            data = (BUNDLE / 'src' / name).read_bytes()
            self.assertEqual((len(data), sha(data)), (record['size'], record['sha256']), name)
        j713 = json.loads((ROOT / 'audio/j713/owner-fir/manifest.json').read_bytes())
        self.assertEqual(self.manifest['helpers']['measure-transfer'], j713['helpers']['measure-transfer'])
        self.assertEqual((BUNDLE / 'src/measure-transfer.c').read_bytes(),
                         (ROOT / 'audio/j713/owner-fir/src/measure-transfer.c').read_bytes())
        self.assertEqual((self.manifest['numpy'], self.manifest['numpy_source']), (j713['numpy'], j713['numpy_source']))

    def test_run_scripts_take_hashes_from_the_generator(self):
        for name in ('run-transfer.py', 'run-memory.py'):
            text = (BUNDLE / 'src' / name).read_text()
            assertion = next(line for line in text.splitlines() if 'AudioDSP.component' in line)
            self.assertIn('owner-inputs.json', assertion, name)
            self.assertIsNone(re.search('[0-9a-f]{64}', text), name)

    def test_static_filters_are_the_pinned_outputs(self):
        expected = {}
        for speaker in self.manifest['speakers'].values():
            expected.update(speaker['outputs'])
        self.assertEqual({path.name for path in FILTERS.glob('*.wav')}, set(expected))
        for name, record in expected.items():
            with self.subTest(name=name):
                data = (FILTERS / name).read_bytes()
                self.assertEqual((len(data), sha(data)), (record['size'], record['sha256']))

    def test_lanes_follow_the_graph_join_and_fit_the_graph_gain(self):
        for speaker_id in owner.SPEAKER_IDS:
            files = [(FILTERS / owner.output_name(speaker_id, lane)).read_bytes() for lane in range(6)]
            with self.subTest(speaker_id=speaker_id):
                for lane, crossover in enumerate(owner.CROSSOVER):
                    self.assertEqual(files[lane], files[crossover])
                self.assertEqual(files[2], files[3])
                self.assertNotEqual(files[0], files[2])
                # 0.336 x the largest L1 stays at or below the J713 bound of 0.976.
                self.assertLessEqual(0.336 * max(sum(abs(x) for x in taps(data)) for data in files), 0.976)

    def test_speaker_ids_have_different_filters(self):
        for lane in range(4):
            self.assertNotEqual((FILTERS / owner.output_name('0', lane)).read_bytes(),
                                (FILTERS / owner.output_name('3', lane)).read_bytes())


class GenerateTests(unittest.TestCase):
    """Run generate() against a synthetic bundle with the native steps mocked."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.bundle, self.system, self.output = base / 'bundle', base / 'system', base / 'out' / 'firs'
        self.output.parent.mkdir()
        for directory in ('src', 'bin', 'dependencies'):
            (self.bundle / directory).mkdir(parents=True)
        self.system.mkdir()
        manifest = {'schema': 1, 'board': 'apple,j715', 'sources': {}, 'helpers': {}, 'owner_inputs': {}, 'speakers': {}}
        for name in owner.SOURCE_NAMES:
            (self.bundle / 'src' / name).write_bytes(name.encode())
            manifest['sources'][name] = self.pin(name.encode())
        for name in owner.HELPER_NAMES:
            (self.bundle / 'bin' / name).write_bytes(name.encode())
            manifest['helpers'][name] = self.pin(name.encode())
        wheel = io.BytesIO()
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('numpy/__init__.py', '')
        (self.bundle / 'dependencies' / owner.WHEEL).write_bytes(wheel.getvalue())
        manifest['numpy'] = {'filename': owner.WHEEL, **self.pin(wheel.getvalue())}
        self.inputs = {'AudioDSP': b'dsp', owner.PROPSTRIP: b'propstrip'}
        for speaker_id in owner.SPEAKER_IDS:
            strip = f'builtin_speaker_out_general_{speaker_id}.austrip'
            self.inputs[strip] = b'strip ' + speaker_id.encode()
            manifest['speakers'][speaker_id] = {
                'strip': strip,
                'presets': {'Tone1.aupreset': self.pin(b'preset ' + speaker_id.encode())},
                'outputs': {owner.output_name(speaker_id, lane):
                            self.pin(b'crossover %d of %s' % (crossover, speaker_id.encode()))
                            for lane, crossover in enumerate(owner.CROSSOVER)}}
        for name, data in self.inputs.items():
            (self.system / name).write_bytes(data)
            manifest['owner_inputs'][name] = {'path': str(self.system / name), 'qualified': [self.pin(data)]}
        (self.bundle / 'manifest.json').write_text(json.dumps(manifest))
        self.seen = []

    @staticmethod
    def pin(data):
        return {'sha256': sha(data), 'size': len(data)}

    def fake_run(self, speaker_id):
        def run(source, work, dependencies, name):
            if name == 'inspect_strip.py':
                self.seen.append((work / 'source/builtin_speaker_out_general.austrip').read_bytes())
                (work / 'decoded').mkdir()
                (work / 'decoded/Tone1.aupreset').write_bytes(b'preset ' + speaker_id.encode())
            elif name == 'run-transfer.py':
                self.seen.append(json.loads((work / 'owner-inputs.json').read_text()))
            elif name == 'qualify_memory.py':
                (work / 'output').mkdir()
                for crossover in range(4):
                    (work / 'output' / f'j715-xover-lane{crossover}-48000.wav').write_bytes(
                        b'crossover %d of %s' % (crossover, speaker_id.encode()))
        return run

    def generate(self, speaker_id, rendered=None):
        fake_sys = types.SimpleNamespace(version_info=(3, 13, 9), flags=types.SimpleNamespace(optimize=0))
        with mock.patch.object(owner, 'run_script', self.fake_run(rendered or speaker_id)), \
             mock.patch.object(owner, 'sys', fake_sys), \
             mock.patch.object(owner.platform, 'system', return_value='Darwin'), \
             mock.patch.object(owner.platform, 'machine', return_value='arm64'), \
             mock.patch.object(owner.platform, 'mac_ver', return_value=('27.0.1', ('', '', ''), '')), \
             mock.patch('builtins.print'):
            owner.generate(self.bundle, self.output, speaker_id)

    def test_each_speaker_id_renders_its_own_strip_into_six_lanes(self):
        for speaker_id in owner.SPEAKER_IDS:
            with self.subTest(speaker_id=speaker_id):
                self.seen.clear()
                self.output = self.output.with_name('firs-' + speaker_id)
                self.generate(speaker_id)
                self.assertEqual(self.seen[0], b'strip ' + speaker_id.encode())
                self.assertEqual(self.seen[1], {'AudioDSP': sha(b'dsp'),
                                                'presets': {'Tone1': sha(b'preset ' + speaker_id.encode())}})
                for lane, crossover in enumerate(owner.CROSSOVER):
                    self.assertEqual((self.output / owner.output_name(speaker_id, lane)).read_bytes(),
                                     b'crossover %d of %s' % (crossover, speaker_id.encode()))
                receipt = json.loads((self.output / 'receipt.json').read_text())
                self.assertEqual((receipt['board'], receipt['speaker_id']), ('apple,j715', int(speaker_id)))
                self.assertEqual(set(receipt['owner_inputs']),
                                 {'AudioDSP', owner.PROPSTRIP, f'builtin_speaker_out_general_{speaker_id}.austrip'})

    def test_the_other_speaker_ids_outputs_are_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported input hash'):
            self.generate('3', rendered='0')
        self.assertFalse(self.output.exists())

    def test_unknown_speaker_id_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported filter reproduction bundle'):
            self.generate('1')


if __name__ == '__main__':
    unittest.main()
