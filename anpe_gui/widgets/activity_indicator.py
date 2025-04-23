from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QPoint, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient
import math

# Import theme colors
from anpe_gui.theme import PRIMARY_COLOR, SUCCESS_COLOR

class PulsingActivityIndicator(QWidget):
    """
    An activity indicator displaying:
    - Active State: Strictly sequential, blue solid ripples expanding outwards.
    - Idle State: A green glowing circle with a subtle breathing effect.
    Provides smooth transitions between states.
    Uses theme colors and non-linear easing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Configure widget appearance
        self.setMinimumSize(24, 24)
        self.setMaximumHeight(24)

        # Animation properties
        self.ripple_duration_steps = 225 # Controls ripple speed (Faster: was 250)
        self.ripples = [] # List to store ripple progress (0.0 to 1.0)
        
        # State and Transition
        self.target_state = 'idle' # Can be 'idle' or 'active'
        self.transition_alpha = 0.0 # 0.0 = fully idle, 1.0 = fully active
        self.transition_step = 0.05 # Speed of fade between states

        # Colors
        self.base_color = QColor(PRIMARY_COLOR)     # Blue for active ripple
        self.idle_color = QColor(SUCCESS_COLOR)     # Green for idle glow
        
        # Idle State Animation
        self.idle_breath_phase = 0.0
        self.idle_breath_speed = 0.02 # Speed of breathing effect (Slower: was 0.04)

        # Set up timer for animation (runs continuously when visible)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.setInterval(15) # Smooth interval (adjust if needed)

    def start(self):
        """Transition to the active (blue ripple) state."""
        self.target_state = 'active'
        if not self.timer.isActive():
            self.timer.start()
        # Ripple launch is handled in update_animation based on transition_alpha

    def stop(self):
        """Transition to the idle (green glow) state."""
        self.target_state = 'idle'
        if not self.timer.isActive(): # Ensure timer runs for idle breathing
            self.timer.start()

    def set_color(self, color):
        """Set the base color for the active ripple."""
        # Note: Idle color is fixed to SUCCESS_COLOR for status indication
        self.base_color = QColor(color)
        self.update()

    def update_animation(self):
        """Update transition, ripple progress, and idle breathing."""

        # Update transition alpha
        if self.target_state == 'active' and self.transition_alpha < 1.0:
            self.transition_alpha = min(1.0, self.transition_alpha + self.transition_step)
        elif self.target_state == 'idle' and self.transition_alpha > 0.0:
            self.transition_alpha = max(0.0, self.transition_alpha - self.transition_step)

        # Update idle breathing phase
        self.idle_breath_phase = (self.idle_breath_phase + self.idle_breath_speed) % (2 * math.pi)

        # Update ripple progress
        progress_step = 1.0 / self.ripple_duration_steps
        new_ripples = []
        for progress in self.ripples:
            new_progress = progress + progress_step
            if new_progress < 1.0:
                new_ripples.append(new_progress)
        self.ripples = new_ripples

        # Launch new ripple only if fully active and no ripple exists
        if self.target_state == 'active' and self.transition_alpha >= 1.0 and not self.ripples:
            self.ripples.append(0.0)

        # Trigger repaint
        self.update()
        
        # Optional: Stop timer if fully idle and nothing is happening? Maybe not needed.
        # if self.target_state == 'idle' and self.transition_alpha == 0.0 and not self.ripples:
        #     self.timer.stop() # Or just let it run for breathing?

    def paintEvent(self, event):
        """Paint the idle glow and active ripple, blending based on transition_alpha."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # Get widget dimensions
        width = self.width()
        height = self.height()
        center = QPoint(width // 2, height // 2)
        center_f = QPointF(center)

        # --- Calculate Idle Glow Properties --- 
        min_widget_dim_idle = min(width, height)
        glow_max_radius = min_widget_dim_idle * 0.35 # Base size for idle glow (Smaller: was 0.40)
        breath_factor = (1.0 + math.sin(self.idle_breath_phase)) / 2.0 # 0.0 to 1.0
        # Modify radius and alpha based on breath
        current_glow_radius = glow_max_radius * (0.90 + 0.10 * breath_factor) # Pulse size (Even more subtle: was 0.85 + 0.15)
        base_glow_alpha = 180 + 40 * breath_factor # Pulse alpha (More subtle: was 160 + 60)
        # Apply transition fade
        final_glow_alpha = base_glow_alpha * (1.0 - self.transition_alpha)

        # --- Calculate Active Ripple Properties (if ripple exists) --- 
        final_ripple_alpha = 0.0
        current_ripple_radius = 0.0
        if self.ripples:
            progress = self.ripples[0]
            min_widget_dim_ripple = min(width, height)
            ripple_max_radius = min_widget_dim_ripple * 0.70 # Ripple expands larger
            ripple_min_radius = ripple_max_radius * 0.10
            # Easing
            t = progress
            eased_progress = t * t * (3.0 - 2.0 * t)
            current_ripple_radius = ripple_min_radius + (ripple_max_radius - ripple_min_radius) * eased_progress
            # Base alpha fade
            base_ripple_alpha = int(180 * (1.0 - progress))
            base_ripple_alpha = max(0, min(255, base_ripple_alpha))
            # Apply transition fade
            final_ripple_alpha = base_ripple_alpha * self.transition_alpha

        # --- Draw Idle Glow --- 
        if final_glow_alpha > 5 and current_glow_radius > 0.5:
            glow_gradient = QRadialGradient(center_f, current_glow_radius)
            glow_center_color = QColor(self.idle_color)
            glow_center_color.setAlpha(int(final_glow_alpha))
            glow_gradient.setColorAt(0.0, glow_center_color)
            glow_edge_color = QColor(self.idle_color)
            glow_edge_color.setAlpha(0)
            glow_gradient.setColorAt(1.0, glow_edge_color)
            painter.setBrush(QBrush(glow_gradient))
            int_glow_radius = int(current_glow_radius)
            painter.drawEllipse(center.x() - int_glow_radius, center.y() - int_glow_radius, int_glow_radius * 2, int_glow_radius * 2)

        # --- Draw Active Center Dot (Added) ---
        # Draw this dot only when transitioning to or in the active state
        center_dot_max_alpha = 100 # Reduced base alpha (was 150)
        center_dot_alpha = center_dot_max_alpha * self.transition_alpha # Fade in/out with transition
        if center_dot_alpha > 5:
            min_widget_dim_center = min(width, height)
            center_dot_radius = min_widget_dim_center * 0.12 # Small, fixed size relative to widget
            
            # Create gradient instead of solid color
            center_dot_gradient = QRadialGradient(center_f, center_dot_radius)
            gradient_center_color = QColor(self.base_color)
            gradient_center_color.setAlpha(int(center_dot_alpha)) # Apply transition alpha
            center_dot_gradient.setColorAt(0.0, gradient_center_color)
            gradient_edge_color = QColor(self.base_color)
            gradient_edge_color.setAlpha(0) # Fully transparent edge
            center_dot_gradient.setColorAt(1.0, gradient_edge_color)
            
            painter.setBrush(QBrush(center_dot_gradient)) # Use gradient brush
            
            int_center_dot_radius = int(center_dot_radius)
            if int_center_dot_radius > 0:
                painter.drawEllipse(center.x() - int_center_dot_radius, center.y() - int_center_dot_radius, int_center_dot_radius * 2, int_center_dot_radius * 2)

        # --- Draw Active Ripple --- 
        # Now draw the ripple *after* the center dot
        if final_ripple_alpha > 5 and current_ripple_radius > 0.5:
            ripple_gradient = QRadialGradient(center_f, current_ripple_radius)
            ripple_center_color = QColor(self.base_color)
            ripple_center_color.setAlpha(int(final_ripple_alpha))
            ripple_gradient.setColorAt(0.0, ripple_center_color)
            ripple_edge_color = QColor(self.base_color)
            ripple_edge_color.setAlpha(0)
            ripple_gradient.setColorAt(1.0, ripple_edge_color)
            painter.setBrush(QBrush(ripple_gradient))
            int_ripple_radius = int(current_ripple_radius)
            painter.drawEllipse(center.x() - int_ripple_radius, center.y() - int_ripple_radius, int_ripple_radius * 2, int_ripple_radius * 2)