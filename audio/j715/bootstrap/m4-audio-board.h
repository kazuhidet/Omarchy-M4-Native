/* SPDX-License-Identifier: GPL-2.0-only */
/* Board selection for the protected M4 speaker stack. Exactly one board per build. */
#ifndef M4_AUDIO_BOARD_H
#define M4_AUDIO_BOARD_H
#ifdef M4_AUDIO_J715
/* J715 (15-inch M4 Air): six SN012776 on i2c3, ADT speaker order. */
#define M4_BOARD "apple,j715"
#define M4_NAMP 6
#define M4_ADDRESSES { 0x38, 0x3b, 0x39, 0x3c, 0x3a, 0x3d }
#define M4_PREFIXES { "Left Woofer 1", "Right Woofer 1", "Left Tweeter", "Right Tweeter", \
		      "Left Woofer 2", "Right Woofer 2" }
/* ADT amp-tx-zd-config trimmed to the 24 feedback byte-slots in use (12 x S16), the same
 * rule the J713 code applies to its ADT value f0 f0 f0 ff -> f0 f0 00 00 (16 byte-slots). */
#define M4_TX_ZD_MASKS { {0xf0,0xf0,0xf0,0}, {0x0f,0x0f,0x0f,0}, {0}, {0}, {0}, {0} }
#define M4_GROUP_COMPAT "apple,j715-speaker-group"
#define M4_GROUP_DRIVER "j715-speaker-group"
#define M4_CARD_COMPAT "apple,j715-audio"
#define M4_CARD_NAME "Apple J715"
#define M4_CARD_ID "AppleJ715"
#define M4_WOOFER_ROUTES \
	{ "Speaker", NULL, "Left Woofer 1 OUT" }, { "Speaker", NULL, "Right Woofer 1 OUT" }, \
	{ "Speaker", NULL, "Left Woofer 2 OUT" }, { "Speaker", NULL, "Right Woofer 2 OUT" },
#else
#define M4_BOARD "apple,j713"
#define M4_NAMP 4
#define M4_ADDRESSES { 0x38, 0x3b, 0x39, 0x3c }
#define M4_PREFIXES { "Left Woofer", "Right Woofer", "Left Tweeter", "Right Tweeter" }
#define M4_TX_ZD_MASKS {{0xf0,0xf0,0,0},{0x0f,0x0f,0,0},{0},{0}}
#define M4_GROUP_COMPAT "apple,j713-speaker-group"
#define M4_GROUP_DRIVER "j713-speaker-group"
#define M4_CARD_COMPAT "apple,j713-audio"
#define M4_CARD_NAME "Apple J713"
#define M4_CARD_ID "AppleJ713"
#define M4_WOOFER_ROUTES \
	{ "Speaker", NULL, "Left Woofer OUT" }, { "Speaker", NULL, "Right Woofer OUT" },
#endif
/* Playback: one S32 slot per amplifier. Feedback: V and I S16 per amplifier. */
#define M4_TX_CH M4_NAMP
#define M4_RX_CH (2 * M4_NAMP)
#define M4_TX_SLOT_MASK ((1U << M4_TX_CH) - 1)
#define M4_RX_SLOT_MASK ((1ULL << M4_RX_CH) - 1)
/* Expected MCA words checked by j713_frame_unlocked(); J713: 0x17503 / 0x1b047 / ~0xf / ~0xff. */
#define M4_TX_SERDES_WORD (0x17500U | (M4_TX_CH - 1))
#define M4_RX_CONFIG_WORD (0x1b040U | (M4_RX_CH - 1))
#define M4_TX_SLOT_INV ((u32)~M4_TX_SLOT_MASK)
#define M4_RX_SLOT_INV ((u32)~M4_RX_SLOT_MASK)
#endif
