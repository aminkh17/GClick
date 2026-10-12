# Acoustic Click Controller — Product TODO

> Turn distinctive physical sounds into configurable computer actions.
>
> **Platforms:** macOS and Windows  
> **Implementation direction:** local-first Python application, extensible detector/action architecture  
> **Current baseline:** prototype for learning a mechanical keychain click and optionally sending a keyboard shortcut.

## Product vision

Build a cross-platform desktop utility that continuously listens for explicitly configured acoustic patterns and maps them to user-defined actions. A pattern might be a single mechanical click, a double click, a sequence of clicks, or another repeatable sound. Actions may include showing a notification, running a script, sending a meeting mute/unmute shortcut, launching an application, or calling a local HTTP endpoint.

The application must be predictable, privacy-conscious, easy to calibrate, and safe by default. Audio recognition and action execution should be separate modules so that new sound detectors and actions can be added without rewriting the core application.

## Product principles

- [ ] **Local-first:** process audio on-device by default; no cloud account or network connection required for core features.
- [ ] **Privacy by design:** do not save or transmit continuous raw microphone audio. Persist only the minimum calibration features needed to recognise configured sounds.
- [ ] **Safe defaults:** begin in dry-run mode; require explicit user opt-in before enabling actions that affect other applications or run commands.
- [ ] **Cross-platform:** support current macOS and Windows releases, documenting platform-specific permissions and limitations.
- [ ] **Composable architecture:** keep audio capture, detection, pattern recognition, action dispatch, configuration, and UI separate.
- [ ] **Observable behaviour:** make it clear when listening is active, what pattern matched, why an event was rejected, and what action was attempted.
- [ ] **Accessible controls:** provide an immediate pause/stop control and keyboard-accessible configuration.
- [ ] **No false certainty:** report confidence and test performance; do not claim a sound is uniquely identified in every environment.

## Current prototype assessment

- [x] Capture microphone audio with SoundDevice.
- [x] List available audio input devices.
- [x] Record a short calibration session.
- [x] Extract and persist normalised spectral fingerprints for candidate clicks.
- [x] Match incoming candidate sounds against calibrated templates.
- [x] Configure a similarity threshold and cooldown.
- [x] Support dry-run output.
- [x] Send a configurable keyboard shortcut when explicitly enabled.
- [x] Document microphone and keyboard permissions at a basic level.
- [ ] Validate and harden the prototype through repeatable tests before treating it as dependable.

## Milestone 0 — Establish a reliable baseline

### Runtime and project hygiene

- [ ] Add a `pyproject.toml` with project metadata, supported Python versions, dependency groups, and development tools.
- [ ] Pin or constrain dependency versions and verify installation on macOS and Windows.
- [ ] Add a `.gitignore` for virtual environments, caches, local configuration, logs, calibration data, build outputs, and temporary recordings.
- [ ] Add a `LICENSE` and contribution guidance before publishing publicly.
- [ ] Add a clear version number and changelog.
- [ ] Ensure generated config and template files are created with restrictive permissions where supported.
- [ ] Make CLI errors actionable and use stable exit codes.
- [ ] Add structured logging with configurable verbosity; avoid printing from the audio callback.
- [ ] Handle audio-device disconnects, queue overflow, sample-rate mismatch, and stream restarts gracefully.
- [ ] Ensure shutdown releases the microphone and worker threads cleanly.

### Baseline correctness

- [ ] Review the current segmentation and matching algorithm against recorded positive and negative examples.
- [ ] Fix any timing or state issues in event onset detection and cooldown handling.
- [ ] Make the detector robust to audio blocks that arrive late or are dropped.
- [ ] Confirm template files are validated before loading, including feature shape and version metadata.
- [ ] Make calibration report the number of candidate events detected and explain when the session is insufficient.
- [ ] Prevent calibration from silently replacing a good template set with a poor one; stage the new templates and ask for confirmation or validate them before replacement.
- [ ] Add a `status` or `diagnostics` command showing config path, template status, selected input device, sample rate, and current mode without exposing raw audio.
- [ ] Add tests for configuration defaults, malformed configuration, missing templates, and invalid device indices.

### Acceptance criteria

- [ ] A new user can install the project, list devices, calibrate, run dry-run detection, and stop it using only the README.
- [ ] A failed microphone setup produces a useful error rather than an unhandled traceback.
- [ ] No action is executed while dry-run mode is enabled.
- [ ] No raw microphone audio is written to disk during ordinary listening.

## Milestone 1 — Reliable learned-sound detection

### Calibration experience

- [ ] Replace the one-pass calibration flow with a guided session: quiet baseline, positive samples, and optional negative/background samples.
- [ ] Ask the user to make a configurable number of isolated sounds, with on-screen or terminal progress.
- [ ] Detect and reject overlapping events, clipping, very quiet samples, and likely speech/handling noise.
- [ ] Allow the user to listen to or inspect a temporary sample only when explicitly requested; delete temporary recordings after feature extraction unless the user chooses to retain them.
- [ ] Save multiple templates per sound to account for changes in click strength, orientation, and timing.
- [ ] Add calibration metadata: detector version, sample rate, feature version, input device identifier, date, and user-provided sound name.
- [ ] Support recalibration, rename, export, import, and deletion of a learned sound.
- [ ] Warn when the input device or sample rate changes and recommend recalibration.

### Detection engine

- [ ] Define a common detector interface that accepts audio frames and emits timestamped candidate events with confidence scores and diagnostic metadata.
- [ ] Separate event segmentation from sound classification.
- [ ] Compare spectral-template matching with additional lightweight features, such as spectral flux, band energies, transient duration, and amplitude envelope.
- [ ] Evaluate normalisation strategies so that microphone gain changes do not make scores meaningless.
- [ ] Add optional noise-floor adaptation with bounds so that a noisy environment does not continually raise or lower sensitivity unpredictably.
- [ ] Add per-sound thresholds rather than a single global threshold.
- [ ] Add configurable minimum/maximum event duration and refractory periods.
- [ ] Add a detector debug mode that reports scores and rejected-candidate reasons without triggering actions.
- [ ] Measure CPU usage and latency during continuous listening.
- [ ] Establish a repeatable positive/negative evaluation dataset recorded on different microphones and in realistic environments.
- [ ] Track precision, recall, false activations per hour, and missed detections; define target thresholds before enabling actions by default.
- [ ] Consider an optional classifier only if template matching cannot meet measured reliability goals; keep it local and optional.

### Acceptance criteria

- [ ] The user can name and calibrate a sound without editing code.
- [ ] Detection produces a confidence score and can be evaluated without executing an action.
- [ ] Positive and negative test results are reproducible from a documented test command.
- [ ] The app clearly communicates that environmental sounds may cause false matches.

## Milestone 2 — Pattern recognition

Support both individual learned sounds and temporal patterns built from recognised events.

### Pattern types

- [ ] Single event: one learned sound occurs.
- [ ] Double event: two matching events occur within a configurable time window.
- [ ] Multi-click sequence: a configurable number of events within a time window.
- [ ] Rhythm/interval pattern: event gaps match configured timing ranges, such as short-short-long.
- [ ] Mixed sequence: multiple learned sounds occur in a defined order.
- [ ] Optional hold/repetition pattern, only if it can be inferred reliably from the audio; do not assume a physical switch remains audibly active while held.
- [ ] Add an explicit pattern timeout so incomplete sequences expire without triggering actions.
- [ ] Define how overlapping patterns are resolved, including priority, longest match, and ambiguity handling.
- [ ] Provide a visual or textual pattern builder with examples and live feedback.
- [ ] Allow patterns to be tested in dry-run mode before assigning actions.
- [ ] Prevent accidental duplicate actions when a single click is also the first event of a double-click pattern.
- [ ] Support per-pattern cooldowns and optional maximum trigger frequency.

### Pattern configuration example

```yaml
patterns:
  - id: keychain-single
    name: Keychain click
    sequence:
      - sound: keychain-click
    timing:
      timeout_ms: 500
    confidence_threshold: 0.84
    actions:
      - type: notification
        message: "Keychain click detected"

  - id: keychain-double
    name: Keychain double click
    sequence:
      - sound: keychain-click
      - sound: keychain-click
    timing:
      min_gap_ms: 100
      max_gap_ms: 450
      timeout_ms: 700
    confidence_threshold: 0.84
    actions:
      - type: hotkey
        keys: ["ctrl", "shift", "m"]
```

> The configuration above is a target schema example, not a claim that the current prototype already supports YAML or multi-event patterns. Validate the schema before implementing it, and preserve backward compatibility where practical.

### Acceptance criteria

- [ ] A single event and a double-click pattern can be distinguished without both firing for the same gesture.
- [ ] Sequence timeouts and ambiguous matches behave deterministically.
- [ ] Users can see a matched pattern and its confidence before actions are enabled.

## Milestone 3 — Extensible action system

Build an action registry and dispatcher independent of the detector. One pattern may trigger one or more actions in a defined order.

### Core action interface

- [ ] Define an action interface with validation, execution, timeout, cancellation where possible, and a structured result.
- [ ] Return action status such as `succeeded`, `failed`, `timed_out`, `skipped`, or `dry_run`.
- [ ] Keep detection and action execution off the real-time audio callback.
- [ ] Add bounded queues and backpressure behaviour so a slow action cannot stall audio capture.
- [ ] Define whether multi-action sequences stop on first failure or continue; make this configurable per sequence.
- [ ] Add action-level cooldown, duplicate suppression, and optional confirmation for risky actions.
- [ ] Validate all action configuration before enabling listening.
- [ ] Show useful, non-sensitive error messages when an action fails.

### Built-in actions

- [ ] **Notification:** show a native desktop notification with title and message.
- [ ] **Hotkey:** send a configured keyboard shortcut, with explicit platform permissions and clear focus limitations.
- [ ] **Script:** execute an explicitly configured executable or script with fixed, validated arguments.
- [ ] **Launch application:** open a selected application or URL using platform-appropriate mechanisms.
- [ ] **Open URL:** open an allowlisted URL in the default browser.
- [ ] **Clipboard:** copy a configured text snippet, only after explicit permission and clear user intent.
- [ ] **Sound feedback:** play a short confirmation tone, with a setting to prevent feedback sounds from retriggering detection.
- [ ] **HTTP request:** call a user-configured local or remote endpoint with method, timeout, and optional authentication stored securely.
- [ ] **Webhook/automation:** support integrations such as Home Assistant or user-owned local automation endpoints through explicit configuration.
- [ ] **Meeting controls:** offer configurable mute/unmute shortcuts for Teams, Zoom, Google Meet, and other applications where the shortcut is user-verifiable.
- [ ] **Application-specific integration:** investigate supported official APIs or documented integration methods where keyboard shortcuts are insufficient.
- [ ] **Action chain:** run several actions from one pattern, with clear ordering and failure handling.

### Script action safety

- [ ] Never evaluate arbitrary command strings through a shell by default.
- [ ] Prefer a configured executable path plus a list of arguments, avoiding shell interpolation.
- [ ] Require the user to explicitly enable script execution and confirm the script path when adding it.
- [ ] Show the exact executable and arguments in the UI before saving.
- [ ] Apply a configurable timeout and terminate child processes on timeout where possible.
- [ ] Limit inherited environment variables where practical and document that scripts run with the user's permissions.
- [ ] Do not allow sound samples, detected labels, or other untrusted input to become executable arguments without explicit safe handling.
- [ ] Log action metadata and result, but do not log secrets or sensitive payloads.

### Notification and meeting-control behaviour

- [ ] Provide a notification-only action as the safest first live action.
- [ ] Make meeting hotkeys configurable per application and platform.
- [ ] Explain that a shortcut may act on whichever application currently has focus.
- [ ] Never imply that a shortcut succeeded in muting a microphone unless the target application confirms the state.
- [ ] Prefer an explicit mute-state integration when supported; otherwise describe the action as sending a shortcut, not guaranteeing mute state.
- [ ] Provide a test action that visibly confirms which shortcut would be sent.

### Acceptance criteria

- [ ] A single sound pattern can trigger a notification and a script independently or in sequence.
- [ ] One action failing does not crash the listener.
- [ ] Risky actions cannot be activated accidentally during initial setup.
- [ ] Dry-run mode shows the exact action that would execute without executing it.

## Milestone 4 — Configuration and user experience

### Configuration model

- [ ] Define and version a stable configuration schema.
- [ ] Validate configuration on startup and provide migration support for older versions.
- [ ] Support named sound profiles, patterns, actions, and reusable action definitions.
- [ ] Support import/export with secrets omitted by default.
- [ ] Keep generated calibration data separate from user-authored configuration.
- [ ] Provide safe defaults and explain every threshold and timing parameter in plain language.
- [ ] Add a reset-to-defaults command without deleting calibration data unless requested.

### CLI improvements

- [ ] Add commands for `sounds list|add|calibrate|rename|delete|test`.
- [ ] Add commands for `patterns list|add|test|enable|disable|delete`.
- [ ] Add commands for `actions list|test` and configuration validation.
- [ ] Add a `doctor` command for microphone access, selected device, template compatibility, permissions, and action setup.
- [ ] Add an explicit `pause`, `resume`, or `listen --once` workflow if useful for debugging.
- [ ] Make CLI output consistent and usable by automated tests.

### Desktop interface

- [ ] Decide whether the first GUI should use a lightweight cross-platform framework such as Qt or remain CLI-first until detection is reliable.
- [ ] Show listening/paused status persistently and clearly.
- [ ] Provide a global pause/stop control that remains available while the app is running.
- [ ] Provide a list of learned sounds with calibration status and last-detected time.
- [ ] Provide a pattern builder and action editor.
- [ ] Show a live detection meter and recent events without storing audio.
- [ ] Provide a dry-run test panel.
- [ ] Add accessible keyboard navigation, readable contrast, and screen-reader labels.
- [ ] Avoid a hidden always-on microphone process with no obvious user-visible status.

### Acceptance criteria

- [ ] A non-developer can create a sound, pattern, and notification action through the interface without editing files.
- [ ] Listening can be paused immediately and its state is always visible.
- [ ] Invalid or unsupported actions are explained before activation.

## Milestone 5 — Background operation and packaging

- [ ] Define supported OS versions and publish a compatibility matrix.
- [ ] Add optional start-on-login behaviour, disabled by default until the user enables it.
- [ ] Use supported OS mechanisms for background startup; provide an uninstall/disable path.
- [ ] Avoid hiding microphone use in a system service without a visible app indicator.
- [ ] Package signed/notarised macOS builds and appropriately signed Windows builds when release infrastructure is available.
- [ ] Verify microphone and accessibility permission flows in packaged builds, not only in a terminal.
- [ ] Add a tray/menu-bar indicator with listening, paused, and error states.
- [ ] Add version checks and a safe update process; no silent executable updates.
- [ ] Document uninstall steps, including removing start-on-login settings and local calibration data.
- [ ] Test behaviour after sleep/wake, device changes, audio-route changes, and application restarts.

## Milestone 6 — Privacy, security, and reliability

- [ ] Document exactly what is processed in memory, what is persisted, and what network calls an action may make.
- [ ] Keep all cloud/network actions opt-in and clearly label them.
- [ ] Add a privacy setting to disable diagnostic logging or reduce it to errors only.
- [ ] Ensure normal listening never persists raw audio by default.
- [ ] If audio export is added for debugging, make it an explicit action with a clear retention/deletion workflow.
- [ ] Protect secrets for HTTP actions using OS credential storage where practical; do not store tokens in plain-text exports.
- [ ] Validate paths and arguments supplied to script actions.
- [ ] Add limits for action duration, queue depth, event rate, and log size.
- [ ] Prevent notification/action feedback loops where generated sounds can retrigger a pattern.
- [ ] Add an emergency stop mechanism and make it easy to find.
- [ ] Test high CPU load, dropped frames, device disconnects, malformed templates, and repeated action failures.
- [ ] Add dependency and packaging security checks.
- [ ] Establish a policy for retaining logs and deleting learned templates.

## Milestone 7 — Test automation and quality gates

### Unit tests

- [ ] Test feature extraction for empty, silent, short, long, clipped, and malformed input.
- [ ] Test template matching and threshold boundaries.
- [ ] Test segmentation of isolated clicks and closely spaced events.
- [ ] Test pattern matching, timing windows, overlap resolution, and timeout behaviour.
- [ ] Test cooldowns and duplicate suppression with a controllable clock.
- [ ] Test configuration schema, migration, and invalid values.
- [ ] Test action validation, dry-run behaviour, timeout, exceptions, and result reporting.
- [ ] Test script action safety without executing real user scripts.

### Integration tests

- [ ] Use synthetic audio fixtures for deterministic detector tests.
- [ ] Use a small, consented set of recorded keychain sounds and environmental negatives for regression tests.
- [ ] Test the audio capture layer separately from the detector so CI does not require a physical microphone.
- [ ] Mock notifications, hotkeys, subprocesses, and HTTP requests in CI.
- [ ] Run linting, formatting, type checking, and tests in GitHub Actions on Windows and macOS.
- [ ] Add a manual release checklist for microphone permission, keyboard permission, sleep/wake, and background behaviour.

### Quality gates before enabling actions

- [ ] Establish and publish a minimum precision target and acceptable false-activation rate from measured tests.
- [ ] Confirm false positives under typing, speech, mouse clicks, desk taps, music, and room noise.
- [ ] Confirm missed detections across different click strengths, distances, and orientations.
- [ ] Require dry-run testing before a pattern can trigger a script or meeting shortcut.
- [ ] Keep notification-only testing as the recommended first live action.

## Milestone 8 — Extensibility and future integrations

- [ ] Define versioned plugin interfaces for detectors and actions.
- [ ] Document plugin lifecycle, configuration schema, permissions, logging, and error handling.
- [ ] Decide whether third-party plugins run in-process or in isolated worker processes.
- [ ] Require explicit trust/enablement for third-party code; do not auto-install plugins from untrusted sources.
- [ ] Provide example plugins for a custom detector and custom action.
- [ ] Add a local event bus so one detected pattern can feed multiple independent consumers.
- [ ] Explore optional integrations with meeting applications through supported APIs where feasible.
- [ ] Explore accessibility use cases, hands-free workflows, streaming controls, presentations, and smart-home automation.
- [ ] Consider multiple microphones or device-specific profiles only when supported by clear user demand.
- [ ] Consider an optional model-based detector as a pluggable backend, not a mandatory dependency.

## Suggested repository structure

```text
acoustic-click-controller/
├── README.md
├── TODO.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── src/
│   └── acoustic_click_controller/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── audio/
│       │   ├── capture.py
│       │   └── segmentation.py
│       ├── detectors/
│       │   ├── base.py
│       │   └── spectral_template.py
│       ├── patterns/
│       │   ├── model.py
│       │   └── matcher.py
│       ├── actions/
│       │   ├── base.py
│       │   ├── dispatcher.py
│       │   ├── notification.py
│       │   ├── hotkey.py
│       │   ├── script.py
│       │   ├── launch.py
│       │   └── http_request.py
│       ├── storage/
│       │   └── templates.py
│       └── diagnostics.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── .github/
    └── workflows/
        └── ci.yml
```

> This is a proposed destination structure. Do not perform a large refactor until baseline tests exist. Migrate in small, tested steps.

## Proposed delivery order

1. [ ] **P0 — Stabilise the existing prototype:** fix detector edge cases, improve errors, validate templates, add unit tests, and verify dry-run safety.
2. [ ] **P1 — Make detection measurable:** guided calibration, positive/negative test workflow, diagnostic scores, and false-positive evaluation.
3. [ ] **P2 — Introduce the action registry:** notification action first, then hotkey and safe script execution.
4. [ ] **P3 — Add pattern recognition:** single, double, and timed multi-event sequences.
5. [ ] **P4 — Improve daily usability:** configuration commands, diagnostics, pause control, and visible listening status.
6. [ ] **P5 — Package the desktop app:** tray/menu-bar indicator, start-on-login opt-in, permissions, and signed builds.
7. [ ] **P6 — Expand plugins and integrations:** additional actions, supported meeting integrations, and optional detector backends.

## Definition of done for a public beta

- [ ] Runs on supported macOS and Windows versions with documented setup.
- [ ] A user can calibrate at least one sound, create a timed pattern, and map it to a notification without editing source code.
- [ ] Additional action types can be implemented through a documented interface.
- [ ] Dry-run mode is on by default and accurately previews all actions.
- [ ] Script execution is explicit, validated, and time-limited.
- [ ] Listening status and immediate pause/stop controls are obvious.
- [ ] Audio privacy behaviour is documented and verified.
- [ ] Automated tests run in CI on both operating systems.
- [ ] False-positive and missed-detection results are measured and documented for the tested setup.
- [ ] Known limitations are clearly communicated; no claim of guaranteed meeting mute state is made without application confirmation.
- [ ] Installation, configuration, calibration, troubleshooting, upgrade, and uninstall instructions are complete.

## Open product decisions

- [ ] CLI-first until detector quality is proven, or build a desktop GUI early?
- [ ] Use YAML for human-readable configuration, JSON for simple built-in configuration, or both with a clear source of truth?
- [ ] Which desktop notification library offers the best supported behaviour across macOS and Windows?
- [ ] Which Python packaging and update approach should be used for signed desktop releases?
- [ ] What measurable false-activation rate is acceptable for notification actions versus scripts and meeting controls?
- [ ] Should a pattern support multiple actions by default, or should users explicitly add an action chain?
- [ ] Should advanced actions require a separate “trusted actions” permission/profile?

## Immediate next actions

- [ ] Run the current prototype on the target Mac and Windows environments, if available.
- [ ] Capture a short set of positive click examples and negative examples for local evaluation; do not commit private raw audio to the repository.
- [ ] Record baseline detection latency, CPU usage, missed clicks, and false activations.
- [ ] Add unit tests around the existing detector before changing its architecture.
- [ ] Implement a native desktop notification action as the first extension beyond the current hotkey action.
- [ ] Define and validate the first version of the `Sound`, `Pattern`, and `Action` configuration models.
- [ ] Implement single-click and double-click pattern handling with deterministic timeouts.
- [ ] Update the README so implemented features and planned features are clearly distinguished.
