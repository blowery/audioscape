#!/usr/bin/env python3
"""Renders the clips of the tape, drone, space, decay, bells and hum styles
into ../sounds/<style>/*.m4a.

    python3 tools/gen_styles.py            # all six
    python3 tools/gen_styles.py bells hum  # only these
"""
import math
import random
import sys

from common import RATE, TAU, clean, echo, glide, hz, lowpass, mix, noise, silence, strike, swell, swell2, tone, write


# --- tape: soft piano-like notes and sung notes, as if on old tape loops ---

def tape():
    out = clean("tape")
    piano = [(k * (1 + 0.0004 * k * k), 1 / k ** 1.7, 5.0 / k ** 0.8) for k in range(1, 7)]
    voice = [(1, 1.0), (1.004, 0.6), (2, 0.35), (3, 0.2), (4, 0.08)]

    def note(midi, cents=()):
        l, r = silence(9)
        pan = random.uniform(-0.4, 0.4)
        strike(l, r, 0.02, hz(midi), piano, pan=pan, attack=0.012)
        for c in cents:  # extra strings tuned off the note, which sounds sour
            strike(l, r, 0.02, hz(midi) * 2 ** (c / 1200), piano, level=0.8, pan=-pan, attack=0.012)
        lowpass(l, 0.5)
        lowpass(r, 0.5)
        return swell(l, 0.005, 2), swell(r, 0.005, 2)

    # D flat major pentatonic
    for midi in [61, 63, 65, 68, 70, 73, 75, 77]:
        write(out, "piano-%d" % midi, *note(midi), 0.5)
    for midi in [64, 71, 76]:
        write(out, "flat-%d" % midi, *note(midi, cents=(-45, 30)), 0.5)
    for midi in [49, 56]:
        write(out, "voice-%d" % midi, *tone(hz(midi), 20, 6, 7, voice, vibrato=0.003), 0.5)
    for midi in [65, 77]:
        write(out, "voice-%d" % midi, *tone(hz(midi), 9, 2.5, 4, voice, vibrato=0.003), 0.45)
    for midi in [73, 77, 80]:
        write(out, "sigh-%d" % midi, *tone(hz(midi), 5, 1.5, 3, voice[:3], vibrato=0.003), 0.35)


# --- drone: very long, very slow chords ---

def drone():
    out = clean("drone")
    rich = [(1, 1.0), (1.003, 0.7), (2, 0.4), (2.004, 0.3), (3, 0.2), (4, 0.12), (5, 0.06)]
    thin = [(1, 1.0), (1.002, 0.6), (2, 0.1)]
    for midi in [38, 45, 50]:
        write(out, "deep-%d" % midi, *tone(hz(midi), 30, 10, 12, rich), 0.5)
    # D with an added ninth; 58, 63 and 65 pull it toward a darker mode
    for midi in [57, 62, 64, 66, 69, 71, 74]:
        write(out, "mid-%d" % midi, *tone(hz(midi), 24, 8, 10, rich[:5]), 0.5)
    for midi in [58, 63, 65]:
        write(out, "dark-%d" % midi, *tone(hz(midi), 24, 8, 10, rich[:5]), 0.5)
    for midi in [81, 86]:
        write(out, "high-%d" % midi, *tone(hz(midi), 12, 4, 6, thin), 0.3)


# --- space: bright synth pads that open like a filter, with long echoes ---

def space():
    out = clean("space")
    saw = [(k, 1 / k) for k in range(1, 11)] + [(k * 1.004, 0.5 / k) for k in range(1, 6)]
    dark = [(1, 1.0), (1.004, 0.5), (2, 0.4), (3, 0.15)]
    glass = [(1, 1.0), (2, 0.2)]

    def pad(midi, seconds=9.0):
        l, r = tone(hz(midi), seconds, 2.5, 3.5, saw, bright=0.5)
        echo(l, r, 0.37, 0.45, 0.8)
        return swell(l, 0.01, 1.5), swell(r, 0.01, 1.5)

    for midi in [36, 43]:
        write(out, "sub-%d" % midi, *tone(hz(midi), 20, 6, 7, dark), 0.5)
    for midi in [48, 55]:
        write(out, "low-%d" % midi, *tone(hz(midi), 10, 3, 4, dark), 0.5)
    # C minor with a seventh and an eleventh
    for midi in [48, 55, 58, 60, 63, 65, 67, 70]:
        write(out, "lead-%d" % midi, *pad(midi), 0.5)
    for midi in [62, 74]:
        write(out, "hang-%d" % midi, *pad(midi), 0.45)
    for midi in [49, 54, 61]:
        write(out, "off-%d" % midi, *pad(midi), 0.5)
    for midi in [64, 76]:
        write(out, "clear-%d" % midi, *pad(midi), 0.5)
    for midi in [72, 75, 79, 82]:
        l, r = tone(hz(midi), 5, 1.2, 3, glass)
        echo(l, r, 0.31, 0.5, 0.8)
        write(out, "glint-%d" % midi, l, r, 0.3)


# --- decay: one warm phrase on a loop of tape that wears out ---

def decay():
    out = clean("decay")
    horn = [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.12), (5, 0.05)]

    def phrase(notes, seconds):
        clip = silence(seconds)
        for midi, at, length in notes:
            mix(clip, tone(hz(midi), length, 1.0, 2.0, horn, wow=0.003), at)
        return clip

    def worn(clip, level):
        """Copies a clip and wears it: duller, with dropouts, crackle and hiss."""
        result = []
        for channel in clip:
            xs = lowpass(list(channel), [1.0, 0.6, 0.4, 0.28, 0.2][level])
            top = max(map(abs, xs))
            for _ in range(level * 5):  # dropouts: the tape loses contact
                first = random.randrange(len(xs) - RATE)
                length = int(random.uniform(0.05, 0.3) * RATE)
                ramp = int(0.01 * RATE)
                for k in range(length):
                    edge = min(k, length - 1 - k, ramp) / ramp
                    xs[first + k] *= 1 - 0.9 * edge
            hiss = lowpass(noise(len(xs) / RATE), 0.5)
            for i in range(len(xs)):
                xs[i] += top * 0.012 * (1 + level) * hiss[i]
                if random.random() < level * 1.5 / RATE:  # crackle
                    xs[i] += top * random.uniform(-0.6, 0.6)
            result.append(xs)
        return result[0], result[1]

    whole = phrase([(58, 0.0, 4.5), (62, 1.6, 4.0), (65, 3.2, 4.0), (63, 5.0, 4.5)], 10)
    for level in range(5):
        write(out, "phrase-%d" % level, *worn(whole, level), 0.5)
    half = phrase([(58, 0.0, 4.5), (62, 1.6, 4.5)], 7)
    write(out, "phrase-half", *worn(half, 1), 0.45)

    for i in (1, 2):  # the machine itself: hiss and a faint hum
        clip = tone(hz(34), 20, 6, 7, [(1, 0.3), (2, 1.0), (3, 0.4)])
        for channel in clip:
            hiss = swell(lowpass(noise(20), 0.15), 6, 7)
            for k in range(len(channel)):
                channel[k] = 0.25 * channel[k] + hiss[k]
        write(out, "bed-%d" % i, clip[0], clip[1], 0.3)

    for i in (1, 2):  # a patch of bad tape
        clip = []
        for _ in range(2):
            xs = lowpass(noise(4), 0.3)
            for k in range(len(xs)):
                xs[k] *= 0.15
                if random.random() < 60 / RATE:
                    xs[k] += random.uniform(-1, 1)
            clip.append(swell(xs, 1, 2))
        write(out, "crackle-%d" % i, clip[0], clip[1], 0.35)

    for midi in [77, 82]:
        write(out, "shimmer-%d" % midi, *tone(hz(midi), 5, 1.5, 3, horn[:2], wow=0.004), 0.3)


# --- bells: struck metal with long ring-outs, in a five-note scale ---

def bells():
    out = clean("bells")
    bell = [(1, 1.0, 4.0), (2.02, 0.5, 2.5), (2.76, 0.35, 1.6), (5.4, 0.12, 0.7)]
    gong = [(1, 1.0, 9.0), (1.012, 0.8, 9.0), (2.4, 0.3, 4.0), (3.9, 0.12, 2.0)]
    # five nearly equal steps to the octave, like a slendro tuning
    steps = [0, 240, 480, 720, 960]

    def pitch(base, step, extra=0):
        return base * 2 ** ((steps[step] + extra) / 1200)

    def one(freq, seconds, modes=bell, attack=0.008):
        l, r = silence(seconds)
        strike(l, r, 0.02, freq, modes, pan=random.uniform(-0.6, 0.6), attack=attack)
        return swell(l, 0.001, seconds * 0.3), swell(r, 0.001, seconds * 0.3)

    write(out, "gong-1", *one(73.4, 20, gong, 0.03), 0.55)
    write(out, "gong-2", *one(pitch(73.4, 3), 20, gong, 0.03), 0.55)
    for step in range(5):
        write(out, "low-%d" % step, *one(pitch(146.8, step), 9), 0.5)
        write(out, "mid-%d" % step, *one(pitch(293.7, step), 8), 0.5)
        write(out, "high-%d" % step, *one(pitch(587.3, step), 6), 0.35)
    for i, step in enumerate([1, 2, 4], 1):  # two bells a bit less than a semitone apart
        l, r = silence(8)
        strike(l, r, 0.02, pitch(293.7, step), bell, pan=-0.4, attack=0.008)
        strike(l, r, 0.05, pitch(293.7, step, 85), bell, level=0.9, pan=0.4, attack=0.008)
        write(out, "clash-%d" % i, swell(l, 0.001, 2.5), swell(r, 0.001, 2.5), 0.5)
    l, r = silence(9)
    for k, (base, step) in enumerate([(293.7, 0), (293.7, 2), (293.7, 3), (587.3, 0)]):
        strike(l, r, 0.02 + 0.35 * k, pitch(base, step), bell, level=0.7, pan=-0.5 + 0.33 * k, attack=0.012)
    write(out, "roll", swell(l, 0.001, 3), swell(r, 0.001, 3), 0.45)


# --- hum: the inside of a ship, deep under water or far out in space ---

def hum():
    out = clean("hum")

    def engine(base):
        clip = tone(base, 20, 6, 7, [(1, 0.6), (2, 1.0), (2.01, 0.5), (3, 0.5), (4, 0.25), (6, 0.08)])
        for channel in clip:
            rumble = swell(lowpass(noise(20), 0.02), 6, 7)
            for k in range(len(channel)):
                channel[k] += 4 * rumble[k]
        return clip

    write(out, "hum-low", *engine(55.0), 0.5)
    write(out, "hum-high", *engine(61.7), 0.5)

    for i, rate in [(1, 1.1), (2, 0.8)]:  # machinery turning over
        clip = tone(82.4, 8, 2, 3, [(1, 1.0), (2, 0.6), (3, 0.2)])
        for channel in clip:
            for k in range(len(channel)):
                channel[k] *= (0.5 + 0.5 * math.sin(TAU * rate * k / RATE)) ** 2
        write(out, "pulse-%d" % i, clip[0], clip[1], 0.45)

    groaning = [(1, 1.0), (2.3, 0.5), (3.7, 0.25)]
    for i in (1, 2):  # the hull settling, far off
        l, r = silence(8)
        t = random.uniform(0.3, 1.0)
        for _ in range(random.randint(1, 2)):
            f = random.uniform(150, 210)
            glide(l, r, t, f, f * 0.78, 2.5, pan=random.uniform(-0.7, 0.7), partials=[(1, 1.0), (1.5, 0.4), (2.02, 0.3)])
            t += random.uniform(2.5, 3.5)
        echo(l, r, 0.45, 0.4, 0.8)
        write(out, "creak-%d" % i, swell(l, 0.01, 1.5), swell(r, 0.01, 1.5), 0.3)

    for i in (1, 2):  # the hull under strain
        l, r = silence(8)
        glide(l, r, 0.2, 125, 72, 4.5, pan=-0.3, partials=groaning)
        glide(l, r, 1.4, 96, 60, 4.5, level=0.7, pan=0.4, partials=groaning)
        for channel in (l, r):
            rumble = swell(lowpass(noise(8), 0.03), 1, 4)
            for k in range(len(channel)):
                channel[k] += 3 * rumble[k]
        write(out, "groan-%d" % i, swell(l, 0.01, 2), swell(r, 0.01, 2), 0.55)

    for i, freq in [(1, 880.0), (2, 740.0)]:  # sonar: one ping and its returns
        l, r = silence(8)
        strike(l, r, 0.1, freq, [(1, 1.0, 0.5), (2, 0.1, 0.2)], attack=0.01)
        echo(l, r, 0.55, 0.55, 0.9)
        write(out, "ping-%d" % i, swell(l, 0.001, 2), swell(r, 0.001, 2), 0.4)

    # pressure released: a breath of air under a soft major chord
    l, r = silence(6)
    for freq in (220.0, 277.2, 329.6):
        mix((l, r), tone(freq, 6, 2, 3, [(1, 1.0), (2, 0.2)]), 0, 0.5)
    for channel in (l, r):
        hiss = noise(6)
        dull = lowpass(list(hiss), 0.3)
        for k in range(len(channel)):
            channel[k] += 0.5 * (hiss[k] - dull[k])
    write(out, "vent", swell(l, 2, 3), swell(r, 2, 3), 0.4)

    for i in (1, 2, 3):  # bubbles rising past the hull
        l, r = silence(4)
        for _ in range(random.randint(6, 12)):
            f = random.uniform(350, 700)
            glide(l, r, random.uniform(0.1, 2.6), f, f * random.uniform(1.6, 2.4), random.uniform(0.04, 0.09),
                  level=random.uniform(0.3, 1.0), pan=random.uniform(-0.8, 0.8))
        echo(l, r, 0.19, 0.35, 0.7)
        write(out, "bubbles-%d" % i, l, r, 0.3)


STYLES = {"tape": tape, "drone": drone, "space": space, "decay": decay, "bells": bells, "hum": hum}

if __name__ == "__main__":
    random.seed(23)
    for name in sys.argv[1:] or STYLES:
        STYLES[name]()
