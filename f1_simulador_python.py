import math
import os
import sys
import time

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from f1_core import TEAMS, TIRES, TRACKS, WEATHER, build_geo, fmt_sec, point_at, refresh_real_track, simulate, state_at, track_layout
from f1_data import (
    available_reference_sessions,
    available_reference_tracks,
    available_reference_years,
    available_sessions_for_year,
    load_reference_profile,
)


PALETTE = {
    "bg": "#08111f",
    "shell": "#0e192a",
    "card": "#13253d",
    "panel": "#193150",
    "line": "#294769",
    "ink": "#f4f7ff",
    "muted": "#8ea7c8",
    "accent": "#ff6a3d",
    "cyan": "#29d5cb",
    "green": "#45d17c",
    "track": "#091423",
    "asphalt": "#7f8ea8",
    "runoff": "#13304d",
    "grass": "#0d2a23",
}

TEAM_LIVERIES = {
    "Ferrari": dict(body="#d61f2c", accent="#f7f1d1", dark="#7d0d14"),
    "McLaren": dict(body="#ff7a1a", accent="#8ce6ff", dark="#8e3f00"),
    "Mercedes": dict(body="#12c6b2", accent="#eefaff", dark="#0f5f57"),
    "Red Bull Racing": dict(body="#1d2f6f", accent="#f2bf27", dark="#101b45"),
    "Aston Martin": dict(body="#0d6a57", accent="#d4fff3", dark="#083c32"),
    "Williams": dict(body="#1a4cff", accent="#d9e6ff", dark="#0e2a8f"),
    "Alpine": dict(body="#ff5ecf", accent="#a0ebff", dark="#7f2a6c"),
    "Haas F1 Team": dict(body="#d7dce4", accent="#ff4d4d", dark="#737983"),
    "Racing Bulls": dict(body="#e9f1ff", accent="#3c78ff", dark="#8e99aa"),
    "Audi": dict(body="#bf2026", accent="#e4e4e4", dark="#5e0f14"),
    "Cadillac": dict(body="#1e5cff", accent="#ffffff", dark="#12316f"),
}

PILOT_PROFILES = {
    "Custom": None,
    "Max Verstappen": dict(team="Red Bull Racing", skill=0.98, aggression=0.84, consistency=0.95, tire="C4 Soft"),
    "Isack Hadjar": dict(team="Red Bull Racing", skill=0.88, aggression=0.78, consistency=0.84, tire="C4 Soft"),
    "Lando Norris": dict(team="McLaren", skill=0.95, aggression=0.80, consistency=0.92, tire="C4 Soft"),
    "Oscar Piastri": dict(team="McLaren", skill=0.94, aggression=0.79, consistency=0.91, tire="C4 Soft"),
    "Charles Leclerc": dict(team="Ferrari", skill=0.96, aggression=0.82, consistency=0.91, tire="C5 Soft"),
    "Lewis Hamilton": dict(team="Ferrari", skill=0.95, aggression=0.76, consistency=0.93, tire="C4 Soft"),
    "George Russell": dict(team="Mercedes", skill=0.93, aggression=0.77, consistency=0.90, tire="C4 Soft"),
    "Kimi Antonelli": dict(team="Mercedes", skill=0.88, aggression=0.75, consistency=0.84, tire="C4 Soft"),
    "Fernando Alonso": dict(team="Aston Martin", skill=0.94, aggression=0.74, consistency=0.92, tire="C4 Soft"),
    "Lance Stroll": dict(team="Aston Martin", skill=0.84, aggression=0.70, consistency=0.80, tire="C3 Medium"),
    "Alex Albon": dict(team="Williams", skill=0.90, aggression=0.76, consistency=0.87, tire="C4 Soft"),
    "Carlos Sainz": dict(team="Williams", skill=0.92, aggression=0.74, consistency=0.90, tire="C4 Soft"),
    "Pierre Gasly": dict(team="Alpine", skill=0.89, aggression=0.74, consistency=0.86, tire="C4 Soft"),
    "Franco Colapinto": dict(team="Alpine", skill=0.86, aggression=0.77, consistency=0.80, tire="C4 Soft"),
    "Esteban Ocon": dict(team="Haas F1 Team", skill=0.88, aggression=0.72, consistency=0.86, tire="C3 Medium"),
    "Oliver Bearman": dict(team="Haas F1 Team", skill=0.83, aggression=0.77, consistency=0.79, tire="C4 Soft"),
    "Liam Lawson": dict(team="Racing Bulls", skill=0.84, aggression=0.78, consistency=0.80, tire="C4 Soft"),
    "Arvid Lindblad": dict(team="Racing Bulls", skill=0.81, aggression=0.81, consistency=0.76, tire="C4 Soft"),
    "Nico Hulkenberg": dict(team="Audi", skill=0.88, aggression=0.68, consistency=0.87, tire="C3 Medium"),
    "Gabriel Bortoleto": dict(team="Audi", skill=0.82, aggression=0.74, consistency=0.78, tire="C4 Soft"),
    "Valtteri Bottas": dict(team="Cadillac", skill=0.89, aggression=0.66, consistency=0.88, tire="C3 Medium"),
    "Sergio Perez": dict(team="Cadillac", skill=0.90, aggression=0.71, consistency=0.87, tire="C3 Medium"),
}


def app_stylesheet():
    return f"""
    QWidget {{
        background: {PALETTE['bg']};
        color: {PALETTE['ink']};
        font-family: 'Segoe UI';
        font-size: 10pt;
    }}
    QMainWindow {{
        background: {PALETTE['bg']};
    }}
    QFrame#shell {{
        background: {PALETTE['shell']};
        border: 1px solid {PALETTE['line']};
        border-radius: 18px;
    }}
    QFrame#card, QFrame#kpi {{
        background: {PALETTE['card']};
        border: 1px solid {PALETTE['line']};
        border-radius: 16px;
    }}
    QFrame#kpi {{
        background: #10243b;
    }}
    QFrame#sidebar {{
        background: {PALETTE['shell']};
        border: none;
    }}
    QLabel#title {{
        font-family: 'Bahnschrift SemiBold';
        font-size: 24pt;
        font-weight: 700;
    }}
    QLabel#subtitle, QLabel#muted, QLabel#fieldLabel {{
        color: {PALETTE['muted']};
    }}
    QLabel#section {{
        color: {PALETTE['cyan']};
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#kpiTitle {{
        color: {PALETTE['muted']};
        font-size: 9pt;
        font-weight: 600;
    }}
    QLabel#kpiValue {{
        font-family: 'Bahnschrift SemiBold';
        font-size: 18pt;
        font-weight: 700;
    }}
    QLineEdit, QComboBox {{
        background: {PALETTE['panel']};
        border: 1px solid {PALETTE['line']};
        border-radius: 10px;
        padding: 8px 10px;
        min-height: 18px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QPushButton {{
        border-radius: 11px;
        padding: 10px 14px;
        border: 1px solid {PALETTE['line']};
        background: {PALETTE['panel']};
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: #24405f;
    }}
    QPushButton#accent {{
        background: {PALETTE['accent']};
        border-color: {PALETTE['accent']};
        color: white;
    }}
    QPushButton#accent:hover {{
        background: #ff7e58;
    }}
    QTabWidget::pane {{
        border: none;
    }}
    QTabBar::tab {{
        background: {PALETTE['shell']};
        color: {PALETTE['muted']};
        border: 1px solid {PALETTE['line']};
        padding: 10px 16px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        margin-right: 4px;
    }}
    QTabBar::tab:selected {{
        background: {PALETTE['card']};
        color: {PALETTE['ink']};
    }}
    QTableWidget {{
        background: {PALETTE['card']};
        border: 1px solid {PALETTE['line']};
        border-radius: 12px;
        gridline-color: {PALETTE['line']};
        selection-background-color: #294565;
    }}
    QHeaderView::section {{
        background: {PALETTE['panel']};
        color: {PALETTE['ink']};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {PALETTE['line']};
        font-weight: 700;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QProgressBar {{
        background: {PALETTE['panel']};
        border: 1px solid {PALETTE['line']};
        border-radius: 6px;
    }}
    QProgressBar::chunk {{
        background: {PALETTE['accent']};
        border-radius: 6px;
    }}
    """


class Field(QWidget):
    def __init__(self, label, widget):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        lbl = QLabel(label.upper())
        lbl.setObjectName("fieldLabel")
        layout.addWidget(lbl)
        layout.addWidget(widget)


class KpiCard(QFrame):
    def __init__(self, title, accent):
        super().__init__()
        self.setObjectName("kpi")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{accent}; border:none; border-radius:2px;")
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("kpiTitle")
        self.value = QLabel("-")
        self.value.setObjectName("kpiValue")
        layout.addWidget(bar)
        layout.addWidget(title_lbl)
        layout.addWidget(self.value)


class Card(QFrame):
    def __init__(self, title=None):
        super().__init__()
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(10)
        if title:
            lbl = QLabel(title.upper())
            lbl.setObjectName("section")
            self.layout.addWidget(lbl)


class CompactCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)


class TrackWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.geo = None
        self.state_a = None
        self.state_b = None
        self.team_a = "Ferrari"
        self.team_b = "McLaren"

    def set_scene(self, geo, state_a=None, state_b=None, team_a=None, team_b=None):
        self.geo = geo
        self.state_a = state_a
        self.state_b = state_b
        if team_a:
            self.team_a = team_a
        if team_b:
            self.team_b = team_b
        self.update()

    def _draw_track_surface(self, painter, path):
        painter.setPen(QPen(QColor(PALETTE["grass"]), 44, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(PALETTE["runoff"]), 34, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#39455c"), 24, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(PALETTE["asphalt"]), 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(255, 255, 255, 45), 2, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

    def _draw_trail(self, painter, state, color):
        if not state:
            return
        base = state["pRace"]
        for idx in range(7, 0, -1):
            fade = idx / 7.0
            pos = point_at(self.geo, max(0.0, base - idx * 0.004))
            painter.setPen(Qt.NoPen)
            c = QColor(color)
            c.setAlpha(int(18 + fade * 42))
            painter.setBrush(c)
            r = max(2, int(2 + fade * 2))
            painter.drawEllipse(int(pos["x"] - r), int(pos["y"] - r), r * 2, r * 2)

    def _draw_f1_car(self, painter, x, y, ang, team_name, label):
        livery = TEAM_LIVERIES.get(team_name, dict(body=PALETTE["accent"], accent="#ffffff", dark="#7a2b14"))
        painter.save()
        painter.translate(x, y)
        painter.rotate(math.degrees(ang))
        body = QColor(livery["body"])
        accent = QColor(livery["accent"])
        dark = QColor(livery["dark"])

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 24, 32, 230))
        for wx, wy in [(-9, -7), (-9, 7), (8, -7), (8, 7)]:
            painter.drawRoundedRect(wx - 2, wy - 3, 4, 6, 1.2, 1.2)

        painter.setBrush(dark)
        painter.drawRect(-12, -9, 2, 18)
        painter.drawRect(8, -10, 3, 20)

        painter.setBrush(body)
        painter.drawRoundedRect(-9, -4, 18, 8, 3.2, 3.2)
        painter.drawRoundedRect(-2, -3, 11, 6, 2.6, 2.6)
        painter.drawRoundedRect(-13, -2.2, 5, 4.4, 1.6, 1.6)

        painter.setBrush(accent)
        painter.drawRect(9, -9, 2, 18)
        painter.drawRect(-14, -11, 2, 22)
        painter.drawRect(-15, -7, 2, 14)
        painter.drawRect(-12, -11, 1, 22)
        painter.drawRect(0, -1, 7, 2)

        painter.setBrush(QColor("#13161d"))
        painter.drawRoundedRect(-3, -2, 5, 4, 1.6, 1.6)
        painter.drawRect(1, -0.8, 3, 1.6)

        painter.setPen(QPen(QColor(PALETTE["ink"]), 1.2))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(-6, -12, 12, 8, Qt.AlignCenter, label)
        painter.restore()

    def _draw_hud(self, painter):
        hud_rect = self.rect().adjusted(14, 12, -14, -12)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(8, 13, 22, 180))
        painter.drawRoundedRect(hud_rect.left(), hud_rect.top(), 184, 52, 10, 10)
        painter.setPen(QColor(PALETTE["muted"]))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(hud_rect.left() + 12, hud_rect.top() + 18, "LIVE TRACK MAP")
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(PALETTE["ink"]))
        painter.drawText(hud_rect.left() + 12, hud_rect.top() + 36, f"A  {self.team_a}")
        painter.drawText(hud_rect.left() + 12, hud_rect.top() + 50, f"B  {self.team_b}")
        painter.setBrush(QColor(PALETTE["accent"]))
        painter.drawRoundedRect(hud_rect.left() + 154, hud_rect.top() + 26, 12, 5, 2, 2)
        painter.setBrush(QColor(PALETTE["cyan"]))
        painter.drawRoundedRect(hud_rect.left() + 154, hud_rect.top() + 40, 12, 5, 2, 2)

    def _draw_driver_panel(self, painter, side, label, team_name, state, color_hex):
        x = 14 if side == "left" else self.width() - 210
        y = self.height() - 92
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(8, 13, 22, 196))
        painter.drawRoundedRect(x, y, 196, 78, 12, 12)
        painter.setBrush(QColor(color_hex))
        painter.drawRoundedRect(x + 10, y + 10, 10, 10, 3, 3)
        painter.setPen(QColor(PALETTE["ink"]))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(x + 28, y + 20, f"{label}  {team_name}")
        if not state:
            return
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(PALETTE["muted"]))
        painter.drawText(x + 12, y + 40, f"Lap {state['lap']}")
        painter.drawText(x + 72, y + 40, f"{state['speed']:.0f} km/h")
        painter.drawText(x + 12, y + 58, f"Tire {state.get('tire', '-')}")
        painter.drawText(x + 12, y + 74, "PIT" if state.get("pit") else "Track")

    def _draw_delta_bar(self, painter):
        if not (self.state_a and self.state_b):
            return
        left = 230
        right = self.width() - 230
        mid = (left + right) / 2
        y = 28
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(8, 13, 22, 180))
        painter.drawRoundedRect(left, y - 10, right - left, 26, 10, 10)
        painter.setBrush(QColor("#2a3e5d"))
        painter.drawRoundedRect(left + 10, y, right - left - 20, 6, 3, 3)
        delta = max(-1.0, min(1.0, self.state_a["pRace"] - self.state_b["pRace"]))
        if delta >= 0:
            painter.setBrush(QColor(PALETTE["accent"]))
            painter.drawRoundedRect(int(mid), y, int((right - left - 20) * abs(delta) * 0.5), 6, 3, 3)
        else:
            painter.setBrush(QColor(PALETTE["cyan"]))
            painter.drawRoundedRect(int(mid - (right - left - 20) * abs(delta) * 0.5), y, int((right - left - 20) * abs(delta) * 0.5), 6, 3, 3)
        painter.setPen(QColor(PALETTE["ink"]))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        leader = "AHEAD A" if delta >= 0 else "AHEAD B"
        painter.drawText(left + 14, y + 18, leader)
        painter.drawText(int(mid - 22), y + 18, f"{abs(delta) * 100:.1f}%")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor("#0c1b30"))
        grad.setColorAt(1, QColor(PALETTE["track"]))
        painter.fillRect(self.rect(), grad)
        if not self.geo:
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "Carga una referencia local y ejecuta la vuelta rapida")
            return
        pts = self.geo["points"]
        if len(pts) < 2 or any((not math.isfinite(p["x"]) or not math.isfinite(p["y"])) for p in pts[: min(len(pts), 200)]):
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "No se pudo dibujar la geometria real del circuito")
            return
        path = QPainterPath()
        path.moveTo(pts[0]["x"], pts[0]["y"])
        for p in pts[1:]:
            path.lineTo(p["x"], p["y"])
        self._draw_track_surface(painter, path)

        start = point_at(self.geo, 0.02)
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawLine(start["x"] - 8, start["y"] - 8, start["x"] + 8, start["y"] + 8)
        painter.drawLine(start["x"] - 8, start["y"] + 8, start["x"] + 8, start["y"] - 8)
        painter.setPen(QPen(QColor("#e12d39"), 2, Qt.DashLine))
        painter.drawLine(start["x"] - 16, start["y"], start["x"] + 16, start["y"])

        self._draw_trail(painter, self.state_a, QColor(PALETTE["accent"]))
        self._draw_trail(painter, self.state_b, QColor(PALETTE["cyan"]))

        for state, team_name, label in ((self.state_a, self.team_a, "A"), (self.state_b, self.team_b, "B")):
            if not state:
                continue
            pos = point_at(self.geo, state["pRace"])
            lane = 7 if label == "A" else -7
            x = pos["x"] - math.sin(pos["ang"]) * lane
            y = pos["y"] + math.cos(pos["ang"]) * lane
            self._draw_f1_car(painter, x, y, pos["ang"], team_name, label)
        self._draw_hud(painter)
        self._draw_driver_panel(painter, "left", "A", self.team_a, self.state_a, PALETTE["accent"])
        self._draw_driver_panel(painter, "right", "B", self.team_b, self.state_b, PALETTE["cyan"])
        self._draw_delta_bar(painter)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Strategy Lab - PySide6")
        self.resize(1560, 960)
        self.setMinimumSize(1040, 700)
        self.loaded_ref = None
        self.res_a = None
        self.res_b = None
        self.track_name = "Monza"
        self.geo = None
        self.vtime = 0.0
        self.vrun = True
        self.last_ts = None
        self.fields = {}
        self._build_ui()
        self.apply_track_defaults()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.frame_update)
        self.timer.start(16)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        title = QLabel("F1 Fast Lap Lab")
        title.setObjectName("title")
        self.title_label = title
        subtitle = QLabel("Comparador de vuelta rapida entre dos pilotos con autos, neumaticos, clima y eventos de riesgo.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        self.subtitle_label = subtitle
        root.addWidget(title)
        root.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)
        self.main_splitter = splitter

        sidebar_shell = QFrame()
        sidebar_shell.setObjectName("shell")
        self.sidebar_shell = sidebar_shell
        sidebar_shell.setMinimumWidth(300)
        sidebar_shell.setMaximumWidth(460)
        sidebar_layout = QVBoxLayout(sidebar_shell)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_content = QFrame()
        sidebar_content.setObjectName("sidebar")
        s = QVBoxLayout(sidebar_content)
        s.setContentsMargins(12, 12, 12, 12)
        s.setSpacing(12)
        sidebar_scroll.setWidget(sidebar_content)
        sidebar_layout.addWidget(sidebar_scroll)
        splitter.addWidget(sidebar_shell)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_scroll = right_scroll
        right = QWidget()
        right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([360, 1180])
        self.right_panel = right
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        s.addWidget(self._real_data_card())
        s.addWidget(self._car_card())
        s.addWidget(self._strategy_card())
        s.addWidget(self._actions_card())
        s.addStretch(1)

        self.kpi_host = QWidget()
        self.kpi_grid = QGridLayout(self.kpi_host)
        self.kpi_grid.setContentsMargins(0, 0, 0, 0)
        self.kpi_grid.setHorizontalSpacing(10)
        self.kpi_grid.setVerticalSpacing(10)
        self.kpis = {
            "ta": KpiCard("Tiempo total A", PALETTE["accent"]),
            "tb": KpiCard("Tiempo total B", PALETTE["cyan"]),
            "df": KpiCard("Diferencia", PALETTE["green"]),
            "ea": KpiCard("Penalizacion A", PALETTE["accent"]),
            "eb": KpiCard("Penalizacion B", PALETTE["cyan"]),
        }
        right_layout.addWidget(self.kpi_host)

        brief = Card("Fast Lap Brief")
        self.note = QLabel("Listo para simular una vuelta lanzada al limite.")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        brief.layout.addWidget(self.note)
        right_layout.addWidget(brief)

        tabs = QTabWidget()
        right_layout.addWidget(tabs, 1)

        sim_tab = QWidget()
        sim_layout = QVBoxLayout(sim_tab)
        sim_layout.setContentsMargins(0, 0, 0, 0)
        sim_layout.setSpacing(8)
        sim_card = CompactCard()
        sim_controls = QHBoxLayout()
        sim_controls.setContentsMargins(0, 0, 0, 0)
        sim_controls.setSpacing(8)
        self.play_btn = QPushButton("Pausar")
        self.play_btn.clicked.connect(self.toggle_play)
        self.reset_btn = QPushButton("Reiniciar")
        self.reset_btn.clicked.connect(self.restart_view)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["12", "20", "30", "45"])
        self.speed_combo.setCurrentText("20")
        sim_controls.addWidget(self.play_btn)
        sim_controls.addWidget(self.reset_btn)
        sim_controls.addStretch(1)
        sim_controls.addWidget(QLabel("Velocidad"))
        sim_controls.addWidget(self.speed_combo)
        sim_card.layout.addLayout(sim_controls)
        self.track_widget = TrackWidget()
        sim_card.layout.addWidget(self.track_widget)
        self.vmsg = QLabel("Listo para simular.")
        self.vmsg.setObjectName("muted")
        sim_card.layout.addWidget(self.vmsg)
        sim_layout.addWidget(sim_card, 1)
        tabs.addTab(sim_tab, "Simulacion")

        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(12)
        charts_card = Card("Graficos")
        self.figure = Figure(figsize=(10, 5), dpi=100, facecolor=PALETTE["card"])
        self.axes = [self.figure.add_subplot(221), self.figure.add_subplot(222), self.figure.add_subplot(223), self.figure.add_subplot(224)]
        self.canvas = FigureCanvasQTAgg(self.figure)
        charts_card.layout.addWidget(self.canvas)
        analysis_layout.addWidget(charts_card, 1)
        table_card = Card("Detalle De Intento")
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Piloto",
            "Tiempo",
            "Auto",
            "Neumatico",
            "Temp inicial",
            "Temp final",
            "Desgaste final",
            "Eventos",
            "Penalizacion",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_card.layout.addWidget(self.table)
        table_card.layout.addWidget(self._event_legend_widget())
        analysis_layout.addWidget(table_card, 1)
        tabs.addTab(analysis_tab, "Analisis")
        self.relayout_kpis()
        self.update_responsive_layout()

    def _event_legend_widget(self):
        legend = QFrame()
        legend.setObjectName("sidebar")
        root = QVBoxLayout(legend)
        root.setContentsMargins(0, 2, 0, 0)
        root.setSpacing(6)

        title = QLabel("Leyenda de eventos:")
        title.setObjectName("muted")
        root.addWidget(title)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        clean = QLabel("Limpia")
        clean.setStyleSheet(
            "color:#9ee6b8; background:#153327; border:1px solid #2a6b49; border-radius:10px; padding:4px 10px;"
        )
        row.addWidget(clean)

        caution = QLabel("Derrape / Drag")
        caution.setStyleSheet(
            "color:#ffd27a; background:#3a2b12; border:1px solid #7c5a22; border-radius:10px; padding:4px 10px;"
        )
        row.addWidget(caution)

        severe = QLabel("Choque")
        severe.setStyleSheet(
            "color:#ff7f7f; background:#3f1a1f; border:1px solid #7c2f3a; border-radius:10px; padding:4px 10px;"
        )
        row.addWidget(severe)

        row.addStretch(1)
        root.addLayout(row)
        return legend

    def _add_field(self, key, widget):
        self.fields[key] = widget
        return widget

    def _real_data_card(self):
        card = Card("Datos Reales")
        grid = QGridLayout()
        self.real_grid = grid
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        year = self._add_field("year", QComboBox())
        year.currentTextChanged.connect(self.on_reference_selection_changed)
        session = self._add_field("session", QComboBox())
        session.setEnabled(False)
        self.real_year_combo = year
        self.real_session_combo = session

        self.real_field_year = Field("Temporada", year)
        self.real_field_session = Field("Sesion referencia (auto)", session)
        grid.addWidget(self.real_field_year, 0, 0)

        self.real_status = QLabel("Modo fijo: vuelta rapida. Se usa automaticamente una sesion de referencia local para calibrar datos.")
        self.real_status.setObjectName("muted")
        self.real_status.setWordWrap(True)

        card.layout.addLayout(grid)
        card.layout.addWidget(self.real_status)
        return card

    def _car_card(self):
        card = Card("Condiciones De Vuelta")
        grid = QGridLayout()
        self.car_grid = grid
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        circuit = self._add_field("track", QComboBox())
        local_tracks = list(dict.fromkeys((available_reference_tracks() or []) + list(TRACKS.keys())))
        circuit.addItems(local_tracks)
        circuit.setCurrentText("Monza" if "Monza" in local_tracks else local_tracks[0])
        circuit.currentTextChanged.connect(self.on_track_selection_changed)
        weather = self._add_field("weather", QComboBox())
        weather.addItems(list(WEATHER.keys()))
        weather.setCurrentText("dry")
        integration = self._add_field("integrationMethod", QComboBox())
        integration.addItems(["Euler", "RK4"])
        integration.setCurrentText("RK4")
        laps = self._add_field("laps", QLineEdit("1"))
        laps.setEnabled(False)
        seed = self._add_field("seed", QLineEdit("42"))

        apply_track = QPushButton("Aplicar Circuito")
        apply_track.clicked.connect(self.apply_track_defaults)
        self.apply_track_btn = apply_track

        self.car_field_track = Field("Circuito", circuit)
        self.car_field_weather = Field("Clima", weather)
        self.car_field_integration = Field("Metodo Numerico", integration)
        self.car_field_laps = Field("Vueltas simuladas", laps)
        self.car_field_seed = Field("Seed (reproducibilidad)", seed)
        grid.addWidget(self.car_field_track, 0, 0)
        grid.addWidget(self.car_field_weather, 0, 1)
        grid.addWidget(self.car_field_integration, 1, 0)
        grid.addWidget(self.car_field_laps, 1, 1)
        grid.addWidget(self.car_field_seed, 2, 0, 1, 2)
        grid.addWidget(apply_track, 3, 0, 1, 2)

        card.layout.addLayout(grid)
        return card

    def _strategy_card(self):
        card = Card("Pilotos Y Configuracion")
        row = QBoxLayout(QBoxLayout.LeftToRight)
        row.setSpacing(10)
        self.strategy_row = row
        plan_a = Card("Piloto A")
        plan_b = Card("Piloto B")
        self.plan_a_card = plan_a
        self.plan_b_card = plan_b
        plan_a.setObjectName("card")
        plan_b.setObjectName("card")

        for key, label, default, values in [
            ("profileA", "Perfil F1", "Max Verstappen", list(PILOT_PROFILES.keys())),
            ("driverNameA", "Nombre piloto", "Piloto A", None),
            ("carA", "Auto", "Ferrari", list(TEAMS.keys())),
            ("tireA", "Neumatico", "C4 Soft", list(TIRES.keys())),
            ("tireTempA", "Temp inicial goma (C)", "97", None),
            ("tireWearA", "Desgaste inicial (%)", "4", None),
            ("skillA", "Habilidad (0-1)", "0.90", None),
            ("aggressionA", "Agresividad (0-1)", "0.72", None),
            ("consistencyA", "Consistencia (0-1)", "0.85", None),
        ]:
            widget = QComboBox() if values else QLineEdit(default)
            if values:
                widget.addItems(values)
                widget.setCurrentText(default)
            self._add_field(key, widget)
            field = Field(label, widget)
            plan_a.layout.addWidget(field)
            if key == "profileA":
                widget.currentTextChanged.connect(lambda _value, s="A": self.apply_driver_profile(s))

        for key, label, default, values in [
            ("profileB", "Perfil F1", "Lando Norris", list(PILOT_PROFILES.keys())),
            ("driverNameB", "Nombre piloto", "Piloto B", None),
            ("carB", "Auto", "McLaren", list(TEAMS.keys())),
            ("tireB", "Neumatico", "C5 Soft", list(TIRES.keys())),
            ("tireTempB", "Temp inicial goma (C)", "99", None),
            ("tireWearB", "Desgaste inicial (%)", "4", None),
            ("skillB", "Habilidad (0-1)", "0.88", None),
            ("aggressionB", "Agresividad (0-1)", "0.78", None),
            ("consistencyB", "Consistencia (0-1)", "0.83", None),
        ]:
            widget = QComboBox() if values else QLineEdit(default)
            if values:
                widget.addItems(values)
                widget.setCurrentText(default)
            self._add_field(key, widget)
            field = Field(label, widget)
            plan_b.layout.addWidget(field)
            if key == "profileB":
                widget.currentTextChanged.connect(lambda _value, s="B": self.apply_driver_profile(s))

        row.addWidget(plan_a, 1)
        row.addWidget(plan_b, 1)
        card.layout.addLayout(row)
        self.apply_driver_profile("A")
        self.apply_driver_profile("B")
        return card

    def _actions_card(self):
        shell = QFrame()
        shell.setObjectName("sidebar")
        layout = QBoxLayout(QBoxLayout.LeftToRight, shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.actions_layout = layout
        simulate_btn = QPushButton("Simular")
        simulate_btn.setObjectName("accent")
        simulate_btn.clicked.connect(self.run_simulation)
        self.simulate_btn = simulate_btn
        swap_btn = QPushButton("Intercambiar A/B")
        swap_btn.clicked.connect(self.swap_plans)
        self.swap_btn = swap_btn
        layout.addWidget(simulate_btn)
        layout.addWidget(swap_btn)
        return shell

    def relayout_kpis(self):
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(self.kpi_host)
        width = max(1, self.kpi_host.width() or self.width())
        columns = 5 if width >= 1500 else 3 if width >= 1100 else 2
        keys = ("ta", "tb", "df", "ea", "eb")
        for idx, key in enumerate(keys):
            row = idx // columns
            col = idx % columns
            self.kpi_grid.addWidget(self.kpis[key], row, col)
        for col in range(columns):
            self.kpi_grid.setColumnStretch(col, 1)

    def format_events(self, event_counts):
        mapping = [
            ("derrape", "Derrape"),
            ("drag", "Drag"),
            ("choque", "Choque"),
            ("frenada_temprana", "Frenada temprana"),
            ("neumatico_excesivamente_gastado", "Neumatico gastado"),
        ]
        chunks = []
        for key, label in mapping:
            count = int(event_counts.get(key, 0))
            if count > 0:
                chunks.append(f"{label} x{count}")
        return " | ".join(chunks) if chunks else "Limpia"

    def update_responsive_layout(self):
        width = self.width()
        compact = width < 1450
        dense = width < 1220
        sidebar_single_col = width < 1320

        title_font = QFont("Bahnschrift SemiBold", 18 if dense else 20 if compact else 24)
        self.title_label.setFont(title_font)
        self.subtitle_label.setMaximumWidth(900 if not compact else 620)

        if compact:
            self.sidebar_shell.setMaximumWidth(360 if not dense else 340)
            self.sidebar_shell.setMinimumWidth(320 if dense else 300)
            self.strategy_row.setDirection(QBoxLayout.TopToBottom)
            self.actions_layout.setDirection(QBoxLayout.TopToBottom if dense else QBoxLayout.LeftToRight)
        else:
            self.sidebar_shell.setMaximumWidth(460)
            self.sidebar_shell.setMinimumWidth(300)
            self.strategy_row.setDirection(QBoxLayout.LeftToRight)
            self.actions_layout.setDirection(QBoxLayout.LeftToRight)

        self.plan_a_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.plan_b_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        value_size = 14 if dense else 16 if compact else 18
        value_font = QFont("Bahnschrift SemiBold", value_size)
        for card in self.kpis.values():
            card.value.setFont(value_font)
        self.update_sidebar_grids(sidebar_single_col)
        self.relayout_kpis()

    def update_sidebar_grids(self, single_col):
        if single_col:
            self.real_grid.addWidget(self.real_field_year, 0, 0)
            self.real_grid.addWidget(self.real_field_session, 1, 0)

            self.car_grid.addWidget(self.car_field_track, 0, 0, 1, 2)
            self.car_grid.addWidget(self.car_field_weather, 1, 0, 1, 2)
            self.car_grid.addWidget(self.car_field_integration, 2, 0, 1, 2)
            self.car_grid.addWidget(self.car_field_laps, 3, 0, 1, 2)
            self.car_grid.addWidget(self.car_field_seed, 4, 0, 1, 2)
            self.car_grid.addWidget(self.apply_track_btn, 5, 0, 1, 2)
        else:
            self.real_grid.addWidget(self.real_field_year, 0, 0)
            self.real_grid.addWidget(self.real_field_session, 0, 1)

            self.car_grid.addWidget(self.car_field_track, 0, 0)
            self.car_grid.addWidget(self.car_field_weather, 0, 1)
            self.car_grid.addWidget(self.car_field_integration, 1, 0)
            self.car_grid.addWidget(self.car_field_laps, 1, 1)
            self.car_grid.addWidget(self.car_field_seed, 2, 0, 1, 2)
            self.car_grid.addWidget(self.apply_track_btn, 3, 0, 1, 2)

    def apply_driver_profile(self, suffix):
        profile_name = self.field_text(f"profile{suffix}")
        profile = PILOT_PROFILES.get(profile_name)
        if not profile:
            return
        self.set_field_text(f"driverName{suffix}", profile_name)
        self.set_field_text(f"car{suffix}", profile["team"])
        self.set_field_text(f"skill{suffix}", f"{profile['skill']:.2f}")
        self.set_field_text(f"aggression{suffix}", f"{profile['aggression']:.2f}")
        self.set_field_text(f"consistency{suffix}", f"{profile['consistency']:.2f}")
        self.set_field_text(f"tire{suffix}", profile["tire"])

    def field_text(self, key):
        widget = self.fields[key]
        return widget.currentText() if isinstance(widget, QComboBox) else widget.text()

    def set_field_text(self, key, value):
        widget = self.fields[key]
        if isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        else:
            widget.setText(str(value))

    def _wire_stop_fields(self):
        return

    def update_stint_fields(self, suffix):
        return

    def apply_team(self):
        return

    def apply_track_defaults(self):
        self.sync_local_reference_options()
        self.apply_session_preset()
        self.fetch_real_data()

    def on_track_selection_changed(self, *_args):
        self.sync_local_reference_options()
        self.apply_session_preset()
        self.fetch_real_data()

    def on_reference_selection_changed(self, *_args):
        self.apply_session_preset()
        self.fetch_real_data()

    def sync_local_reference_options(self, *_args):
        track = self.field_text("track")
        years = available_reference_years(track)

        current_year = self.real_year_combo.currentText() if hasattr(self, "real_year_combo") else ""

        self.real_year_combo.blockSignals(True)
        self.real_year_combo.clear()
        self.real_year_combo.addItems(years or ["2025"])
        if current_year in years:
            self.real_year_combo.setCurrentText(current_year)
        self.real_year_combo.blockSignals(False)

        selected_year = self.real_year_combo.currentText()
        sessions = available_sessions_for_year(track, selected_year)
        self.real_session_combo.blockSignals(True)
        self.real_session_combo.clear()
        self.real_session_combo.addItems(sessions or ["Q"])
        preferred = "Q" if "Q" in sessions else (sessions[0] if sessions else "Q")
        self.real_session_combo.setCurrentText(preferred)
        self.real_session_combo.blockSignals(False)

    def sprint_laps_for_track(self, track_name):
        lap_km = TRACKS[track_name]["lapDistanceKm"]
        return max(16, round(100.0 / max(0.1, lap_km)))

    def apply_session_preset(self, *_args):
        preset = dict(
            tire_a="C5 Soft",
            tire_b="C4 Soft",
            temp_a=98,
            temp_b=98,
            wear=4,
            status="Modo fijo de vuelta rapida aplicado: una vuelta lanzada con preparacion automatica.",
        )

        self.set_field_text("laps", 1)
        self.set_field_text("tireA", preset["tire_a"])
        self.set_field_text("tireB", preset["tire_b"])
        self.set_field_text("tireTempA", preset["temp_a"])
        self.set_field_text("tireTempB", preset["temp_b"])
        self.set_field_text("tireWearA", preset["wear"])
        self.set_field_text("tireWearB", preset["wear"])
        self.real_status.setText(preset["status"])

    def build_cfg(self, suffix):
        try:
            team_name = self.field_text(f"car{suffix}")
            team = TEAMS[team_name]
            return dict(
                mode="fastlap",
                driverName=self.field_text(f"driverName{suffix}").strip() or f"Piloto {suffix}",
                teamName=team_name,
                power=float(team["power"]),
                mass=float(team["mass"]),
                drag=float(team["drag"]),
                downforce=float(team["downforce"]),
                traction=float(team["traction"]),
                brake=float(team["brake"]),
                ers=float(team["ers"]),
                topSpeedKph=float(348 - (team["drag"] - 0.81) * 80 + (team["power"] - 748) * 0.9),
                trackName=self.field_text("track"),
                laps=1,
                weather=self.field_text("weather"),
                sessionName=self.field_text("session"),
                integrationMethod=self.field_text("integrationMethod"),
                tireName=self.field_text(f"tire{suffix}"),
                tireTempC=float(self.field_text(f"tireTemp{suffix}")),
                tireWearPct=float(self.field_text(f"tireWear{suffix}")),
                pilotSkill=float(self.field_text(f"skill{suffix}")),
                pilotAggression=float(self.field_text(f"aggression{suffix}")),
                pilotConsistency=float(self.field_text(f"consistency{suffix}")),
                fuel=5.5,
                seed=int(float(self.field_text("seed"))),
            )
        except Exception as exc:
            raise ValueError("Revisa los valores numericos.") from exc

    def fetch_real_data(self, *_args, on_ready=None):
        track = self.field_text("track")
        year = int(float(self.field_text("year")))
        session = self.field_text("session").strip()
        ref = load_reference_profile(track, year=year, session=session)
        if ref and int(ref.get("year", 0)) == year and str(ref.get("session", "")).upper() == session.upper():
            self.loaded_ref = ref
            self.real_status.setText(f"Referencia local: {track} {year} {session} lista")
            refresh_real_track(track)
            if on_ready:
                on_ready()
            return ref
        fallback_ref = load_reference_profile(track)
        if fallback_ref:
            self.loaded_ref = fallback_ref
            fallback_year = fallback_ref.get("year", "?")
            fallback_session = fallback_ref.get("session", "?")
            self.real_status.setText(
                f"Referencia local: usando {track} {fallback_year} {fallback_session} porque {year} {session} no esta cargado."
            )
            refresh_real_track(track)
            if on_ready:
                on_ready()
            return fallback_ref
        self.loaded_ref = None
        self.real_status.setText(
            f"Sin referencia local para {track} {year} {session}. Se simulara con parametros de pista base."
        )
        refresh_real_track(track)
        if on_ready:
            on_ready()
        return None

    def _run_simulation_after_data(self):
        try:
            cfg_a = self.build_cfg("A")
            cfg_b = self.build_cfg("B")
            self.res_a = simulate(cfg_a)
            self.res_b = simulate(cfg_b)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._present_results()

    def run_simulation(self):
        try:
            self.fetch_real_data()
            self._run_simulation_after_data()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _present_results(self):
        cfg_a = self.build_cfg("A")
        cfg_b = self.build_cfg("B")

        a_finished = self.res_a.get("finished", True)
        b_finished = self.res_b.get("finished", True)
        if a_finished and b_finished:
            diff = self.res_a["total"] - self.res_b["total"]
            winner = "A" if diff < 0 else "B"
            diff_text = f"{abs(diff):.3f} s"
        elif a_finished and not b_finished:
            winner = "A"
            diff_text = "B DNF"
        elif b_finished and not a_finished:
            winner = "B"
            diff_text = "A DNF"
        else:
            winner = "-"
            diff_text = "DOBLE DNF"
        self.kpis["ta"].value.setText(fmt_sec(self.res_a["total"]) if a_finished else "DNF")
        self.kpis["tb"].value.setText(fmt_sec(self.res_b["total"]) if b_finished else "DNF")
        self.kpis["df"].value.setText(diff_text)
        self.kpis["ea"].value.setText(f"+{self.res_a.get('eventPenalty', 0):.2f} s")
        self.kpis["eb"].value.setText(f"+{self.res_b.get('eventPenalty', 0):.2f} s")
        ref = self.loaded_ref or load_reference_profile(cfg_a["trackName"]) or {}
        src = f"{ref.get('event', cfg_a['trackName'])} {ref.get('year', self.field_text('year'))} {ref.get('session', self.field_text('session'))}"
        events_a = self.res_a.get("eventCounts", {})
        events_b = self.res_b.get("eventCounts", {})
        events_a_txt = self.format_events(events_a)
        events_b_txt = self.format_events(events_b)
        method_name = cfg_a.get("integrationMethod", "Euler")
        start_a = self.res_a.get("flyingStartSpeedKph", 0.0)
        start_b = self.res_b.get("flyingStartSpeedKph", 0.0)
        self.note.setText(
            f"Intento {winner} mas rapido. "
            f"A ({cfg_a['driverName']} - {cfg_a['teamName']}): {cfg_a['tireName']} / {events_a_txt}. "
            f"B ({cfg_b['driverName']} - {cfg_b['teamName']}): {cfg_b['tireName']} / {events_b_txt}. "
            f"Vueltas de preparacion: salida lanzada A {start_a:.1f} km/h, B {start_b:.1f} km/h. "
            f"Sesion de referencia: {cfg_a.get('sessionName', self.field_text('session'))}. Metodo: {method_name}. Datos reales: {src}."
        )
        self.track_name = cfg_a["trackName"]
        self.update_charts()
        self.update_table()
        self.restart_view()

    def update_charts(self):
        if not (self.res_a and self.res_b):
            return
        self.figure.patch.set_facecolor(PALETTE["card"])
        colors = (PALETTE["accent"], PALETTE["cyan"])
        for ax in self.axes:
            ax.clear()
            ax.set_facecolor(PALETTE["card"])
            ax.grid(color="#31415e", alpha=0.35, linewidth=0.8)
            ax.tick_params(colors=PALETTE["muted"])
            for spine in ax.spines.values():
                spine.set_color(PALETTE["line"])
        labels = ["Piloto A", "Piloto B"]
        totals = [self.res_a["total"], self.res_b["total"]]
        self.axes[0].bar(labels, totals, color=colors)
        self.axes[0].set_title("Tiempo De Vuelta", color=PALETTE["ink"])

        wear_vals = [self.res_a["laps"][0]["wear"], self.res_b["laps"][0]["wear"]]
        self.axes[1].bar(labels, wear_vals, color=colors)
        self.axes[1].set_title("Desgaste Final (%)", color=PALETTE["ink"])

        temp_vals = [self.res_a["laps"][0].get("tireTemp", 0), self.res_b["laps"][0].get("tireTemp", 0)]
        self.axes[2].bar(labels, temp_vals, color=colors)
        self.axes[2].set_title("Temperatura Final Goma (C)", color=PALETTE["ink"])

        cats = ["straight", "fast", "slow"]
        la = [self.res_a["avgSegment"][k] for k in cats]
        lb = [self.res_b["avgSegment"][k] for k in cats]
        xs = [0, 1, 2]
        self.axes[3].bar([i - 0.18 for i in xs], la, 0.36, color=colors[0], label="Piloto A")
        self.axes[3].bar([i + 0.18 for i in xs], lb, 0.36, color=colors[1], label="Piloto B")
        self.axes[3].set_xticks(xs, ["Recta", "Curva rapida", "Curva lenta"])
        self.axes[3].set_title("Velocidad Promedio", color=PALETTE["ink"])
        for ax in self.axes:
            leg = ax.legend(frameon=False)
            if leg:
                for txt in leg.get_texts():
                    txt.set_color(PALETTE["muted"])
        self.figure.tight_layout(pad=2)
        self.canvas.draw_idle()

    def update_table(self):
        self.table.setRowCount(2)
        configs = [self.build_cfg("A"), self.build_cfg("B")]
        rows = [self.res_a, self.res_b]
        for i, (cfg, res) in enumerate(zip(configs, rows)):
            lap = res["laps"][0] if res.get("laps") else {}
            events = res.get("eventCounts", {})
            ev_text = self.format_events(events)
            values = [
                cfg["driverName"],
                (fmt_sec(res["total"]) if res.get("finished") else "DNF"),
                cfg["teamName"],
                cfg["tireName"],
                f"{cfg['tireTempC']:.1f} C",
                f"{lap.get('tireTemp', 0):.1f} C",
                f"{lap.get('wear', 0):.1f} %",
                ev_text,
                f"{res.get('eventPenalty', 0):.2f} s",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 7:
                    if ev_text == "Limpia":
                        item.setForeground(QColor("#9ee6b8"))
                    elif "Choque" in ev_text:
                        item.setForeground(QColor("#ff7f7f"))
                    elif "Derrape" in ev_text or "Drag" in ev_text:
                        item.setForeground(QColor("#ffd27a"))
                self.table.setItem(i, col, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 110)

    def swap_plans(self):
        for ka, kb in (
            ("profileA", "profileB"),
            ("driverNameA", "driverNameB"),
            ("carA", "carB"),
            ("tireA", "tireB"),
            ("tireTempA", "tireTempB"),
            ("tireWearA", "tireWearB"),
            ("skillA", "skillB"),
            ("aggressionA", "aggressionB"),
            ("consistencyA", "consistencyB"),
        ):
            va, vb = self.field_text(ka), self.field_text(kb)
            self.set_field_text(ka, vb)
            self.set_field_text(kb, va)
        self.run_simulation()

    def restart_view(self):
        if not (self.res_a and self.res_b):
            return
        self.vtime = 0.0
        self.vrun = True
        self.last_ts = None
        self.play_btn.setText("Pausar")
        self.rebuild_track_scene(reset_time=False)
        self.vtime = 0.0

    def rebuild_track_scene(self, reset_time=False):
        if not self.track_name:
            return
        width = self.track_widget.width()
        height = self.track_widget.height()
        if width <= 1 or height <= 1:
            return
        self.geo = build_geo(self.track_name, width, height)
        if not self.geo:
            self.track_widget.set_scene(None)
            return
        team_a = self.field_text("carA")
        team_b = self.field_text("carB")
        self.track_widget.set_scene(self.geo, team_a=team_a, team_b=team_b)
        if reset_time:
            self.vtime = 0.0

    def toggle_play(self):
        self.vrun = not self.vrun
        self.play_btn.setText("Pausar" if self.vrun else "Reanudar")

    def frame_update(self):
        if not (self.res_a and self.res_b and self.geo):
            return
        track = track_layout(self.track_name)
        tref = max(self.res_a["total"], self.res_b["total"])
        now = time.time()
        speed = float(self.speed_combo.currentText())
        if self.vrun:
            if self.last_ts is not None:
                self.vtime = min(tref, self.vtime + (now - self.last_ts) * speed)
            self.last_ts = now
        else:
            self.last_ts = now
        a = state_at(self.res_a, track, self.vtime)
        b = state_at(self.res_b, track, self.vtime)
        team_a = self.field_text("carA")
        team_b = self.field_text("carB")
        self.track_widget.set_scene(self.geo, a, b, team_a=team_a, team_b=team_b)
        lead = "A" if a["pRace"] > b["pRace"] else "B"
        self.vmsg.setText(
            f"t={self.vtime:.1f}s | A V{a['lap']} {a['speed']:.0f} km/h | "
            f"B V{b['lap']} {b['speed']:.0f} km/h | Lider: {lead}"
        )
        if self.vtime >= tref and self.vrun:
            self.vrun = False
            self.play_btn.setText("Reanudar")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_responsive_layout()
        if self.width() < 1220:
            self.main_splitter.setSizes([340, max(560, self.width() - 380)])
        elif self.width() < 1380:
            self.main_splitter.setSizes([360, max(640, self.width() - 400)])
        else:
            self.main_splitter.setSizes([360, max(820, self.width() - 420)])
        if self.res_a and self.res_b:
            QTimer.singleShot(0, lambda: self.rebuild_track_scene(reset_time=False))


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(app_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
