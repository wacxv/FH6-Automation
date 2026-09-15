"""
Forza Skill Point Farm Automation
"""

import cv2
import mss
import ctypes
import random
import time
import logging
import os
import sys
import threading
import keyboard
import numpy as np
from ctypes import Structure, POINTER, c_uint, c_uint16, c_uint32, c_long, c_void_p, byref
from typing import Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import customtkinter as ctk
from queue import Queue, Empty

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

# DirectX Scan Codes
SCAN_CODE_X = 0x2D          # 'X' key for restart
SCAN_CODE_ENTER = 0x1C      # 'Enter' key for confirmation
SCAN_CODE_W = 0x11          # 'W' key for gas acceleration

# Input event flags
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002

# Mouse event flags
MOUSE_EVENT_LEFTDOWN = 0x0002
MOUSE_EVENT_LEFTUP = 0x0004

# UI Theme Colors (Dark + Electric Blue)
COLOR_BG_DARK = "#0F0F0F"           # Main background
COLOR_BG_SECONDARY = "#1A1A1A"      # Panels & cards
COLOR_BG_TERTIARY = "#242424"       # Hover states
COLOR_BORDER = "#2E2E2E"            # Dividers & borders
COLOR_TEXT_PRIMARY = "#FFFFFF"      # Primary text
COLOR_TEXT_SECONDARY = "#B0B0B0"    # Secondary text
COLOR_TEXT_MUTED = "#666666"        # Muted/debug text
COLOR_ACCENT = "#00AAFF"            # Electric blue
COLOR_SUCCESS = "#00FF88"           # Success indicators
COLOR_WARNING = "#FFC300"           # Warnings
COLOR_ERROR = "#FF4444"             # Errors

# Window configuration
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 680
WINDOW_TITLE = "Forza Auto-Skill Controller"

# Force DirectX-only mode (disable keyboard library fallback)
FORCE_DIRECTX_ONLY = True

# ============================================================================
# PATH RESOLUTION FOR EXECUTABLE COMPATIBILITY
# ============================================================================

def get_template_dir() -> str:
    """
    Get the template directory path.
    Works both when running as Python script and as PyInstaller executable.
    """
    # When running as PyInstaller executable, use sys._MEIPASS
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    # When running as Python script, use current working directory
    return os.getcwd()

# ============================================================================
# DIRECTX INPUT STRUCTURES
# ============================================================================

class KEYBDINPUT(Structure):
    """Keyboard input structure for DirectX - matches Windows API KEYBDINPUT"""
    _fields_ = [
        ("wVk", c_uint16),
        ("wScan", c_uint16),
        ("dwFlags", c_uint32),
        ("time", c_uint32),
        ("dwExtraInfo", c_void_p),
    ]


class INPUT(Structure):
    """Input structure for SendInput API"""
    _fields_ = [
        ("type", c_uint32),
        ("ki", KEYBDINPUT),
    ]


# Load Windows User32 library
user32 = ctypes.windll.user32
SendInput = user32.SendInput
SendInput.argtypes = [c_uint, c_void_p, c_uint]
SendInput.restype = c_uint

# ============================================================================
# DUAL LOGGING SYSTEM
# ============================================================================

class DetectionLogger(logging.Logger):
    """Logger for automation detection events and state changes"""
    
    def __init__(self, name, level=logging.DEBUG):
        super().__init__(name, level)
        self.event_queue = Queue()
    
    def emit_to_ui(self, message: str):
        """Queue message for UI display"""
        self.event_queue.put(message)


class TimingData:
    """Records timing data for a single automation cycle"""
    
    def __init__(self, cycle_number: int):
        self.cycle_number = cycle_number
        self.stage_1_delay = 0.0
        self.stage_2_delay = 0.0
        self.stage_3_delay = 0.0
        self.stage_4_delay = 0.0
        self.stage_4_gas_hold = 0.0
        self.cooldown_time = 0.0
        self.total_time = 0.0
        self.timestamp = datetime.now()
    
    def format_summary(self) -> str:
        """Format timing data as a clean summary block"""
        lines = [
            f"[Cycle {self.cycle_number}] Timing Summary:",
            f"  → Stage 1 │ Reaction delay:        {self.stage_1_delay:.3f}s",
            f"  → Stage 2 │ Reaction delay:        {self.stage_2_delay:.3f}s",
            f"  → Stage 3 │ Reaction delay:        {self.stage_3_delay:.3f}s",
            f"  → Stage 4 │ Reaction delay:        {self.stage_4_delay:.3f}s  │  W key held: {int(self.stage_4_gas_hold*1000):,}ms",
            f"  → Cooldown │                        {int(self.cooldown_time*1000):,}ms",
            f"  ─────────────────────────────────────────",
            f"  Total cycle time:                  {self.total_time:.3f}s",
        ]
        return "\n".join(lines)


# ============================================================================
# SCREEN CAPTURE & TEMPLATE MATCHING
# ============================================================================

class ScreenCapture:
    """Efficient screenshot capture using MSS"""
    
    def __init__(self):
        self.mss = mss.MSS()
        self.monitor = self.mss.monitors[1]  # Primary monitor
    
    def capture(self) -> cv2.Mat:
        """Capture current screen"""
        screenshot = self.mss.grab(self.monitor)
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGBA2BGR)
        return frame


def load_template(template_path: str) -> Optional[cv2.Mat]:
    """Load template image from file"""
    if not os.path.exists(template_path):
        return None
    
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    return template


def detect_ui_element(frame: cv2.Mat, template: cv2.Mat, 
                      confidence_threshold: float = 0.80) -> Tuple[bool, Optional[Tuple[int, int]]]:
    """Detect UI element using template matching"""
    if template is None or frame.shape[0] < template.shape[0] or frame.shape[1] < template.shape[1]:
        return False, None
    
    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    if max_val >= confidence_threshold:
        return True, max_loc
    
    return False, None

# ============================================================================
# DIRECTX INPUT FUNCTIONS
# ============================================================================

def simulate_key_press_directx(scan_code: int, press_duration: float = 0.1) -> bool:
    """
    Simulate hardware key press using DirectX scan codes.
    Returns True if successful, False otherwise.
    """
    try:
        # Key down
        key_down = INPUT()
        key_down.type = INPUT_KEYBOARD
        key_down.ki.wVk = 0
        key_down.ki.wScan = scan_code
        key_down.ki.dwFlags = KEYEVENTF_SCANCODE
        key_down.ki.time = 0
        key_down.ki.dwExtraInfo = 0
        
        result_down = SendInput(1, byref(key_down), ctypes.sizeof(INPUT))
        time.sleep(press_duration)
        
        # Key up
        key_up = INPUT()
        key_up.type = INPUT_KEYBOARD
        key_up.ki.wVk = 0
        key_up.ki.wScan = scan_code
        key_up.ki.dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        key_up.ki.time = 0
        key_up.ki.dwExtraInfo = 0
        
        result_up = SendInput(1, byref(key_up), ctypes.sizeof(INPUT))
        
        return result_down == 1 and result_up == 1
    
    except Exception:
        return False


def click_at_cursor(x: int, y: int) -> bool:
    """Click at specified screen coordinates"""
    try:
        user32.SetCursorPos(x, y)
        time.sleep(random.uniform(0.05, 0.1))
        user32.mouse_event(MOUSE_EVENT_LEFTDOWN, x, y, 0, 0)
        time.sleep(random.uniform(0.08, 0.15))
        user32.mouse_event(MOUSE_EVENT_LEFTUP, x, y, 0, 0)
        return True
    except Exception:
        return False

# ============================================================================
# AUTOMATION CORE ENGINE
# ============================================================================

class ForzaAutomationEngine:
    """Core automation logic with clean separation from UI"""
    
    def __init__(self, template_dir: str = None, logger: Optional[logging.Logger] = None):
        # Use provided template_dir, or auto-detect based on execution context
        if template_dir is None:
            template_dir = get_template_dir()
        
        self.template_dir = template_dir
        self.logger = logger or logging.getLogger(__name__)
        self.screen_capture = ScreenCapture()
        self.stop_signal = False
        self.pause_signal = False
        self.loop_count = 0
        self.timing_queue = Queue()  # For sending timing data to UI
        
        # Track timing variation for pacing diagnostics
        self.previous_gas_hold_duration = None
        self.previous_cooldown_duration = None
        self.extended_cooldown_counter = 0
        self.extended_cooldown_trigger = random.randint(8, 12)  # Every 8-12 cycles
        
        # Load templates
        self.template_scoreboard_x = load_template(os.path.join(template_dir, "scoreboard_x.png"))
        self.template_confirm_yes = load_template(os.path.join(template_dir, "confirm_yes.png"))
        self.template_start_race = load_template(os.path.join(template_dir, "start_race.png"))
        self.template_race_progress_0 = load_template(os.path.join(template_dir, "race_progress0.png"))
        self.template_race_progress_90 = load_template(os.path.join(template_dir, "race_progress90.png"))
    
    def _interruptible_sleep(self, duration: float) -> bool:
        """Sleep with stop/pause signal checking. Returns False if interrupted"""
        elapsed = 0.0
        chunk_size = 0.2
        while elapsed < duration:
            if self.stop_signal or self.pause_signal:
                return False
            remaining = duration - elapsed
            sleep_time = min(chunk_size, remaining)
            time.sleep(sleep_time)
            elapsed += sleep_time
        return True
    
    def _ensure_game_focused(self):
        """Ensure Forza window is focused"""
        try:
            EnumWindows = ctypes.windll.user32.EnumWindows
            GetWindowText = ctypes.windll.user32.GetWindowTextW
            GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
            SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
            
            forza_hwnd = None
            
            def enum_handler(hwnd, ctx):
                nonlocal forza_hwnd
                if GetWindowTextLength(hwnd):
                    buff = ctypes.create_unicode_buffer(GetWindowTextLength(hwnd) + 1)
                    GetWindowText(hwnd, buff, len(buff))
                    if 'Forza' in buff.value:
                        forza_hwnd = hwnd
                        return False
                return True
            
            EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(enum_handler), 0)
            
            if forza_hwnd:
                SetForegroundWindow(forza_hwnd)
        except Exception:
            pass
    
    def stage_1_detect_scoreboard(self) -> Tuple[bool, float]:
        """Stage 1: Detect race scoreboard. Returns (success, reaction_delay)"""
        frame = self.screen_capture.capture()
        detected, coords = detect_ui_element(frame, self.template_scoreboard_x, confidence_threshold=0.80)
        
        if detected:
            reaction_delay = random.uniform(1, 2)
            if not self._interruptible_sleep(reaction_delay):
                return False, 0.0
            
            self._ensure_game_focused()
            time.sleep(0.2)
            
            click_x = coords[0] + self.template_scoreboard_x.shape[1] // 2
            click_y = coords[1] + self.template_scoreboard_x.shape[0] // 2
            click_at_cursor(click_x, click_y)
            
            return True, reaction_delay
        
        return False, 0.0
    
    def stage_2_detect_confirm_yes(self) -> Tuple[bool, float]:
        """Stage 2: Detect confirmation dialog. Returns (success, reaction_delay)"""
        frame = self.screen_capture.capture()
        detected, coords = detect_ui_element(frame, self.template_confirm_yes, confidence_threshold=0.60)
        
        if detected:
            reaction_delay = random.uniform(1, 2)
            if not self._interruptible_sleep(reaction_delay):
                return False, 0.0
            
            self._ensure_game_focused()
            time.sleep(0.2)
            
            click_x = coords[0] + self.template_confirm_yes.shape[1] // 2
            click_y = coords[1] + self.template_confirm_yes.shape[0] // 2
            click_at_cursor(click_x, click_y)
            
            return True, reaction_delay
        
        return False, 0.0
    
    def stage_3_detect_start_race(self) -> Tuple[bool, float]:
        """Stage 3: Detect start race screen. Returns (success, reaction_delay)"""
        frame = self.screen_capture.capture()
        detected, coords = detect_ui_element(frame, self.template_start_race, confidence_threshold=0.70)
        
        if detected:
            reaction_delay = random.uniform(1, 2)
            if not self._interruptible_sleep(reaction_delay):
                return False, 0.0
            
            self._ensure_game_focused()
            time.sleep(0.2)
            
            click_x = coords[0] + self.template_start_race.shape[1] // 2
            click_y = coords[1] + self.template_start_race.shape[0] // 2
            click_at_cursor(click_x, click_y)
            
            return True, reaction_delay
        
        return False, 0.0
    
    def stage_4_continuous_gas_hold(self) -> Tuple[bool, float, float]:
        """
        Stage 4: Detect race start (0% progress), hold W key until race end.
        Returns (success, reaction_delay, gas_hold_duration)
        """
        self.logger.info("[STAGE 4] Scanning for race start (0% progress)...")
        
        # Wait for race start detection (0% progress)
        race_start_detected = False
        start_wait_timeout = time.time() + 60
        
        while not race_start_detected and time.time() < start_wait_timeout:
            if self.stop_signal:
                return False, 0.0, 0.0
            
            frame = self.screen_capture.capture()
            
            # Detect race start using race_progress0 template
            if self.template_race_progress_0 is not None:
                detected, coords = detect_ui_element(frame, self.template_race_progress_0, confidence_threshold=0.70)
            else:
                detected = False
            
            if detected:
                race_start_detected = True
                self.logger.info(f"✓ RACE START (0% progress) DETECTED at {coords}")
            else:
                self._interruptible_sleep(0.2)
        
        if not race_start_detected:
            self.logger.warning("⚠ Race start not detected within timeout")
            return False, 0.0, 0.0
        
        # Reaction delay before pressing W
        reaction_delay = random.uniform(0.3, 1)
        self.logger.info(f"   ├─ Human reaction delay: {reaction_delay:.3f}s")
        if not self._interruptible_sleep(reaction_delay):
            return False, 0.0, 0.0
        
        # Hold W key for a variable duration to support pacing diagnostics
        while True:
            gas_hold_duration = random.uniform(24.5, 28.4)
            # Ensure different from previous cycle
            if self.previous_gas_hold_duration is None or abs(gas_hold_duration - self.previous_gas_hold_duration) > 0.1:
                break
        self.previous_gas_hold_duration = gas_hold_duration
        
        self.logger.info(f"   ├─ HOLDING W KEY to accelerate car...")
        self.logger.info(f"      └─ Will hold for {gas_hold_duration:.3f} seconds (variable pacing: 24.5-28.4s)")
        
        try:
            self.logger.info(f"      ✓ Pressing W key down...")
            keyboard.press('w')
            time.sleep(0.2)
            self.logger.info(f"      ✓ W key held - car accelerating for 27 seconds...")
            
            hold_time = 0.0
            while hold_time < gas_hold_duration and not self.stop_signal:
                time.sleep(0.5)
                hold_time += 0.5
            
            self.logger.info(f"      └─ Releasing W key...")
            keyboard.release('w')
            time.sleep(0.2)
            
            if self.stop_signal:
                self.logger.info("⚠ Stage 4 interrupted by stop signal\n")
                return True, reaction_delay, gas_hold_duration
            
            self.logger.info("✓ Stage 4 completed - Race finished! ✓\n")
            return True, reaction_delay, gas_hold_duration
        
        except Exception as e:
            self.logger.error(f"      ✗ Error during W key hold: {e}")
            try:
                keyboard.release('w')
            except:
                pass
            return False, 0.0, 0.0
    
    def run_cycle(self) -> bool:
        """Execute one complete automation cycle. Returns False if interrupted."""
        if self.stop_signal:
            return False
        
        self.loop_count += 1
        timing = TimingData(self.loop_count)
        cycle_start = time.time()
        
        # Stage 1
        stage_1_start = time.time()
        stage_1_complete = False
        while not stage_1_complete:
            if self.stop_signal:
                return False
            success, delay = self.stage_1_detect_scoreboard()
            if success:
                stage_1_complete = True
                timing.stage_1_delay = delay
            else:
                self._interruptible_sleep(0.5)
        
        # Stage 2
        stage_2_start = time.time()
        stage_2_complete = False
        while not stage_2_complete:
            if self.stop_signal:
                return False
            success, delay = self.stage_2_detect_confirm_yes()
            if success:
                stage_2_complete = True
                timing.stage_2_delay = delay
            else:
                self._interruptible_sleep(0.5)
        
        # Stage 3
        stage_3_start = time.time()
        stage_3_complete = False
        while not stage_3_complete:
            if self.stop_signal:
                return False
            success, delay = self.stage_3_detect_start_race()
            if success:
                stage_3_complete = True
                timing.stage_3_delay = delay
            else:
                self._interruptible_sleep(0.5)
        
        # Stage 4
        stage_4_start = time.time()
        stage_4_complete = False
        while not stage_4_complete:
            if self.stop_signal:
                return False
            success, delay, gas_duration = self.stage_4_continuous_gas_hold()
            if success:
                stage_4_complete = True
                timing.stage_4_delay = delay
                timing.stage_4_gas_hold = gas_duration
            else:
                self._interruptible_sleep(0.5)
        
        # Cooldown with timing variation and occasional extended breaks
        self.extended_cooldown_counter += 1
        
        # Check if we should trigger extended cooldown (every 8-12 cycles)
        if self.extended_cooldown_counter >= self.extended_cooldown_trigger:
            # Extended cooldown: simulate human stepping away briefly
            cooldown_duration = random.uniform(15.0, 30.0)
            self.logger.info(f"[EXTENDED COOLDOWN] Stepping away for {cooldown_duration:.2f}s (human behavior)")
            self.extended_cooldown_counter = 0
            self.extended_cooldown_trigger = random.randint(8, 12)  # Next trigger in 8-12 cycles
        else:
            # Normal cooldown with timing variation (4.2s - 7.5s)
            while True:
                cooldown_duration = random.uniform(4.2, 7.5)
                # Ensure different from previous cycle
                if self.previous_cooldown_duration is None or abs(cooldown_duration - self.previous_cooldown_duration) > 0.1:
                    break
        
        self.previous_cooldown_duration = cooldown_duration
        timing.cooldown_time = cooldown_duration
        self.logger.info(f"[COOLDOWN] Waiting {cooldown_duration:.3f}s before next cycle...")
        
        if not self._interruptible_sleep(cooldown_duration):
            return False
        
        # Calculate total time
        timing.total_time = time.time() - cycle_start
        
        # Send timing data to UI
        self.timing_queue.put(timing)
        
        return True
    
    def run(self):
        """Run automation in continuous loop"""
        try:
            while not self.stop_signal:
                if not self.run_cycle():
                    break
        except Exception as e:
            self.logger.error(f"Automation error: {e}", exc_info=True)

# ============================================================================
# CUSTOMTKINTER UI COMPONENTS
# ============================================================================

class AutomationUI:
    """Professional CustomTkinter UI for Forza automation"""
    
    def __init__(self):
        # Setup theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Create main window
        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(fg_color=COLOR_BG_DARK)
        
        # Setup logging
        self.logger = logging.getLogger("ForzaApp")
        self.logger.setLevel(logging.DEBUG)
        
        # State variables
        self.automation_engine: Optional[ForzaAutomationEngine] = None
        self.automation_thread: Optional[threading.Thread] = None
        self.running = False
        self.paused = False
        self.start_time: Optional[float] = None
        self.elapsed_seconds = 0
        
        # Queues for thread-safe communication
        self.detection_log_queue = Queue()
        self.timing_log_queue = Queue()
        
        # Build UI
        self._build_ui()
        self._setup_hotkeys()
        
        # Start update loop
        self.root.after(100, self._update_loop)
    
    def _build_ui(self):
        """Build the complete UI layout"""
        # Configure grid
        self.root.grid_rowconfigure(0, weight=0)      # Top bar
        self.root.grid_rowconfigure(1, weight=0)      # Control panel
        self.root.grid_rowconfigure(2, weight=1)      # Detection log
        self.root.grid_rowconfigure(3, weight=1)      # Timing log
        self.root.grid_rowconfigure(4, weight=0)      # Bottom status bar
        self.root.grid_columnconfigure(0, weight=1)
        
        # TOP BAR
        self._build_top_bar()
        
        # CONTROL PANEL
        self._build_control_panel()
        
        # DETECTION LOG PANEL
        self._build_detection_log_panel()
        
        # TIMING LOG PANEL
        self._build_timing_log_panel()
        
        # BOTTOM STATUS BAR
        self._build_bottom_status_bar()
    
    def _build_top_bar(self):
        """Build top bar with title, status indicator, and timer"""
        top_bar = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SECONDARY, 
                               corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        top_bar.grid_columnconfigure((0, 1), weight=1)
        top_bar.grid_columnconfigure(2, weight=0)
        
        # Title + Status indicator (left)
        left_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        left_frame.grid_columnconfigure(0, weight=0)
        
        ctk.CTkLabel(left_frame, text="🏁 Forza Automation", 
                    font=("Helvetica", 14, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 8))
        
        self.status_indicator = ctk.CTkLabel(left_frame, text="●", 
                                            font=("Helvetica", 12), text_color="#666666")
        self.status_indicator.pack(side="left", padx=4)
        
        self.status_text = ctk.CTkLabel(left_frame, text="IDLE", 
                                       font=("Helvetica", 10), text_color=COLOR_TEXT_SECONDARY)
        self.status_text.pack(side="left", padx=0)
        
        # Timer (center)
        self.timer_label = ctk.CTkLabel(top_bar, text="00:00:00", 
                                       font=("Courier", 12, "bold"), text_color=COLOR_ACCENT)
        self.timer_label.grid(row=0, column=1, sticky="ew", padx=8, pady=10)
        
        # Cycle count (right)
        cycle_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        cycle_frame.grid(row=0, column=2, sticky="e", padx=12, pady=10)
        
        ctk.CTkLabel(cycle_frame, text="Cycles:", 
                    font=("Helvetica", 9), text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        
        self.cycle_count_label = ctk.CTkLabel(cycle_frame, text="0", 
                                             font=("Courier", 11, "bold"), text_color=COLOR_ACCENT)
        self.cycle_count_label.pack(side="left")
    
    def _build_control_panel(self):
        """Build control panel with Start, Stop, Pause buttons"""
        control_panel = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SECONDARY, 
                                     corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        control_panel.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        control_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Start button
        self.start_btn = ctk.CTkButton(control_panel, text="▶  START (F5)", 
                                      fg_color=COLOR_ACCENT, text_color="#000000",
                                      font=("Helvetica", 11, "bold"),
                                      corner_radius=6, height=36,
                                      command=self.start_automation)
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        
        # Pause button
        self.pause_btn = ctk.CTkButton(control_panel, text="⏸  PAUSE (F8)", 
                                      fg_color=COLOR_BG_TERTIARY, text_color=COLOR_TEXT_PRIMARY,
                                      font=("Helvetica", 11, "bold"),
                                      corner_radius=6, height=36,
                                      command=self.toggle_pause, state="disabled")
        self.pause_btn.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        
        # Stop button
        self.stop_btn = ctk.CTkButton(control_panel, text="⏹  STOP (F6)", 
                                     fg_color=COLOR_ERROR, text_color="#FFFFFF",
                                     font=("Helvetica", 11, "bold"),
                                     corner_radius=6, height=36,
                                     command=self.stop_automation, state="disabled")
        self.stop_btn.grid(row=0, column=2, sticky="ew", padx=8, pady=8)
        
        # Debug button
        self.debug_btn = ctk.CTkButton(control_panel, text="🔍  TEST (F7)", 
                                      fg_color=COLOR_BG_TERTIARY, text_color=COLOR_ACCENT,
                                      font=("Helvetica", 11, "bold"),
                                      corner_radius=6, height=36,
                                      command=self.run_debug)
        self.debug_btn.grid(row=0, column=3, sticky="ew", padx=8, pady=8)
    
    def _build_detection_log_panel(self):
        """Build detection log panel (top log area)"""
        log_container = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SECONDARY, 
                                     corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        log_container.grid(row=2, column=0, sticky="nsew", padx=8, pady=(8, 4))
        log_container.grid_rowconfigure(1, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkLabel(log_container, text="📋 Detection Log", 
                             font=("Helvetica", 10, "bold"), text_color=COLOR_ACCENT)
        header.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        
        # Text widget
        self.detection_log_text = ctk.CTkTextbox(log_container, 
                                                 font=("Courier", 8),
                                                 fg_color=COLOR_BG_DARK,
                                                 text_color=COLOR_TEXT_PRIMARY,
                                                 border_width=0,
                                                 corner_radius=4)
        self.detection_log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.detection_log_text.configure(state="disabled")
    
    def _build_timing_log_panel(self):
        """Build timing summary log panel (bottom log area)"""
        log_container = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SECONDARY, 
                                     corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        log_container.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 8))
        log_container.grid_rowconfigure(1, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkLabel(log_container, text="⏱  Cycle Timing Summary", 
                             font=("Helvetica", 10, "bold"), text_color=COLOR_SUCCESS)
        header.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        
        # Text widget
        self.timing_log_text = ctk.CTkTextbox(log_container, 
                                              font=("Courier", 8),
                                              fg_color=COLOR_BG_DARK,
                                              text_color=COLOR_TEXT_PRIMARY,
                                              border_width=0,
                                              corner_radius=4)
        self.timing_log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.timing_log_text.configure(state="disabled")
    
    def _build_bottom_status_bar(self):
        """Build bottom status bar with stage info"""
        status_bar = ctk.CTkFrame(self.root, fg_color=COLOR_BG_SECONDARY, 
                                  corner_radius=0, border_width=1, border_color=COLOR_BORDER)
        status_bar.grid(row=4, column=0, sticky="ew", padx=0, pady=0)
        status_bar.grid_columnconfigure(0, weight=1)
        
        self.stage_label = ctk.CTkLabel(status_bar, text="Stage: —  │  Last action: Ready", 
                                       font=("Helvetica", 9), text_color=COLOR_TEXT_SECONDARY)
        self.stage_label.grid(row=0, column=0, sticky="w", padx=10, pady=8)
    
    def _setup_hotkeys(self):
        """Register global hotkeys"""
        try:
            keyboard.add_hotkey('f5', lambda: self.root.after(0, self.start_automation))
            keyboard.add_hotkey('f6', lambda: self.root.after(0, self.stop_automation))
            keyboard.add_hotkey('f7', lambda: self.root.after(0, self.run_debug))
            keyboard.add_hotkey('f8', lambda: self.root.after(0, self.toggle_pause))
        except Exception as e:
            self.logger.warning(f"Could not register hotkeys: {e}")
    
    def _update_loop(self):
        """Update loop called every 100ms"""
        # Update timer
        if self.running and self.start_time:
            elapsed = time.time() - self.start_time
            mins, secs = divmod(int(elapsed), 60)
            hours, mins = divmod(mins, 60)
            self.timer_label.configure(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
        
        # Process detection log queue
        try:
            while True:
                message = self.detection_log_queue.get_nowait()
                self._append_to_detection_log(message)
        except Empty:
            pass
        
        # Process timing log queue
        try:
            while True:
                timing_data = self.timing_log_queue.get_nowait()
                self._append_to_timing_log(timing_data)
        except Empty:
            pass
        
        # Process engine timing queue
        if self.automation_engine:
            try:
                while True:
                    timing_data = self.automation_engine.timing_queue.get_nowait()
                    self.timing_log_queue.put(timing_data)
            except Empty:
                pass
        
        # Update cycle count
        if self.automation_engine:
            self.cycle_count_label.configure(text=str(self.automation_engine.loop_count))
        
        self.root.after(100, self._update_loop)
    
    def _append_to_detection_log(self, message: str):
        """Append message to detection log"""
        self.detection_log_text.configure(state="normal")
        self.detection_log_text.insert("end", message + "\n")
        self.detection_log_text.see("end")
        self.detection_log_text.configure(state="disabled")
    
    def _append_to_timing_log(self, timing_data: TimingData):
        """Append timing summary to timing log"""
        self.timing_log_text.configure(state="normal")
        self.timing_log_text.insert("end", timing_data.format_summary() + "\n\n")
        self.timing_log_text.see("end")
        self.timing_log_text.configure(state="disabled")
    
    def _update_status(self, status: str, color: str):
        """Update status indicator"""
        status_colors = {
            "IDLE": "#666666",
            "RUNNING": COLOR_SUCCESS,
            "PAUSED": COLOR_WARNING,
            "STOPPED": COLOR_ERROR,
        }
        self.status_text.configure(text=status)
        self.status_indicator.configure(text_color=status_colors.get(status, color))
    
    def start_automation(self):
        """Start the automation"""
        if self.running:
            return
        
        self.running = True
        self.paused = False
        self.start_time = time.time()
        
        self.automation_engine = ForzaAutomationEngine(template_dir=".")
        self.automation_engine.stop_signal = False
        self.automation_engine.pause_signal = False
        
        # Update UI state
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self._update_status("RUNNING", COLOR_SUCCESS)
        self.stage_label.configure(text="Stage: 1 / 4  │  Last action: Automation started")
        
        # Log event
        self._append_to_detection_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ Automation started (F5)\n")
        
        # Start automation thread
        self.automation_thread = threading.Thread(target=self._automation_loop, daemon=True)
        self.automation_thread.start()
    
    def stop_automation(self):
        """Stop the automation"""
        if not self.running:
            return
        
        self.automation_engine.stop_signal = True
        self.running = False
        self.paused = False
        
        # Update UI state
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self._update_status("STOPPED", COLOR_ERROR)
        self.stage_label.configure(text=f"Stage: —  │  Last action: Stopped after {self.automation_engine.loop_count} cycles")
        
        # Log event
        self._append_to_detection_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⛔ Automation stopped (F6)\n")
    
    def toggle_pause(self):
        """Toggle pause state"""
        if not self.running:
            return
        
        self.paused = not self.paused
        self.automation_engine.pause_signal = self.paused
        
        if self.paused:
            self._update_status("PAUSED", COLOR_WARNING)
            self.pause_btn.configure(text="▶  RESUME (F8)")
            self._append_to_detection_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏸  Automation paused\n")
        else:
            self._update_status("RUNNING", COLOR_SUCCESS)
            self.pause_btn.configure(text="⏸  PAUSE (F8)")
            self._append_to_detection_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ▶  Automation resumed\n")
    
    def run_debug(self):
        """Run template matching debug test"""
        self._append_to_detection_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Debug test started\n")
        self._append_to_detection_log("Checking template loads and capturing screen...\n")
        
        if not self.automation_engine:
            self.automation_engine = ForzaAutomationEngine(template_dir=".")
        
        frame = self.automation_engine.screen_capture.capture()
        debug_path = os.path.join(".", "DEBUG_SCREEN.png")
        cv2.imwrite(debug_path, frame)
        
        self._append_to_detection_log(f"✓ Screen captured to: {debug_path}\n")
        self._append_to_detection_log(f"✓ Debug test completed\n\n")
    
    def _automation_loop(self):
        """Background automation thread"""
        try:
            self.automation_engine.run()
        except Exception as e:
            self.logger.error(f"Automation error: {e}", exc_info=True)
            self._append_to_detection_log(f"✗ ERROR: {e}\n")
        finally:
            self.root.after(0, self.stop_automation)
    
    def run(self):
        """Start the UI"""
        self.root.mainloop()

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Application entry point"""
    try:
        ui = AutomationUI()
        ui.run()
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
