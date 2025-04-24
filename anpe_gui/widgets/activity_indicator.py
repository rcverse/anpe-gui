from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QPoint, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient
import math

# Import theme colors
from anpe_gui.theme import PRIMARY_COLOR, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR

# --- State Constants ---
STATE_IDLE = 'idle'
STATE_ACTIVE = 'active'
STATE_WARNING = 'warning'
STATE_ERROR = 'error'
STATE_CHECKING = 'checking' # New state for background checks
STATE_LOADING = 'loading' # New state specifically for splash loading

class PulsingActivityIndicator(QWidget):
    """
    An activity indicator displaying four states with smooth transitions:
    - Idle (IDLE): Green glowing circle with subtle breathing.
    - Active (ACTIVE): Blue solid ripple expanding outwards.
    - Warning (WARNING): Orange glowing circle with faster breathing.
    - Error (ERROR): Red glowing circle with smooth blinking.
    Uses theme colors and non-linear easing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Configure widget appearance
        self.setMinimumSize(24, 24)
        # self.setMaximumHeight(24) # REMOVED - Allow widget to be larger for ripple

        # Animation properties
        self.ripple_duration_steps = 200 # Slightly Faster, Ease-Out (was 225)
        self.ripples = [] # List to store ripple progress (0.0 to 1.0) for ACTIVE state

        # --- State Management ---
        self._target_state = STATE_IDLE       # The state we are transitioning towards
        self._current_visual_state = STATE_IDLE # The state represented *before* the transition started
        self._transition_progress = 1.0     # 0.0 (start) to 1.0 (end) of transition
        self._transition_step = 0.06        # Speed of fade between states (Slightly faster: was 0.05)

        # --- Colors ---
        self.active_color = QColor(PRIMARY_COLOR) # Blue for active ripple
        self.idle_color = QColor(SUCCESS_COLOR)   # Green for idle glow
        self.warning_color = QColor(WARNING_COLOR) # Orange for warning glow
        self.error_color = QColor(ERROR_COLOR)     # Red for error glow

        # --- Idle State Animation ---
        self._idle_breath_phase = 0.0
        self._idle_breath_speed = 0.02

        # --- Warning State Animation ---
        self._warning_breath_phase = 0.0
        self._warning_breath_speed = 0.05 # Faster than idle

        # --- Error State Animation ---
        self._error_blink_phase = 0.0
        self._error_blink_speed = 0.08 # Faster than breathing for blinking effect

        # --- Checking State Animation ---
        self._checking_pulse_phase = 0.0
        self._checking_pulse_speed = 0.06 # Faster than idle, slower than error blink

        # --- Set up timer for animation ---
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.setInterval(15) # Smooth interval

        # Initialize in idle state without visual transition
        self._ensure_timer_running()

    def _ensure_timer_running(self):
        """Starts the timer if it's not already active."""
        if not self._timer.isActive():
            self._timer.start()

    def _set_state(self, new_state):
        """Internal method to initiate a state transition."""
        # --- DEBUGGING --- 
        # print(f"[Indicator] Request to set state to: {new_state}")
        # print(f"[Indicator] Current state: {self._current_visual_state}, Target state: {self._target_state}, Progress: {self._transition_progress:.2f}")
        # --- END DEBUGGING ---

        if new_state == self._target_state:
            # If we are already fully in the target state, do nothing.
            if self._transition_progress >= 1.0:
                # print(f"[Indicator] Already in state {new_state}. Ignoring.")
                return
            # If currently transitioning *to* this state, also do nothing.
            # This prevents resetting the progress if the button is clicked multiple times quickly.
            # print(f"[Indicator] Already transitioning to {new_state}. Ignoring.")
            return

        # Determine the state we are transitioning *from*
        # If a transition is in progress (progress < 1.0), the visual starting point
        # is the state stored in _current_visual_state (the state *before*
        # the current transition began).
        # If no transition is in progress (progress == 1.0), the visual starting point
        # is the state we are currently fully in (_target_state).
        if self._transition_progress >= 1.0:
            self._current_visual_state = self._target_state
            # print(f"[Indicator] Starting from fully reached state: {self._current_visual_state}")

        # Set the new target and reset progress
        self._target_state = new_state
        self._transition_progress = 0.0
        # print(f"[Indicator] Transitioning from {self._current_visual_state} to {self._target_state}. Progress reset.")
        self._ensure_timer_running()

    def _get_dominant_state(self):
        """Helper to determine which state is visually dominant during transition."""
        # If we are more than halfway through the transition, consider the target state dominant.
        # Otherwise, the state we came from is dominant.
        if self._transition_progress >= 0.5:
            return self._target_state
        else:
            # This needs refinement - we don't explicitly store the 'from' state if interrupted.
            # Let's stick to the simpler model: _current_visual_state = self._target_state before reset
            return self._current_visual_state # Return the state we were transitioning *from*


    # --- Public Methods to Control State ---

    def start(self):
        """Transition to the ACTIVE (blue ripple) state."""
        self._set_state(STATE_ACTIVE)

    def idle(self):
        """Transition to the IDLE (green glow) state."""
        self._set_state(STATE_IDLE)

    def stop(self):
        """Alias for idle() for backward compatibility / common usage."""
        self.idle()

    def warn(self):
        """Transition to the WARNING (orange glow) state."""
        self._set_state(STATE_WARNING)

    def error(self):
        """Transition to the ERROR (red blink) state."""
        self._set_state(STATE_ERROR)

    def checking(self):
        """Transition to the CHECKING (yellow pulse) state."""
        self._set_state(STATE_CHECKING)

    def loading(self):
        """Transition to the LOADING (faster, transparent blue ripple) state."""
        self._set_state(STATE_LOADING)

    def set_color(self, color):
        """Set the base color for the ACTIVE ripple state."""
        # Note: Idle, Warning, Error colors are fixed for status indication
        self.active_color = QColor(color)
        self.update() # Trigger repaint if needed

    def _update_animation(self):
        """Update transition progress and state-specific animations."""
        # --- DEBUGGING ---
        # if self._transition_progress < 1.0:
        #      print(f"[Indicator Update] Transitioning from {self._current_visual_state} to {self._target_state}. Progress: {self._transition_progress:.2f}")
        # --- END DEBUGGING ---

        # Update transition progress
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + self._transition_step)
            # When transition finishes, the _current_visual_state is effectively the _target_state
            # We don't need to explicitly set _current_visual_state = _target_state here,
            # the paintEvent interpolation handles reaching the final state.

        # Update state-specific animation phases
        self._idle_breath_phase = (self._idle_breath_phase + self._idle_breath_speed) % (2 * math.pi)
        self._warning_breath_phase = (self._warning_breath_phase + self._warning_breath_speed) % (2 * math.pi)
        self._error_blink_phase = (self._error_blink_phase + self._error_blink_speed) % (2 * math.pi)
        self._checking_pulse_phase = (self._checking_pulse_phase + self._checking_pulse_speed) % (2 * math.pi)

        # --- Update ACTIVE/LOADING state ripple progress ---
        # Use faster duration for LOADING state
        duration_steps = self.ripple_duration_steps
        if self._target_state == STATE_LOADING:
            duration_steps = 150 # Faster completion (was 200)
        
        progress_step = 1.0 / duration_steps if duration_steps > 0 else 1.0 # Avoid division by zero
        
        new_ripples = []
        for progress in self.ripples:
            new_progress = progress + progress_step
            if new_progress < 1.0:
                new_ripples.append(new_progress)
        self.ripples = new_ripples

        # Launch new ripple if fully in ACTIVE or LOADING state and no ripple exists
        # Maybe allow multiple overlapping ripples for LOADING state?
        is_fully_active_or_loading = (self._target_state in [STATE_ACTIVE, STATE_LOADING] and self._transition_progress >= 1.0)
        
        # Simple approach: Launch one ripple when idle
        if is_fully_active_or_loading and not self.ripples:
             self.ripples.append(0.0)
        
        # TODO: Consider launching ripples more frequently for LOADING state if desired

        # Trigger repaint
        self.update()


    def _get_glow_params(self, state, phase):
        """Calculates radius and alpha for glow-based states (Idle, Warning, Error)."""
        # Initialize with all possible parameters, defaulting non-glow ones to 0
        params = {
            'type': 'glow',
            'glow_radius': 0.0, 'glow_alpha': 0.0, 'color': self.idle_color,
            'center_dot_radius': 0.0, 'center_dot_alpha': 0.0,
            'ripple_radius': 0.0, 'ripple_alpha': 0.0
        }

        if state == STATE_IDLE:
            params['color'] = self.idle_color
            breath_factor = (1.0 + math.sin(phase)) / 2.0 # 0.0 to 1.0
            max_radius = 0.35
            base_radius = max_radius * (0.90 + 0.10 * breath_factor) # Subtle pulse size
            base_alpha = 180 + 40 * breath_factor # Subtle pulse alpha
            params['glow_radius'] = base_radius
            params['glow_alpha'] = base_alpha
        elif state == STATE_WARNING:
            params['color'] = self.warning_color
            breath_factor = (1.0 + math.sin(phase)) / 2.0 # 0.0 to 1.0
            max_radius = 0.40 # Consistent base
            base_radius = max_radius * (0.85 + 0.15 * breath_factor) # More noticeable pulse
            base_alpha = 170 + 60 * breath_factor # More noticeable alpha change
            params['glow_radius'] = base_radius
            params['glow_alpha'] = base_alpha
        elif state == STATE_ERROR:
            params['color'] = self.error_color
            blink_factor = (1.0 + math.sin(phase)) / 2.0 # 0.0 to 1.0
            max_radius = 0.40 # Consistent radius
            min_alpha = 60 # Blink low alpha
            max_alpha = 220 # Blink high alpha
            current_alpha = min_alpha + (max_alpha - min_alpha) * blink_factor
            params['glow_radius'] = max_radius # Fixed radius during blink
            params['glow_alpha'] = current_alpha
        elif state == STATE_CHECKING: # Added state
            params['color'] = self.warning_color # Use yellow
            pulse_factor = (1.0 + math.sin(phase)) / 2.0 # 0.0 to 1.0
            max_radius = 0.40 # Consistent radius with warn/error
            min_pulse_alpha = 100 # Dimmer than warn/error base
            max_pulse_alpha = 230 # Brighter peak than warn/error base
            # Make alpha pulse more sharply than breathing
            pulse_alpha = min_pulse_alpha + (max_pulse_alpha - min_pulse_alpha) * pow(pulse_factor, 1.5)
            params['glow_radius'] = max_radius # Keep radius constant during pulse
            params['glow_alpha'] = pulse_alpha

        return params

    def _get_active_params(self, width, height):
        """Calculates parameters for the ACTIVE state (ripple and center dot)."""
        # Initialize with all possible parameters, defaulting non-active ones to 0
        params = {
            'type': 'active',
            'glow_radius': 0.0, 'glow_alpha': 0.0,
            'center_dot_radius': 0.0, 'center_dot_alpha': 0.0,
            'ripple_radius': 0.0, 'ripple_alpha': 0.0,
            'color': self.active_color
        }
        min_widget_dim = min(width, height)

        # Center Dot parameters (always present in active state, fades with transition)
        center_dot_max_alpha = 100
        center_dot_radius = min_widget_dim * 0.12
        params['center_dot_alpha'] = center_dot_max_alpha # Base alpha when fully active
        params['center_dot_radius'] = center_dot_radius

        # Ripple parameters (only when a ripple exists)
        if self.ripples:
            progress = self.ripples[0]
            ripple_max_radius = min_widget_dim * 0.55
            ripple_min_radius = ripple_max_radius * 0.10
            t = progress
            eased_progress = 1.0 - pow(1.0 - t, 3)
            current_ripple_radius = ripple_min_radius + (ripple_max_radius - ripple_min_radius) * eased_progress
            base_ripple_alpha = int(180 * (1.0 - progress))
            base_ripple_alpha = max(0, min(255, base_ripple_alpha))
            params['ripple_alpha'] = base_ripple_alpha
            params['ripple_radius'] = current_ripple_radius

        return params

    def _get_loading_params(self, width, height):
        """Calculates parameters for the LOADING state (transparent blue ripple)."""
        # Initialize parameters, similar to active
        params = {
            'type': 'loading', # Use a distinct type for clarity
            'glow_radius': 0.0, 'glow_alpha': 0.0,
            'center_dot_radius': 0.0, 'center_dot_alpha': 0.0,
            'ripple_radius': 0.0, 'ripple_alpha': 0.0,
            'color': self.active_color
        }
        min_widget_dim = min(width, height)

        # Center Dot parameters (more transparent)
        center_dot_max_alpha = 75 # Increased from 50, still less than active (100)
        center_dot_radius = min_widget_dim * 0.12 # Same size as active
        params['center_dot_alpha'] = center_dot_max_alpha
        params['center_dot_radius'] = center_dot_radius

        # Ripple parameters (more transparent)
        if self.ripples:
            progress = self.ripples[0]
            ripple_max_radius = min_widget_dim * 0.5 
            ripple_min_radius = ripple_max_radius * 0.10
            t = progress
            # Use same easing for now, speed difference via ripple launch frequency?
            eased_progress = 1.0 - pow(1.0 - t, 3)
            current_ripple_radius = ripple_min_radius + (ripple_max_radius - ripple_min_radius) * eased_progress
            # Reduced starting alpha significantly from active state (180)
            base_ripple_alpha = int(140 * (1.0 - progress)) # Increased from 100, still less than active (180)
            base_ripple_alpha = max(0, min(255, base_ripple_alpha))
            params['ripple_alpha'] = base_ripple_alpha
            params['ripple_radius'] = current_ripple_radius

        return params

    def _interpolate_color(self, color1, color2, progress):
        """Linearly interpolate between two QColors."""
        r = int(color1.red() * (1.0 - progress) + color2.red() * progress)
        g = int(color1.green() * (1.0 - progress) + color2.green() * progress)
        b = int(color1.blue() * (1.0 - progress) + color2.blue() * progress)
        a = int(color1.alpha() * (1.0 - progress) + color2.alpha() * progress)
        return QColor(r, g, b, a)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        width = self.width()
        height = self.height()
        center = QPoint(width // 2, height // 2)
        center_f = QPointF(center)
        min_widget_dim = min(width, height)

        # Determine states and progress for interpolation
        from_state = self._current_visual_state
        to_state = self._target_state
        progress = self._transition_progress # 0.0 (start) to 1.0 (end)

        # Get parameters for the state we are transitioning FROM
        from_params = {}
        if from_state in [STATE_IDLE, STATE_WARNING, STATE_ERROR, STATE_CHECKING]:
            phase = 0.0
            if from_state == STATE_IDLE: phase = self._idle_breath_phase
            elif from_state == STATE_WARNING: phase = self._warning_breath_phase
            elif from_state == STATE_ERROR: phase = self._error_blink_phase
            elif from_state == STATE_CHECKING: phase = self._checking_pulse_phase
            from_params = self._get_glow_params(from_state, phase)
        elif from_state == STATE_ACTIVE:
            from_params = self._get_active_params(width, height)
        elif from_state == STATE_LOADING:
            from_params = self._get_loading_params(width, height)

        # Get parameters for the state we are transitioning TO
        to_params = {}
        if to_state in [STATE_IDLE, STATE_WARNING, STATE_ERROR, STATE_CHECKING]:
            phase = 0.0
            if to_state == STATE_IDLE: phase = self._idle_breath_phase
            elif to_state == STATE_WARNING: phase = self._warning_breath_phase
            elif to_state == STATE_ERROR: phase = self._error_blink_phase
            elif to_state == STATE_CHECKING: phase = self._checking_pulse_phase
            to_params = self._get_glow_params(to_state, phase)
        elif to_state == STATE_ACTIVE:
            to_params = self._get_active_params(width, height)
        elif to_state == STATE_LOADING:
            to_params = self._get_loading_params(width, height)

        # --- Unified Interpolation --- 
        def lerp(a, b, t):
            return a * (1.0 - t) + b * t

        interp_glow_radius_factor = lerp(from_params.get('glow_radius', 0.0), to_params.get('glow_radius', 0.0), progress)
        interp_glow_alpha = lerp(from_params.get('glow_alpha', 0.0), to_params.get('glow_alpha', 0.0), progress)
        interp_glow_color = self._interpolate_color(from_params.get('color', QColor(0,0,0,0)) if from_params.get('type') == 'glow' else QColor(0,0,0,0),
                                                to_params.get('color', QColor(0,0,0,0)) if to_params.get('type') == 'glow' else QColor(0,0,0,0),
                                                progress)

        interp_dot_radius = lerp(from_params.get('center_dot_radius', 0.0), to_params.get('center_dot_radius', 0.0), progress)
        interp_dot_alpha = lerp(from_params.get('center_dot_alpha', 0.0), to_params.get('center_dot_alpha', 0.0), progress)

        interp_ripple_radius = lerp(from_params.get('ripple_radius', 0.0), to_params.get('ripple_radius', 0.0), progress)
        interp_ripple_alpha = lerp(from_params.get('ripple_alpha', 0.0), to_params.get('ripple_alpha', 0.0), progress)

        # Active/Loading color interpolation
        active_loading_types = ['active', 'loading']
        interp_active_color = self._interpolate_color(
            from_params.get('color', QColor(0,0,0,0)) if from_params.get('type') in active_loading_types else QColor(0,0,0,0),
            to_params.get('color', QColor(0,0,0,0)) if to_params.get('type') in active_loading_types else QColor(0,0,0,0),
            progress
        )

        # --- Unified Drawing --- 

        # Draw Glow component
        if interp_glow_alpha > 5 and interp_glow_radius_factor > 0.01:
            display_glow_radius = interp_glow_radius_factor * min_widget_dim
            if display_glow_radius > 0.5:
                glow_gradient = QRadialGradient(center_f, display_glow_radius)
                center_color = QColor(interp_glow_color) # Base color is already interpolated
                center_color.setAlpha(int(interp_glow_alpha)) # Apply interpolated alpha
                glow_gradient.setColorAt(0.0, center_color)
                edge_color = QColor(center_color)
                edge_color.setAlpha(0) # Fully transparent edge
                glow_gradient.setColorAt(1.0, edge_color)
                painter.setBrush(QBrush(glow_gradient))
                int_display_radius = int(display_glow_radius)
                painter.drawEllipse(center.x() - int_display_radius, center.y() - int_display_radius, int_display_radius * 2, int_display_radius * 2)

        # Draw Center Dot component
        if interp_dot_alpha > 5 and interp_dot_radius > 0.5:
            center_dot_gradient = QRadialGradient(center_f, interp_dot_radius)
            center_color = QColor(interp_active_color) # Use interpolated active/loading color
            center_color.setAlpha(int(interp_dot_alpha))
            edge_color = QColor(center_color)
            edge_color.setAlpha(0)
            center_dot_gradient.setColorAt(0.0, center_color)
            center_dot_gradient.setColorAt(1.0, edge_color)
            painter.setBrush(QBrush(center_dot_gradient))
            int_radius = int(interp_dot_radius)
            painter.drawEllipse(center.x() - int_radius, center.y() - int_radius, int_radius * 2, int_radius * 2)

        # Draw Ripple component
        if interp_ripple_alpha > 5 and interp_ripple_radius > 0.5:
            ripple_gradient = QRadialGradient(center_f, interp_ripple_radius)
            center_color = QColor(interp_active_color) # Use interpolated active/loading color
            center_color.setAlpha(int(interp_ripple_alpha))
            edge_color = QColor(center_color)
            edge_color.setAlpha(0)
            ripple_gradient.setColorAt(0.0, center_color)
            ripple_gradient.setColorAt(1.0, edge_color)
            painter.setBrush(QBrush(ripple_gradient))
            int_radius = int(interp_ripple_radius)
            painter.drawEllipse(center.x() - int_radius, center.y() - int_radius, int_radius * 2, int_radius * 2)