import sys
import psutil
import time
from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QLabel,
                             QWidget)
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QIcon, QPixmap, QPen, QBrush
import threading
import winreg
import os


class NetworkUpdater(QObject):
    speed_updated = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()
        self.prev_bytes = psutil.net_io_counters().bytes_recv
        self.prev_sent = psutil.net_io_counters().bytes_sent
        self.is_running = True
    
    def get_speed(self, prev, curr, interval):
        return (curr - prev) / interval
    
    def update_speeds(self):
        while self.is_running:
            try:
                counters = psutil.net_io_counters()
                curr_recv = counters.bytes_recv
                curr_sent = counters.bytes_sent
                
                down_speed = self.get_speed(self.prev_bytes, curr_recv, 1) / 1024  # KB/s
                up_speed = self.get_speed(self.prev_sent, curr_sent, 1) / 1024  # KB/s
                
                self.prev_bytes = curr_recv
                self.prev_sent = curr_sent
                
                self.prev_bytes = curr_recv
                self.prev_sent = curr_sent
                
                self.speed_updated.emit(down_speed, up_speed)
            except:
                pass
            time.sleep(1)


class DetailedStatsWindow(QDialog):
    """Detailed network stats window"""
    def __init__(self, down_speed, up_speed):
        super().__init__()
        self.down_speed = down_speed
        self.up_speed = up_speed
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Network Speed Monitor - Details")
        self.setGeometry(100, 100, 400, 300)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(30, 30, 40), stop:1 rgb(20, 20, 30));
            }
            QLabel {
                color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Network Speed Monitor")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Download section
        down_label = QLabel("Download Speed")
        down_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Normal))
        down_label.setStyleSheet("color: #B0B0B0;")
        layout.addWidget(down_label)
        
        down_speed_label = QLabel(f"{self.down_speed:.2f} KB/s")
        down_speed_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        down_speed_label.setStyleSheet("color: #00D9FF;")
        layout.addWidget(down_speed_label)
        
        # Upload section
        up_label = QLabel("Upload Speed")
        up_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Normal))
        up_label.setStyleSheet("color: #B0B0B0;")
        layout.addWidget(up_label)
        
        up_speed_label = QLabel(f"{self.up_speed:.2f} KB/s")
        up_speed_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        up_speed_label.setStyleSheet("color: #FF006E;")
        layout.addWidget(up_speed_label)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Store labels for updating
        self.down_speed_label = down_speed_label
        self.up_speed_label = up_speed_label
    
    def update_stats(self, down_speed, up_speed):
        """Update the stats labels"""
        self.down_speed_label.setText(f"{down_speed:.2f} KB/s")
        self.up_speed_label.setText(f"{up_speed:.2f} KB/s")


class TaskbarOverlay(QWidget):
    """Minimalist taskbar overlay mimicking NetSpeedMonitor"""
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.snap_to_position()
        self.old_pos = None
        
        # Auto-snap on screen change
        self.screen = QApplication.primaryScreen()
        if self.screen:
            self.screen.geometryChanged.connect(self.snap_to_position)
            self.screen.availableGeometryChanged.connect(self.snap_to_position)
            
        # Backup timer to ensure positioning (every 5s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.snap_to_position)
        self.timer.start(5000)
        
    def setup_ui(self):
        # Window flags for floating behavior + tool window (no taskbar icon)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Compact size for taskbar
        self.setFixedSize(120, 40)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)
        
        # Font setup
        font = QFont("Segoe UI", 9)
        font.setBold(False)
        
        # Row 1: Download
        self.down_label = QLabel("↓ 0.0 Mbps")
        self.down_label.setFont(font)
        self.down_label.setStyleSheet("color: white;")
        self.down_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Row 2: Upload
        self.up_label = QLabel("↑ 0.0 Mbps")
        self.up_label.setFont(font)
        self.up_label.setStyleSheet("color: white;")
        self.up_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.down_label)
        layout.addWidget(self.up_label)
        self.setLayout(layout)
        
    def snap_to_position(self):
        """Snap to the taskbar area (bottom right usually)"""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            avail = screen.availableGeometry()
            
            # Default to bottom right
            # x = Width - Widget Width - Offset (space for tray icons)
            x = geo.width() - self.width() - 250
            
            # Check where taskbar is
            # If available height < full height, taskbar is taking up space
            if avail.height() < geo.height():
                # If available y > 0, taskbar is at TOP
                if avail.y() > 0:
                    y = 0
                else:
                    # Taskbar is at BOTTOM (most common)
                    # Place at very bottom of screen
                    y = geo.height() - self.height()
            else:
                # Taskbar might be auto-hidden or on side
                y = geo.height() - self.height()
                
            self.move(x, y)
            
    def update_stats(self, down, up):
        # Format speeds (Mbps for consistency with reference image, or KB/s if preferred)
        # Reference image showed "Mbps", but let's stick to dynamic units for accuracy
        
        def format_speed(speed_kb):
            # speed_kb is in KB/s
            if speed_kb >= 1024:
                return f"{speed_kb/1024:.1f} MB/s"
            else:
                return f"{speed_kb:.1f} KB/s"
            
        self.down_label.setText(f"↓ {format_speed(down)}")
        self.up_label.setText(f"↑ {format_speed(up)}")
        
        # Force window to top (Z-order fix)
        self.raise_()

    # Draggable logic (in case user wants to fine-tune position)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


class NetworkMonitorTray:
    """System tray network monitor - appears alongside WiFi, Bluetooth, Battery"""
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.details_window = None
        self.overlay = None
        
        # Create tray icon
        self.setup_tray()
        
        # Start monitoring
        self.start_monitoring()
    
    def create_speed_text_icon(self, down_speed, up_speed):
        """Create a compact square icon for tray"""
        # Standard tray icon size is usually small, but we draw larger for high DPI
        size = 64
        icon_pixmap = QPixmap(size, size)
        
        # Transparent background
        icon_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(icon_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Format display text (short format)
        def format_speed(speed):
            if speed >= 1024:
                return f"{speed/1024:.1f}M"
            else:
                return f"{speed:.0f}K"
        
        down_text = format_speed(down_speed)
        up_text = format_speed(up_speed)
        
        # Draw background for better visibility (semi-transparent black)
        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 10, 10)
        
        # Font setup
        font = QFont("Segoe UI", 26, QFont.Weight.Bold)
        painter.setFont(font)
        
        # Draw Download Speed (Top, Cyan)
        painter.setPen(QColor("#00D9FF"))
        painter.drawText(0, 5, size, size//2, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, down_text)
        
        # Draw Upload Speed (Bottom, Pink)
        painter.setPen(QColor("#FF006E"))
        painter.drawText(0, size//2 - 5, size, size//2, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, up_text)
        
        # Draw separator line
        painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
        painter.drawLine(10, size//2, size-10, size//2)
        
        painter.end()
        return QIcon(icon_pixmap)
    
    def setup_tray(self):
        """Setup system tray icon (like WiFi, Battery, Bluetooth)"""
        self.tray_icon = QSystemTrayIcon()
        
        # Set initial icon before showing
        initial_icon = self.create_speed_text_icon(0, 0)
        self.tray_icon.setIcon(initial_icon)
        
        # Create menu
        menu = QMenu()
        
        # Status display (disabled, just shows speeds)
        self.status_action = menu.addAction("Network Monitor")
        self.status_action.setEnabled(False)
        
        menu.addSeparator()
        
        # Show detailed stats
        show_details = menu.addAction("Show Details")
        show_details.triggered.connect(self.show_details)
        
        # Toggle Overlay
        self.toggle_overlay_action = menu.addAction("Hide Overlay")
        self.toggle_overlay_action.triggered.connect(self.toggle_overlay)
        
        menu.addSeparator()
        
        # Run on Startup
        self.startup_action = menu.addAction("Run on Startup")
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(self.is_startup_enabled())
        self.startup_action.triggered.connect(self.toggle_startup)
        
        menu.addSeparator()
        
        # Exit
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.exit_app)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()
    
    def show_details(self):
        """Show detailed stats in a window"""
        if self.details_window is None:
            self.details_window = DetailedStatsWindow(self.download_speed, self.upload_speed)
        
        self.details_window.show()
        self.details_window.raise_()
        self.details_window.activateWindow()
    
    def start_monitoring(self):
        """Start network speed monitoring"""
        self.updater = NetworkUpdater()
        self.updater.speed_updated.connect(self.on_speed_update)
        
        # Start in background thread
        self.monitor_thread = threading.Thread(target=self.updater.update_speeds, daemon=True)
        self.monitor_thread.start()
        
        # Show overlay by default
        self.overlay = TaskbarOverlay()
        self.overlay.show()
        
    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.toggle_overlay_action.setText("Show Overlay")
        else:
            self.overlay.show()
            self.toggle_overlay_action.setText("Hide Overlay")
            self.overlay.snap_to_position()
            
    def is_startup_enabled(self):
        """Check if app is in startup registry"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "NetworkSpeedMonitor")
            winreg.CloseKey(key)
            return True
        except WindowsError:
            return False
            
    def toggle_startup(self):
        """Toggle run on startup"""
        app_path = os.path.abspath(sys.argv[0])
        # If running as python script, use python executable
        if not app_path.endswith('.exe'):
            # This is a bit tricky for scripts, but for the EXE it will work perfectly.
            # For script dev mode:
            app_path = f'"{sys.executable}" "{app_path}"'
        else:
            app_path = f'"{app_path}"'
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            if self.startup_action.isChecked():
                winreg.SetValueEx(key, "NetworkSpeedMonitor", 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, "NetworkSpeedMonitor")
                except WindowsError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Error setting startup: {e}")
            # Revert check state if failed
            self.startup_action.setChecked(not self.startup_action.isChecked())
    
    def on_speed_update(self, down_speed, up_speed):
        """Update tray icon and tooltip with new speeds"""
        self.download_speed = down_speed
        self.upload_speed = up_speed
        
        # Update overlay
        if self.overlay and self.overlay.isVisible():
            self.overlay.update_stats(down_speed, up_speed)
        
        # Format speeds nicely
        if down_speed >= 1024:
            down_str = f"{down_speed/1024:.2f} MB/s"
        else:
            down_str = f"{down_speed:.1f} KB/s"
        
        if up_speed >= 1024:
            up_str = f"{up_speed/1024:.2f} MB/s"
        else:
            up_str = f"{up_speed:.1f} KB/s"
        
        # Update tooltip (shows on hover)
        tooltip = f"Network Monitor\n📥 Download: {down_str}\n📤 Upload: {up_str}"
        self.tray_icon.setToolTip(tooltip)
        
        # Update menu text (shows in tray menu)
        self.status_action.setText(f"⬇️ {down_str}  |  ⬆️ {up_str}")
        
        # Update icon with custom design
        self.tray_icon.setIcon(self.create_speed_text_icon(down_speed, up_speed))
        
        # Update details window if open
        if self.details_window and self.details_window.isVisible():
            self.details_window.update_stats(down_speed, up_speed)
    
    def exit_app(self):
        """Clean exit"""
        self.updater.is_running = False
        self.tray_icon.hide()
        self.app.quit()
    
    def run(self):
        """Run the application"""
        return self.app.exec()


def main():
    monitor = NetworkMonitorTray()
    sys.exit(monitor.run())


if __name__ == '__main__':
    main()
