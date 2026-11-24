# Static J715 speaker profiles

Six mono 48 kHz float32 FIR files for each AID38 speaker ID, one per J715
amplifier lane in ADT order: left woofer 1, right woofer 1, left tweeter,
right tweeter, left woofer 2, right woofer 2. Their sizes and SHA-256
identities are the `outputs` of each speaker ID in
[`../owner-fir/manifest.json`](../owner-fir/manifest.json), and
[`../owner-fir/`](../owner-fir/README.md) reproduces them.

| Speaker ID | Files | Woofer taps | Tweeter taps | Largest L1 | Tested |
| --- | --- | --- | --- | --- | --- |
| 3 | `j715-spk3-static-minimal-lane{0-5}-48000.wav` | 8192 | 1024 | 2.9016 | Protected playback on one J715 |
| 0 | `j715-spk0-static-minimal-lane{0-5}-48000.wav` | 8192 | 1024 | 2.8932 | Not played on hardware |

Lanes 4 and 5 are copies of lanes 0 and 1, as the AID38 graph feeds the
second woofers, and the two tweeter lanes are equal. A graph gain of 0.336
keeps every lane of both speaker IDs at or below the J713's bound of 0.976
for any input (0.336 × 2.9016 = 0.975).

The woofer filters have 8192 taps, against the J713's 4096, because AID38's
70 Hz order-8 high-pass has a longer tail. Like the J713 profile, these leave
out Apple's dynamic and volume-dependent processing and the large low-shelf
in Tone2, so they are quieter in the bass than macOS.

Only speaker ID 3 has been played. `tools/m4-j715-speaker-id.py` reads the
speaker ID on Linux ([J715 README](../README.md#speaker-id)); nothing uses it
to pick a filter set yet.

## Distribution and provenance

As for the [J713 profile](../../j713/filters/README.md#distribution-and-provenance):
these are final functional numerical filters, platform profile data. They
contain no AudioDSP executable, serialized Apple preset, tuning strip, recorded
music or personal calibration data, and do not grant rights in Apple software
or source data. Their response is derived from Apple's tuning through the
documented measurement pipeline.
