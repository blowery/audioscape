import type { EngineInterface, Register } from 'claude-code'

import { STYLES, type Mood, type Style } from './styles'

let styleName = 'nature'
let style: Style = STYLES.nature as Style
let mood: Mood = 'idle'
let tension = 0
let volume = 0.6
let isMuted = false
let lastPad: string | undefined
let lastAirAt = 0
let mainTurns = 0
let droneTimer: { cancel: () => void } | undefined
let padTimer: { cancel: () => void } | undefined
let askTimer: { cancel: () => void } | undefined
let stop = new AbortController()

const pick = <T,>(list: readonly T[]): T | undefined => list[Math.floor(Math.random() * list.length)]
const between = ([low, high]: readonly [number, number]): number => low + Math.random() * (high - low)

function play($: EngineInterface, name: string | undefined, gain: number): void {
  if (isMuted || name === undefined) return
  $.audio
    .play({ asset: `sounds/${styleName}/${name}.m4a` }, { gain: Math.min(4, gain * volume), signal: stop.signal })
    .catch(() => {})
}

function runDrone($: EngineInterface, wait: number): void {
  droneTimer?.cancel()
  droneTimer = $.clock.after(wait, () => {
    const layer = style.drone[mood]
    play($, pick(layer.clips), layer.gain)
    runDrone($, between(layer.gap))
  })
}

function runPad($: EngineInterface, wait: number): void {
  padTimer?.cancel()
  padTimer = $.clock.after(wait, () => {
    const layer = style.pad[mood]
    const clips = mood === 'working' && Math.random() < tension / 4 ? style.sour : layer.clips
    const fresh = clips.filter(clip => clip !== lastPad)
    lastPad = pick(fresh.length > 0 ? fresh : clips)
    play($, lastPad, layer.gain)
    runPad($, between(layer.gap))
  })
}

function setMood($: EngineInterface, to: Mood): void {
  if (to === mood) return
  mood = to
  showStatus($)
  // Busier moods start at once. Idle arrives by letting the notes thin out.
  runPad($, to === 'idle' ? between(style.pad.idle.gap) : 200)
}

function showStatus($: EngineInterface): void {
  $.ui.status(isMuted ? undefined : `♪ ${styleName}: ${mood}${tension >= 1 ? ' ~' : ''}`)
}

function start($: EngineInterface): void {
  showStatus($)
  runDrone($, 100)
  runPad($, 4000)
}

function useStyle(name: unknown): boolean {
  const found = typeof name === 'string' ? STYLES[name] : undefined
  if (found === undefined) return false
  styleName = name as string
  style = found

  return true
}

function listStyles(): string {
  const rows = Object.entries(STYLES).map(([name, one]) => `${name === styleName ? '*' : ' '} ${name}: ${one.about}`)

  return `${rows.join('\n')}\n\n/audioscape <style> | on | off | 0-100`
}

function silence(): void {
  droneTimer?.cancel()
  padTimer?.cancel()
  askTimer?.cancel()
  stop.abort()
  stop = new AbortController()
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const stored = await Promise.all([$.store.get('volume'), $.store.get('isMuted'), $.store.get('style')])
    if (typeof stored[0] === 'number') volume = stored[0]
    useStyle(stored[2])
    isMuted = stored[1] === true || !e.isInteractive

    await $.command.register({
      name: 'audioscape',
      description: `Soundscape: on, off, 0-100 for volume, or a style (${Object.keys(STYLES).join(', ')})`,
    })
    if (!isMuted) start($)

    return next(e)
  })

  on('session.end', ($, e, next) => {
    silence()

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
        play($, pick(style.resolve), 0.45)
      }
      setMood($, 'idle')
      showStatus($)
    }

    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    // Air clips are spaced out, however many tools run.
    const now = Date.now()
    if (now - lastAirAt > style.airEvery) {
      lastAirAt = now
      play($, pick(style.air[String(e.tool)] ?? style.airOther), style.airGain)
    }

    const ran = await next(e)

    askTimer?.cancel()
    if (mood === 'waiting') setMood($, mainTurns > 0 ? 'working' : 'idle')
    if (ran.deny !== undefined || ran.isError === true) {
      tension = Math.min(3, tension + 1)
      play($, pick(style.onError), 0.4)
    } else {
      tension = Math.max(0, tension - 0.34)
    }
    showStatus($)

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
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off') {
      isMuted = true
      silence()
      showStatus($)
    } else if (arg === 'on') {
      isMuted = false
      start($)
    } else if (/^\d+$/.test(arg)) {
      volume = Math.min(100, Number(arg)) / 100
    } else if (arg === 'styles' || arg === 'style') {
      return { text: listStyles() }
    } else if (arg !== '') {
      // "/audioscape hum" and "/audioscape style hum" both switch.
      if (!useStyle(arg.replace(/^style\s+/, ''))) return { text: `No style "${arg}".\n\n${listStyles()}` }
      silence()
      if (!isMuted) start($)
    }
    await Promise.all([
      $.store.set('volume', volume),
      $.store.set('isMuted', isMuted),
      $.store.set('style', styleName),
    ])

    return {
      text: `audioscape is ${isMuted ? 'off' : 'on'}, style ${styleName}, volume ${Math.round(volume * 100)}, mood ${mood}.`,
    }
  })
}
