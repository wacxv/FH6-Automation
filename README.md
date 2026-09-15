# Forza Desktop Automation Demo

Desktop automation application demonstrating computer vision, Windows input APIs, a threaded CustomTkinter UI, and timing diagnostics.

## Demo Video

[Watch the application demo](fh6-asp_demo.mp4)

The demo shows the interface, template-based screen detection, automation stages, logging, timing summaries, and pause/stop controls.

## Dependencies

The application uses:

- `customtkinter` for the desktop UI
- `opencv-python` for template matching
- `mss` for screen capture
- `keyboard` for keyboard input
- `numpy` for image processing
- `Pillow` for image support

## Template Files

The following PNG files are loaded from the same directory as `fh6-asp-refactored.py`:

```text
scoreboard_x.png       Race completion scoreboard
confirm_yes.png        Confirmation dialog button
start_race.png         Race start screen
race_progress0.png     Race start progress indicator
race_progress90.png    Race progress indicator near completion
```

## Controls

| Key | Action |
|-----|--------|
| **F5** | Start automation |
| **F6** | Stop automation |
| **F7** | Capture a debug screenshot and test templates |
| **F8** | Pause or resume automation |

The same actions are available through the on-screen controls.

## Main Content Area

The interface contains two live log panels:

### Detection Log

Displays screen-detection events, stage transitions, confidence values, and actions taken by the automation engine.

### Cycle Timing Summary

Displays per-cycle timing data, including detection delays, keyboard-hold duration, cooldown duration, and total cycle time.

The status bar shows the current stage and most recent action. The top bar displays the application state, elapsed runtime, and completed cycle count.

## Technical Highlights

- OpenCV template matching with configurable confidence thresholds
- MSS-based screen capture
- Windows API keyboard and mouse input
- Background automation thread with pause and stop signals
- Thread-safe queues for UI logging and timing data
- CustomTkinter interface with live status updates
- Debug screenshot capture for detection troubleshooting

## Project Scope

This repository is a source-code demonstration focused on desktop automation, computer vision, event-driven UI design, and diagnostics. The demo video and source are provided for portfolio and educational review.
