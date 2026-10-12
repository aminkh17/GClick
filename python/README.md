# Acoustic Click Controller

A small, local Python prototype that listens to a microphone, matches sounds against the mechanical keychain click in `../sample/sampleclick.m4a`, and optionally sends a meeting hotkey. Designed for macOS and Windows.

Calibration uses the **reference file by default**, not surrounding microphone sounds. A supplied file can contain multiple isolated clicks; each detected candidate becomes a reference variation. Use a recording containing only the desired clicks, without typing, speech, or handling noises you do not want learned. Optional microphone calibration adds only candidates whose spectral fingerprints match one of the reference variations. Listening always requires a reference match, even when additional templates exist. Similarity is not a probability or a guarantee against false positives.

Reference, calibration, and live candidates share the same transient alignment: locate the strongest 5ms window, align its peak 8ms into a 120ms analysis window, then extract the fingerprint. Live capture retains 40ms of preceding audio so the click attack is not lost at an audio-block boundary. Candidate logs explain reference rejection, template rejection, and cooldown suppression. Multi-variation references use feature version 4; earlier templates are ignored until rebuilt with `calibrate`.

## Important limitations

- This is a prototype, not a certified accessibility or safety tool. Test in dry-run mode first.
- The default configuration is **dry-run** and will not send keys until you explicitly change it.
- The hotkey is sent to the active application. It will only mute/unmute the meeting app if that app is focused and configured to use the selected shortcut. App shortcuts vary by app, OS, and user settings.
- Continuous microphone access is required. Audio is processed in memory; normal listening does not save audio. Calibration stores spectral fingerprints, not raw recordings.
- The detector can mistake other sharp noises for the click. Raise the similarity threshold or improve microphone placement if false positives occur.
- The first prototype uses a short transient plus a normalised spectral fingerprint. Microphones and operating-system audio processing can alter the sound, so recalibrate when you change microphones or environment.

## Requirements

- Python 3.10 or newer (Python 3.11 is a good default)
- A built-in or external microphone
- macOS or Windows
- FFmpeg on PATH to decode the reference `.m4a` (`brew install ffmpeg` on macOS; `winget install Gyan.FFmpeg` on Windows, then reopen the terminal)

## Setup

### macOS

```bash
# From this repository's python/ directory (keep ../sample/ alongside it)
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python acoustic_click.py devices
python acoustic_click.py calibrate
python acoustic_click.py listen
```

If microphone access is denied, allow microphone access for the terminal app (or IDE) under **System Settings → Privacy & Security → Microphone**, then restart the terminal. When you later set `dry_run` to `false`, macOS may also require Accessibility permission for the terminal/Python process to send keyboard input. Exact prompts depend on your macOS version.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python acoustic_click.py devices
python acoustic_click.py calibrate
python acoustic_click.py listen
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process Bypass` in that PowerShell window, then activate the environment again. Approve microphone access in Windows **Settings → Privacy & security → Microphone**. If no audio device is listed, check Windows sound settings and restart the terminal.

## Configuration

On first run the app creates `~/.acoustic-click-controller/config.json` (Windows resolves this beneath your user home directory). Use `python acoustic_click.py config` to print the path.

Example:

```json
{
  "input_device": null,
  "sample_rate": 16000,
  "sensitivity_rms": 0.004,
  "similarity_threshold": 0.82,
  "reference_threshold": 0.82,
  "cooldown_seconds": 1.2,
  "min_click_interval_seconds": 0.18,
  "action": "hotkey",
  "hotkey": ["ctrl", "shift", "m"],
  "dry_run": true,
  "log_matches": true
}
```

- `input_device`: `null` means the default input. To select another device, run `python acoustic_click.py devices` and use its device index.
- `sensitivity_rms`: energy threshold for finding candidate sounds, not identifying the key. Increase to ignore quiet background sounds; decrease if it misses clicks. New configs use `0.004`. Existing configs are not overwritten; if yours still uses `0.012`, consider lowering it to `0.004` when clicks are missed.
- `similarity_threshold`: increase to reduce false positives; decrease if real clicks are missed. Try `0.86` or `0.78` in small increments.
- `reference_threshold`: minimum similarity to the supplied reference, for both microphone calibration and listening. Additional templates cannot bypass this check. Start at `0.82`; tune using candidate scores, not as a probability.
- `cooldown_seconds`: minimum time between actions.
- `hotkey`: keys sent to the currently focused app. The default is an example only; set it to the shortcut configured in your meeting app.
- `dry_run`: keep `true` while testing. Change to `false` only after the detector is reliable.

## Calibration and test workflow

1. Run `python acoustic_click.py calibrate`. This extracts the click fingerprint directly from `../sample/sampleclick.m4a`; it does not open the microphone.
2. Put the microphone in its normal position. Optionally run `python acoustic_click.py calibrate --microphone --seconds 15` and make 10–20 isolated keychain clicks. Candidates are checked against the reference; at least four must match before templates are replaced. Unsuccessful calibration leaves existing templates intact.
3. Run `python acoustic_click.py listen`. Click the keychain and inspect reference and template similarity values. In dry-run mode, a match logs the action it would have sent. Old templates without compatible reference metadata are ignored; listening falls back to the reference file alone.
4. Test non-click noises: typing, mouse clicks, speech, a desk tap, and room sounds. If these trigger matches, increase `similarity_threshold` (for example, from `0.82` to `0.88`) and recalibrate in a quieter environment.
5. If real clicks are not detected, try moving the microphone closer, lowering `sensitivity_rms` slightly, or reducing `similarity_threshold` in small increments.
6. Configure a mute/unmute shortcut in the meeting app, set the same shortcut in `hotkey`, and confirm it works manually while that app is focused.
7. Only then set `dry_run` to `false`. Test with a non-critical call or a test meeting.
8. To stop listening, press `Ctrl+C` in the terminal.

To use the new multi-click recording, select it during calibration. Successful calibration remembers its absolute path, so listening uses it automatically:

```bash
python acoustic_click.py calibrate --sample ../sample/sample4.m4a
python acoustic_click.py listen
```

Use `listen --sample /path/to/click.m4a` for a temporary reference override. Later microphone calibration also uses the remembered reference unless overridden with `--sample`. The fingerprint format has changed; run `calibrate` again to replace old templates. Actions are unchanged in this update: only dry-run logging and the existing hotkey are implemented, not notifications yet.

## Meeting shortcut notes

There is no universal mute shortcut across Zoom, Microsoft Teams, Google Meet, and different OS configurations. Use the shortcut configured by your meeting application. Since this prototype sends a regular keyboard shortcut, the meeting window generally needs focus; it does not use private APIs or bypass app permissions.

## Troubleshooting

- **Reference cannot be loaded:** verify the sample path and that FFmpeg is installed and on PATH.
- **Microphone calibration rejects clicks:** inspect reference similarity scores, move closer to the microphone, and avoid overlapping speech or typing. Do not lower the reference threshold just to accept unrelated sounds.
- **No candidates detected during microphone calibration:** make clear isolated clicks, lengthen calibration, or lower `sensitivity_rms` in config.
- **Too many candidates:** increase `sensitivity_rms` and calibrate in a quieter setting.
- **Candidates appear but similarity is low:** recalibrate using the same microphone and distance; try a threshold around `0.78` temporarily to diagnose.
- **Hotkey doesn't work:** confirm it manually in the meeting app, ensure the app is focused, check OS permissions, and verify the key names supported by PyAutoGUI.
- **Audio device errors:** run `python acoustic_click.py devices`; select a device index in config and verify it supports 16 kHz input. If not, change `sample_rate` to a supported rate. Features are converted to the fixed 16 kHz analysis rate; microphone templates should be recalibrated after device/rate changes.

## Privacy

The program continuously reads microphone samples while running. Audio is held in short-lived memory buffers and is not transmitted or written to disk during listening. Calibration writes only derived spectral feature arrays to `templates.npz`. Stop the program when you do not want the microphone active.
