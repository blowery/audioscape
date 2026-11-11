#!/usr/bin/env python3
"""Renders the clips of the "nature" style into ../sounds/nature/*.m4a.

Everything is synthesized from filtered noise and sine chirps, so it is a
stylized outdoors and not a field recording. Standard library only:
    python3 tools/gen_nature.py
"""
import math
import os
import random
import struct
import wave

import common

RATE = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds", "nature")
TAU = 2 * math.pi

random.seed(11)


def write(name, left, right, peak):
    common.write(OUT, name, left, right, peak)


def swell(xs, attack, release):
    """Fades a clip in and out, so clips can overlap without a seam."""
    n = len(xs)
    a, r = int(attack * RATE), int(release * RATE)
    for i in range(a):
        xs[i] *= math.sin(0.5 * math.pi * i / a) ** 2
    for i in range(r):
        xs[n - 1 - i] *= math.sin(0.5 * math.pi * i / r) ** 2
    return xs


def both(make):
    """Runs a one-channel generator twice. The two ears get different noise,
    which is what makes it sound wide."""
    return make(), make()


def pan_gains(pan):
    return math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)


def wind_channel(seconds, low, high, gust):
    """Noise through a band-pass filter whose centre drifts between low and high."""
    n = int(seconds * RATE)
    p1, p2, p3 = (random.random() * TAU for _ in range(3))
    lo = band = rumble = 0.0
    f = amp = 0.0
    out = []
    for i in range(n):
        if i % 64 == 0:
            t = i / RATE
            drift = 0.5 + 0.25 * math.sin(TAU * 0.07 * t + p1) + 0.25 * math.sin(TAU * 0.19 * t + p2)
            f = 2 * math.sin(math.pi * (low + (high - low) * drift) / RATE)
            amp = (0.6 + 0.4 * math.sin(TAU * 0.05 * t + p3)) ** (1 + gust)
        x = random.random() * 2 - 1
        lo += f * band
        band += f * (x - lo - 0.7 * band)
        rumble += 0.02 * (x - rumble)
        out.append(amp * (band + 1.5 * rumble))
    return out


def rain_channel(seconds, hiss, drops_per_second, roof):
    """A hiss, separate droplets ringing at a few pitches, and a low patter."""
    n = int(seconds * RATE)
    chance = drops_per_second / RATE
    rings = [[2 * math.sin(math.pi * fc / RATE), 0.0, 0.0] for fc in (1900, 2700, 3600, 4700)]
    lp = smooth = low = 0.0
    phase = random.random() * TAU
    out = []
    for i in range(n):
        x = random.random() * 2 - 1
        lp += 0.35 * (x - lp)
        smooth += 0.6 * ((x - lp) - smooth)
        low += 0.05 * (x - low)
        hit = random.random() < chance
        drops = 0.0
        for ring in rings:
            f, rlo, rband = ring
            kick = 0.0
            if hit and random.random() < 0.3:
                kick = 0.3 + random.random()
            rlo += f * rband
            rband += f * (kick - rlo - 0.12 * rband)
            ring[1], ring[2] = rlo, rband
            drops += rband
        wobble = 0.85 + 0.15 * math.sin(TAU * 0.13 * i / RATE + phase)
        out.append(wobble * (hiss * smooth + roof * low) + 0.25 * drops)
    return out


def crickets(seconds, voices):
    n = int(seconds * RATE)
    left, right = [0.0] * n, [0.0] * n
    for _ in range(voices):
        freq = random.uniform(4100, 4900)
        period = random.uniform(0.45, 0.95)
        pulses = random.choice([2, 3, 3, 4])
        level = random.uniform(0.3, 1.0)
        gl, gr = pan_gains(random.uniform(-0.9, 0.9))
        t = random.uniform(0, period)
        while t < seconds:
            for p in range(pulses):
                first = int((t + p * 0.032) * RATE)
                length = int(0.02 * RATE)
                for k in range(length):
                    if first + k >= n:
                        break
                    s = level * math.sin(math.pi * k / length) ** 2 * math.sin(TAU * freq * k / RATE)
                    left[first + k] += s * gl
                    right[first + k] += s * gr
            t += period * random.uniform(0.92, 1.08)
    return left, right


def chirp(left, right, at, f0, f1, length, level, pan, echoes):
    """A sine that glides from f0 to f1, with quieter repeats for distance."""
    n = len(left)
    count = int(length * RATE)
    for delay, gain, shift in [(0.0, 1.0, 0.0)] + echoes:
        gl, gr = pan_gains(max(-1.0, min(1.0, pan + shift)))
        first = int((at + delay) * RATE)
        phase = 0.0
        for k in range(count):
            if first + k >= n:
                break
            u = k / count
            phase += TAU * (f0 + (f1 - f0) * u) / RATE
            s = level * gain * math.sin(math.pi * u) ** 2 * math.sin(phase)
            left[first + k] += s * gl
            right[first + k] += s * gr


def birds(seconds, phrases):
    n = int(seconds * RATE)
    left, right = [0.0] * n, [0.0] * n
    echoes = [(0.13, 0.3, 0.3), (0.27, 0.12, -0.3)]
    for _ in range(phrases):
        t = random.uniform(0.4, seconds - 2.0)
        pan = random.uniform(-0.8, 0.8)
        base = random.uniform(2500, 4000)
        for _ in range(random.randint(3, 6)):
            length = random.uniform(0.06, 0.14)
            f0 = base * random.uniform(0.85, 1.2)
            chirp(left, right, t, f0, f0 * random.uniform(0.75, 1.35), length, 1.0, pan, echoes)
            t += length + random.uniform(0.03, 0.09)
    return left, right


def chimes(seconds):
    """Wind chimes: five metal tubes in a pentatonic scale. A breath of wind
    knocks two to four of them, then they ring out before the next one."""
    n = int(seconds * RATE)
    left, right = [0.0] * n, [0.0] * n
    # (frequency, pan) for D5 E5 G5 A5 C6, slightly off true like real tubes
    tubes = [(587.3 * 1.004, -0.6), (659.3 * 0.997, 0.3), (784.0 * 1.002, -0.2), (880.0 * 0.995, 0.6), (1046.5 * 1.003, 0.0)]
    # a tube's overtones are not whole multiples, which is what sounds metallic
    modes = [(1.0, 1.0, 2.6), (2.76, 0.45, 1.4), (5.40, 0.2, 0.7), (8.93, 0.08, 0.35)]
    t = random.uniform(0.3, 1.2)
    while t < seconds - 4.0:
        at = t
        for _ in range(random.randint(2, 4)):
            freq, pan = random.choice(tubes)
            level = random.uniform(0.25, 1.0)
            gl, gr = pan_gains(pan)
            first = int(at * RATE)
            for k in range(n - first):
                u = k / RATE
                s = 0.0
                for ratio, mlevel, decay in modes:
                    s += mlevel * math.exp(-u / decay) * math.sin(TAU * freq * ratio * u)
                s *= level * min(1.0, u / 0.003)
                left[first + k] += s * gl
                right[first + k] += s * gr
            at += random.uniform(0.08, 0.45)
        t = at + random.uniform(1.5, 3.5)
    return left, right


def rustle_channel(seconds):
    """Leaves: bright noise whose loudness flutters at random."""
    n = int(seconds * RATE)
    lp = smooth = flutter = 0.0
    out = []
    for _ in range(n):
        x = random.random() * 2 - 1
        lp += 0.4 * (x - lp)
        smooth += 0.7 * ((x - lp) - smooth)
        flutter += 0.004 * (abs(random.random() * 2 - 1) ** 3 * 4 - flutter)
        out.append(smooth * flutter)
    return out


def thunder_channel(seconds):
    """Far-off thunder: low noise shaped as a few rolling rumbles."""
    n = int(seconds * RATE)
    rolls = [(0.3, 1.0), (random.uniform(1.2, 1.8), 0.7), (random.uniform(2.6, 3.4), 0.5), (random.uniform(4.2, 5.0), 0.3)]
    a = b = mid = wobble = 0.0
    out = []
    for i in range(n):
        t = i / RATE
        x = random.random() * 2 - 1
        a += 0.03 * (x - a)
        b += 0.06 * (a - b)
        mid += 0.2 * (x - mid)
        wobble += 0.0008 * (abs(x) * 2 - wobble)
        env = 0.0
        for start, level in rolls:
            if t > start:
                env += level * min(1.0, (t - start) / 0.25) * math.exp(-(t - start) / 2.0)
        out.append(env * (0.5 + wobble) * (b * 6 + mid * 0.12))
    return out


def main():
    common.clean("nature")

    # The floor: wind. 20 second clips that overlap.
    for name, low, high, gust, peak in [("wind-low", 180, 500, 0.0, 0.5), ("wind-mid", 300, 900, 0.5, 0.5), ("wind-gusty", 350, 1300, 1.5, 0.55)]:
        l, r = both(lambda: swell(wind_channel(20, low, high, gust), 6, 7))
        write(name, l, r, peak)

    # Working: rain. 12 second clips; "heavy" is for when things go wrong.
    for name, hiss, rate, roof, peak in [("rain-light", 0.5, 25, 0.0, 0.3), ("rain-steady", 1.0, 60, 0.3, 0.45), ("rain-heavy", 1.6, 140, 1.2, 0.6)]:
        l, r = both(lambda: swell(rain_channel(12, hiss, rate, roof), 3.5, 4.5))
        write(name, l, r, peak)

    # Idle: a still night.
    for i, voices in [(1, 3), (2, 5)]:
        l, r = crickets(10, voices)
        write("crickets-%d" % i, swell(l, 3, 3.5), swell(r, 3, 3.5), 0.22)

    # Waiting on a person: wind chimes ringing in a light wind.
    for i in (1, 2, 3):
        l, r = chimes(11)
        write("chimes-%d" % i, swell(l, 0.01, 2.5), swell(r, 0.01, 2.5), 0.35)

    # Tools running: distant birds, leaves, a gust.
    for i in (1, 2, 3):
        l, r = birds(5, 1)
        write("bird-%d" % i, l, r, 0.22)
    for i in (1, 2):
        l, r = both(lambda: swell(rustle_channel(5), 1.5, 2.5))
        write("rustle-%d" % i, l, r, 0.3)
        l, r = both(lambda: swell(wind_channel(5, 250, 800, 1.0), 1.5, 2.5))
        write("gust-%d" % i, l, r, 0.45)

    # A failed tool call: thunder, far away.
    for i in (1, 2):
        l, r = both(lambda: swell(thunder_channel(10), 0.2, 3))
        write("thunder-%d" % i, l, r, 0.7)

    # A turn that ends with an answer: the sky clears and several birds sing.
    l, r = birds(8, 4)
    write("clearing", swell(l, 0.5, 2), swell(r, 0.5, 2), 0.25)


if __name__ == "__main__":
    main()
