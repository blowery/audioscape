// A style fills three layers with its own clips, from sounds/<style>/:
//   drone  the floor. Long clips that overlap, so it never goes silent.
//   pad    the middle. Its clips and pace follow the session's mood.
//   air    the top. Soft, brief clips that appear while tools are running.
export type Mood = 'idle' | 'working' | 'waiting'

export type Layer = {
  clips: readonly string[]
  /** Shortest and longest gap between clips, in milliseconds. */
  gap: readonly [number, number]
  gain: number
}

export type Style = {
  /** One line for the style list. */
  about: string
  drone: Record<Mood, Layer>
  pad: Record<Mood, Layer>
  /** Mixed into the working pad as failed tool calls add tension. */
  sour: readonly string[]
  /** Played once when a tool call fails. */
  onError: readonly string[]
  /** Played once when a turn ends with an answer. */
  resolve: readonly string[]
  /** What each tool adds while it runs, and what any other tool adds. */
  air: Record<string, readonly string[]>
  airOther: readonly string[]
  airGain: number
  /** The least time between two air clips, in milliseconds. */
  airEvery: number
}

const named = (prefix: string, ...ids: (number | string)[]): string[] => ids.map(id => `${prefix}-${id}`)
const layer = (clips: readonly string[], low: number, high: number, gain: number): Layer => ({
  clips,
  gap: [low * 1000, high * 1000],
  gain,
})

const BIRDS = named('bird', 1, 2, 3)
const RUSTLES = named('rustle', 1, 2)
const TONAL_HIGH = named('air', 77, 81)
const TONAL_MIDDLE = named('air', 69, 72)
const THUNDER = named('thunder', 1, 2)
const TONAL_SOUR = named('pad', 51, 56, 61, 63)
const TAPE_SOUR = named('flat', 64, 71, 76)
const DRONE_SOUR = named('dark', 58, 63, 65)
const SPACE_SOUR = named('off', 49, 54, 61)
const BELL_SOUR = named('clash', 1, 2, 3)
const GROANS = named('groan', 1, 2)
const TYPING = named('typing', 1, 2, 3)
const PAGES = named('page', 1, 2)
const CLATTER = named('clatter', 1, 2)

export const STYLES: Record<string, Style> = {
  nature: {
    about: 'wind, crickets, rain, wind chimes for questions, thunder for errors',
    drone: {
      idle: layer(['wind-low', 'wind-mid'], 5, 7, 0.32),
      working: layer(['wind-mid', 'wind-gusty'], 5, 7, 0.32),
      waiting: layer(['wind-low'], 6, 8, 0.22),
    },
    pad: {
      idle: layer(named('crickets', 1, 2), 5, 7.5, 0.3),
      working: layer(['rain-light', 'rain-steady', 'rain-steady'], 4, 6, 0.5),
      waiting: layer(named('chimes', 1, 2, 3), 6, 9, 0.4),
    },
    sour: [...THUNDER, 'rain-heavy', 'rain-heavy'],
    onError: THUNDER,
    resolve: ['clearing'],
    air: { Read: BIRDS, Grep: BIRDS, Glob: BIRDS, Edit: RUSTLES, Write: RUSTLES, Bash: named('gust', 1, 2) },
    airOther: ['rustle-1', 'gust-1', 'bird-2'],
    airGain: 0.3,
    airEvery: 3500,
  },
  tonal: {
    about: 'slow synth notes in a minor pentatonic scale',
    drone: {
      idle: layer(named('drone', 38, 45), 5, 7, 0.38),
      working: layer(named('drone', 38, 45, 50), 5, 7, 0.34),
      waiting: layer(['drone-45'], 6, 8, 0.25),
    },
    pad: {
      idle: layer(named('pad', 50, 57), 10, 16, 0.3),
      working: layer(named('pad', 50, 53, 55, 57, 60, 62, 65), 2.2, 4.2, 0.5),
      waiting: layer(named('pad', 57, 64), 3, 3.6, 0.42),
    },
    sour: TONAL_SOUR,
    onError: TONAL_SOUR,
    resolve: named('pad', 54, 66),
    air: {
      Read: TONAL_HIGH,
      Grep: TONAL_HIGH,
      Glob: TONAL_HIGH,
      Edit: TONAL_MIDDLE,
      Write: TONAL_MIDDLE,
    },
    airOther: named('air', 72, 74),
    airGain: 0.3,
    airEvery: 1500,
  },
  tape: {
    about: 'soft piano notes and sung notes on loops that never line up',
    drone: {
      idle: layer(named('voice', 49, 56), 5, 7, 0.28),
      working: layer(named('voice', 49, 56), 5, 7, 0.3),
      waiting: layer(['voice-56'], 6, 8, 0.22),
    },
    pad: {
      idle: layer(named('piano', 61, 68, 73), 8, 13, 0.4),
      working: layer(named('piano', 61, 63, 65, 68, 70, 73, 75, 77), 2.8, 5.2, 0.45),
      waiting: layer(named('piano', 63, 70), 3.5, 4.5, 0.4),
    },
    sour: TAPE_SOUR,
    onError: TAPE_SOUR,
    resolve: named('voice', 65, 77),
    air: {},
    airOther: named('sigh', 73, 77, 80),
    airGain: 0.22,
    airEvery: 2500,
  },
  drone: {
    about: 'very long, very slow chords that darken when things go wrong',
    drone: {
      idle: layer(named('deep', 38, 45), 8, 11, 0.36),
      working: layer(named('deep', 38, 45, 50), 8, 11, 0.36),
      waiting: layer(['deep-45'], 9, 12, 0.28),
    },
    pad: {
      idle: layer(named('mid', 57, 62), 14, 20, 0.3),
      working: layer(named('mid', 57, 62, 64, 66, 69), 7, 11, 0.38),
      waiting: layer(named('mid', 64, 71), 9, 12, 0.34),
    },
    sour: DRONE_SOUR,
    onError: DRONE_SOUR,
    resolve: ['mid-74'],
    air: {},
    airOther: named('high', 81, 86),
    airGain: 0.15,
    airEvery: 9000,
  },
  space: {
    about: 'wide, bright synth pads with long echoes over a low hum',
    drone: {
      idle: layer(named('sub', 36, 43), 5, 7, 0.38),
      working: layer(named('sub', 36, 43), 5, 7, 0.32),
      waiting: layer(['sub-43'], 6, 8, 0.25),
    },
    pad: {
      idle: layer(named('low', 48, 55), 9, 14, 0.35),
      working: layer(named('lead', 48, 55, 58, 60, 63, 65, 67, 70), 2.6, 4.8, 0.42),
      waiting: layer(named('hang', 62, 74), 3.2, 4, 0.36),
    },
    sour: SPACE_SOUR,
    onError: SPACE_SOUR,
    resolve: named('clear', 64, 76),
    air: {},
    airOther: named('glint', 72, 75, 79, 82),
    airGain: 0.25,
    airEvery: 1800,
  },
  decay: {
    about: 'one warm phrase on a tape loop that wears out as errors pile up',
    drone: {
      idle: layer(named('bed', 1, 2), 5, 7, 0.3),
      working: layer(named('bed', 1, 2), 5, 7, 0.3),
      waiting: layer(named('bed', 1, 2), 5, 7, 0.26),
    },
    pad: {
      idle: layer(['phrase-0'], 13, 17, 0.35),
      working: layer(named('phrase', 0, 1), 8.8, 9.4, 0.45),
      waiting: layer(['phrase-half'], 7.5, 8.5, 0.4),
    },
    sour: named('phrase', 2, 3, 4),
    onError: named('crackle', 1, 2),
    resolve: ['shimmer-77'],
    air: {},
    airOther: named('shimmer', 77, 82),
    airGain: 0.2,
    airEvery: 4000,
  },
  bells: {
    about: 'struck metal with long ring-outs over a slow gong',
    drone: {
      idle: layer(['gong-1'], 7, 10, 0.4),
      working: layer(named('gong', 1, 2), 6, 9, 0.36),
      waiting: layer(['gong-2'], 8, 10, 0.28),
    },
    pad: {
      idle: layer(named('low', 0, 1, 2, 3, 4), 7, 11, 0.35),
      working: layer([...named('mid', 0, 1, 2, 3, 4), ...named('low', 0, 3)], 1.8, 3.6, 0.4),
      waiting: layer(named('high', 1, 4), 2.8, 3.4, 0.3),
    },
    sour: BELL_SOUR,
    onError: BELL_SOUR,
    resolve: ['roll'],
    air: {},
    airOther: named('high', 0, 1, 2, 3, 4),
    airGain: 0.2,
    airEvery: 1500,
  },
  hum: {
    about: 'a ship interior: engine hum, sonar for questions, hull groans for errors',
    drone: {
      idle: layer(['hum-low'], 5, 7, 0.36),
      working: layer(['hum-high'], 5, 7, 0.36),
      waiting: layer(['hum-low'], 6, 8, 0.26),
    },
    pad: {
      idle: layer(named('creak', 1, 2), 12, 18, 0.3),
      working: layer(named('pulse', 1, 2), 5, 7, 0.4),
      waiting: layer(named('ping', 1, 2), 6, 7.5, 0.35),
    },
    sour: GROANS,
    onError: GROANS,
    resolve: ['vent'],
    air: {},
    airOther: named('bubbles', 1, 2, 3),
    airGain: 0.25,
    airEvery: 2500,
  },
  cafe: {
    about: 'a coffee shop: murmur, steam and cups, typing while tools run',
    drone: {
      idle: layer(['murmur-quiet'], 5, 7, 0.3),
      working: layer(['murmur-busy', 'murmur-busy', 'murmur-quiet'], 5, 7, 0.34),
      waiting: layer(['murmur-quiet'], 6, 8, 0.2),
    },
    pad: {
      idle: layer([...named('clink', 1, 2), ...named('radio', 1, 2)], 6, 10, 0.3),
      working: layer([...named('steam', 1, 2), 'grinder', ...named('clink', 1, 2, 3), ...named('radio', 1, 2)], 3.5, 6, 0.36),
      waiting: layer(named('stir', 1, 2), 5, 7, 0.32),
    },
    sour: [...CLATTER, 'scrape'],
    onError: CLATTER,
    resolve: ['doorbell'],
    air: { Read: PAGES, Grep: PAGES, Glob: PAGES, Edit: TYPING, Write: TYPING, Bash: TYPING },
    airOther: [...TYPING, 'clink-3'],
    airGain: 0.28,
    airEvery: 2500,
  },
}
