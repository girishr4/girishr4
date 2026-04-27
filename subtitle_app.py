import os
import threading
from pathlib import Path

import tkinter as tk

# Must monkey-patch BEFORE importing PySimpleGUI so TkinterDnD becomes the Tk root
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    tk.Tk = TkinterDnD.Tk
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

import PySimpleGUI as sg
from faster_whisper import WhisperModel

SUPPORTED_EXT = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac",
}

MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]

LANGUAGES = {
    "Auto Detect": None,
    "English": "en", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja",
    "Chinese": "zh", "Korean": "ko", "Arabic": "ar", "Hindi": "hi",
}

DROP_HINT = (
    "  Drag & Drop a video or audio file here  \n\n"
    "  .mp4  ·  .mkv  ·  .avi  ·  .mov  ·  .mp3  ·  .wav  ·  …  "
)


# ── subtitle formatters ──────────────────────────────────────────────────────

def _srt_ts(s):
    h, m, sc = int(s // 3600), int((s % 3600) // 60), s % 60
    return f"{h:02d}:{m:02d}:{int(sc):02d},{int((sc % 1) * 1000):03d}"


def _vtt_ts(s):
    h, m, sc = int(s // 3600), int((s % 3600) // 60), s % 60
    return f"{h:02d}:{m:02d}:{int(sc):02d}.{int((sc % 1) * 1000):03d}"


def to_srt(segs):
    lines = []
    for i, s in enumerate(segs, 1):
        lines += [str(i), f"{_srt_ts(s.start)} --> {_srt_ts(s.end)}", s.text.strip(), ""]
    return "\n".join(lines)


def to_vtt(segs):
    lines = ["WEBVTT", ""]
    for i, s in enumerate(segs, 1):
        lines += [str(i), f"{_vtt_ts(s.start)} --> {_vtt_ts(s.end)}", s.text.strip(), ""]
    return "\n".join(lines)


def to_txt(segs):
    return "\n".join(s.text.strip() for s in segs)


FORMATTERS = {"SRT": to_srt, "VTT": to_vtt, "TXT": to_txt}


# ── background transcription worker ─────────────────────────────────────────

def transcribe_worker(filepath, model_name, language, fmt, window):
    def post(event, val=""):
        window.write_event_value(event, val)

    try:
        post("-MSG-", f"Loading model '{model_name}' (downloads on first use)...")
        post("-PROG-", 5)

        model = WhisperModel(model_name, device="cpu", compute_type="int8")

        post("-MSG-", f"Transcribing: {Path(filepath).name}")
        post("-PROG-", 15)

        lang = LANGUAGES.get(language)
        gen, info = model.transcribe(filepath, beam_size=5, language=lang, vad_filter=True)

        post("-MSG-",
             f"Detected: {info.language}  ({info.language_probability:.0%})"
             f"  —  duration: {info.duration:.1f}s")

        segs = []
        for seg in gen:
            segs.append(seg)
            pct = 15 + int(min(seg.end, info.duration) / max(info.duration, 1) * 75)
            post("-PROG-", pct)

        post("-MSG-", f"Writing {len(segs)} segments as {fmt}...")
        post("-PROG-", 93)

        out_path = Path(filepath).with_suffix("." + fmt.lower())
        out_path.write_text(FORMATTERS[fmt](segs), encoding="utf-8")

        post("-PROG-", 100)
        post("-MSG-", f"Saved: {out_path}")
        post("-DONE-", str(out_path))

    except Exception as exc:
        post("-ERR-", str(exc))


# ── GUI layout ───────────────────────────────────────────────────────────────

def make_layout():
    sg.theme("DarkBlue14")

    return [
        [sg.Text("Whisper Subtitle Generator",
                 font=("Helvetica", 18, "bold"), text_color="#00bfff",
                 expand_x=True, justification="center")],
        [sg.Text("Free AI subtitles  ·  no API key  ·  runs fully offline after model download",
                 font=("Helvetica", 9), text_color="#556677",
                 expand_x=True, justification="center")],

        [sg.HSep(pad=(0, 8))],

        [sg.Multiline(DROP_HINT, size=(64, 4), font=("Helvetica", 11),
                      justification="center", text_color="#4477aa",
                      background_color="#081824", key="-DROP-",
                      enable_events=True, no_scrollbar=True)],

        [sg.Push(),
         sg.Input(key="-PICK-", visible=False, enable_events=True),
         sg.FileBrowse("  Browse file…  ", target="-PICK-",
                       file_types=[("Media files",
                                    "*.mp4 *.mkv *.avi *.mov *.wmv *.flv "
                                    "*.webm *.m4v *.mp3 *.wav *.flac *.m4a *.ogg *.aac")],
                       button_color=("#ffffff", "#1a5c99")),
         sg.Push()],

        [sg.HSep(pad=(0, 8))],

        [sg.T("Model:"),
         sg.Combo(MODELS, "base", key="-MODEL-", size=11, readonly=True,
                  tooltip="tiny=fastest  base=balanced  large-v3=best quality"),
         sg.T("  Language:"),
         sg.Combo(list(LANGUAGES), "Auto Detect", key="-LANG-", size=14, readonly=True),
         sg.T("  Format:"),
         sg.Combo(["SRT", "VTT", "TXT"], "SRT", key="-FMT-", size=6, readonly=True)],

        [sg.HSep(pad=(0, 8))],

        [sg.ProgressBar(100, "h", size=(62, 20), key="-PB-",
                        bar_color=("#00bfff", "#081824"), expand_x=True)],

        [sg.Multiline("", size=(64, 6), key="-LOGBOX-", disabled=True,
                      autoscroll=True, font=("Courier New", 9),
                      background_color="#050d14", text_color="#00e676",
                      no_scrollbar=False)],

        [sg.Push(),
         sg.Button("Generate Subtitles", key="-GO-", disabled=True, size=(18, 1),
                   button_color=("#ffffff", "#007722"),
                   font=("Helvetica", 10, "bold")),
         sg.Button("Clear", key="-CLR-", size=(8, 1),
                   button_color=("#cccccc", "#333333")),
         sg.Push()],

        [sg.Text("Powered by OpenAI Whisper via faster-whisper  ·  models stored in ~/.cache/huggingface",
                 font=("Helvetica", 8), text_color="#334455",
                 expand_x=True, justification="center")],
    ]


# ── helpers ──────────────────────────────────────────────────────────────────

def apply_file(raw_path, window, state):
    path = raw_path.strip().strip("{}")
    if not os.path.isfile(path):
        return
    if Path(path).suffix.lower() not in SUPPORTED_EXT:
        window["-LOGBOX-"].print(f"Unsupported format: {Path(path).suffix}")
        return
    state["file"] = path
    window["-DROP-"].update(f"  ✓  {Path(path).name}  \n\n  {path}  ")
    window["-DROP-"].update(text_color="#00e676")
    window["-GO-"].update(disabled=False)


def reset_ui(window, state):
    state.update({"file": None, "busy": False})
    window["-DROP-"].update(DROP_HINT)
    window["-DROP-"].update(text_color="#4477aa")
    window["-LOGBOX-"].update("")
    window["-PB-"].update(0)
    window["-GO-"].update(disabled=True, text="Generate Subtitles")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    state = {"file": None, "busy": False}

    window = sg.Window("Whisper Subtitle Generator", make_layout(),
                       finalize=True, size=(680, 555))

    if DND_AVAILABLE:
        dz = window["-DROP-"].Widget
        dz.drop_target_register(DND_FILES)
        dz.dnd_bind("<<Drop>>", lambda e: apply_file(e.data, window, state))
        window["-LOGBOX-"].print("Drag-and-drop is enabled. Drop a file above or use Browse.")
    else:
        window["-LOGBOX-"].print(
            "Drag-and-drop unavailable (tkinterdnd2 not installed).\n"
            "Use the Browse button to select a file."
        )

    while True:
        event, values = window.read(timeout=200)

        if event == sg.WIN_CLOSED:
            break

        if event == "-PICK-" and values["-PICK-"]:
            apply_file(values["-PICK-"], window, state)

        if event == "-GO-" and state["file"] and not state["busy"]:
            state["busy"] = True
            window["-GO-"].update(disabled=True, text="Processing…")
            window["-LOGBOX-"].update("")
            window["-PB-"].update(0)
            threading.Thread(
                target=transcribe_worker,
                args=(state["file"], values["-MODEL-"], values["-LANG-"],
                      values["-FMT-"], window),
                daemon=True,
            ).start()

        if event == "-MSG-":
            window["-LOGBOX-"].print(values["-MSG-"])

        if event == "-PROG-":
            window["-PB-"].update(values["-PROG-"])

        if event == "-DONE-":
            state["busy"] = False
            window["-GO-"].update(disabled=False, text="Generate Subtitles")
            sg.popup_ok(
                f"Subtitles saved successfully!\n\n{values['-DONE-']}",
                title="Done!", button_color=("#ffffff", "#007722"),
            )

        if event == "-ERR-":
            state["busy"] = False
            window["-GO-"].update(disabled=False, text="Generate Subtitles")
            window["-LOGBOX-"].print(f"ERROR: {values['-ERR-']}")
            sg.popup_error(f"Error:\n\n{values['-ERR-']}", title="Error")

        if event == "-CLR-":
            reset_ui(window, state)

    window.close()


if __name__ == "__main__":
    main()
