# 🏁 Forza Skill Point Farm Automation — Production Edition

## Overview

Desktop automation application demonstrating computer vision, Windows input APIs, a threaded UI, and timing diagnostics.

**Features:**
- ✨ Modern dark theme with electric blue accents (CustomTkinter)
- 📊 Dual logging: Detection events + Cycle timing diagnostics
- ⏱️ Live elapsed timer (HH:MM:SS)
- 🎮 Thread-safe automation with pause/resume support
- 🔍 Template-based UI detection with confidence scoring
- 📦 PyInstaller-compatible, standalone executable support
- 🎯 Fixed 520×680px window — compact, focused, professional

---

## Installation

### 1. Install Python 3.11+
Ensure you have Python 3.11 or later installed on your system.

### 2. Install Dependencies
```bash
cd d:\CODE\fh6-automation\prod
pip install -r requirements.txt
```

**Key Dependencies:**
- `customtkinter` — Modern UI framework with dark theme
- `opencv-python` — Template matching & screen capture
- `mss` — Fast multi-monitor screenshot capture
- `keyboard` — Global hotkey support
- `numpy` — Numerical computations for image processing

### 3. Prepare Template Files
Place these PNG template files in the same directory as `fh6-asp-refactored.py`:
```
fh6-asp-refactored.py
├── scoreboard_x.png         (race completion scoreboard)
├── confirm_yes.png          (confirmation dialog "Yes" button)
├── start_race.png           (race start button)
├── race_progress0.png       (race at 0% progress — START)
└── race_progress90.png      (race at 90% progress — FINISH)
```

### 4. Run the Application
```bash
python fh6-asp-refactored.py
```

---

## UI Layout & Controls

### Top Bar
- **Left**: App title + Live status indicator (● color-coded)
- **Center**: Elapsed timer (HH:MM:SS, electric blue)
- **Right**: Cycle counter

### Control Panel
- **▶ START (F5)** — Launch automation (bright accent blue, bold)
- **⏸ PAUSE (F8)** — Pause/resume without losing state
- **⏹ STOP (F6)** — Graceful shutdown
- **🔍 TEST (F7)** — Debug mode (capture screen, test templates)

### Main Content Area
Two stacked, independently scrollable log panels:

#### 📋 Detection Log (Top)
Real-time automation events with color-coded levels:
```
[2026-05-28 20:21:08] INFO  - [STAGE 1] Scanning for race scoreboard...
[2026-05-28 20:21:08] INFO  - ✓ SCOREBOARD DETECTED at (126, 840)
[2026-05-28 20:21:09] INFO  -    ├─ Human reaction delay: 1.65s
```

#### ⏱ Cycle Timing Summary (Bottom)
Structured timing diagnostics per cycle:
```
[Cycle 1] Timing Summary:
  → Stage 1 │ Reaction delay:        1.65s
  → Stage 2 │ Reaction delay:        1.12s
  → Stage 3 │ Reaction delay:        1.88s
  → Stage 4 │ Reaction delay:        0.617s  │  W key held: 27,000ms
  → Cooldown │                        5,000ms
  ─────────────────────────────────────────
  Total cycle time:                  37.267s
```

### Bottom Status Bar
Current stage info and last action description.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F5** | Start automation |
| **F6** | Stop automation |
| **F7** | Debug test (capture screen) |
| **F8** | Pause/Resume |

---

## Code Architecture

### Core Modules

#### 1. **DirectX Input Simulation** (`simulate_key_press_directx`)
- Hardware-level key press simulation via Windows API
- Scan code-based keyboard input through the Windows API
- Fallback to keyboard library if needed

#### 2. **Screen Capture & Template Matching**
```python
ScreenCapture()          # Fast MSS-based screenshot capture
load_template()          # Load PNG template images
detect_ui_element()      # Template matching with confidence scoring
```

#### 3. **Timing Data Collection**
```python
TimingData               # Records per-stage delays & durations
.format_summary()        # Outputs formatted timing block
```

#### 4. **Automation Engine** (`ForzaAutomationEngine`)
Core automation logic:
- **Stage 1**: Detect scoreboard → click
- **Stage 2**: Detect confirmation dialog → click
- **Stage 3**: Detect start race screen → click
- **Stage 4**: Automated W key hold (27s) for race completion

Each stage records variable reaction timing for realistic pacing and diagnostics.

#### 5. **CustomTkinter UI** (`AutomationUI`)
Professional UI with:
- Threaded automation (non-blocking)
- Dual logging system
- Live timer updates
- State management (running/paused/stopped)
- Global hotkey support

---

## Configuration

### File: `fh6-asp-refactored.py` (Top of file)

```python
# DirectX Scan Codes
SCAN_CODE_X = 0x2D          # 'X' key for restart
SCAN_CODE_ENTER = 0x1C      # 'Enter' key for confirmation
SCAN_CODE_W = 0x11          # 'W' key for gas

# UI Theme Colors (Dark + Electric Blue)
COLOR_ACCENT = "#00AAFF"    # Electric blue highlight
COLOR_SUCCESS = "#00FF88"   # Green for success
COLOR_WARNING = "#FFC300"   # Amber for warnings
COLOR_ERROR = "#FF4444"     # Red for errors

# Window
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 680

# Input mode
FORCE_DIRECTX_ONLY = True   # Use the Windows API input path
```

### Adjusting Template Confidence Thresholds
In `ForzaAutomationEngine._stage_X_detect_*()` methods:
```python
detect_ui_element(frame, template, confidence_threshold=0.80)
# Lower = more sensitive (may cause false positives)
# Higher = more strict (may miss valid detections)
```

---

## Building Standalone Executable with PyInstaller

### 1. Install PyInstaller
```bash
pip install pyinstaller
```

### 2. Create `.spec` File
```bash
pyinstaller --onefile \
  --windowed \
  --add-data ".:." \
  --name "ForzaAutoSkill" \
  fh6-asp-refactored.py
```

### 3. Build Executable
```bash
pyinstaller ForzaAutoSkill.spec
```

### 4. Result
Standalone executable: `dist/ForzaAutoSkill.exe`

**Note:** Include template PNG files in the same directory as `.exe` for template detection to work.

---

## Logging & Debugging

### Enable Debug Mode
Click **🔍 TEST (F7)** button to:
1. Capture current screen
2. Save as `DEBUG_SCREEN.png` in working directory
3. Test template matching with diagnostic output

### Manual Template Testing
```python
from fh6_asp_refactored import ForzaAutomationEngine

engine = ForzaAutomationEngine(template_dir=".")
# Inspect engine.template_scoreboard_x, etc.
```

---

## Production Checklist

- [x] Code refactored for clarity & efficiency
- [x] Resource cleanup & error handling throughout
- [x] Thread-safe logging with queues
- [x] Professional UI with modern styling
- [x] Dual logging (detection + timing)
- [x] Live elapsed timer
- [x] Pause/resume functionality
- [x] PyInstaller compatible
- [x] No hardcoded paths (relative template loading)
- [x] Global hotkey support
- [x] Graceful shutdown signal handling

---

## Troubleshooting

### Templates Not Detected
- Verify PNG files exist in working directory
- Lower confidence threshold in `detect_ui_element()` calls
- Capture debug screen with **TEST (F7)** and verify image quality

### DirectX Input Not Working
- Ensure Forza window has focus when automation starts
- Set `FORCE_DIRECTX_ONLY = False` to allow keyboard library fallback
- Administrator privileges may be required for DirectX input

### Pause Not Working
- Pause operates at cycle boundaries, not mid-stage
- May take up to 1 second to respond

### High CPU Usage
- Normal during active screen capture
- Update loop set to 100ms (10Hz) — reduce for lower CPU, increase for more responsive UI

---

## Performance Metrics

Typical cycle timing (from Timing Summary log):
- **Stage 1** (detection → click): ~2 seconds
- **Stage 2** (confirmation): ~2 seconds
- **Stage 3** (race start): ~2 seconds
- **Stage 4** (race + gas hold): ~28 seconds
- **Cooldown**: 5 seconds
- **Total per cycle**: ~37 seconds

---

## License & Attribution

Built as a portfolio project focused on desktop automation, computer vision, and maintainable application structure.

---

## Contact & Support

For issues or enhancements, refer to the inline code comments marked with `# TODO` or `# NOTE`.
