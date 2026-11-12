"""Synthesis helpers shared by the style generators. Standard library only.

Clips are rendered as WAV and then compressed to AAC with afconvert, which
ships with macOS. The mod plays through afplay, so it is macOS only anyway.
"""
import math
import os
import random
import struct
import subprocess
import wave

RATE = 22050
TAU = 2 * math.pi
SOUNDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sounds")


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def clean(style):
    """Empties sounds/<style>/ and returns its path."""
    out = os.path.join(SOUNDS, style)
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        os.remove(os.path.join(out, name))
    return out


def write(out, name, left, right, peak):
    """Writes one stereo clip as <out>/<name>.m4a, scaled so its loudest sample is `peak`."""
    top = max(max(map(abs, left)), max(map(abs, right)), 1e-9)
    scale = peak / top * 32767
    frames = bytearray()
    for l, r in zip(left, right):
        frames += struct.pack("<hh", int(l * scale), int(r * scale))
    wav = os.path.join(out, name + ".wav")
    with wave.open(wav, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(bytes(frames))
    subprocess.run(
        ["afconvert", wav, "-o", os.path.join(out, name + ".m4a"), "-f", "m4af", "-d", "aac", "-b", "64000"],
        check=True,
    )
    os.remove(wav)
    print(os.path.basename(out) + "/" + name)


def silence(seconds):
    n = int(seconds * RATE)
    return [0.0] * n, [0.0] * n


def swell(xs, attack, release):
    """Fades a clip in and out, so clips can overlap without a seam."""
    n = len(xs)
    a, r = int(attack * RATE), int(release * RATE)
    for i in range(a):
        xs[i] *= math.sin(0.5 * math.pi * i / a) ** 2
    for i in range(r):
        xs[n - 1 - i] *= math.sin(0.5 * math.pi * i / r) ** 2
    return xs


def swell2(pair, attack, release):
    return swell(pair[0], attack, release), swell(pair[1], attack, release)


def pan_gains(pan):
    return math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)


def lowpass(xs, coef):
    """One-pole low-pass in place. coef 1 passes everything; smaller is darker."""
    y = 0.0
    for i, x in enumerate(xs):
        y += coef * (x - y)
        xs[i] = y
    return xs


def bandpass(xs, low, high, damp=0.5):
    """Band-pass in place. The centre moves from `low` to `high` Hz across the
    clip; pass the same value twice to hold it still. Smaller damp rings more."""
    n = len(xs)
    lo = band = 0.0
    f = 2 * math.sin(math.pi * low / RATE)
    for i, x in enumerate(xs):
        if low != high and i % 64 == 0:
            f = 2 * math.sin(math.pi * (low + (high - low) * i / n) / RATE)
        lo += f * band
        band += f * (x - lo - damp * band)
        xs[i] = band
    return xs


def noise(seconds):
    return [random.random() * 2 - 1 for _ in range(int(seconds * RATE))]


def mix(into, pair, at=0.0, level=1.0):
    """Adds a stereo clip into a longer one, starting `at` seconds in."""
    first = int(at * RATE)
    for dst, src in zip(into, pair):
        for i, s in enumerate(src):
            if first + i >= len(dst):
                break
            dst[first + i] += s * level
    return into


def echo(left, right, delay, feedback, level):
    """Repeats that bounce between the ears and die away."""
    d = int(delay * RATE)
    for i in range(d, len(left)):
        left[i] += level * feedback * right[i - d]
        right[i] += level * feedback * left[i - d]
    return left, right


def tone(freq, seconds, attack, release, partials, bright=0.0, vibrato=0.0, wow=0.0):
    """A sustained note that swells in and out.

    partials: [(frequency ratio, level)]. Each ear is tuned slightly apart.
    bright:   above 0, the upper partials arrive late and leave early, like a
              filter opening and closing.
    vibrato:  depth of a 5 Hz pitch wobble (0.003 is gentle).
    wow:      depth of a slow, uneven pitch drift, like a worn tape.
    """
    n = int(seconds * RATE)
    lfo = 0.11 + random.random() * 0.1
    p0, p1, p2 = (random.random() * TAU for _ in range(3))
    count = len(partials)
    phase_l = [0.0] * count
    phase_r = [random.random() for _ in range(count)]
    step = [TAU * freq * ratio / RATE for ratio, _ in partials]
    spread = [0.0015 if k % 2 == 0 else -0.0015 for k in range(count)]
    left, right = [], []
    for i in range(n):
        t = i / RATE
        if t < attack:
            env = math.sin(0.5 * math.pi * t / attack) ** 2
        elif t > seconds - release:
            env = math.cos(0.5 * math.pi * (t - (seconds - release)) / release) ** 2
        else:
            env = 1.0
        bend = 1.0
        if vibrato:
            bend += vibrato * math.sin(TAU * 5.2 * t + p1)
        if wow:
            bend += wow * math.sin(TAU * 0.6 * t + p2) + 0.5 * wow * math.sin(TAU * 3.1 * t)
        l = r = 0.0
        for k in range(count):
            ratio, level = partials[k]
            if bright:
                level *= (env + 1e-6) ** (bright * (ratio - 1))
            phase_l[k] += step[k] * bend * (1 + spread[k])
            phase_r[k] += step[k] * bend * (1 - spread[k])
            l += level * math.sin(phase_l[k])
            r += level * math.sin(phase_r[k])
        env *= 0.85 + 0.15 * math.sin(TAU * lfo * t + p0)
        left.append(l * env)
        right.append(r * env)
    return left, right


def strike(left, right, at, freq, modes, level=1.0, pan=0.0, attack=0.003):
    """Adds a struck note that rings out. modes: [(ratio, level, decay seconds)]."""
    gl, gr = pan_gains(pan)
    first = int(at * RATE)
    for k in range(len(left) - first):
        u = k / RATE
        s = 0.0
        for ratio, mlevel, decay in modes:
            s += mlevel * math.exp(-u / decay) * math.sin(TAU * freq * ratio * u)
        s *= level * min(1.0, u / attack)
        left[first + k] += s * gl
        right[first + k] += s * gr


def glide(left, right, at, f0, f1, length, level=1.0, pan=0.0, partials=((1.0, 1.0),)):
    """Adds a note that slides from f0 to f1 over `length` seconds."""
    gl, gr = pan_gains(pan)
    first = int(at * RATE)
    count = int(length * RATE)
    phase = 0.0
    for k in range(count):
        if first + k >= len(left):
            break
        u = k / count
        phase += TAU * (f0 + (f1 - f0) * u) / RATE
        s = 0.0
        for ratio, plevel in partials:
            s += plevel * math.sin(phase * ratio)
        s *= level * math.sin(math.pi * u) ** 2
        left[first + k] += s * gl
        right[first + k] += s * gr
