#!/usr/bin/env python3
"""Local acoustic keychain click -> configurable meeting hotkey.

Audio is processed locally. No recording is saved during normal listening.
Calibration recordings are reduced to spectral templates and stored locally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd

APP_DIR = Path.home() / ".acoustic-click-controller"
CONFIG_PATH = APP_DIR / "config.json"
TEMPLATE_PATH = APP_DIR / "templates.npz"
SAMPLE_RATE = 16_000
BLOCK_MS = 10
BLOCK_SIZE = SAMPLE_RATE * BLOCK_MS // 1000
EVENT_MS = 120
EVENT_SAMPLES = SAMPLE_RATE * EVENT_MS // 1000
CAPTURE_PRE_MS = 40
ALIGN_PRE_MS = 8
REFERENCE_PATH = Path(__file__).resolve().parent.parent / "sample" / "sampleclick.m4a"
FEATURE_VERSION = 4

DEFAULT_CONFIG: dict[str, Any] = {
    "input_device": None,
    "sample_path": str(REFERENCE_PATH),
    "sample_rate": SAMPLE_RATE,
    "sensitivity_rms": 0.004,
    "similarity_threshold": 0.82,
    "reference_threshold": 0.82,
    "cooldown_seconds": 1.2,
    "min_click_interval_seconds": 0.18,
    "action": "hotkey",
    "hotkey": ["ctrl", "shift", "m"],
    "dry_run": True,
    "log_matches": True,
}


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_app_dir()
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        print(f"Created config: {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged


def list_devices() -> None:
    print(sd.query_devices())


def choose_input_device(cfg: dict[str, Any]) -> int | None:
    selected = cfg.get("input_device")
    if selected is not None:
        return int(selected)
    try:
        default = sd.default.device[0]
        return int(default) if default is not None and int(default) >= 0 else None
    except Exception:
        return None


def get_audio_segment(seconds: float, prompt: str, cfg: dict[str, Any]) -> np.ndarray:
    chunks: list[np.ndarray] = []
    sample_rate = int(cfg["sample_rate"])
    total = int(seconds * sample_rate)
    block_size = max(1, sample_rate * BLOCK_MS // 1000)
    print(prompt, flush=True)
    try:
        with sd.InputStream(
            samplerate=sample_rate, channels=1, dtype="float32",
            blocksize=block_size, device=choose_input_device(cfg),
        ) as stream:
            while sum(len(x) for x in chunks) < total:
                block, _ = stream.read(block_size)
                chunks.append(block[:, 0].copy())
    except Exception as exc:
        raise RuntimeError(f"Could not access microphone: {exc}\nCheck OS microphone permissions and input_device in config.json.") from exc
    return np.concatenate(chunks)[:total]


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + 1e-12))


def detect_events(audio: np.ndarray, sample_rate: int, sensitivity: float) -> list[np.ndarray]:
    """Segment sharp clicks from a calibration recording using short-frame RMS."""
    frame = max(1, int(sample_rate * 0.005))  # 5 ms frames
    env = np.array([rms(audio[i:i + frame]) for i in range(0, len(audio), frame)])
    # Adaptive threshold, but keep the configured floor to avoid room noise.
    floor = float(np.percentile(env, 35))
    threshold = max(sensitivity, floor * 3.2)
    active = env > threshold
    events: list[np.ndarray] = []
    last_end = -10**9
    min_gap = int(0.16 * sample_rate / frame)
    pre = int(CAPTURE_PRE_MS / 1000 * sample_rate)
    post = int(EVENT_MS / 1000 * sample_rate)
    for idx in np.where(active & ~np.r_[False, active[:-1]])[0]:
        if idx - last_end < min_gap:
            continue
        start = max(0, idx * frame - pre)
        end = min(len(audio), idx * frame + post)
        seg = audio[start:end]
        # A short click can have high onset energy but low whole-window RMS.
        if len(seg) >= post // 2:
            if len(seg) < post:
                seg = np.pad(seg, (0, post - len(seg)))
            events.append(seg.astype(np.float32))
            last_end = idx
    return events


def align_click(audio: np.ndarray) -> tuple[np.ndarray, int]:
    """Align a 16kHz event to its strongest 5ms transient, independent of blocks.

    Find the highest-energy 5ms window at sample resolution, then anchor to
    its amplitude peak. Always place that peak 8ms into a 120ms fingerprint
    window. Used identically for the file, calibration, and live candidates.
    """
    x = np.asarray(audio, dtype=np.float32)
    if not len(x):
        return np.zeros(EVENT_SAMPLES, dtype=np.float32), 0
    x = x - np.mean(x)
    frame = min(len(x), SAMPLE_RATE // 200)
    energy = np.r_[0.0, np.cumsum(np.square(x, dtype=np.float64))]
    start = int(np.argmax(energy[frame:] - energy[:-frame]))
    peak = start + int(np.argmax(np.abs(x[start:start + frame])))
    window_start = peak - SAMPLE_RATE * ALIGN_PRE_MS // 1000
    window = x[max(0, window_start):max(0, window_start + EVENT_SAMPLES)]
    if window_start < 0:
        window = np.pad(window, (-window_start, 0))
    window = np.pad(window, (0, max(0, EVENT_SAMPLES - len(window))))
    return window[:EVENT_SAMPLES], peak


def feature(event: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Transient-aligned, amplitude-normalised spectral fingerprint."""
    x = np.asarray(event, dtype=np.float32)
    if sample_rate != SAMPLE_RATE:
        # Keep the analysis rate fixed even when the microphone uses another rate.
        positions = np.arange(int(round(len(x) * SAMPLE_RATE / sample_rate))) * sample_rate / SAMPLE_RATE
        x = np.interp(positions, np.arange(len(x)), x).astype(np.float32)
    x, _ = align_click(x)
    x = x - np.mean(x)
    peak = float(np.max(np.abs(x))) + 1e-8
    x = x / peak
    # Preserve the attack near the beginning rather than suppressing it with a Hann window.
    x *= np.exp(-np.arange(len(x)) / (0.035 * SAMPLE_RATE)).astype(np.float32)
    spec = np.abs(np.fft.rfft(x, n=4096)).astype(np.float32)
    # Compress FFT bins into 96 broad bands for robustness to small timing shifts.
    bands = np.array_split(spec, 96)
    feat = np.array([np.mean(b) for b in bands], dtype=np.float32)
    feat = np.log(np.maximum(feat, max(float(feat.max()) * 0.001, 1e-8)))
    # Remove the common spectral offset so unrelated broadband noises do not
    # get high cosine similarity merely because every band is positive.
    feat -= feat.mean()
    feat /= float(np.linalg.norm(feat) + 1e-8)
    return feat


def similarity(candidate: np.ndarray, templates: np.ndarray) -> float:
    """Best match against explicitly supplied reference/template variations."""
    return float(np.max(templates @ candidate))


def load_reference(cfg: dict[str, Any]) -> tuple[np.ndarray, str]:
    path = Path(cfg.get("sample_path", REFERENCE_PATH)).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Reference sample not found: {path}. Use --sample PATH to select it.")
    try:
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-f", "f32le", "-"], capture_output=True, check=True, timeout=30,
        )
    except FileNotFoundError as exc:
        raise ValueError("FFmpeg is required to read the sample. On macOS: brew install ffmpeg; on Windows: winget install Gyan.FFmpeg") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Could not decode reference sample: {path}") from exc
    audio = np.frombuffer(decoded.stdout, dtype=np.float32)
    if len(audio) < EVENT_SAMPLES or not np.isfinite(audio).all() or rms(audio) <= 1e-5:
        raise ValueError("Reference sample is too short, silent, or invalid.")
    # A deliberately supplied recording may contain several click variations.
    # Extract these from the file, never from unfiltered ambient microphone audio.
    frame = SAMPLE_RATE // 200
    levels = np.array([rms(audio[i:i + frame]) for i in range(0, len(audio), frame)])
    sensitivity = max(float(levels.max()) * 0.1, 1e-5)
    events = detect_events(audio, SAMPLE_RATE, sensitivity)
    features = [feature(event) for event in events]
    features = [feat for feat in features if np.linalg.norm(feat) >= 0.5]
    if not features:
        raise ValueError("Reference sample has no usable spectral fingerprint.")
    reference = np.stack(features)
    print(f"Reference: {path} ({len(reference)} click variations; aligned features v{FEATURE_VERSION})")
    return reference, hashlib.sha256(path.read_bytes()).hexdigest()


def calibrate(cfg: dict[str, Any], seconds: float, microphone: bool = False) -> None:
    reference, digest = load_reference(cfg)
    feats = reference.copy()
    if microphone:
        print("Only sounds matching the reference will be learned. Raw audio is not saved.")
        audio = get_audio_segment(seconds, f"Recording for {seconds:.0f}s — click the keychain with pauses.", cfg)
        events = detect_events(audio, int(cfg["sample_rate"]), float(cfg["sensitivity_rms"]))
        accepted = []
        for event in events:
            candidate = feature(event, int(cfg["sample_rate"]))
            score = similarity(candidate, reference)
            matches = score >= float(cfg["reference_threshold"])
            print(f"Reference similarity={score:.3f}: {'accepted' if matches else 'rejected'}")
            if matches:
                accepted.append(candidate)
        print(f"Accepted {len(accepted)} of {len(events)} candidates.")
        if len(accepted) < 4:
            raise ValueError("Need at least 4 reference-matching clicks. Existing templates were not changed. Try a quieter room or move closer to the mic.")
        feats = np.vstack([reference, *accepted])
    ensure_app_dir()
    np.savez_compressed(TEMPLATE_PATH, features=feats, feature_version=FEATURE_VERSION,
                        reference_sha256=digest, sample_rate=SAMPLE_RATE)
    # Remember the selected file only after calibration succeeds. Keep all
    # other user-authored settings unchanged, including dry-run and thresholds.
    saved_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    saved_cfg["sample_path"] = str(Path(cfg.get("sample_path", REFERENCE_PATH)).expanduser().resolve())
    CONFIG_PATH.write_text(json.dumps(saved_cfg, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(feats)} click templates to {TEMPLATE_PATH}")
    print(f"Selected reference saved in {CONFIG_PATH}")
    print("Next: run `python acoustic_click.py listen`. Start with dry_run=true.")


def fire_action(cfg: dict[str, Any]) -> None:
    if cfg.get("dry_run", True):
        print("[DRY RUN] Click matched. Would send hotkey: " + "+".join(cfg.get("hotkey", [])), flush=True)
        return
    try:
        import pyautogui
        keys = [str(k).lower() for k in cfg.get("hotkey", ["ctrl", "shift", "m"])]
        pyautogui.hotkey(*keys, interval=0.04)
        print("Sent hotkey: " + "+".join(keys), flush=True)
    except Exception as exc:
        print(f"Action failed: {exc}", file=sys.stderr, flush=True)


def listen(cfg: dict[str, Any]) -> None:
    reference, digest = load_reference(cfg)
    templates = reference.copy()
    if TEMPLATE_PATH.exists():
        try:
            with np.load(TEMPLATE_PATH, allow_pickle=False) as saved:
                if (int(saved["feature_version"]) != FEATURE_VERSION
                        or str(saved["reference_sha256"]) != digest):
                    raise ValueError("Template version or reference differs")
                loaded = saved["features"].astype(np.float32)
                if loaded.ndim != 2 or loaded.shape[1] != reference.shape[1] or not len(loaded) or not np.isfinite(loaded).all():
                    raise ValueError("Invalid template features")
                templates = loaded
        except (KeyError, ValueError, OSError, EOFError):
            print("Ignoring old/incompatible templates; using the sample only. Run calibrate to rebuild.")
    q: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
    sample_rate = int(cfg["sample_rate"])
    block_size = max(1, sample_rate * BLOCK_MS // 1000)
    # Extra context lets feature() locate the actual transient rather than
    # assuming it starts at a callback boundary.
    event_samples = int((CAPTURE_PRE_MS + BLOCK_MS + EVENT_MS) / 1000 * sample_rate)
    buffer = np.zeros(0, dtype=np.float32)
    armed_event: np.ndarray | None = None
    last_trigger = 0.0
    last_onset = 0.0
    above = False

    def callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        if status:
            print(f"Audio warning: {status}", file=sys.stderr)
        try:
            q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    print("Listening continuously. Audio stays local; Ctrl+C to stop.")
    print(f"Reference threshold={cfg['reference_threshold']}; template threshold={cfg['similarity_threshold']}; dry_run={cfg['dry_run']}; device={choose_input_device(cfg)}")
    print("Tip: leave dry_run enabled until false positives are acceptably rare.")
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size,
                            device=choose_input_device(cfg), callback=callback):
            while True:
                try:
                    block = q.get(timeout=1.0)
                except queue.Empty:
                    continue
                buffer = np.concatenate((buffer, block))
                if len(buffer) > sample_rate:
                    buffer = buffer[-sample_rate:]
                frame = max(1, sample_rate // 200)
                level = max(rms(block[i:i + frame]) for i in range(0, len(block), frame))
                threshold = float(cfg["sensitivity_rms"])
                # Do not miss a return to quiet while collecting an event.
                if level < threshold * 0.55:
                    above = False
                now = time.monotonic()
                if armed_event is not None:
                    armed_event = np.concatenate((armed_event, block))
                    if len(armed_event) >= event_samples:
                        candidate = feature(armed_event[:event_samples], sample_rate)
                        reference_score = similarity(candidate, reference)
                        score = similarity(candidate, templates)
                        reference_match = reference_score >= float(cfg["reference_threshold"])
                        template_match = score >= float(cfg["similarity_threshold"])
                        cooldown_ready = now - last_trigger >= float(cfg["cooldown_seconds"])
                        verdict = ("rejected: reference mismatch" if not reference_match else
                                   "rejected: template mismatch" if not template_match else
                                   "suppressed: cooldown" if not cooldown_ready else "MATCH")
                        if cfg.get("log_matches", True):
                            print(f"Candidate reference similarity={reference_score:.3f}; template similarity={score:.3f}; {verdict}", flush=True)
                        if reference_match and template_match and cooldown_ready:
                            fire_action(cfg)
                            last_trigger = now
                        armed_event = None
                    continue
                if level >= threshold and not above and now - last_onset >= float(cfg["min_click_interval_seconds"]):
                    # Capture the current transient plus following audio in subsequent blocks.
                    armed_event = buffer[-min(len(buffer), len(block) + int(CAPTURE_PRE_MS / 1000 * sample_rate)):].copy()
                    last_onset = now
                    above = True
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        raise RuntimeError(f"Audio stream failed: {exc}\nCheck microphone permission, device selection, and sample-rate support.") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Use a mechanical click as a local computer hotkey.")
    sub = parser.add_subparsers(dest="command", required=True)
    listener = sub.add_parser("listen", help="Listen for sounds matching the reference sample")
    listener.add_argument("--sample", type=Path, help="Override the saved reference sound for this run")
    cal = sub.add_parser("calibrate", help="Build templates from the reference sample")
    cal.add_argument("--sample", type=Path, help="Reference recording to learn and remember (default: saved reference or ../sample/sampleclick.m4a)")
    cal.add_argument("--microphone", action="store_true", help="Optionally learn additional clicks, filtered against the reference")
    cal.add_argument("--seconds", type=float, default=12.0, help="Calibration recording duration (default: 12)")
    sub.add_parser("devices", help="List available audio devices")
    sub.add_parser("config", help="Print config file location")
    args = parser.parse_args()
    cfg = load_config()
    if getattr(args, "sample", None) is not None:
        cfg["sample_path"] = str(args.sample)
    if args.command == "listen":
        listen(cfg)
    elif args.command == "calibrate":
        calibrate(cfg, max(5.0, min(float(args.seconds), 60.0)), microphone=args.microphone)
    elif args.command == "devices":
        list_devices()
    elif args.command == "config":
        print(CONFIG_PATH)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
