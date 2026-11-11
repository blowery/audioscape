#!/usr/bin/env python3
"""Renders the clips of the "tonal" style into ../sounds/tonal/*.m4a.

Standard library only. Run it again after changing a sound:
    python3 tools/gen_tonal.py
"""
import math
import os
import random
import struct
import wave

import common

RATE = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds", "tonal")
TAU = 2 * math.pi

random.seed(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def write(name, left, right, peak=0.6):
    common.write(OUT, name, left, right, peak)


def pad(midi, seconds=8.0, attack=2.5, release=3.5):
    """A slow swell: detuned sines with a little drift, different per ear."""
    f = hz(midi)
    n = int(seconds * RATE)
    # (frequency ratio, level, detune for left, detune for right)
    partials = [
        (1.0, 1.00, 0.9985, 1.0015),
        (1.0, 0.60, 1.0030, 0.9970),
        (2.0, 0.22, 1.0010, 0.9990),
        (3.0, 0.07, 0.9990, 1.0010),
    ]
    lfo = 0.11 + random.random() * 0.1
    phase = random.random() * TAU
    left, right = [], []
    for i in range(n):
        t = i / RATE
        if t < attack:
            env = math.sin(0.5 * math.pi * t / attack) ** 2
        elif t > seconds - release:
            env = math.cos(0.5 * math.pi * (t - (seconds - release)) / release) ** 2
        else:
            env = 1.0
        env *= 0.85 + 0.15 * math.sin(TAU * lfo * t + phase)
        l = r = 0.0
        for ratio, level, dl, dr in partials:
            l += level * math.sin(TAU * f * ratio * dl * t)
            r += level * math.sin(TAU * f * ratio * dr * t + 0.7)
        left.append(l * env)
        right.append(r * env)
    return left, right


def main():
    common.clean("tonal")

    # The floor: 20 second swells that overlap, so there is never silence.
    for midi in [38, 45, 50]:
        write("drone-%d" % midi, *pad(midi, 20, 6, 7), peak=0.55)
        print("drone", midi)

    # The middle: 8 second swells. 51 and 56 are the sour notes; 54 and 66
    # are the major third that a finished turn resolves to.
    for midi in [50, 51, 53, 54, 55, 56, 57, 60, 61, 62, 63, 64, 65, 66]:
        write("pad-%d" % midi, *pad(midi), peak=0.55)
        print("pad", midi)

    # The top: short, soft, high swells that follow tool activity.
    for midi in [69, 72, 74, 77, 81]:
        write("air-%d" % midi, *pad(midi, 5, 1.5, 3), peak=0.4)
        print("air", midi)


if __name__ == "__main__":
    main()
