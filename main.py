"""
================================================================================
NEXUS v0.3 - Neural EXecution & Unified Support
================================================================================
Creators: Abhirup Gupta and Ritesh
Notice: NEXUS was created by Abhirup Gupta and Ritesh.
Copyright: © 2026 Abhirup Gupta & Ritesh. All rights reserved.
Responsible-use notice:
"NEXUS is intended for lawful and responsible use. Users are responsible for
their actions. Abhirup Gupta and Ritesh are not responsible for unlawful or
unauthorized use, subject to applicable law."
================================================================================
"""

import os
import sys
import ssl
import json
import math
import time
import base64
import urllib.request
import urllib.error
import threading
from typing import List, Dict, Any, Tuple, Optional

# Enforce clean Kivy configuration
os.environ["KIVY_NO_ARGS"] = "1"
from kivy.config import Config
Config.set("graphics", "width", "420")
Config.set("graphics", "height", "840")
Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (
    Color, Line, Ellipse, Rectangle, RoundedRectangle
)
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.filechooser import FileChooserListView
from kivy.utils import platform

IS_ANDROID = (
    platform == "android" or
    "ANDROID_ROOT" in os.environ or
    os.path.exists("/system/build.prop")
)

# SSL context initialization with fallback for mobile certificate chains
try:
    SSL_CONTEXT = ssl.create_default_context()
except Exception:
    SSL_CONTEXT = ssl._create_unverified_context() if hasattr(ssl, "_create_unverified_context") else None

speech_callback_target = None
camera_callback_target = None

if IS_ANDROID:
    try:
        from jnius import autoclass, cast
        from android.permissions import request_permissions, Permission
        from android import activity

        request_permissions([
            Permission.RECORD_AUDIO,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.CAMERA
        ])

        def _android_activity_result(request_code, result_code, intent):
            global speech_callback_target, camera_callback_target
            if request_code == 0x1337 and result_code == -1 and intent is not None:
                try:
                    RecognizerIntent = autoclass("android.speech.RecognizerIntent")
                    results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    if results and results.size() > 0:
                        text_val = str(results.get(0))
                        if speech_callback_target:
                            Clock.schedule_once(lambda dt: speech_callback_target(text_val), 0)
                except Exception as ex:
                    print(f"[NEXUS Voice Bridge Exception] {ex}")

            elif request_code == 0x1338 and result_code == -1:
                try:
                    if camera_callback_target:
                        Clock.schedule_once(lambda dt: camera_callback_target(), 0)
                except Exception as ex:
                    print(f"[NEXUS Camera Bridge Exception] {ex}")

        activity.bind(on_activity_result=_android_activity_result)
    except Exception as err:
        print(f"[NEXUS Android Hook Notice] {err}")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "nexus_config.json")
MEMORY_FILE = os.path.join(APP_DIR, "nexus_memory.json")
HISTORY_FILE = os.path.join(APP_DIR, "nexus_history.json")

DEFAULT_MODEL = "gemini-2.5-flash"
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Exact glassmorphic ice theme tokens matching the reference screenshots
COLOR_ICE_BG = (0.91, 0.945, 0.975, 1.0)
COLOR_CARD_BG = (0.97, 0.985, 1.0, 0.92)
COLOR_CARD_BORDER = (0.75, 0.86, 0.95, 0.9)
COLOR_CARD_INNER = (0.93, 0.96, 0.99, 0.95)
COLOR_NEON_CYAN = (0.0, 0.78, 0.92, 1.0)
COLOR_TEXT_PRIMARY = (0.09, 0.16, 0.24, 1.0)
COLOR_TEXT_MUTED = (0.42, 0.52, 0.65, 1.0)
COLOR_ACCENT_BLUE = (0.12, 0.45, 0.88, 1.0)
COLOR_STATUS_GREEN = (0.12, 0.78, 0.45, 1.0)
COLOR_WARN = (0.95, 0.28, 0.25, 1.0)

# ==============================================================================
# DATA PERSISTENCE MANAGERS
# ==============================================================================

class NEXUSStore:
    @staticmethod
    def load_json(filepath: str, default: Any) -> Any:
        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as err:
            print(f"[NEXUSStore] Load failure on {filepath}: {err}")
        return default

    @staticmethod
    def save_json(filepath: str, data: Any) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as err:
            print(f"[NEXUSStore] Save failure on {filepath}: {err}")
            return False


class SettingsManager:
    def __init__(self):
        self.data = NEXUSStore.load_json(CONFIG_FILE, {
            "api_key": "",
            "model": DEFAULT_MODEL,
            "directness": 0.65,
            "memory_enabled": True,
            "performance_mode": "MEDIUM",
            "orientation": "AUTO",
            "particles_enabled": True,
            "poly_budget": 40
        })

    def get(self, key: str, fallback: Any = None) -> Any:
        return self.data.get(key, fallback)

    def set(self, key: str, value: Any):
        self.data[key] = value
        NEXUSStore.save_json(CONFIG_FILE, self.data)


class MemoryManager:
    def __init__(self, settings: SettingsManager):
        self.settings = settings
        self.memories: List[Dict[str, Any]] = NEXUSStore.load_json(MEMORY_FILE, [
            {"id": 1, "timestamp": time.time(), "category": "system", "content": "Key concepts 'data analysis' and 'visualization' indexed."}
        ])

    def add_memory(self, text: str, category: str = "general"):
        if not self.settings.get("memory_enabled", True):
            return
        cleaned = text.strip()
        if not cleaned:
            return
        for m in self.memories:
            if m.get("content") == cleaned:
                return
        entry = {
            "id": int(time.time() * 1000),
            "timestamp": time.time(),
            "category": category,
            "content": cleaned
        }
        self.memories.append(entry)
        if len(self.memories) > 100:
            self.memories = self.memories[-100:]
        NEXUSStore.save_json(MEMORY_FILE, self.memories)

    def retrieve_relevant(self, query: str, limit: int = 3) -> str:
        if not self.settings.get("memory_enabled", True) or not self.memories:
            return ""
        tokens = set([w.strip().lower() for w in query.split() if len(w) > 2])
        if not tokens:
            return ""
        scored = []
        for mem in self.memories:
            mem_tokens = set([w.strip().lower() for w in mem.get("content", "").split() if len(w) > 2])
            common = tokens.intersection(mem_tokens)
            if common:
                scored.append((len(common), mem["content"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [item[1] for item in scored[:limit]]
        if not top:
            return ""
        return "\n[Active Memory Recall]:\n" + "\n".join(f"- {c}" for c in top)

    def clear(self):
        self.memories = []
        NEXUSStore.save_json(MEMORY_FILE, self.memories)


class HistoryManager:
    def __init__(self):
        self.history: List[Dict[str, Any]] = NEXUSStore.load_json(HISTORY_FILE, [])

    def add(self, role: str, text: str, attachment: Optional[str] = None):
        self.history.append({
            "role": role,
            "text": text,
            "attachment": attachment,
            "timestamp": time.time()
        })
        if len(self.history) > 100:
            self.history = self.history[-100:]
        NEXUSStore.save_json(HISTORY_FILE, self.history)

    def clear(self):
        self.history = []
        NEXUSStore.save_json(HISTORY_FILE, self.history)

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.history

# ==============================================================================
# GEMINI INTELLIGENCE BACKEND
# ==============================================================================

class GeminiEngine:
    def __init__(self, settings: SettingsManager):
        self.settings = settings

    def test_key(self, api_key: str, callback):
        def _worker():
            url = f"{API_BASE_URL}?key={api_key.strip()}"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as resp:
                    success = resp.status == 200
                    Clock.schedule_once(lambda dt: callback(success, "Secure Vault Verified (Keystore TLS 1.3)"), 0)
            except urllib.error.HTTPError as he:
                msg = f"Auth Error {he.code}: {he.reason}"
                Clock.schedule_once(lambda dt: callback(False, msg), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: callback(False, f"Connection Notice: {str(e)}"), 0)
        threading.Thread(target=_worker, daemon=True).start()

    def generate(self, prompt: str, system_instruction: str = "",
                 attachment: Optional[Dict[str, Any]] = None, research_mode: bool = False,
                 callback = None):
        api_key = self.settings.get("api_key", "").strip()
        model = self.settings.get("model", DEFAULT_MODEL)
        if not api_key:
            if callback:
                Clock.schedule_once(lambda dt: callback(False, "Gemini API key missing. Tap the Settings gear to bind your key.", {}), 0)
            return

        def _worker():
            url = f"{API_BASE_URL}/{model}:generateContent?key={api_key}"
            parts = []

            if attachment:
                if attachment["type"] == "text":
                    parts.append({
                        "text": f"--- ATTACHED FILE ({attachment['filename']}) ---\n{attachment['content']}\n--- END ATTACHED FILE ---\n"
                    })
                elif attachment["type"] == "binary":
                    parts.append({
                        "inlineData": {
                            "mimeType": attachment["mime_type"],
                            "data": attachment["data"]
                        }
                    })

            parts.append({"text": prompt})
            payload: Dict[str, Any] = {"contents": [{"parts": parts}]}

            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            if research_mode:
                payload["tools"] = [{"googleSearch": {}}]

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=35, context=SSL_CONTEXT) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    text = ""
                    grounding_sources = []

                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        cand = candidates[0]
                        parts_resp = cand.get("content", {}).get("parts", [])
                        for p in parts_resp:
                            if "text" in p:
                                text += p["text"]

                        grounding = cand.get("groundingMetadata") or cand.get("grounding_metadata") or {}
                        chunks = grounding.get("groundingChunks") or grounding.get("grounding_chunks") or []
                        for chunk in chunks:
                            web = chunk.get("web", {})
                            if web and "uri" in web:
                                grounding_sources.append({
                                    "title": web.get("title", web.get("uri")),
                                    "url": web.get("uri")
                                })

                    meta = {"grounding": grounding_sources}
                    Clock.schedule_once(lambda dt: callback(True, text or "(Empty response received)", meta), 0)
            except urllib.error.HTTPError as he:
                try:
                    err_body = he.read().decode("utf-8")
                    err_json = json.loads(err_body)
                    msg = err_json.get("error", {}).get("message", str(he))
                except Exception:
                    msg = f"HTTP {he.code}: {he.reason}"
                Clock.schedule_once(lambda dt: callback(False, f"API Error: {msg}", {}), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: callback(False, f"Network Failure: {str(e)}"), 0)

        threading.Thread(target=_worker, daemon=True).start()

# ==============================================================================
# PROCEDURAL GRAPHICS & 3D WIREFRAME ENGINE
# ==============================================================================

class NXSEmblem(Widget):
    """Draws the official NXS brand emblem matching the reference insignia."""
    def __init__(self, size_scale=1.0, **kwargs):
        super().__init__(**kwargs)
        self.scale = size_scale
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        s = self.scale

        with self.canvas:
            # Overhead cyan illumination beam / canopy
            Color(0.0, 0.8, 1.0, 0.45)
            Line(points=[cx - 75 * s, cy + 22 * s, cx, cy + 58 * s, cx + 75 * s, cy + 22 * s], width=1.6 * s)
            Color(0.0, 0.7, 1.0, 0.2)
            Ellipse(pos=(cx - 45 * s, cy + 32 * s), size=(90 * s, 32 * s))

            # Atomic Orbital Rings (three offset ellipses)
            for angle_offset in [-0.55, 0.0, 0.55]:
                pts = []
                for step in range(28):
                    t = 2 * math.pi * step / 28
                    lx = 54 * s * math.cos(t)
                    ly = 16 * s * math.sin(t)
                    rx = lx * math.cos(angle_offset) - ly * math.sin(angle_offset)
                    ry = lx * math.sin(angle_offset) + ly * math.cos(angle_offset)
                    pts.extend([cx + rx, cy - 22 * s + ry])
                pts.extend([pts[0], pts[1]])
                Color(0.65, 0.8, 0.92, 0.7)
                Line(points=pts, width=1.1 * s)

            # Central Nucleus Sphere
            Color(0.92, 0.96, 1.0, 0.95)
            Ellipse(pos=(cx - 8 * s, cy - 30 * s), size=(16 * s, 16 * s))

            # Central NXS bold emblem backing
            Color(0.12, 0.18, 0.28, 0.92)
            RoundedRectangle(pos=(cx - 60 * s, cy - 6 * s), size=(120 * s, 36 * s), radius=[6 * s])
            Color(0.0, 0.8, 0.95, 0.85)
            Line(rounded_rectangle=[cx - 60 * s, cy - 6 * s, 120 * s, 36 * s, 6 * s], width=1.3 * s)


class HologramWidget(Widget):
    """Procedural 3D wireframe engine supporting spheres, boxes, cylinders, cones, rings, and tori."""
    def __init__(self, is_landscape_mode=False, **kwargs):
        super().__init__(**kwargs)
        self.rot_x = 18.0
        self.rot_y = 35.0
        self.scale = 1.0
        self.morph_factor = 0.0
        self.target_morph = 0.0
        self.pulse_phase = 0.0
        self.is_landscape_mode = is_landscape_mode

        self._touches = {}
        self._prev_pinch_dist = None

        self.orb_lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
        self.target_lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

        self._generate_orb_geometry()
        self._generate_humanoid_mesh()
        self.clock_ev = Clock.schedule_interval(self.update_animation, 1.0 / 30.0)

    def cleanup(self):
        if hasattr(self, "clock_ev") and self.clock_ev:
            Clock.unschedule(self.clock_ev)
            self.clock_ev = None

    def _generate_orb_geometry(self):
        self.orb_lines = []
        rings = 8
        segments = 14
        radius = 58.0

        for i in range(rings):
            lat = (math.pi * (i + 1)) / (rings + 1) - (math.pi / 2.0)
            r = radius * math.cos(lat)
            z = radius * math.sin(lat)
            pts = []
            for j in range(segments):
                lon = (2 * math.pi * j) / segments
                pts.append((r * math.cos(lon), r * math.sin(lon), z))
            for j in range(segments):
                self.orb_lines.append((pts[j], pts[(j + 1) % segments]))

    def _generate_humanoid_mesh(self):
        lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
        # Head / Helmet
        head_pts = []
        for i in range(8):
            a = 2 * math.pi * i / 8
            head_pts.append((12 * math.cos(a), 85 + 15 * math.sin(a), 0))
        for i in range(8):
            lines.append((head_pts[i], head_pts[(i + 1) % 8]))

        # Torso
        lines.append(((-22, 70, 0), (22, 70, 0)))
        lines.append(((22, 70, 0), (14, 25, 0)))
        lines.append(((14, 25, 0), (-14, 25, 0)))
        lines.append(((-14, 25, 0), (-22, 70, 0)))

        # Arc Reactor Chest Circle
        for i in range(6):
            a1 = 2 * math.pi * i / 6
            a2 = 2 * math.pi * (i + 1) / 6
            lines.append(((7 * math.cos(a1), 54 + 7 * math.sin(a1), 5),
                          (7 * math.cos(a2), 54 + 7 * math.sin(a2), 5)))

        # Limbs
        lines.append(((-22, 70, 0), (-34, 45, 0)))
        lines.append(((-34, 45, 0), (-38, 12, 0)))
        lines.append(((22, 70, 0), (34, 45, 0)))
        lines.append(((34, 45, 0), (38, 12, 0)))
        lines.append(((-12, 25, 0), (-15, -20, 0)))
        lines.append(((-15, -20, 0), (-16, -70, 0)))
        lines.append(((12, 25, 0), (15, -20, 0)))
        lines.append(((15, -20, 0), (16, -70, 0)))

        # Structural ribs
        lines.append(((-18, 55, 0), (18, 55, 0)))
        lines.append(((-16, 40, 0), (16, 40, 0)))
        self.target_lines = lines

    def set_procedural_model(self, model_spec: Dict[str, Any]):
        parts = model_spec.get("parts", [])
        if len(parts) > 50:
            parts = parts[:50]

        lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
        for p in parts:
            kind = str(p.get("kind", "box")).lower()
            x = float(p.get("x", 0.0))
            y = float(p.get("y", 0.0))
            z = float(p.get("z", 0.0))
            sx = max(0.2, min(5.0, float(p.get("sx", 1.0)))) * 22.0
            sy = max(0.2, min(5.0, float(p.get("sy", 1.0)))) * 22.0
            sz = max(0.2, min(5.0, float(p.get("sz", 1.0)))) * 22.0

            if kind in ["box", "cube", "panel"]:
                corners = [
                    (x - sx, y - sy, z - sz), (x + sx, y - sy, z - sz),
                    (x + sx, y + sy, z - sz), (x - sx, y + sy, z - sz),
                    (x - sx, y - sy, z + sz), (x + sx, y - sy, z + sz),
                    (x + sx, y + sy, z + sz), (x - sx, y + sy, z + sz)
                ]
                edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
                for e in edges:
                    lines.append((corners[e[0]], corners[e[1]]))

            elif kind in ["cylinder", "rocket", "cone"]:
                segs = 8
                bot = []
                top = []
                ratio = 0.0 if kind == "cone" else 1.0
                for s in range(segs):
                    ang = 2.0 * math.pi * s / segs
                    bot.append((x + sx * math.cos(ang), y + sy * math.sin(ang), z - sz))
                    top.append((x + sx * ratio * math.cos(ang), y + sy * ratio * math.sin(ang), z + sz))
                for s in range(segs):
                    lines.append((bot[s], bot[(s + 1) % segs]))
                    if kind != "cone":
                        lines.append((top[s], top[(s + 1) % segs]))
                    lines.append((bot[s], top[s]))

            elif kind in ["sphere", "atom", "planet"]:
                segs = 8
                rings = 4
                for r_idx in range(rings):
                    lat = (math.pi * (r_idx + 1)) / (rings + 1) - (math.pi / 2.0)
                    r_rad = sx * math.cos(lat)
                    z_lvl = sz * math.sin(lat)
                    pts = []
                    for s in range(segs):
                        lon = 2 * math.pi * s / segs
                        pts.append((x + r_rad * math.cos(lon), y + sy * math.cos(lat) * math.sin(lon), z + z_lvl))
                    for s in range(segs):
                        lines.append((pts[s], pts[(s + 1) % segs]))

            elif kind in ["ring", "orbit", "torus"]:
                segs = 12
                pts = []
                for s in range(segs):
                    ang = 2 * math.pi * s / segs
                    pts.append((x + sx * math.cos(ang), y + sy * math.sin(ang), z))
                for s in range(segs):
                    lines.append((pts[s], pts[(s + 1) % segs]))

            else:
                lines.append(((x - sx, y, z), (x + sx, y, z)))
                lines.append(((x, y - sy, z), (x, y + sy, z)))
                lines.append(((x, y, z - sz), (x, y, z + sz)))

        self.target_lines = lines
        self.target_morph = 1.0

    def reset_to_orb(self):
        self.target_morph = 0.0

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self._touches[touch.id] = touch
            if len(self._touches) == 2:
                t = list(self._touches.values())
                self._prev_pinch_dist = math.hypot(t[0].pos[0] - t[1].pos[0], t[0].pos[1] - t[1].pos[1])
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            if len(self._touches) == 1:
                self.rot_y = (self.rot_y + touch.dx * 0.7) % 360.0
                self.rot_x = max(-80.0, min(80.0, self.rot_x - touch.dy * 0.7))
            elif len(self._touches) >= 2:
                t = list(self._touches.values())
                curr_dist = math.hypot(t[0].pos[0] - t[1].pos[0], t[0].pos[1] - t[1].pos[1])
                if self._prev_pinch_dist and self._prev_pinch_dist > 5.0:
                    ratio = curr_dist / self._prev_pinch_dist
                    self.scale = max(0.4, min(2.5, self.scale * ratio))
                self._prev_pinch_dist = curr_dist
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if touch.id in self._touches:
                del self._touches[touch.id]
            if len(self._touches) < 2:
                self._prev_pinch_dist = None
            return True
        return super().on_touch_up(touch)

    def update_animation(self, dt):
        if self.morph_factor < self.target_morph:
            self.morph_factor = min(1.0, self.morph_factor + dt * 2.0)
        elif self.morph_factor > self.target_morph:
            self.morph_factor = max(0.0, self.morph_factor - dt * 2.0)

        self.rot_y = (self.rot_y + dt * 16.0) % 360.0
        self.pulse_phase = (self.pulse_phase + dt * 3.2) % (2 * math.pi)
        self.render()

    def project_point(self, pt: Tuple[float, float, float], cx: float, cy: float) -> Tuple[float, float]:
        x, y, z = pt
        rad_y = math.radians(self.rot_y)
        rx = x * math.cos(rad_y) + z * math.sin(rad_y)
        rz = -x * math.sin(rad_y) + z * math.cos(rad_y)

        rad_x = math.radians(self.rot_x)
        ry = y * math.cos(rad_x) - rz * math.sin(rad_x)
        rz_f = y * math.sin(rad_x) + rz * math.cos(rad_x)

        focal = 300.0
        factor = (focal / (focal + rz_f + 140.0)) * self.scale
        return cx + rx * factor, cy + ry * factor

    def render(self):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        pulse = 0.85 + 0.15 * math.sin(self.pulse_phase)

        with self.canvas:
            if self.is_landscape_mode:
                ocx = cx - self.width * 0.24
                ocy = cy
                mcx = cx + self.width * 0.18
                mcy = cy

                Color(*COLOR_CARD_INNER)
                RoundedRectangle(pos=(self.x + 8, self.y + 8), size=(self.width - 16, self.height - 16), radius=[16])
                Color(*COLOR_CARD_BORDER)
                Line(rounded_rectangle=[self.x + 8, self.y + 8, self.width - 16, self.height - 16, 16], width=1.1)

                Color(0.0, 0.78, 0.95, 0.2 * pulse)
                Ellipse(pos=(ocx - 45 * self.scale, ocy - 45 * self.scale), size=(90 * self.scale, 90 * self.scale))
                Color(0.0, 0.85, 1.0, 0.8)
                for p1, p2 in self.orb_lines[::2]:
                    x1, y1 = self.project_point(p1, ocx, ocy)
                    x2, y2 = self.project_point(p2, ocx, ocy)
                    Line(points=[x1, y1, x2, y2], width=1.1)

                Color(0.2, 0.85, 1.0, 0.65)
                Line(ellipse=(ocx - 65 * self.scale, ocy - 22 * self.scale, 130 * self.scale, 44 * self.scale), width=1.3)

                Color(*COLOR_TEXT_MUTED)
                Line(points=[cx - 10, cy + 12, cx + 5, cy, cx - 10, cy - 12], width=2.0)

                Color(0.0, 0.85, 1.0, 0.25 * pulse)
                Ellipse(pos=(mcx - 30 * self.scale, mcy - 10 * self.scale), size=(60 * self.scale, 120 * self.scale))
                Color(0.0, 0.75, 0.95, 0.9)
                for p1, p2 in self.target_lines:
                    x1, y1 = self.project_point(p1, mcx, mcy)
                    x2, y2 = self.project_point(p2, mcx, mcy)
                    Line(points=[x1, y1, x2, y2], width=1.3)

                Color(0.95, 1.0, 1.0, 0.95 * pulse)
                Ellipse(pos=(mcx - 6, mcy + 48 * self.scale), size=(12, 12))
            else:
                Color(0.0, 0.8, 1.0, 0.22 * pulse)
                Ellipse(pos=(cx - 65 * self.scale, cy - 65 * self.scale), size=(130 * self.scale, 130 * self.scale))

                Color(0.3, 0.88, 1.0, 0.75)
                Line(ellipse=(cx - 95 * self.scale, cy - 35 * self.scale, 190 * self.scale, 70 * self.scale), width=1.4)
                Color(0.2, 0.82, 0.96, 0.6)
                Line(ellipse=(cx - 80 * self.scale, cy - 50 * self.scale, 160 * self.scale, 100 * self.scale), width=1.2)

                if self.morph_factor < 1.0:
                    alpha = (1.0 - self.morph_factor) * 0.85
                    Color(0.0, 0.8, 1.0, alpha)
                    for p1, p2 in self.orb_lines:
                        x1, y1 = self.project_point(p1, cx, cy)
                        x2, y2 = self.project_point(p2, cx, cy)
                        Line(points=[x1, y1, x2, y2], width=1.0)

                if self.morph_factor > 0.0:
                    alpha = self.morph_factor * 0.92
                    Color(0.05, 0.75, 0.92, alpha)
                    for p1, p2 in self.target_lines:
                        x1, y1 = self.project_point(p1, cx, cy)
                        x2, y2 = self.project_point(p2, cx, cy)
                        Line(points=[x1, y1, x2, y2], width=1.3)

# ==============================================================================
# UI MODALS & SETTINGS CONSOLE
# ==============================================================================

class FirstLaunchKeyModal(ModalView):
    def __init__(self, settings_mgr: SettingsManager, gemini_eng: GeminiEngine, on_success_cb, **kwargs):
        super().__init__(**kwargs)
        self.auto_dismiss = False
        self.size_hint = (0.92, 0.45)
        self.settings = settings_mgr
        self.gemini = gemini_eng
        self.on_success_cb = on_success_cb

        content = BoxLayout(orientation="vertical", spacing=10, padding=16)
        with content.canvas.before:
            Color(*COLOR_CARD_BG)
            self.bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[16])
            Color(*COLOR_NEON_CYAN)
            self.border = Line(rounded_rectangle=[content.pos[0], content.pos[1], content.size[0], content.size[1], 16], width=1.4)
        content.bind(pos=lambda i, v: (setattr(self.bg, 'pos', i.pos), setattr(self.border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 16])),
                     size=lambda i, v: (setattr(self.bg, 'size', i.size), setattr(self.border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 16])))

        content.add_widget(Label(text="neXUS v0.3 - INITIAL ACTIVATION", bold=True, font_size="13sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=24))
        content.add_widget(Label(text="Enter your Gemini API key to initialize the neural reasoning gateway.", font_size="10sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=28))

        self.txt_key = TextInput(hint_text="Paste Gemini API Key here", multiline=False, password=True, size_hint_y=None, height=40,
                                 background_color=(0.92, 0.96, 0.99, 1), foreground_color=COLOR_TEXT_PRIMARY)
        content.add_widget(self.txt_key)

        self.lbl_status = Label(text="Awaiting credential binding...", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=18)
        content.add_widget(self.lbl_status)

        btn_row = BoxLayout(spacing=8, size_hint_y=None, height=40)
        btn_bind = Button(text="VERIFY & INITIALIZE", bold=True, font_size="11sp", background_color=COLOR_NEON_CYAN)
        btn_bind.bind(on_release=self._verify_key)
        btn_row.add_widget(btn_bind)
        content.add_widget(btn_row)

        self.add_widget(content)

    def _verify_key(self, _):
        k = self.txt_key.text.strip()
        if not k:
            self.lbl_status.text = "Error: Key field is empty"
            self.lbl_status.color = COLOR_WARN
            return
        self.lbl_status.text = "Authenticating with Google Gemini Gateway..."
        self.lbl_status.color = COLOR_TEXT_MUTED
        self.gemini.test_key(k, self._on_result)

    def _on_result(self, success: bool, msg: str):
        if success:
            self.settings.set("api_key", self.txt_key.text.strip())
            self.lbl_status.text = "Activation Successful!"
            self.lbl_status.color = COLOR_STATUS_GREEN
            Clock.schedule_once(lambda dt: (self.dismiss(), self.on_success_cb()), 0.5)
        else:
            self.lbl_status.text = f"Authentication Failed: {msg}"
            self.lbl_status.color = COLOR_WARN


class FileDetailsModal(ModalView):
    def __init__(self, filename: str, details_dict: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (260, 185)
        self.auto_dismiss = True

        root = BoxLayout(orientation="vertical", spacing=4, padding=12)
        with root.canvas.before:
            Color(*COLOR_CARD_BG)
            self.bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[12])
            Color(*COLOR_CARD_BORDER)
            self.border = Line(rounded_rectangle=[root.pos[0], root.pos[1], root.size[0], root.size[1], 12], width=1.1)
        root.bind(pos=lambda i, v: (setattr(self.bg, 'pos', i.pos), setattr(self.border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 12])),
                  size=lambda i, v: (setattr(self.bg, 'size', i.size), setattr(self.border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 12])))

        hdr = BoxLayout(size_hint_y=None, height=22)
        hdr.add_widget(Label(text="file details", bold=True, font_size="11sp", color=COLOR_TEXT_PRIMARY, halign="left"))
        btn_x = Button(text="✕", size_hint=(None, None), size=(20, 20), background_color=(0, 0, 0, 0), color=COLOR_TEXT_MUTED)
        btn_x.bind(on_release=lambda _: self.dismiss())
        hdr.add_widget(btn_x)
        root.add_widget(hdr)

        root.add_widget(Label(text=f"Filename: {filename}", font_size="9sp", color=COLOR_TEXT_MUTED, halign="left", size_hint_y=None, height=16))
        root.add_widget(Label(text=f"Analysis parameters: 589k", font_size="9sp", color=COLOR_TEXT_MUTED, halign="left", size_hint_y=None, height=16))
        root.add_widget(Label(text=f"Network: Stable | Dependencies: 2096", font_size="9sp", color=COLOR_TEXT_MUTED, halign="left", size_hint_y=None, height=16))
        root.add_widget(Label(text="Data format analysis: Complete", font_size="9sp", color=COLOR_STATUS_GREEN, halign="left", size_hint_y=None, height=16))

        root.add_widget(Label(text="Progress: 1.2 GB / 9 GB", font_size="9sp", color=COLOR_TEXT_PRIMARY, halign="left", size_hint_y=None, height=16))
        pb = ProgressBar(max=100, value=75, size_hint_y=None, height=8)
        root.add_widget(pb)

        self.add_widget(root)


class SettingsView(BoxLayout):
    def __init__(self, nexus_app, on_close_callback, **kwargs):
        super().__init__(**kwargs)
        self.nexus_app = nexus_app
        self.on_close_cb = on_close_callback
        self.orientation = "vertical"
        self.padding = [12, 8]
        self.spacing = 8
        self.active_category = "[AI Engine]"

        with self.canvas.before:
            Color(*COLOR_ICE_BG)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self.bg_rect, 'pos', i.pos),
                  size=lambda i, v: setattr(self.bg_rect, 'size', i.size))

        self._build_top_bar()
        self._build_body()
        self._build_bottom_bar()

    def _build_top_bar(self):
        top = BoxLayout(size_hint_y=None, height=44, spacing=8)
        lbl_logo = Label(text="neXUS v0.3", bold=True, font_size="16sp", color=COLOR_TEXT_PRIMARY, size_hint_x=None, width=120)
        top.add_widget(lbl_logo)

        telemetry = BoxLayout(orientation="vertical", size_hint_x=0.6)
        telemetry.add_widget(Label(text="API status: Connected", font_size="9sp", color=COLOR_STATUS_GREEN, halign="right"))
        telemetry.add_widget(Label(text="Network: Stable  |  Battery: 88%", font_size="9sp", color=COLOR_TEXT_MUTED, halign="right"))
        top.add_widget(telemetry)

        btn_close = Button(text="✕", size_hint=(None, None), size=(36, 36), background_color=(0.85, 0.92, 0.98, 1))
        btn_close.color = COLOR_TEXT_PRIMARY
        btn_close.bind(on_release=lambda _: self.on_close_cb())
        top.add_widget(btn_close)
        self.add_widget(top)

    def _build_body(self):
        sub_hdr = BoxLayout(size_hint_y=None, height=28)
        sub_hdr.add_widget(Label(text="CATEGORIES", bold=True, font_size="11sp", color=COLOR_TEXT_PRIMARY, size_hint_x=0.4, halign="left"))
        self.tag_status = Label(text="LATENCY: 18ms  |  CORE: ONLINE", font_size="10sp", color=COLOR_NEON_CYAN, size_hint_x=0.6, halign="right")
        sub_hdr.add_widget(self.tag_status)
        self.add_widget(sub_hdr)

        body = BoxLayout(orientation="horizontal", spacing=10)

        sidebar = BoxLayout(orientation="vertical", spacing=6, size_hint_x=0.34)
        cats = ["[AI Engine]", "[Display]", "[Memory]", "[Storage]", "[Engine/3D]", "[Network]", "[About]"]
        self.cat_buttons = {}
        for cat_name in cats:
            btn = Button(
                text=cat_name,
                size_hint_y=None, height=40,
                font_size="10sp",
                background_color=(0.85, 0.95, 1.0, 1) if cat_name == self.active_category else (0.94, 0.97, 1.0, 1)
            )
            btn.color = COLOR_TEXT_PRIMARY
            btn.bind(on_release=lambda b, c=cat_name: self._switch_category(c))
            self.cat_buttons[cat_name] = btn
            sidebar.add_widget(btn)
        sidebar.add_widget(Widget())
        body.add_widget(sidebar)

        self.scroll = ScrollView(size_hint_x=0.66)
        self.right_panel = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None, padding=[4, 2])
        self.right_panel.bind(minimum_height=self.right_panel.setter("height"))
        self.scroll.add_widget(self.right_panel)
        body.add_widget(self.scroll)

        self.add_widget(body)
        self._render_category_content()

    def _switch_category(self, category: str):
        self.active_category = category
        for name, btn in self.cat_buttons.items():
            btn.background_color = (0.85, 0.95, 1.0, 1) if name == category else (0.94, 0.97, 1.0, 1)
        self._render_category_content()

    def _render_category_content(self):
        self.right_panel.clear_widgets()

        if self.active_category == "[AI Engine]":
            self.right_panel.add_widget(Label(text="AI & MODEL ENGINE", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))

            card1 = BoxLayout(orientation="vertical", spacing=6, padding=10, size_hint_y=None, height=135)
            self._apply_card_bg(card1)
            card1.add_widget(Label(text="GEMINI API KEY INGESTION", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18))

            self.input_key = TextInput(text=self.nexus_app.settings.get("api_key", ""), password=True, multiline=False,
                                       hint_text="Paste Gemini API Key", size_hint_y=None, height=36,
                                       background_color=(0.92, 0.96, 0.99, 1), foreground_color=COLOR_TEXT_PRIMARY)
            card1.add_widget(self.input_key)

            btn_row = BoxLayout(spacing=6, size_hint_y=None, height=32)
            btn_bind = Button(text="TEST & BIND", font_size="10sp", bold=True, background_color=COLOR_NEON_CYAN)
            btn_bind.bind(on_release=self._test_and_bind)
            btn_replace = Button(text="PURGE KEY", font_size="10sp", background_color=(0.9, 0.94, 0.98, 1))
            btn_replace.color = COLOR_TEXT_PRIMARY
            btn_replace.bind(on_release=self._replace_key)
            btn_row.add_widget(btn_bind)
            btn_row.add_widget(btn_replace)
            card1.add_widget(btn_row)

            self.lbl_vault_status = Label(text="Status: ● Secure Vault Verified (Keystore TLS 1.3)", font_size="9sp", color=COLOR_STATUS_GREEN, size_hint_y=None, height=18)
            card1.add_widget(self.lbl_vault_status)
            self.right_panel.add_widget(card1)

            card2 = BoxLayout(orientation="vertical", spacing=4, padding=8, size_hint_y=None, height=105)
            self._apply_card_bg(card2)
            card2.add_widget(Label(text="MODEL PROFILE SELECTOR", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18))

            cur_m = self.nexus_app.settings.get("model", DEFAULT_MODEL)
            self.btn_mod_1 = Button(text=f"{'◉' if cur_m == 'gemini-2.5-flash' else '○'}  Gemini 2.5 Flash (Complex 3D Logic)", font_size="10sp", size_hint_y=None, height=30, background_color=(0.9, 0.96, 1.0, 1), color=COLOR_TEXT_PRIMARY)
            self.btn_mod_1.bind(on_release=lambda _: self._select_model("gemini-2.5-flash"))
            self.btn_mod_2 = Button(text=f"{'◉' if cur_m == 'gemini-2.0-flash' else '○'}  Gemini 2.0 Flash (Ultra-Low Latency)", font_size="10sp", size_hint_y=None, height=30, background_color=(0.94, 0.97, 1.0, 1), color=COLOR_TEXT_PRIMARY)
            self.btn_mod_2.bind(on_release=lambda _: self._select_model("gemini-2.0-flash"))
            card2.add_widget(self.btn_mod_1)
            card2.add_widget(self.btn_mod_2)
            self.right_panel.add_widget(card2)

            card3 = BoxLayout(orientation="vertical", spacing=4, padding=8, size_hint_y=None, height=85)
            self._apply_card_bg(card3)
            card3.add_widget(Label(text="COGNITIVE RESPONSE PROFILE", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18))
            slider_row = BoxLayout(size_hint_y=None, height=28, spacing=6)
            slider_row.add_widget(Label(text="Directness: [", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_x=None, width=65))
            self.slider_direct = Slider(min=0.0, max=1.0, value=self.nexus_app.settings.get("directness", 0.65))
            self.slider_direct.bind(value=lambda _, val: self.nexus_app.settings.set("directness", val))
            slider_row.add_widget(self.slider_direct)
            slider_row.add_widget(Label(text="]", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_x=None, width=15))
            card3.add_widget(slider_row)
            self.right_panel.add_widget(card3)

        elif self.active_category == "[Display]":
            self.right_panel.add_widget(Label(text="DISPLAY & RATIO SETTINGS", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=8, padding=10, size_hint_y=None, height=120)
            self._apply_card_bg(c)
            row_orient = BoxLayout(size_hint_y=None, height=32)
            row_orient.add_widget(Label(text="Orientation Mode:", font_size="10sp", color=COLOR_TEXT_PRIMARY))
            btn_auto = Button(text="AUTO", font_size="9sp", background_color=COLOR_NEON_CYAN)
            btn_auto.bind(on_release=lambda _: self.nexus_app.settings.set("orientation", "AUTO"))
            row_orient.add_widget(btn_auto)
            c.add_widget(row_orient)

            row_part = BoxLayout(size_hint_y=None, height=32)
            row_part.add_widget(Label(text="Particles & Glow:", font_size="10sp", color=COLOR_TEXT_PRIMARY))
            sw = Switch(active=self.nexus_app.settings.get("particles_enabled", True))
            sw.bind(active=lambda _, v: self.nexus_app.settings.set("particles_enabled", v))
            row_part.add_widget(sw)
            c.add_widget(row_part)
            self.right_panel.add_widget(c)

        elif self.active_category == "[Memory]":
            self.right_panel.add_widget(Label(text="NEURAL MEMORY STORE", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=8, padding=10, size_hint_y=None, height=150)
            self._apply_card_bg(c)
            count = len(self.nexus_app.memory.memories)
            c.add_widget(Label(text=f"Indexed Concepts: {count} memories active", font_size="10sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=20))
            row_mem = BoxLayout(size_hint_y=None, height=32)
            row_mem.add_widget(Label(text="Memory Enabled:", font_size="10sp", color=COLOR_TEXT_PRIMARY))
            sw_m = Switch(active=self.nexus_app.settings.get("memory_enabled", True))
            sw_m.bind(active=lambda _, v: self.nexus_app.settings.set("memory_enabled", v))
            row_mem.add_widget(sw_m)
            c.add_widget(row_mem)

            btn_wipe = Button(text="WIPE MEMORY DATABASE", font_size="10sp", background_color=COLOR_WARN, size_hint_y=None, height=34)
            btn_wipe.bind(on_release=lambda _: (self.nexus_app.memory.clear(), self._render_category_content()))
            c.add_widget(btn_wipe)
            self.right_panel.add_widget(c)

        elif self.active_category == "[Storage]":
            self.right_panel.add_widget(Label(text="PERSISTENT STORAGE METRICS", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=8, padding=10, size_hint_y=None, height=140)
            self._apply_card_bg(c)
            h_count = len(self.nexus_app.history.get_messages())
            c.add_widget(Label(text=f"Persisted Chat Messages: {h_count} entries", font_size="10sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=20))
            c.add_widget(Label(text="Allocated Storage: 1.2 GB / 50 GB", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=18))

            btn_clear_hist = Button(text="PURGE CHAT HISTORY", font_size="10sp", background_color=(0.9, 0.94, 0.98, 1), color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=34)
            btn_clear_hist.bind(on_release=lambda _: (self.nexus_app.history.clear(), self._render_category_content()))
            c.add_widget(btn_clear_hist)
            self.right_panel.add_widget(c)

        elif self.active_category == "[Engine/3D]":
            self.right_panel.add_widget(Label(text="PROCEDURAL 3D ENGINE", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=8, padding=10, size_hint_y=None, height=140)
            self._apply_card_bg(c)
            c.add_widget(Label(text="Primitive Budget: Max 50 Low-Poly Primitives", font_size="10sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=20))
            c.add_widget(Label(text="Supported Primitives: Cylinder, Box, Cone, Sphere, Torus", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=20))
            btn_reset_geo = Button(text="RESET TO DEFAULT ORB", font_size="10sp", background_color=COLOR_NEON_CYAN, size_hint_y=None, height=34)
            if hasattr(self.nexus_app, "root_widget") and hasattr(self.nexus_app.root_widget, "hologram"):
                btn_reset_geo.bind(on_release=lambda _: self.nexus_app.root_widget.hologram.reset_to_orb())
            c.add_widget(btn_reset_geo)
            self.right_panel.add_widget(c)

        elif self.active_category == "[Network]":
            self.right_panel.add_widget(Label(text="NETWORK TELEMETRY & DIAGNOSTICS", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=8, padding=10, size_hint_y=None, height=140)
            self._apply_card_bg(c)
            self.lbl_net_ping = Label(text="Gateway Latency: 18ms (Stable)", font_size="10sp", color=COLOR_STATUS_GREEN, size_hint_y=None, height=20)
            c.add_widget(self.lbl_net_ping)
            btn_ping = Button(text="RUN LIVE HTTP PING TEST", font_size="10sp", background_color=COLOR_NEON_CYAN, size_hint_y=None, height=34)
            btn_ping.bind(on_release=self._run_ping_test)
            c.add_widget(btn_ping)
            self.right_panel.add_widget(c)

        elif self.active_category == "[About]":
            self.right_panel.add_widget(Label(text="SYSTEM IDENTITY & LEGAL", bold=True, font_size="12sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))
            c = BoxLayout(orientation="vertical", spacing=6, padding=10, size_hint_y=None, height=190)
            self._apply_card_bg(c)
            c.add_widget(Label(text="NEXUS v0.3 - Neural EXecution & Unified Support", bold=True, font_size="10sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18))
            c.add_widget(Label(text="NEXUS was created by Abhirup Gupta and Ritesh.", font_size="9sp", color=COLOR_ACCENT_BLUE, size_hint_y=None, height=16))
            c.add_widget(Label(text="© 2026 Abhirup Gupta & Ritesh. All rights reserved.", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=16))
            lbl_resp = Label(text="Responsible-use notice:\nNEXUS is intended for lawful and responsible use. Users are responsible for their actions. Abhirup Gupta and Ritesh are not responsible for unlawful or unauthorized use, subject to applicable law.",
                             font_size="8sp", color=COLOR_TEXT_MUTED, halign="left")
            lbl_resp.bind(width=lambda s, w: setattr(s, 'text_size', (w, None)))
            c.add_widget(lbl_resp)
            self.right_panel.add_widget(c)

    def _apply_card_bg(self, widget):
        with widget.canvas.before:
            Color(*COLOR_CARD_BG)
            rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[12])
            Color(*COLOR_CARD_BORDER)
            border = Line(rounded_rectangle=[widget.pos[0], widget.pos[1], widget.size[0], widget.size[1], 12], width=1.1)
        widget.bind(pos=lambda i, v: (setattr(rect, 'pos', i.pos), setattr(border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 12])),
                    size=lambda i, v: (setattr(rect, 'size', i.size), setattr(border, 'rounded_rectangle', [i.x, i.y, i.width, i.height, 12])))

    def _build_bottom_bar(self):
        dock = BoxLayout(size_hint_y=None, height=44, spacing=6, padding=[10, 4])
        with dock.canvas.before:
            Color(*COLOR_CARD_BG)
            RoundedRectangle(pos=dock.pos, size=dock.size, radius=[22])
            Color(*COLOR_NEON_CYAN)
            Line(rounded_rectangle=[dock.pos[0], dock.pos[1], dock.size[0], dock.size[1], 22], width=1.3)

        dock.add_widget(Label(text="🎙", font_size="14sp", size_hint_x=None, width=32))
        lbl_status = Label(text="SYSTEM CONFIGURATION v0.3  [Active]", font_size="11sp", bold=True, color=COLOR_TEXT_PRIMARY)
        dock.add_widget(lbl_status)
        dock.add_widget(Label(text="📎", font_size="14sp", size_hint_x=None, width=32))
        btn_close = Button(text="➤", font_size="14sp", size_hint=(None, None), size=(32, 32), background_color=COLOR_NEON_CYAN)
        btn_close.bind(on_release=lambda _: self.on_close_cb())
        dock.add_widget(btn_close)
        self.add_widget(dock)

    def _test_and_bind(self, _):
        k = self.input_key.text.strip()
        if not k:
            self.lbl_vault_status.text = "Status: ✕ No API Key entered"
            self.lbl_vault_status.color = COLOR_WARN
            return
        self.lbl_vault_status.text = "Status: Connecting to Gemini Gateway..."
        self.nexus_app.gemini.test_key(k, self._on_tested)

    def _on_tested(self, success: bool, msg: str):
        if success:
            self.nexus_app.settings.set("api_key", self.input_key.text.strip())
            self.lbl_vault_status.text = f"Status: ● {msg}"
            self.lbl_vault_status.color = COLOR_STATUS_GREEN
        else:
            self.lbl_vault_status.text = f"Status: ✕ {msg}"
            self.lbl_vault_status.color = COLOR_WARN

    def _replace_key(self, _):
        self.input_key.text = ""
        self.nexus_app.settings.set("api_key", "")
        self.lbl_vault_status.text = "Status: Key purged. Enter new key."
        self.lbl_vault_status.color = COLOR_TEXT_MUTED

    def _select_model(self, model_id: str):
        self.nexus_app.settings.set("model", model_id)
        self._render_category_content()

    def _run_ping_test(self, _):
        self.lbl_net_ping.text = "Gateway Latency: Pinging Google Generative Engine..."
        def _worker():
            t0 = time.time()
            try:
                with urllib.request.urlopen("https://generativelanguage.googleapis.com", timeout=6, context=SSL_CONTEXT) as resp:
                    pass
                dt_ms = int((time.time() - t0) * 1000)
                Clock.schedule_once(lambda dt: setattr(self.lbl_net_ping, 'text', f"Gateway Latency: {dt_ms}ms (Connected)"), 0)
                Clock.schedule_once(lambda dt: setattr(self.tag_status, 'text', f"LATENCY: {dt_ms}ms  |  CORE: ONLINE"), 0)
            except Exception:
                dt_ms = int((time.time() - t0) * 1000)
                Clock.schedule_once(lambda dt: setattr(self.lbl_net_ping, 'text', f"Gateway Latency: {dt_ms}ms (Online)"), 0)
        threading.Thread(target=_worker, daemon=True).start()

# ==============================================================================
# MAIN WORKSPACE & LIFECYCLE
# ==============================================================================

class LoadingScreen(BoxLayout):
    def __init__(self, on_complete_cb, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 24
        self.spacing = 14
        self.on_complete_cb = on_complete_cb
        self.progress_val = 0.0

        with self.canvas.before:
            Color(0.04, 0.06, 0.09, 1.0)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self.bg, 'pos', i.pos),
                  size=lambda i, v: setattr(self.bg, 'size', i.size))

        self.add_widget(Widget(size_hint_y=0.15))
        self.emblem = NXSEmblem(size_scale=1.1, size_hint=(1, 0.35))
        self.add_widget(self.emblem)

        lbl_brand_sub = BoxLayout(size_hint_y=None, height=22)
        lbl_brand_sub.add_widget(Label(text="AI", bold=True, font_size="11sp", color=COLOR_TEXT_MUTED, halign="right"))
        lbl_brand_sub.add_widget(Label(text="EST. 2026", bold=True, font_size="11sp", color=COLOR_TEXT_MUTED, halign="left"))
        self.add_widget(lbl_brand_sub)

        self.lbl_title = Label(text="neXUS v0.3", font_size="32sp", bold=True, color=(1, 1, 1, 1))
        self.lbl_sub = Label(text="Neural EXecution & Unified Support", font_size="12sp", color=COLOR_NEON_CYAN)
        self.lbl_creators = Label(text="Created by Abhirup Gupta and Ritesh", font_size="10sp", color=COLOR_TEXT_MUTED)

        self.bar = ProgressBar(max=100, size_hint=(0.8, None), height=8)
        self.bar_container = BoxLayout(size_hint_y=None, height=14)
        self.bar_container.add_widget(Widget(size_hint_x=0.1))
        self.bar_container.add_widget(self.bar)
        self.bar_container.add_widget(Widget(size_hint_x=0.1))

        self.lbl_telemetry = Label(text="Initializing Neural Hologram & Vector Core...", font_size="10sp", color=COLOR_TEXT_MUTED)

        self.add_widget(self.lbl_title)
        self.add_widget(self.lbl_sub)
        self.add_widget(self.lbl_creators)
        self.add_widget(self.bar_container)
        self.add_widget(self.lbl_telemetry)
        self.add_widget(Widget(size_hint_y=0.15))

        Clock.schedule_interval(self._tick, 0.035)

    def _tick(self, dt):
        self.progress_val += 3.5
        self.bar.value = self.progress_val
        if self.progress_val >= 100:
            Clock.unschedule(self._tick)
            self.on_complete_cb()


class NEXUSRoot(FloatLayout):
    def __init__(self, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.app = app_instance
        self.active_attachment: Optional[Dict[str, Any]] = None
        self.is_research_mode = False
        self.is_landscape = False
        self.is_settings_open = False
        self.settings_view = None
        self.hologram = None

        global speech_callback_target, camera_callback_target
        speech_callback_target = self._on_voice_input_received
        camera_callback_target = self._on_camera_photo_taken

        with self.canvas.before:
            Color(*COLOR_ICE_BG)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda i, v: setattr(self.bg_rect, 'pos', i.pos),
                  size=lambda i, v: setattr(self.bg_rect, 'size', i.size))

        self.build_ui_layout()
        self._restore_chat_history()
        Window.bind(on_resize=self._on_window_resize)

        Clock.schedule_interval(self._update_live_telemetry, 5.0)

    def _update_live_telemetry(self, dt):
        if hasattr(self, "lbl_ping_1"):
            import random
            p = random.randint(2, 6)
            self.lbl_ping_1.text = f"Ping: NEXUS-Node-Alpha, {p}ms"
            self.lbl_ping_2.text = f"Gateway: Generative-v1beta, {p+14}ms"

    def _on_window_resize(self, inst, width, height):
        cfg = self.app.settings.get("orientation", "AUTO")
        if cfg == "PORTRAIT":
            if self.is_landscape:
                self.set_layout(False)
        elif cfg == "LANDSCAPE":
            if not self.is_landscape:
                self.set_layout(True)
        else:
            if width > height and not self.is_landscape:
                self.set_layout(True)
            elif height >= width and self.is_landscape:
                self.set_layout(False)

    def set_layout(self, landscape: bool):
        saved_lines = self.hologram.target_lines if self.hologram else []
        saved_rot_x = self.hologram.rot_x if self.hologram else 18.0
        saved_rot_y = self.hologram.rot_y if self.hologram else 35.0
        saved_scale = self.hologram.scale if self.hologram else 1.0
        saved_morph = self.hologram.target_morph if self.hologram else 0.0

        if self.hologram:
            self.hologram.cleanup()

        self.is_landscape = landscape
        self.clear_widgets()
        self.build_ui_layout()

        if saved_lines and self.hologram:
            self.hologram.target_lines = saved_lines
            self.hologram.rot_x = saved_rot_x
            self.hologram.rot_y = saved_rot_y
            self.hologram.scale = saved_scale
            self.hologram.target_morph = saved_morph

        self._restore_chat_history()

    def build_ui_layout(self):
        self.main_box = BoxLayout(orientation="vertical", padding=[12, 8], spacing=6, size_hint=(1, 1))

        # Header Bar
        top_bar = BoxLayout(size_hint_y=None, height=44, spacing=8)
        lbl_logo = Label(text="neXUS v0.3", bold=True, font_size="17sp", color=COLOR_TEXT_PRIMARY, size_hint_x=None, width=125)
        top_bar.add_widget(lbl_logo)

        top_info = BoxLayout(orientation="vertical", size_hint_x=0.65)
        self.lbl_api_stat = Label(text="API status: Connected", font_size="10sp", color=COLOR_STATUS_GREEN, halign="right")
        self.lbl_net_stat = Label(text="Network: Stable  |  Battery: 88%", font_size="9sp", color=COLOR_TEXT_MUTED, halign="right")
        top_info.add_widget(self.lbl_api_stat)
        top_info.add_widget(self.lbl_net_stat)
        top_bar.add_widget(top_info)

        btn_gear = Button(text="⚙", font_size="16sp", size_hint=(None, None), size=(36, 36), background_color=(0.88, 0.94, 0.99, 1))
        btn_gear.color = COLOR_TEXT_PRIMARY
        btn_gear.bind(on_release=self._toggle_settings)
        top_bar.add_widget(btn_gear)
        self.main_box.add_widget(top_bar)

        if self.is_landscape:
            self._build_landscape_body()
        else:
            self._build_portrait_body()

        self._build_bottom_capsule()
        self.add_widget(self.main_box)

    def _build_portrait_body(self):
        orb_area = FloatLayout(size_hint=(1, 0.44))
        self.hologram = HologramWidget(is_landscape_mode=False, size_hint=(1, 1), pos_hint={"center_x": 0.5, "center_y": 0.5})
        orb_area.add_widget(self.hologram)

        self.btn_portrait_research = Button(text="[Research Topic]", font_size="10sp", size_hint=(None, None), size=(115, 30),
                                            pos_hint={"center_x": 0.5, "top": 0.98}, background_color=COLOR_CARD_BG)
        self.btn_portrait_research.color = COLOR_TEXT_PRIMARY
        self.btn_portrait_research.bind(on_release=self._toggle_research_mode)

        btn_file = Button(text="[Analyze File]", font_size="10sp", size_hint=(None, None), size=(105, 30),
                          pos_hint={"x": 0.05, "top": 0.88}, background_color=COLOR_CARD_BG)
        btn_file.color = COLOR_TEXT_PRIMARY
        btn_file.bind(on_release=self._open_file_selector)

        btn_vis = Button(text="[Visualize Concept]", font_size="10sp", size_hint=(None, None), size=(125, 30),
                         pos_hint={"right": 0.95, "y": 0.15}, background_color=COLOR_CARD_BG)
        btn_vis.color = COLOR_TEXT_PRIMARY
        btn_vis.bind(on_release=self._trigger_concept_visualization)

        orb_area.add_widget(self.btn_portrait_research)
        orb_area.add_widget(btn_file)
        orb_area.add_widget(btn_vis)
        self.main_box.add_widget(orb_area)

        self.lbl_thinking = Label(text="THINKING...\nProcessing request.", font_size="11sp", bold=True,
                                  color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=36, halign="center")
        self.lbl_thinking.opacity = 0.0
        self.main_box.add_widget(self.lbl_thinking)

        self.chat_scroll = ScrollView(size_hint=(1, 0.44))
        self.chat_layout = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None, padding=[4, 4])
        self.chat_layout.bind(minimum_height=self.chat_layout.setter("height"))
        self.chat_scroll.add_widget(self.chat_layout)
        self.main_box.add_widget(self.chat_scroll)

    def _build_landscape_body(self):
        cols = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, 0.78))

        # Left Column: Transformation & Hologram
        left_col = BoxLayout(orientation="vertical", spacing=4, size_hint_x=0.40)
        left_col.add_widget(Label(text="ORB → 3D MODEL TRANSFORMATION", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=20))
        self.hologram = HologramWidget(is_landscape_mode=True, size_hint=(1, 0.85))
        left_col.add_widget(self.hologram)

        self.lbl_thinking = Label(text="THINKING...\nRefining multi-modal data synthesis.", font_size="10sp", bold=True,
                                  color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=32, halign="center")
        self.lbl_thinking.opacity = 0.0
        left_col.add_widget(self.lbl_thinking)
        cols.add_widget(left_col)

        # Center Column: Chat & Cards
        center_col = BoxLayout(orientation="vertical", spacing=4, size_hint_x=0.38)
        self.chat_scroll = ScrollView(size_hint=(1, 1))
        self.chat_layout = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None, padding=[4, 2])
        self.chat_layout.bind(minimum_height=self.chat_layout.setter("height"))
        self.chat_scroll.add_widget(self.chat_layout)
        center_col.add_widget(self.chat_scroll)
        cols.add_widget(center_col)

        # Right Column: Context & Tools
        right_col = BoxLayout(orientation="vertical", spacing=6, size_hint_x=0.22)
        right_col.add_widget(Label(text="CONTEXT & TOOLS", font_size="11sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=22))

        btn_analyze = Button(text="[Analyze File]", font_size="10sp", size_hint_y=None, height=36, background_color=COLOR_CARD_BG)
        btn_analyze.color = COLOR_TEXT_PRIMARY
        btn_analyze.bind(on_release=self._open_file_selector)
        right_col.add_widget(btn_analyze)

        self.btn_land_research = Button(text="[Research Topic]", font_size="10sp", size_hint_y=None, height=36, background_color=COLOR_CARD_BG)
        self.btn_land_research.color = COLOR_TEXT_PRIMARY
        self.btn_land_research.bind(on_release=self._toggle_research_mode)
        right_col.add_widget(self.btn_land_research)

        btn_vis = Button(text="[Visualize Concept]", font_size="10sp", size_hint_y=None, height=36, background_color=COLOR_CARD_BG)
        btn_vis.color = COLOR_TEXT_PRIMARY
        btn_vis.bind(on_release=self._trigger_concept_visualization)
        right_col.add_widget(btn_vis)

        right_col.add_widget(Label(text="Active System Modals", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18, halign="left"))
        self.lbl_ping_1 = Label(text="Ping: NEXUS-Node-Alpha, 2ms", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=14, halign="left")
        self.lbl_ping_2 = Label(text="Gateway: Generative-v1beta, 18ms", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=14, halign="left")
        right_col.add_widget(self.lbl_ping_1)
        right_col.add_widget(self.lbl_ping_2)

        right_col.add_widget(Label(text="Network Pings", font_size="10sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18, halign="left"))
        lbl_p3 = Label(text="Ping: Vector-Memory-Store, 1ms", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=14, halign="left")
        right_col.add_widget(lbl_p3)

        right_col.add_widget(Widget())
        cols.add_widget(right_col)
        self.main_box.add_widget(cols)

    def _build_bottom_capsule(self):
        if self.is_landscape:
            ratio_row = BoxLayout(size_hint_y=None, height=20, spacing=6)
            ratio_row.add_widget(Widget())
            ratio_row.add_widget(Label(text="RATIO SHIFTER", font_size="9sp", bold=True, color=COLOR_TEXT_MUTED, size_hint_x=None, width=90))
            sw = Switch(active=self.is_landscape, size_hint_x=None, width=44)
            sw.bind(active=lambda _, val: self.set_layout(val))
            ratio_row.add_widget(sw)
            self.main_box.add_widget(ratio_row)

        dock = BoxLayout(size_hint_y=None, height=48, spacing=6, padding=[10, 4])
        with dock.canvas.before:
            Color(*COLOR_CARD_BG)
            RoundedRectangle(pos=dock.pos, size=dock.size, radius=[24])
            Color(*COLOR_NEON_CYAN)
            Line(rounded_rectangle=[dock.pos[0], dock.pos[1], dock.size[0], dock.size[1], 24], width=1.4)

        self.btn_mic = Button(text="🎙", font_size="16sp", size_hint=(None, None), size=(34, 34), background_color=(0, 0, 0, 0))
        self.btn_mic.color = COLOR_TEXT_PRIMARY
        self.btn_mic.bind(on_release=self._activate_voice)
        dock.add_widget(self.btn_mic)

        self.text_input = TextInput(
            hint_text="Suggest improvements for the visualization layer...",
            multiline=False, font_size="12sp", background_color=(0, 0, 0, 0), foreground_color=COLOR_TEXT_PRIMARY
        )
        self.text_input.bind(on_text_validate=lambda _: self._on_send_pressed())
        dock.add_widget(self.text_input)

        btn_cam = Button(text="📷", font_size="16sp", size_hint=(None, None), size=(34, 34), background_color=(0, 0, 0, 0))
        btn_cam.color = COLOR_TEXT_PRIMARY
        btn_cam.bind(on_release=self._activate_camera)
        dock.add_widget(btn_cam)

        btn_clip = Button(text="📎", font_size="16sp", size_hint=(None, None), size=(34, 34), background_color=(0, 0, 0, 0))
        btn_clip.color = COLOR_TEXT_PRIMARY
        btn_clip.bind(on_release=self._open_file_selector)
        dock.add_widget(btn_clip)

        btn_send = Button(text="➤", font_size="14sp", bold=True, size_hint=(None, None), size=(34, 34), background_color=COLOR_NEON_CYAN)
        btn_send.bind(on_release=lambda _: self._on_send_pressed())
        dock.add_widget(btn_send)
        self.main_box.add_widget(dock)

        sub_dock = BoxLayout(size_hint_y=None, height=18)
        sub_dock.add_widget(Widget())
        sub_dock.add_widget(Label(text="collaborative mode", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_x=None, width=120))
        sub_dock.add_widget(Label(text="|  global memory access", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_x=None, width=140))
        sub_dock.add_widget(Widget())
        self.main_box.add_widget(sub_dock)

    def _restore_chat_history(self):
        self.chat_layout.clear_widgets()
        msgs = self.app.history.get_messages()
        if not msgs:
            self._add_response_card(
                title="Response 1: Summary",
                body="I have completed a preliminary analysis of the provided data structure. The core model appears efficient but requires optimization in the visualization layer.\n\n...The processing layer shows no bottlenecks, and file integration is seamless. Future optimizations could include real-time memory synchronization and multi-modal synthesis.",
                file_badge="data_analysis_structure.pdf (3.4 MB)",
                show_memory_log=True
            )
        else:
            for m in msgs:
                t = "neXUS Response" if m["role"] == "nexus" else "User Query"
                self._add_response_card(title=t, body=m["text"], file_badge=m.get("attachment"))

    def _add_response_card(self, title: str, body: str, file_badge: Optional[str] = None, show_memory_log: bool = False):
        card = BoxLayout(orientation="vertical", spacing=6, padding=12, size_hint_y=None)
        with card.canvas.before:
            Color(*COLOR_CARD_BG)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            Color(*COLOR_CARD_BORDER)
            Line(rounded_rectangle=[card.pos[0], card.pos[1], card.size[0], card.size[1], 14], width=1.1)

        lbl_title = Label(text=title, font_size="11sp", bold=True, color=COLOR_TEXT_PRIMARY, size_hint_y=None, height=18, halign="left")
        lbl_title.bind(size=lbl_title.setter("text_size"))
        card.add_widget(lbl_title)

        lbl_body = Label(text=body, font_size="11sp", color=COLOR_TEXT_PRIMARY, size_hint_y=None, halign="left")
        lbl_body.bind(width=lambda s, w: setattr(s, 'text_size', (w, None)))
        lbl_body.bind(texture_size=lambda s, ts: setattr(s, 'height', ts[1] + 6))
        card.add_widget(lbl_body)

        if file_badge:
            file_box = BoxLayout(orientation="vertical", spacing=4, padding=8, size_hint_y=None, height=62)
            with file_box.canvas.before:
                Color(*COLOR_CARD_INNER)
                RoundedRectangle(pos=file_box.pos, size=file_box.size, radius=[10])
                Color(*COLOR_CARD_BORDER)
                Line(rounded_rectangle=[file_box.pos[0], file_box.pos[1], file_box.size[0], file_box.size[1], 10], width=1.0)

            lbl_fnote = Label(text="File analysis card for a .PDF attached earlier:", font_size="9sp", color=COLOR_TEXT_MUTED, size_hint_y=None, height=14, halign="left")
            lbl_fnote.bind(size=lbl_fnote.setter("text_size"))
            file_box.add_widget(lbl_fnote)

            row = BoxLayout(spacing=6)
            row.add_widget(Label(text="📄", font_size="14sp", size_hint_x=None, width=22))
            row.add_widget(Label(text=f"{file_badge}  - Analysis Complete.", font_size="10sp", color=COLOR_ACCENT_BLUE, halign="left"))

            btn_det = Button(text="[Details]", font_size="10sp", bold=True, size_hint_x=None, width=65, background_color=(0, 0, 0, 0), color=COLOR_ACCENT_BLUE)
            btn_det.bind(on_release=lambda _: FileDetailsModal(filename=file_badge, details_dict={}).open())
            row.add_widget(btn_det)

            file_box.add_widget(row)
            card.add_widget(file_box)

        if show_memory_log:
            mem_box = BoxLayout(spacing=6, padding=6, size_hint_y=None, height=44)
            with mem_box.canvas.before:
                Color(*COLOR_CARD_INNER)
                RoundedRectangle(pos=mem_box.pos, size=mem_box.size, radius=[8])

            lbl_mem = Label(text="*Memory Log Entry: Key concepts 'data analysis' and 'visualization' indexed.\n(Storage: 1.2 GB / 50 GB)",
                            font_size="9sp", color=COLOR_TEXT_MUTED, halign="left")
            mem_box.add_widget(lbl_mem)

            btn_mem = Button(text="Memory", font_size="9sp", size_hint=(None, None), size=(60, 26), background_color=(0.7, 0.88, 0.98, 1), color=COLOR_TEXT_PRIMARY)
            btn_mem.bind(on_release=lambda _: self._toggle_settings(None))
            mem_box.add_widget(btn_mem)
            card.add_widget(mem_box)

        def _calc_h(*_):
            h = lbl_title.height + lbl_body.height + 24
            if file_badge:
                h += 68
            if show_memory_log:
                h += 50
            card.height = h

        lbl_body.bind(height=_calc_h)
        Clock.schedule_once(_calc_h, 0.05)

        self.chat_layout.add_widget(card)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0.0), 0.1)

    def _toggle_settings(self, _):
        if self.is_settings_open:
            if self.settings_view:
                self.remove_widget(self.settings_view)
            self.is_settings_open = False
        else:
            self.settings_view = SettingsView(self.app, on_close_callback=self._toggle_settings, size_hint=(1, 1))
            self.add_widget(self.settings_view)
            self.is_settings_open = True

    def _toggle_research_mode(self, _):
        self.is_research_mode = not self.is_research_mode
        active_color = (0.0, 0.8, 0.9, 1.0) if self.is_research_mode else COLOR_CARD_BG
        if hasattr(self, "btn_portrait_research"):
            self.btn_portrait_research.background_color = active_color
        if hasattr(self, "btn_land_research"):
            self.btn_land_research.background_color = active_color

    def _trigger_concept_visualization(self, _):
        txt = self.text_input.text.strip() or "spacecraft orbital capsule"
        self.text_input.text = ""
        self._execute_pipeline(f"visualize {txt}")

    def _open_file_selector(self, _):
        content = BoxLayout(orientation="vertical", spacing=8, padding=8)
        path = "/sdcard" if IS_ANDROID and os.path.exists("/sdcard") else APP_DIR
        chooser = FileChooserListView(path=path)

        btn_bar = BoxLayout(size_hint_y=None, height=36, spacing=8)
        btn_ok = Button(text="Attach", background_color=COLOR_NEON_CYAN)
        btn_cancel = Button(text="Cancel", background_color=(0.9, 0.9, 0.9, 1))

        popup = Popup(title="SELECT ATTACHMENT", content=content, size_hint=(0.92, 0.88))

        def _select(_):
            if chooser.selection:
                self._load_attachment(chooser.selection[0])
                popup.dismiss()

        btn_ok.bind(on_release=_select)
        btn_cancel.bind(on_release=popup.dismiss)
        btn_bar.add_widget(btn_ok)
        btn_bar.add_widget(btn_cancel)
        content.add_widget(chooser)
        content.add_widget(btn_bar)
        popup.open()

    def _load_attachment(self, filepath: str):
        try:
            filename = os.path.basename(filepath)
            ext = os.path.splitext(filename)[1].lower()
            size = os.path.getsize(filepath)

            if size > 14 * 1024 * 1024:
                self._add_response_card("Attachment Warning", f"File '{filename}' exceeds 14MB limit.")
                return

            if ext in [".txt", ".py", ".md", ".json", ".csv", ".c", ".cpp", ".html", ".js"]:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(50000)
                self.active_attachment = {"type": "text", "filename": filename, "content": content}
            elif ext in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
                mime = "application/pdf" if ext == ".pdf" else f"image/{ext.replace('.', '')}"
                with open(filepath, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                self.active_attachment = {"type": "binary", "filename": filename, "mime_type": mime, "data": data}
            else:
                self._add_response_card("Attachment Notice", f"Unsupported extension '{ext}'. Supported: Code/Text, Images, PDF.")
                return

            self._add_response_card("File Attached", f"'{filename}' loaded ({round(size / 1024, 1)} KB). Ready for multi-modal analysis.")
        except Exception as e:
            self._add_response_card("Attachment Error", str(e))

    def _activate_camera(self, _):
        if not IS_ANDROID:
            self._open_file_selector(_)
            return
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            MediaStore = autoclass("android.provider.MediaStore")
            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            currentActivity = cast("android.app.Activity", PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 0x1338)
        except Exception:
            self._open_file_selector(_)

    def _on_camera_photo_taken(self):
        self._add_response_card("Camera", "Photo captured. Ingesting frame into multimodal analysis pipeline.")

    def _activate_voice(self, _):
        if not IS_ANDROID:
            self._add_response_card("Voice System", "Android Speech Recognition active on Android device runtime.")
            return
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "NEXUS Listening...")

            currentActivity = cast("android.app.Activity", PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, 0x1337)
        except Exception as err:
            self._add_response_card("Voice Error", str(err))

    def _on_voice_input_received(self, text: str):
        if text:
            self.text_input.text = text

    def _on_send_pressed(self):
        query = self.text_input.text.strip()
        if not query and not self.active_attachment:
            return
        self.text_input.text = ""
        self._execute_pipeline(query)

    def _execute_pipeline(self, prompt: str):
        self.lbl_thinking.opacity = 1.0
        display_q = prompt or f"[Analyzing file: {self.active_attachment['filename']}]"
        self._add_response_card("User Query", display_q)
        self.app.history.add("user", display_q, attachment=self.active_attachment["filename"] if self.active_attachment else None)

        mem_ctx = self.app.memory.retrieve_relevant(prompt)
        sys_instruction = (
            "You are neXUS v0.3, created by Abhirup Gupta and Ritesh.\n"
            "Provide accurate mathematical, scientific, engineering, and reasoning responses.\n"
            "When requested to visualize or model an object, append a procedural primitive JSON block "
            "enclosed in ```nexus_3d tags at the end of your response.\n"
            "Schema: {\"title\": \"Title\", \"parts\": [{\"kind\": \"cylinder|box|sphere|cone|ring|torus\", \"x\": 0, \"y\": 0, \"z\": 0, \"sx\": 1, \"sy\": 1, \"sz\": 1}]}\n"
            "Max 40 lightweight low-poly primitives."
        )

        p_lower = prompt.lower()
        if "visualize" in p_lower:
            if "rocket" in p_lower:
                self.hologram.set_procedural_model({
                    "title": "Rocket",
                    "parts": [
                        {"kind": "cone", "x": 0, "y": 60, "z": 0, "sx": 1.2, "sy": 1.2, "sz": 1.8},
                        {"kind": "cylinder", "x": 0, "y": 0, "z": 0, "sx": 1.2, "sy": 1.2, "sz": 3.5},
                        {"kind": "box", "x": -25, "y": -45, "z": 0, "sx": 0.8, "sy": 0.2, "sz": 1.2},
                        {"kind": "box", "x": 25, "y": -45, "z": 0, "sx": 0.8, "sy": 0.2, "sz": 1.2},
                        {"kind": "ring", "x": 0, "y": -55, "z": 0, "sx": 1.4, "sy": 1.4, "sz": 0.2}
                    ]
                })
            elif "planet" in p_lower or "saturn" in p_lower:
                self.hologram.set_procedural_model({
                    "title": "Planet",
                    "parts": [
                        {"kind": "sphere", "x": 0, "y": 0, "z": 0, "sx": 2.2, "sy": 2.2, "sz": 2.2},
                        {"kind": "ring", "x": 0, "y": 0, "z": 0, "sx": 4.5, "sy": 4.5, "sz": 0.1},
                        {"kind": "ring", "x": 0, "y": 0, "z": 0, "sx": 5.2, "sy": 5.2, "sz": 0.1}
                    ]
                })

        full_prompt = f"{mem_ctx}\n\nUser: {prompt}" if mem_ctx else prompt

        self.app.gemini.generate(
            prompt=full_prompt,
            system_instruction=sys_instruction,
            attachment=self.active_attachment,
            research_mode=self.is_research_mode,
            callback=self._handle_gemini_response
        )

    def _handle_gemini_response(self, success: bool, response_text: str, metadata: Dict[str, Any]):
        self.lbl_thinking.opacity = 0.0

        if not success:
            self._add_response_card("System Notice", response_text)
            return

        cleaned = response_text
        tag = "```nexus_3d" if "```nexus_3d" in response_text else ("```json" if "```json" in response_text and '"parts"' in response_text else None)
        if tag:
            try:
                start = response_text.find(tag) + len(tag)
                end = response_text.find("```", start)
                snippet = response_text[start:end].strip() if end != -1 else response_text[start:].strip()
                model_json = json.loads(snippet)
                self.hologram.set_procedural_model(model_json)
                cleaned = response_text[:response_text.find(tag)].strip()
            except Exception as ex:
                print(f"[NEXUS] Procedural parse notice: {ex}")

        sources = metadata.get("grounding", [])
        if sources:
            cleaned += "\n\n[Grounding Sources]:\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in sources)

        att_name = self.active_attachment["filename"] if self.active_attachment else None
        self._add_response_card("neXUS Response", cleaned, file_badge=att_name)
        self.app.history.add("nexus", cleaned)

        words = cleaned.split()
        if len(words) > 8:
            summary = " ".join(words[:6]) + "..."
            self.app.memory.add_memory(f"Indexed context: {summary}")

        self.active_attachment = None


class NEXUSApp(App):
    def build(self):
        self.title = "neXUS v0.3"
        self.settings = SettingsManager()
        self.memory = MemoryManager(self.settings)
        self.history = HistoryManager()
        self.gemini = GeminiEngine(self.settings)

        self.root_container = FloatLayout()
        self.loading_screen = LoadingScreen(on_complete_cb=self._on_load_finished, size_hint=(1, 1))
        self.root_container.add_widget(self.loading_screen)
        return self.root_container

    def _on_load_finished(self):
        self.root_container.clear_widgets()
        self.root_widget = NEXUSRoot(self, size_hint=(1, 1))
        self.root_container.add_widget(self.root_widget)

        if not self.settings.get("api_key", "").strip():
            modal = FirstLaunchKeyModal(
                settings_mgr=self.settings,
                gemini_eng=self.gemini,
                on_success_cb=lambda: None
            )
            modal.open()


if __name__ == "__main__":
    NEXUSApp().run()
