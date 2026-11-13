import type { EngineInterface, Register } from 'claude-code'

import { STYLES, type Mood, type Style } from './styles'

// Every Claude Code session on the machine that has this mod reports its
// state to a shared folder. Exactly one of them, the oldest one alive, is the
// player: it reads every report and plays one soundscape for all of them.
//
//   ~/.claude/audioscape/sessions/<session id>.json   one report per session
//   ~/.claude/audioscape/settings.json                style, volume, on or off

/** Something that happened in a session, for the player to turn into sound. */
type Signal = { n: number; kind: 'air' | 'error' | 'resolve'; tool?: string }

type Report = {
  id: string
  startedAt: number
  mood: Mood
  tension: number
  /** The most recent signals, numbered so the player plays each one once. */
  signals: Signal[]
  hasEnded?: boolean
}

type Settings = { style: string; volume: number; isMuted: boolean }

/** All live sessions, added up. */
type Scene = { working: number; waiting: number; idle: number; tension: number }

type Timer = { cancel: () => void }

const TICK_MS = 1000
/** A session rewrites its report at least this often. */
const HEARTBEAT_MS = 4000
/** A report older than this belongs to a session that is gone. */
const STALE_MS = 12000

// --- this session ---
let dir: string | undefined
let id = ''
let startedAt = 0
let mood: Mood = 'idle'
let tension = 0
let mainTurns = 0
let signals: Signal[] = []
let nextSignal = 1
let isDirty = true
let lastWriteAt = 0
let isTicking = false
let tickTimer: Timer | undefined
let askTimer: Timer | undefined

// --- shared ---
let settings: Settings = { style: 'nature', volume: 0.6, isMuted: false }
let style: Style = STYLES.nature as Style
let scene: Scene = { working: 0, waiting: 0, idle: 1, tension: 0 }
let playerId = ''

// --- the player, when this session is it ---
let isPlayer = false
let primary: Mood | undefined
let seen = new Map<string, number>()
let droneTimer: Timer | undefined
let padTimer: Timer | undefined
let overlayTimer: Timer | undefined
let lastPad: string | undefined
let lastAirAt = 0
let lastErrorAt = 0
let stop = new AbortController()

const pick = <T,>(list: readonly T[]): T | undefined => list[Math.floor(Math.random() * list.length)]
const between = ([low, high]: readonly [number, number]): number => low + Math.random() * (high - low)
const reportPath = (session: string): string => `${dir}/sessions/${session}.json`

// ---------------------------------------------------------------- reporting

function myReport(): Report {
  return { id, startedAt, mood, tension, signals }
}

async function writeReport($: EngineInterface, hasEnded = false): Promise<void> {
  if (dir === undefined) return
  isDirty = false
  lastWriteAt = Date.now()
  await $.fs.write(reportPath(id), JSON.stringify({ ...myReport(), hasEnded }))
}

/** Reads a report another session wrote. Anything malformed is dropped. */
function parseReport(text: string): Report | undefined {
  try {
    const raw = JSON.parse(text) as Partial<Report>
    if (typeof raw.id !== 'string' || typeof raw.startedAt !== 'number' || raw.hasEnded === true) return undefined
    const theirMood: Mood = raw.mood === 'working' || raw.mood === 'waiting' ? raw.mood : 'idle'
    const theirSignals = Array.isArray(raw.signals)
      ? raw.signals.filter(one => typeof one?.n === 'number' && typeof one.kind === 'string')
      : []

    return {
      id: raw.id,
      startedAt: raw.startedAt,
      mood: theirMood,
      tension: typeof raw.tension === 'number' ? raw.tension : 0,
      signals: theirSignals,
    }
  } catch {
    return undefined
  }
}

/** This session's report from memory, and every other live session's from disk. */
async function readReports($: EngineInterface, now: number): Promise<Report[]> {
  const entries = await $.fs.list(`${dir}/sessions`).catch(() => [])
  const live = entries.filter(
    entry => entry.name.endsWith('.json') && entry.name !== `${id}.json` && now - entry.mtimeMs < STALE_MS,
  )
  const texts = await Promise.all(
    live.map(entry => $.fs.read(`${dir}/sessions/${entry.name}`).catch(() => '')),
  )
  const others = texts.map(parseReport).filter((one): one is Report => one !== undefined && one.id !== id)

  return [myReport(), ...others]
}

async function loadSettings($: EngineInterface): Promise<void> {
  const text = await $.fs.read(`${dir}/settings.json`).catch(() => undefined)
  if (text === undefined) return
  try {
    const raw = JSON.parse(text) as Partial<Settings>
    const wasStyle = settings.style
    const wasMuted = settings.isMuted
    settings = {
      style: typeof raw.style === 'string' && STYLES[raw.style] !== undefined ? raw.style : settings.style,
      volume: typeof raw.volume === 'number' ? Math.max(0, Math.min(1, raw.volume)) : settings.volume,
      isMuted: raw.isMuted === true,
    }
    style = STYLES[settings.style] as Style
    // Another session changed the style or muted: the player starts over.
    if (isPlayer && (wasStyle !== settings.style || (settings.isMuted && !wasMuted))) stepDown(true)
  } catch {
    // Half-written by another session; the next tick reads it whole.
  }
}

async function saveSettings($: EngineInterface): Promise<void> {
  if (dir !== undefined) await $.fs.write(`${dir}/settings.json`, JSON.stringify(settings))
}

function addSignal($: EngineInterface, kind: Signal['kind'], tool?: string): void {
  const signal: Signal = { n: nextSignal, kind, tool }
  nextSignal += 1
  signals = [...signals, signal].slice(-24)
  if (isPlayer) {
    // No need to wait for a tick to hear this session's own signals.
    perform($, signal)
    seen.set(id, signal.n)
  }
  changed($)
}

function setMood($: EngineInterface, to: Mood): void {
  if (to === mood) return
  mood = to
  changed($)
}

/** This session's state changed: tell the others now, not at the next heartbeat. */
function changed($: EngineInterface): void {
  isDirty = true
  void tick($)
}

// ------------------------------------------------------------------ playing

function play($: EngineInterface, name: string | undefined, gain: number): void {
  if (name === undefined) return
  $.audio
    .play(
      { asset: `sounds/${settings.style}/${name}.m4a` },
      { gain: Math.min(4, gain * settings.volume), signal: stop.signal },
    )
    .catch(() => {})
}

function runDrone($: EngineInterface, wait: number): void {
  droneTimer?.cancel()
  droneTimer = $.clock.after(wait, () => {
    const layer = style.drone[primary ?? 'idle']
    play($, pick(layer.clips), layer.gain)
    runDrone($, between(layer.gap))
  })
}

function runPad($: EngineInterface, wait: number): void {
  padTimer?.cancel()
  padTimer = $.clock.after(wait, () => {
    const now = primary ?? 'idle'
    const layer = style.pad[now]
    const isSour = now === 'working' && Math.random() < scene.tension / 4
    const clips = isSour ? style.sour : layer.clips
    const fresh = clips.filter(clip => clip !== lastPad)
    lastPad = pick(fresh.length > 0 ? fresh : clips)
    play($, lastPad, layer.gain)
    // Each extra working session makes the pad denser, up to a ceiling.
    const crowd = now === 'working' ? Math.min(2.2, 1 + 0.35 * (scene.working - 1)) : 1
    runPad($, between(layer.gap) / crowd)
  })
}

/** While some sessions work and another waits on a person, the waiting
 * sound plays over the working one instead of replacing it. */
function runOverlay($: EngineInterface, wait: number): void {
  overlayTimer?.cancel()
  overlayTimer = $.clock.after(wait, () => {
    const layer = style.pad.waiting
    play($, pick(layer.clips), layer.gain)
    runOverlay($, between(layer.gap))
  })
}

function perform($: EngineInterface, signal: Signal): void {
  const now = Date.now()
  if (signal.kind === 'air' && now - lastAirAt > style.airEvery) {
    lastAirAt = now
    play($, pick(style.air[signal.tool ?? ''] ?? style.airOther), style.airGain)
  } else if (signal.kind === 'error' && now - lastErrorAt > 1500) {
    lastErrorAt = now
    play($, pick(style.onError), 0.4)
  } else if (signal.kind === 'resolve') {
    play($, pick(style.resolve), 0.45)
  }
}

function takeOver($: EngineInterface, reports: readonly Report[]): void {
  isPlayer = true
  primary = undefined
  stop = new AbortController()
  // Whatever the others signalled before now was the last player's to play.
  seen = new Map(reports.map(one => [one.id, one.signals.at(-1)?.n ?? 0]))
  runDrone($, 100)
  // Reports of sessions that ended long ago are of no use to anyone.
  $.process.run(['find', `${dir}/sessions`, '-name', '*.json', '-mmin', '+60', '-delete']).catch(() => {})
}

function stepDown(isAbrupt: boolean): void {
  isPlayer = false
  primary = undefined
  droneTimer?.cancel()
  padTimer?.cancel()
  overlayTimer?.cancel()
  overlayTimer = undefined
  // Unless told to cut off, clips already playing ring out.
  if (isAbrupt) stop.abort()
}

function conduct($: EngineInterface, reports: readonly Report[]): void {
  const to: Mood = scene.working > 0 ? 'working' : scene.waiting > 0 ? 'waiting' : 'idle'
  if (to !== primary) {
    primary = to
    // Busier moods start at once. Idle arrives by letting the clips thin out.
    runPad($, to === 'idle' ? between(style.pad.idle.gap) : 200)
  }

  const wantsOverlay = scene.working > 0 && scene.waiting > 0
  if (wantsOverlay && overlayTimer === undefined) runOverlay($, 300)
  if (!wantsOverlay && overlayTimer !== undefined) {
    overlayTimer.cancel()
    overlayTimer = undefined
  }

  for (const report of reports) {
    const last = seen.get(report.id)
    const newest = report.signals.at(-1)?.n ?? 0
    // A session seen for the first time: start from where it is now.
    if (last !== undefined) for (const signal of report.signals) if (signal.n > last) perform($, signal)
    seen.set(report.id, Math.max(last ?? 0, newest))
  }
}

// ------------------------------------------------------------------ the tick

async function tick($: EngineInterface): Promise<void> {
  if (isTicking || dir === undefined) return
  isTicking = true
  try {
    await loadSettings($)
    const now = Date.now()
    if (isDirty || now - lastWriteAt > HEARTBEAT_MS) await writeReport($)

    const reports = await readReports($, now)
    scene = { working: 0, waiting: 0, idle: 0, tension: 0 }
    for (const report of reports) {
      scene[report.mood] += 1
      scene.tension = Math.max(scene.tension, report.tension)
    }
    // The oldest live session plays. Every session works this out alike.
    const oldest = reports.reduce((a, b) =>
      b.startedAt < a.startedAt || (b.startedAt === a.startedAt && b.id < a.id) ? b : a,
    )
    playerId = oldest.id

    if (oldest.id === id && !settings.isMuted) {
      if (!isPlayer) takeOver($, reports)
      conduct($, reports)
    } else if (isPlayer) {
      stepDown(settings.isMuted)
    }
    $.ui.status(settings.isMuted ? undefined : `♪ ${settings.style}: ${describe()}`)
  } catch {
    // A failed tick is retried by the next one.
  } finally {
    isTicking = false
  }
}

function describe(): string {
  const sour = scene.tension >= 1 ? ' ~' : ''
  const total = scene.working + scene.waiting + scene.idle
  if (total <= 1) return `${mood}${sour}`
  const parts = (['working', 'waiting', 'idle'] as const)
    .filter(one => scene[one] > 0)
    .map(one => `${scene[one]} ${one}`)

  return `${parts.join(', ')}${sour}`
}

function listStyles(): string {
  const rows = Object.entries(STYLES).map(
    ([name, one]) => `${name === settings.style ? '*' : ' '} ${name}: ${one.about}`,
  )

  return `${rows.join('\n')}\n\n/audioscape <style> | on | off | 0-100`
}

// ------------------------------------------------------------------- hooks

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'audioscape',
      description: `Soundscape: on, off, 0-100 for volume, or a style (${Object.keys(STYLES).join(', ')})`,
    })
    const home = await $.env.get('HOME')
    // A run with nobody at the prompt neither plays nor counts as a session.
    if (!e.isInteractive || home === undefined) return next(e)

    dir = `${home}/.claude/audioscape`
    id = await $.session.id()
    // A reload keeps this session's age, so it does not lose its place.
    const mine = parseReport(await $.fs.read(reportPath(id)).catch(() => ''))
    startedAt = mine?.startedAt ?? Date.now()
    nextSignal = (mine?.signals.at(-1)?.n ?? 0) + 1

    if (!(await $.fs.exists(`${dir}/settings.json`))) {
      // Carry over what this mod kept per session before it was shared.
      const stored = await Promise.all([$.store.get('style'), $.store.get('volume'), $.store.get('isMuted')])
      if (typeof stored[0] === 'string' && STYLES[stored[0]] !== undefined) settings.style = stored[0]
      if (typeof stored[1] === 'number') settings.volume = stored[1]
      settings.isMuted = stored[2] === true
      await saveSettings($)
    }

    tickTimer?.cancel()
    tickTimer = $.clock.every(TICK_MS, () => void tick($))
    void tick($)

    return next(e)
  })

  on('session.end', async ($, e, next) => {
    // After a /clear the process goes on, so the session keeps reporting.
    if (e.reason !== 'clear' && dir !== undefined) {
      tickTimer?.cancel()
      askTimer?.cancel()
      stepDown(true)
      // Tell the others at once, so the next oldest takes over without a wait.
      await writeReport($, true).catch(() => {})
      dir = undefined
    }

    return next(e)
  })

  on('turn.start', ($, e, next) => {
    if (e.agentId === undefined) {
      mainTurns += 1
      setMood($, 'working')
    }

    return next(e)
  })

  on('turn.complete', ($, e, next) => {
    if (e.agentId === undefined) {
      mainTurns = Math.max(0, mainTurns - 1)
      askTimer?.cancel()
      if (e.reason === 'answer') {
        tension = 0
        addSignal($, 'resolve')
      }
      setMood($, 'idle')
    }

    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    addSignal($, 'air', String(e.tool))

    const ran = await next(e)

    askTimer?.cancel()
    if (mood === 'waiting') setMood($, mainTurns > 0 ? 'working' : 'idle')
    if (ran.deny !== undefined || ran.isError === true) {
      tension = Math.min(3, tension + 1)
      addSignal($, 'error')
    } else if (tension > 0) {
      tension = Math.max(0, tension - 0.34)
      changed($)
    }

    return ran
  })

  // An "ask" verdict may be settled by the permission mode without a prompt.
  // So wait a moment: if the call is still held, a person is being asked.
  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask') {
      askTimer?.cancel()
      askTimer = $.clock.after(1200, () => setMood($, 'waiting'))
    }

    return verdict
  })

  on('command.run', { command: 'audioscape' }, async ($, e) => {
    if (dir === undefined) return { text: 'audioscape only runs in an interactive session.' }
    const arg = e.args.trim().toLowerCase()
    await loadSettings($)
    if (arg === 'off') {
      settings.isMuted = true
    } else if (arg === 'on') {
      settings.isMuted = false
    } else if (/^\d+$/.test(arg)) {
      settings.volume = Math.min(100, Number(arg)) / 100
    } else if (arg === 'styles' || arg === 'style') {
      return { text: listStyles() }
    } else if (arg !== '') {
      // "/audioscape hum" and "/audioscape style hum" both switch.
      const name = arg.replace(/^style\s+/, '')
      if (STYLES[name] === undefined) return { text: `No style "${arg}".\n\n${listStyles()}` }
      settings.style = name
    }
    if (arg !== '') {
      // Cut off what is playing, so the change is heard at once.
      if (isPlayer) stepDown(true)
      await saveSettings($)
    }
    await tick($)

    const total = scene.working + scene.waiting + scene.idle
    const who = playerId === id ? 'This session plays the sound.' : `Session ${playerId.slice(0, 8)} plays the sound.`
    const state = settings.isMuted ? 'off' : 'on'
    const volume = Math.round(settings.volume * 100)

    return {
      text: `audioscape is ${state} for every session: style ${settings.style}, volume ${volume}.\n${total} session${total === 1 ? '' : 's'}: ${describe()}. ${settings.isMuted ? '' : who}`,
    }
  })
}
