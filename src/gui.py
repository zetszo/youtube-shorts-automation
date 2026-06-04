import os
import sys
import json
import random
import threading
import subprocess
import time
import tempfile
import urllib.request
import traceback
from datetime import datetime
from io import BytesIO

import customtkinter as ctk
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GROQ_API_KEY, PEXELS_API_KEY, TTS_VOICE, TTS_RATE, TOPICS_ARABIC, VIDEO_WIDTH, VIDEO_HEIGHT
import script_gen
import voiceover
import footage
import video_editor
import uploader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TTS_VOICES = [
    "ar-EG-ShakirNeural",
    "ar-SA-HamedNeural",
    "ar-QA-AmalNeural",
    "ar-AE-FatimaNeural",
    "ar-SA-ZariyahNeural",
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("\u0645\u0646\u0634\u0626 \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0627\u0644\u0642\u0635\u0635 \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a\u0629")
        self.geometry("1400x900")
        self.minsize(1200, 750)

        self.script_data = None
        self.footage_clips = []
        self.generated_video = None
        self.custom_clips = []
        self.selected_footage = []
        self.running = False

        self._build_ui()

    # ─── UI ───

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main = ctk.CTkFrame(self)
        main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)

        left = ctk.CTkFrame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_rowconfigure(1, weight=1)
        self._build_left(left)

        right = ctk.CTkFrame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_rowconfigure(2, weight=1)
        self._build_right(right)

        bottom = ctk.CTkFrame(self)
        bottom.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._build_bottom(bottom)

    def _build_left(self, parent):
        # Story frame
        sf = ctk.CTkFrame(parent)
        sf.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        sf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sf, text="\u0627\u0644\u0642\u0635\u0629", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        self.story_mode = ctk.StringVar(value="preset")
        ctk.CTkRadioButton(sf, text="\u0642\u0635\u0629 \u062c\u0627\u0647\u0632\u0629", variable=self.story_mode, value="preset", command=self._toggle_story_mode).grid(row=1, column=0, sticky="w", padx=5)
        ctk.CTkRadioButton(sf, text="\u0643\u062a\u0627\u0628\u0629 \u0645\u062e\u0635\u0635\u0629", variable=self.story_mode, value="custom", command=self._toggle_story_mode).grid(row=1, column=1, sticky="w", padx=5)

        self.story_dropdown = ctk.CTkOptionMenu(sf, values=[t for _, t in TOPICS_ARABIC], command=self._on_story_select, width=400)
        self.story_dropdown.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        self.story_text = ctk.CTkTextbox(sf, height=220, wrap="word")
        self.story_text.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        self.story_text.insert("0.0", "\u0627\u0643\u062a\u0628 \u0627\u0644\u0642\u0635\u0629 \u0647\u0646\u0627...")
        self.story_text.configure(state="disabled")

        sw = ctk.CTkFrame(sf)
        sw.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        ctk.CTkLabel(sw, text="\u0639\u062f\u062f \u0627\u0644\u0643\u0644\u0645\u0627\u062a:").pack(side="left", padx=2)
        self.word_count_lbl = ctk.CTkLabel(sw, text="0")
        self.word_count_lbl.pack(side="left", padx=2)
        ctk.CTkButton(sw, text="\u0645\u0639\u0627\u064a\u0646\u0629 \u0627\u0644\u0646\u0635", command=self._preview_text, width=120).pack(side="right", padx=2)

        # Audio frame
        af = ctk.CTkFrame(parent)
        af.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        af.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(af, text="\u0627\u0644\u0635\u0648\u062a", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=5, pady=2)

        ctk.CTkLabel(af, text="\u0627\u0644\u0635\u0648\u062a:").grid(row=1, column=0, sticky="w", padx=5)
        self.voice_dropdown = ctk.CTkOptionMenu(af, values=TTS_VOICES, width=250)
        self.voice_dropdown.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)

        ctk.CTkLabel(af, text="\u0627\u0644\u0633\u0631\u0639\u0629:").grid(row=2, column=0, sticky="w", padx=5)
        self.speed_slider = ctk.CTkSlider(af, from_=-30, to=30, number_of_steps=12, command=self._on_speed_change, width=200)
        self.speed_slider.set(0)
        self.speed_slider.grid(row=2, column=1, sticky="w", padx=5)
        self.speed_lbl = ctk.CTkLabel(af, text="+0%")
        self.speed_lbl.grid(row=2, column=2, sticky="w", padx=2)

        btnf = ctk.CTkFrame(af)
        btnf.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        self.gen_audio_btn = ctk.CTkButton(btnf, text="\u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0635\u0648\u062a", command=self._generate_audio, width=140)
        self.gen_audio_btn.pack(side="left", padx=2)
        self.play_audio_btn = ctk.CTkButton(btnf, text="\u25b6 \u0645\u0639\u0627\u064a\u0646\u0629 \u0627\u0644\u0635\u0648\u062a", command=self._play_audio, width=140, state="disabled")
        self.play_audio_btn.pack(side="left", padx=2)
        self.audio_status = ctk.CTkLabel(btnf, text="")
        self.audio_status.pack(side="left", padx=10)

        # Karaoke frame
        kf = ctk.CTkFrame(parent)
        kf.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        kf.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(kf, text="\u0627\u0644\u0643\u0627\u0631\u064a\u0648\u0643\u064a (\u0627\u0644\u0646\u0635)", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=2)

        self.karaoke_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(kf, text="\u062a\u0634\u063a\u064a\u0644 \u0627\u0644\u0643\u0627\u0631\u064a\u0648\u0643\u064a", variable=self.karaoke_var).grid(row=1, column=0, sticky="w", padx=5)

        ctk.CTkLabel(kf, text="\u062d\u062c\u0645 \u0627\u0644\u062e\u0637:").grid(row=2, column=0, sticky="w", padx=5)
        self.font_size_var = ctk.IntVar(value=200)
        fs_frame = ctk.CTkFrame(kf, fg_color="transparent")
        fs_frame.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5)
        ctk.CTkSlider(fs_frame, from_=100, to=300, variable=self.font_size_var, width=150).pack(side="left", padx=2)
        self.fs_lbl = ctk.CTkLabel(fs_frame, text="200")
        self.fs_lbl.pack(side="left", padx=2)
        self.font_size_var.trace_add("write", lambda *a: self.fs_lbl.configure(text=str(self.font_size_var.get())))

        ctk.CTkLabel(kf, text="\u0644\u0648\u0646 \u0627\u0644\u062a\u0645\u064a\u064a\u0632:").grid(row=3, column=0, sticky="w", padx=5)
        self.highlight_color = ctk.CTkOptionMenu(kf, values=["\u0623\u0635\u0641\u0631", "\u0628\u0631\u062a\u0642\u0627\u0644\u064a", "\u0623\u062e\u0636\u0631", "\u0623\u0632\u0631\u0642", "\u0623\u062d\u0645\u0631"], width=120)
        self.highlight_color.grid(row=3, column=1, sticky="w", padx=5)
        self.highlight_color.set("\u0623\u0635\u0641\u0631")

    def _build_right(self, parent):
        ctk.CTkLabel(parent, text="\u0627\u0644\u062e\u0644\u0641\u064a\u0627\u062a", font=("Arial", 16, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=2)

        sf = ctk.CTkFrame(parent)
        sf.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
        sf.grid_columnconfigure(1, weight=1)
        self.footage_search_entry = ctk.CTkEntry(sf, placeholder_text="\u0628\u062d\u062b \u0641\u064a Pexels...")
        self.footage_search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(sf, text="\u0628\u062d\u062b", command=self._search_footage, width=60).grid(row=0, column=1, padx=2)
        ctk.CTkButton(sf, text="\u062a\u062d\u0645\u064a\u0644 \u0645\u0646 \u062c\u0647\u0627\u0632\u064a", command=self._upload_footage).grid(row=0, column=2, padx=2)

        self.footage_canvas = ctk.CTkScrollableFrame(parent, height=300)
        self.footage_canvas.grid(row=2, column=0, sticky="nsew", padx=5, pady=2)
        self.footage_thumbs = []

        ff = ctk.CTkFrame(parent)
        ff.grid(row=3, column=0, sticky="ew", padx=5, pady=2)
        ctk.CTkLabel(ff, text="\u0627\u0644\u0645\u062e\u062a\u0627\u0631:").pack(side="left", padx=2)
        self.footage_count_lbl = ctk.CTkLabel(ff, text="0")
        self.footage_count_lbl.pack(side="left", padx=2)
        ctk.CTkButton(ff, text="\u062a\u0641\u0631\u064a\u063a \u0627\u0644\u0643\u0644", command=self._clear_footage, width=80).pack(side="right", padx=2)

        # YouTube frame
        yf = ctk.CTkFrame(parent)
        yf.grid(row=4, column=0, sticky="ew", padx=5, pady=(10, 0))
        yf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(yf, text="\u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(yf, text="\u0627\u0644\u0639\u0646\u0648\u0627\u0646:").grid(row=1, column=0, sticky="w", padx=5)
        self.yt_title = ctk.CTkEntry(yf, placeholder_text="\u0639\u0646\u0648\u0627\u0646 \u0627\u0644\u0641\u064a\u062f\u064a\u0648")
        self.yt_title.grid(row=1, column=1, sticky="ew", padx=5)
        ctk.CTkLabel(yf, text="\u0627\u0644\u0648\u0635\u0641:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.yt_desc = ctk.CTkTextbox(yf, height=60)
        self.yt_desc.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

    def _build_bottom(self, parent):
        parent.grid_columnconfigure(3, weight=1)
        self.progress = ctk.CTkProgressBar(parent, width=300)
        self.progress.grid(row=0, column=0, padx=5, pady=5)
        self.progress.set(0)
        self.status_lbl = ctk.CTkLabel(parent, text="\u062c\u0627\u0647\u0632", width=200, anchor="w")
        self.status_lbl.grid(row=0, column=1, padx=5)
        self.generate_btn = ctk.CTkButton(parent, text="\ud83d\udd03 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0641\u064a\u062f\u064a\u0648", command=self._generate_video, fg_color="#1a73e8", width=140)
        self.generate_btn.grid(row=0, column=2, padx=5)
        self.preview_video_btn = ctk.CTkButton(parent, text="\u25b6 \u0645\u0639\u0627\u064a\u0646\u0629 \u0627\u0644\u0641\u064a\u062f\u064a\u0648", command=self._preview_video, state="disabled", width=140)
        self.preview_video_btn.grid(row=0, column=3, padx=5)
        self.upload_btn = ctk.CTkButton(parent, text="\ud83d\udce4 \u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628", command=self._upload_video, state="disabled", fg_color="#c5221f", width=140)
        self.upload_btn.grid(row=0, column=4, padx=5)

    # ─── Story ───

    def _toggle_story_mode(self):
        if self.story_mode.get() == "preset":
            self.story_dropdown.configure(state="normal")
            self.story_text.configure(state="disabled")
        else:
            self.story_dropdown.configure(state="disabled")
            self.story_text.configure(state="normal")
            self.story_text.delete("0.0", "end")
            self._update_word_count()

    def _on_story_select(self, choice):
        self.story_text.configure(state="normal")
        self.story_text.delete("0.0", "end")
        # Placeholder — story gets generated later
        self.story_text.insert("0.0", "\u062a\u0645 \u0627\u062e\u062a\u064a\u0627\u0631: " + choice)
        self.story_text.configure(state="disabled")
        self._update_word_count()

    def _preview_text(self):
        text = self._get_story_text()
        if not text or len(text) < 10:
            self.status_lbl.configure(text="\u0627\u0644\u0642\u0635\u0629 \u0641\u0627\u0631\u063a\u0629!")
            return
        try:
            path = os.path.join(tempfile.gettempdir(), "story_preview.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.startfile(path)
        except Exception:
            pass

    def _get_story_text(self):
        if self.story_mode.get() == "preset":
            return None
        return self.story_text.get("0.0", "end").strip()

    def _update_word_count(self):
        text = self._get_story_text()
        if text:
            cnt = len(text.split())
        else:
            cnt = 0
        self.word_count_lbl.configure(text=str(cnt))

    # ─── Audio ───

    def _on_speed_change(self, val):
        self.speed_lbl.configure(text=f"{int(val):+d}%")

    def _generate_audio(self):
        if self.running:
            return

        story_text = self._get_story_text()
        if not story_text:
            # Use preset topic text
            story_text = self.story_dropdown.get()
            if not story_text:
                self.status_lbl.configure(text="\u0627\u062e\u062a\u0631 \u0642\u0635\u0629 \u0623\u0648\u0644\u0627\u064b!")
                return

        self.running = True
        self.gen_audio_btn.configure(state="disabled", text="\u062c\u0627\u0631...")
        self.status_lbl.configure(text="\u062c\u0627\u0631 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0635\u0648\u062a...")
        self.progress.set(0)

        def task():
            voice = self.voice_dropdown.get()
            speed = f"{int(self.speed_slider.get()):+d}%"
            self.script_data = {"story": story_text}

            async def _run():
                import edge_tts
                from config import TTS_VOICE
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(OUTPUT_DIR, "audio", f"audio_{ts}_ar.mp3")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                communicate = edge_tts.Communicate(story_text, voice, rate=speed, boundary="WordBoundary")
                words = []
                with open(path, "wb") as f:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            f.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":
                            offset = chunk.get("offset", 0)
                            duration = chunk.get("duration", 0)
                            wtext = chunk.get("text", "").strip()
                            if wtext:
                                words.append({
                                    "text": wtext,
                                    "start": offset / 10000000,
                                    "end": (offset + duration) / 10000000,
                                })
                self.script_data["word_timings"] = words
                self.script_data["audio_file"] = path

            import asyncio
            asyncio.run(_run())
            self.after(0, self._on_audio_done)

        threading.Thread(target=task, daemon=True).start()

    def _on_audio_done(self):
        self.running = False
        self.gen_audio_btn.configure(state="normal", text="\u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0635\u0648\u062a")
        if self.script_data and self.script_data.get("audio_file"):
            self.play_audio_btn.configure(state="normal")
            wc = len(self.script_data.get("word_timings", []))
            self.audio_status.configure(text=f"\u2713 {wc} \u0643\u0644\u0645\u0629 \u0645\u0648\u0642\u0651\u062a\u0629")
            self.status_lbl.configure(text="\u0627\u0644\u0635\u0648\u062a \u062c\u0627\u0647\u0632")
        else:
            self.audio_status.configure(text="\u2717 \u0641\u0634\u0644")
            self.status_lbl.configure(text="\u0641\u0634\u0644 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0635\u0648\u062a")
        self.progress.set(1)

    def _play_audio(self):
        if self.script_data and self.script_data.get("audio_file"):
            path = self.script_data["audio_file"]
            if os.path.exists(path):
                try:
                    os.startfile(path)
                except Exception:
                    subprocess.Popen(["start", path], shell=True)

    # ─── Footage ───

    def _search_footage(self):
        query = self.footage_search_entry.get().strip()
        if not query:
            self.status_lbl.configure(text="\u0627\u062f\u062e\u0644 \u0643\u0644\u0645\u0629 \u0628\u062d\u062b!")
            return
        self.status_lbl.configure(text="\u062c\u0627\u0631 \u0627\u0644\u0628\u062d\u062b...")
        for w in self.footage_thumbs:
            w.destroy()
        self.footage_thumbs.clear()

        def task():
            results = footage._search_pexels(query)
            self.after(0, lambda: self._show_footage_results(results, query))

        threading.Thread(target=task, daemon=True).start()

    def _show_footage_results(self, results, query):
        if not results:
            self.status_lbl.configure(text="\u0644\u0627 \u062a\u0648\u062c\u062f \u0646\u062a\u0627\u0626\u062c")
            self.footage_search_entry.delete(0, "end")
            self.footage_search_entry.insert(0, f"{query} (0)")
            return
        for r in results[:12]:
            f = ctk.CTkFrame(self.footage_canvas, width=160, height=120)
            f.pack(side="left", padx=4, pady=4)
            f.pack_propagate(False)
            lbl = ctk.CTkLabel(f, text=f"\u2b07 {r['duration']}\u062b", font=("Arial", 10))
            lbl.pack(pady=2)
            btn = ctk.CTkButton(f, text="\u062a\u062d\u0645\u064a\u0644", command=lambda r=r: self._download_footage(r), width=80, height=25)
            btn.pack(pady=2)
            self.footage_thumbs.append(f)
        self.status_lbl.configure(text=f"{len(results)} \u0646\u062a\u064a\u062c\u0629")
        self.footage_search_entry.delete(0, "end")
        self.footage_search_entry.insert(0, f"{query} ({len(results)})")

    def _download_footage(self, item):
        self.status_lbl.configure(text=f"\u062c\u0627\u0631 \u062a\u062d\u0645\u064a\u0644 {item['id']}...")

        def task():
            clip = footage._download_video(item)
            if clip:
                self.custom_clips.append(clip)
                self.after(0, self._update_footage_count)
            self.after(0, lambda: self.status_lbl.configure(text=f"\u062a\u0645 \u062a\u062d\u0645\u064a\u0644 {len(self.custom_clips)}"))

        threading.Thread(target=task, daemon=True).start()

    def _upload_footage(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="\u0627\u062e\u062a\u0631 \u0645\u0642\u0627\u0637\u0639 \u0641\u064a\u062f\u064a\u0648",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        for path in files:
            if os.path.exists(path):
                import mimetypes
                self.custom_clips.append({"path": path, "duration": 10, "keyword": os.path.basename(path)})
        self._update_footage_count()
        self.status_lbl.configure(text=f"\u062a\u0645 \u0625\u0636\u0627\u0641\u0629 {len(files)} \u0645\u0642\u0637\u0639")

    def _update_footage_count(self):
        total = len(self.custom_clips) + len(self.selected_footage)
        self.footage_count_lbl.configure(text=str(total))

    def _clear_footage(self):
        self.custom_clips.clear()
        self.selected_footage.clear()
        self._update_footage_count()
        for w in self.footage_thumbs:
            w.destroy()
        self.footage_thumbs.clear()
        self.status_lbl.configure(text="\u062a\u0645 \u062a\u0641\u0631\u064a\u063a \u0627\u0644\u062e\u0644\u0641\u064a\u0627\u062a")

    # ─── Generate ───

    def _generate_video(self):
        if self.running:
            return
        self.running = True
        self.generate_btn.configure(state="disabled", text="\u062c\u0627\u0631...")
        self.status_lbl.configure(text="\u062c\u0627\u0631 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0641\u064a\u062f\u064a\u0648...")
        self.progress.set(0)

        # Prepare script_data
        if not self.script_data:
            self.script_data = {}
        story_text = self._get_story_text()
        if story_text:
            self.script_data["story"] = story_text
        elif self.story_dropdown.get():
            self.script_data["story"] = self.story_dropdown.get()
        else:
            self.status_lbl.configure(text="\u0627\u062e\u062a\u0631 \u0642\u0635\u0629!")
            self.running = False
            self.generate_btn.configure(state="normal", text="\ud83d\udd03 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0641\u064a\u062f\u064a\u0648")
            return

        def task():
            clips = self.custom_clips[:]
            if not clips:
                from footage import SAFE_QUERIES, _search_pexels, _download_video
                for q in random.sample(SAFE_QUERIES, min(6, len(SAFE_QUERIES))):
                    results = _search_pexels(q)
                    for r in results[:2]:
                        clip = _download_video(r)
                        if clip:
                            clips.append(clip)

            try:
                video_editor.EXPORT_FPS = 30
                out = video_editor.create_video(self.script_data, clips)
                self.generated_video = out
                self.after(0, self._on_video_done)
            except Exception as e:
                err = traceback.format_exc()
                self.after(0, lambda: self._on_video_error(e, err))

        threading.Thread(target=task, daemon=True).start()

    def _on_video_done(self):
        self.running = False
        self.generate_btn.configure(state="normal", text="\ud83d\udd03 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0641\u064a\u062f\u064a\u0648")
        self.preview_video_btn.configure(state="normal")
        self.upload_btn.configure(state="normal")
        self.progress.set(1)
        size_mb = os.path.getsize(self.generated_video) / 1048576
        self.status_lbl.configure(text=f"\u2713 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u062c\u0627\u0647\u0632 ({size_mb:.1f} MB)")

    def _on_video_error(self, err, tb):
        self.running = False
        self.generate_btn.configure(state="normal", text="\ud83d\udd03 \u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0641\u064a\u062f\u064a\u0648")
        self.status_lbl.configure(text=f"\u2717 {err[:80]}")
        self.progress.set(0)

    def _preview_video(self):
        if self.generated_video and os.path.exists(self.generated_video):
            try:
                os.startfile(self.generated_video)
            except Exception:
                subprocess.Popen(["start", self.generated_video], shell=True)

    # ─── Upload ───

    def _upload_video(self):
        if self.running or not self.generated_video:
            return
        self.running = True
        self.upload_btn.configure(state="disabled", text="\u062c\u0627\u0631 \u0627\u0644\u0631\u0641\u0639...")
        self.status_lbl.configure(text="\u062c\u0627\u0631 \u0627\u0644\u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628...")

        if not self.script_data:
            self.script_data = {}
        self.script_data["video_file"] = self.generated_video
        title = self.yt_title.get().strip() or self.story_dropdown.get() or "\u0642\u0635\u0629 \u0625\u0633\u0644\u0627\u0645\u064a\u0629"
        desc = self.yt_desc.get("0.0", "end").strip()
        self.script_data["title"] = title
        self.script_data["description"] = desc

        def task():
            try:
                url = uploader.upload_video(self.script_data)
                self.after(0, lambda: self._on_upload_done(url))
            except Exception as e:
                err = traceback.format_exc()
                self.after(0, lambda: self._on_upload_error(e, err))

        threading.Thread(target=task, daemon=True).start()

    def _on_upload_done(self, url):
        self.running = False
        self.upload_btn.configure(state="normal", text="\ud83d\udce4 \u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628")
        self.status_lbl.configure(text=f"\u2713 \u062a\u0645 \u0627\u0644\u0631\u0641\u0639: {url}")

    def _on_upload_error(self, err, tb):
        self.running = False
        self.upload_btn.configure(state="normal", text="\ud83d\udce4 \u0631\u0641\u0639 \u0644\u0644\u064a\u0648\u062a\u064a\u0648\u0628")
        self.status_lbl.configure(text=f"\u2717 \u0641\u0634\u0644 \u0627\u0644\u0631\u0641\u0639: {err[:80]}")
        self.progress.set(0)


if __name__ == "__main__":
    app = App()
    app.mainloop()
