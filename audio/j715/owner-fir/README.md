# J715 audio filter reproduction

This development tool reproduces the J715 FIR files in
[`../filters/`](../filters/README.md) from installed macOS AudioDSP and AID38
tuning inputs. It is the J715 variant of [`../../j713/owner-fir/`](../../j713/owner-fir/README.md)
and follows the same rules: a reproduction bundle must not contain or publish
Apple presets, tuning strips, AudioDSP or raw render captures, every input,
extracted preset, helper, dependency and output is pinned in `manifest.json`,
and a different input or output is a refusal, not permission to use a
substitute filter.

```sh
/path/to/bundled/python3.13 tools/m4-j715-fir-owner.py --speaker-id 3 --output /absolute/new/owner-firs
```

## What differs from the J713 generator

- **Tuning.** The J715 is acoustic ID 38 (`acoustic-id` 0x26 in its ADT; the
  J713 is 37). AID38 has one speaker strip per speaker ID:
  `builtin_speaker_out_general_0.austrip` and `_3.austrip`. `--speaker-id`
  picks one; `manifest.json` pins the presets and outputs of each.
- **Stages.** The same three stages as the J713's static-minimal profile: the
  high-pass in Tone1 filter 0 (70 Hz, order 8), the high-pass with Q in Tone2
  filter 7 (50 Hz), then the whole `analytical` unit (AID37's Tone3: the
  four-lane crossover, woofer low-pass 2000 Hz and tweeter high-pass 2150 Hz,
  and per-lane EQ). Everything else, including AID38's VarEQ, LowFlow and
  SpeakerProtect, is left out, as on the J713.
- **`measure-memory-j715`.** `measure-memory` with its two fixed J713 subsets
  (`hp90`, `hp80`) replaced by `keep:INDEX:TYPE:FREQ`, which keeps one filter
  after checking its type and frequency (the J713 subsets also checked the
  order). Given the J713 subsets' filters, it renders exactly what they render.
  `measure-transfer` is the J713's, and its pinned build is shared.
- **Six lanes.** The AID38 graph runs the crossover on four lanes and its last
  join copies them to six amplifiers: left woofer 1, right woofer 1, left
  tweeter, right tweeter, then left woofer 2 = lane 0 and right woofer 2 =
  lane 1. The generator copies the four rendered files the same way.
- **Hashes.** `run-transfer.py` and `run-memory.py` take the AudioDSP hash and
  the speaker ID's preset hashes from the generator in `owner-inputs.json`.

The two speaker IDs' SpeakerProtect presets differ in one per-channel value
only; the thermal values are the same. Tone1 differs only in a selection
parameter, Tone2 in shelves and bells outside the retained high-pass, and
`analytical` in ten parameters, so their filters differ.

## Reproduction

On 2026-10-19, on a 15-inch M4 Air (Mac16,13, speaker ID 3) running macOS
27.0.1 (26A434), with the J713 bundle's CPython 3.13.9 and NumPy 2.5.3, the
generator produced the pinned outputs for both speaker IDs from a fresh
bundle. The speaker ID 3 files equal, byte for byte, the ones generated for
that Air on 2026-10-17 and played on it through the protected J715 stack.
AudioDSP is qualified for 27.0.1 only (`910423a2…`); the J713's 26.x AudioDSP
builds are not listed, and no compatibility claim is made for them.

Build the helpers on native arm64 macOS:

```sh
bash audio/j715/owner-fir/build-helpers.sh /absolute/new/helper-output
```

`measure-memory-j715` built with Apple clang 21.0.0 on macOS 27.0.1 is the
pinned `391a0a7f…`. Use the J713 bundle's pinned `measure-transfer`
(`ffbd3d9f…`); a rebuild on another host may differ. Place both in the
bundle's `bin/` and the NumPy wheel named in `manifest.json` in
`dependencies/`, as for the J713 bundle. The license, notices and NumPy
license copies in [`../../j713/owner-fir/`](../../j713/owner-fir/) apply
unchanged.
