# audioscape

An ambient soundscape for Claude Code. It plays all the time, and it changes
with what the session is doing. Nothing in it is an alert. You hear the state
of the session the way you hear weather through a window.

It needs macOS, because it plays sound through `afplay`.

## Install

At the prompt of a terminal session:

```
/plugin install audioscape --marketplace blowery/audioscape
```

Answer `y` to add the marketplace, then choose a scope.

From a shell:

```
claude plugin install audioscape --marketplace blowery/audioscape
```

In the desktop app, click + next to the prompt box, then Plugins, then
Add marketplace with `blowery/audioscape`, then Add plugin.

## What you hear

Every style has three layers of slow clips that fade in and out and overlap.

| Layer | What it is | What changes it |
| --- | --- | --- |
| Drone | The floor. Long clips that overlap, so it is never silent. | The session's mood |
| Pad | The middle. | The mood sets which clips play and how often |
| Air | The top. Soft, brief clips. | One appears now and then while tools run |

The session is always in one of three moods:

- **idle**: nobody is doing anything. Sparse and low.
- **working**: a turn is running. Denser and higher.
- **waiting**: a permission prompt or a question is open. The texture thins
  out and something hangs unresolved until you answer.

Two more things react:

- **Errors.** A failed tool call plays the style's error sound once. It also
  adds tension, and tension mixes the style's sour clips into the pad. Each
  tool call that succeeds removes some tension.
- **Finished turns.** A turn that ends with an answer clears the tension and
  plays one resolving clip.

The status line shows the style and the mood, for example `♪ nature: working`.
A `~` after the mood means errors have soured it.

## Styles

| Style | Idle | Working | Waiting | Errors |
| --- | --- | --- | --- | --- |
| `nature` | Wind and crickets | Rain | Wind chimes | Thunder, then heavier rain |
| `tonal` | Low synth notes | A minor pentatonic scale | Two hanging notes | Notes outside the scale |
| `tape` | A few soft piano notes over sung notes | More piano notes | Two unresolved piano notes | Out-of-tune piano |
| `drone` | A very slow low chord | The chord fills in | Two high notes | The chord darkens |
| `space` | A dark low hum | Bright pads with long echoes | Two hanging pads | Notes outside the scale |
| `decay` | A warm phrase, repeated rarely | The phrase loops | Half the phrase | Tape crackle, then worn copies of the phrase |
| `bells` | Low bells over a gong | Mid bells, more often | Two high bells | Bells that clash |
| `hum` | Engine hum and distant creaks | A higher hum and turning machinery | Sonar pings | Hull groans |

## Commands

```
/audioscape            show the current state
/audioscape styles     list the styles
/audioscape <style>    switch style, for example /audioscape hum
/audioscape off        stop the sound
/audioscape on         start it again
/audioscape 40         set the volume, from 0 to 100
```

The style, the volume and the on/off setting persist across sessions.

## Changing the sounds

All clips are synthesized by Python scripts that use only the standard
library. `afconvert`, which ships with macOS, compresses them.

```
python3 tools/gen_nature.py
python3 tools/gen_tonal.py
python3 tools/gen_styles.py            # tape, drone, space, decay, bells, hum
python3 tools/gen_styles.py bells hum  # only these
```

`hooks/styles.ts` holds one table per style. Each table says which clips each
layer plays in each mood, how long to wait between clips, and how loud they
are. To add a style, render its clips into `sounds/<name>/` and add a table.

`hooks/register.ts` listens to the session and moves between moods.

## Limits

- Each clip plays at a fixed volume, so a clip cannot fade or change once it
  has started. All movement comes from which clips start, and when.
- Every session with the mod makes its own sound. Two sessions play two
  soundscapes at once.
- The nature style is synthesized from filtered noise and sine chirps. It is
  a stylized outdoors, not a field recording.

## License

MIT
