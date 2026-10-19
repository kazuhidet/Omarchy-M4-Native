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
| `j715.conf` | The speakersafetyd model for `apple,j715` |
| `owner-fir/`, `filters/` | The J715 filter generator and its static filters for AID38 speaker IDs 0 and 3 |
| `policy/` | The J715 speaker routing: filter graph, WirePlumber and UCM |

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

## Speaker protection daemon

`../j713/speakersafetyd` built with `--features j715` reads twelve feedback
channels and uses the lease only on `apple,j715`; without the feature it is
the J713 daemon. Its tests (`cargo test --features j715`) check `j715.conf`.
The daemon finds the model at `apple/j715.conf` under its config directory.

`j715.conf` takes each channel's thermal values from macOS's AID38
SpeakerProtect (spp3) data, which, unlike the J713's AID37, has them. The
mapping is `T_sett_vc` → `tr_coil`, `T_sett_mg` → `tr_magnet`, `tau_Tvc` →
`tau_coil` and `tau_Tmg` → `tau_magnet`. That the units are the same is
inferred, not documented by Apple: the daemon's values are °C/W and seconds
in a coil-over-magnet model of the same structure, the AID38 values have the
J713 candidate's magnitudes, and AID38's ambient (50 °C) and V/I scales
(14, 3.75) equal the J713 model's exactly. Three choices are
more conservative than AID38:

- the tweeters keep the J713 candidate `tr_coil`/`tr_magnet` 140/200 (AID38:
  124/89.8 and 129/87.2), which allows them less power;
- `t_limit` stays the J713 candidate 120 °C (AID38: 140 °C);
- `z_nominal` is AID38's lowest `Reb` for each channel (3.185 to 3.576 Ω), not
  one unit's calibration; it only scales the startup peak-power bound, and a
  lower value lets the daemon attenuate further.

On 2026-10-19 on an aarch64 host (cargo 1.93.1, the locked offline registry):
the daemon built and passed its tests both ways (9 without the feature,
including the J713 model test; 8 with it, including the J715 one). Without the feature, its code and
read-only data are those of the daemon built from the sources before this
change; it differs only in one panic message column (`set_channels`) and in
LLVM's internal symbol suffixes. The daemon one J715 ran protected playback
with was built from the same changes with another toolchain, and used one
unit's 3.696 Ω for every `z_nominal`.

## Routing

`policy/` is the J713 routing (`../j713/policy/`) with the J715's names and
six lanes; `tests/test_j715_audio_policy.py` checks every file against its J713
source and the exact replacements. The filter graph keeps the J713's input
clamps and feeds left to lanes 0, 2 and 4 and right to lanes 1, 3 and 5
through the [speaker ID 3 filters](filters/README.md), each at the common gain
0.336: the largest filter L1 is 2.9016, so no input can exceed 0.975 of full
scale, the J713's bound. The raw six-channel card is hidden, as on the J713.

The J715 kit runs the same WirePlumber, UCM and default-node files, byte for
byte, but a louder graph (gain 0.60, a +4 dB low shelf at 150 Hz on the
woofers and an output clamp per lane) that is outside that bound; it is not
proposed here.

## Speaker ID

AID38 tunes each J715 by its speaker ID, 0 or 3, and the two filter sets
differ. The ADT's first amplifier (`i2c3/audio-speaker@38`) names the GPIOs
that carry it: `function-speaker-id0` and `function-speaker-id1` are pins 4
and 13 of the AP pinctrl (0x39a000000), with `valid-speaker-ids` 0 and 3.
Firmware leaves both as pulled-up inputs that no Linux driver claims.

`tools/m4-j715-speaker-id.py` reads them through the GPIO character device,
requesting both lines as-is (no direction, bias or drive flags) and releasing
them at once; pin 4 is bit 0 and pin 13 bit 1, and any value other than 0 or
3 is refused. On 2026-10-20, on one J715 whose macOS reports speaker ID 3, it
returned 3 three times; the three pinctrl registers (pins 4, 13 and the
amplifier reset, pin 15), the pin claims and the speaker protection state were
the same before and after, and the lines were released. The pinctrl driver
has no request or configuration hook, so an as-is request writes no register.

The inputs are pulled up, so an unconnected pin reads 1 as well. That a speaker
ID 0 J715 reads 0 on both pins follows from its ADT, but no such unit has been
read.

## Not here yet

Using the speaker ID to pick the filter set, and a delivery path. Until those
land, nothing in this repository installs these modules, the model, the
filters or the routing.
