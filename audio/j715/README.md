# J715 speaker overlay loaders

The 15-inch M4 Air (J715, Mac16,13) is a `testing` board
([m4-boards.md](../../docs/m4-boards.md),
[#142](https://github.com/Kb2uka/Omarchy-M4-Native/issues/142)). Its speakers
use the J713 protected stack with six amplifiers in place of four. The five
kernel modules build from [`../j713/kernel/`](../j713/README.md#one-board-per-build-j713-or-j715)
with `M4_BOARD=j715`. This directory holds the J715 copies of the two overlay
loaders, because the J713 ones in `../j713/bootstrap/` and `../j713/topology/`
stay as released (the release source joins pin them at the alpha.1 tag).

| Path | What it is |
| --- | --- |
| `bootstrap/` | `j713_audio_bootstrap.ko` for the J715: the J713 loader built with `-DM4_AUDIO_J715`, applying `j715-cold-transport.dtso` |
| `topology/` | `j713_audio_dt3.ko` for the J715: the J713 loader built with `-DM4_AUDIO_J715`, applying `j715-audio.dtso` |
| `*/m4-audio-board.h` | The same board header as `../j713/kernel/` |

The module names stay the J713 ones; the J715 build admits only `apple,j715`.

## What differs from the J713

From the J715 ADT (`docs/j715-macos-survey.md`):

- **Amplifiers.** Six `sn012776` on `i2c3`: 0x38 left woofer 1, 0x3b right
  woofer 1, 0x39 left tweeter, 0x3c right tweeter (the J713's four, in the same
  order), then 0x3a left woofer 2 and 0x3d right woofer 2. Their V/I sense
  slots continue the J713 pattern (amplifier 4: 16/18, amplifier 5: 20/22).
- **Frame.** Six S32 playback slots (mask `0x3f`) and twelve S16 feedback slots
  (mask `0xfff`) in the J713's 250-bit frame at 48 kHz.
- **TX zero drive.** The ADT's `amp-tx-zd-config` is `f0 f0 f0 ff` and
  `0f 0f 0f ff` for amplifiers 0 and 1, as on the J713. The J713 code cuts it to
  the 16 byte-slots its feedback uses; the J715 cuts it to 24.
- **`i2c3` at 400 kHz** (`clock-frequency` in `j715-cold-transport.dtso`); the
  rest of the cold transport is the J713's.
- **Card** "Apple J715" (`AppleJ715`), group `apple,j715-speaker-group`, card
  `apple,j715-audio`, codec prefixes "Left Woofer 1" … "Right Woofer 2".

`j715_bootstrap_blob.h` and `j715_audio_blob.h` are `dtc -I dts -O dtb` (1.8.1)
of the `.dtso` beside them.

## Build

As `tools/build-j713-audio.sh` builds the J713 modules, with `M4_BOARD=j715`
for `../j713/kernel/` and this directory's `bootstrap/` and `topology/` in
place of the J713 ones. On 2026-10-19 the seven J715 modules built that way
on an aarch64 host matched, section for section, the ones one J715 has played
protected audio with; only the compiler identification and the build ID
differ.

## Not here yet

The J715 speaker protection profile (speakersafetyd with twelve feedback
channels and the J715 thermal values), the six-lane filters, the routing
policy and a delivery path. Until those land, nothing in this repository
loads these modules.
