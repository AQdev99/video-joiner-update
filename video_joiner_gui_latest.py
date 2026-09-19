import os
import re
import sys
import json
import shutil
import subprocess
import threading
import tempfile
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "3.0.1"
CONFIG_FILE = "video_joiner_config.json"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/AQdev99/video-joiner-update/main/manifest.json"

VIDEO_EXTENSIONS = (
    ".mp4", ".mov", ".mkv", ".avi",
    ".m4v", ".webm", ".ts", ".mts", ".m2ts"
)

def natural_sort_key(text):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", text)
    ]

def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def config_path():
    return os.path.join(app_base_dir(), CONFIG_FILE)

def load_config():
    path = config_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(data):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def auto_find_ffmpeg():
    local = os.path.join(app_base_dir(), "ffmpeg.exe")
    if os.path.isfile(local):
        return local
    found = shutil.which("ffmpeg")
    return found or ""

def version_tuple(v):
    nums = re.findall(r"\d+", str(v))
    return tuple(int(x) for x in nums[:4]) if nums else (0,)

class ScrollableFrame(ttk.Frame):
    def __init__(self, container):
        super().__init__(container)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas)

        self.content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._resize_content)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _resize_content(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def _on_mousewheel(self, event):
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

class VideoJoinerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Video Joiner - v{APP_VERSION}")
        self.root.geometry("920x820")
        self.root.minsize(560, 420)

        cfg = load_config()

        self.folder_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.ffmpeg_var = tk.StringVar(value=cfg.get("ffmpeg_path") or auto_find_ffmpeg())
        self.mode_var = tk.StringVar(value=cfg.get("mode", "fast"))
        self.update_source_var = tk.StringVar(value=cfg.get("update_source") or DEFAULT_UPDATE_URL)

        self.video_files = []
        self.build_ui()

    def build_ui(self):
        wrapper = ScrollableFrame(self.root)
        wrapper.pack(fill="both", expand=True)

        main = ttk.Frame(wrapper.content, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="GHEP VIDEO THEO THU TU TANG DAN",
            font=("Segoe UI", 18, "bold"),
            anchor="center"
        ).pack(fill="x", pady=(0, 4))

        ttk.Label(
            main,
            text=f"Phien ban hien tai: {APP_VERSION}",
            font=("Segoe UI", 9),
            anchor="center"
        ).pack(fill="x", pady=(0, 12))

        update_box = ttk.LabelFrame(main, text="0. Cap nhat tool tren cac may", padding=10)
        update_box.pack(fill="x", pady=6)

        update_row = ttk.Frame(update_box)
        update_row.pack(fill="x")

        ttk.Entry(update_row, textvariable=self.update_source_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )

        ttk.Button(
            update_row,
            text="Chon folder cap nhat",
            command=self.choose_update_folder
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            update_row,
            text="UPDATE",
            command=self.start_update
        ).pack(side="right")

        ttk.Label(
            update_box,
            text=(
                "Nguon cap nhat co the la folder dung chung (LAN/Dropbox/Google Drive/OneDrive) "
                "hoac URL manifest.json. May khac chi can bam UPDATE."
            ),
            font=("Segoe UI", 9),
            wraplength=820
        ).pack(anchor="w", pady=(6, 0))

        ffmpeg_box = ttk.LabelFrame(main, text="1. Chon file FFmpeg (ffmpeg.exe)", padding=10)
        ffmpeg_box.pack(fill="x", pady=6)

        ffmpeg_row = ttk.Frame(ffmpeg_box)
        ffmpeg_row.pack(fill="x")

        ttk.Entry(ffmpeg_row, textvariable=self.ffmpeg_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )

        ttk.Button(
            ffmpeg_row,
            text="Chon ffmpeg.exe",
            command=self.choose_ffmpeg
        ).pack(side="right")

        folder_box = ttk.LabelFrame(main, text="2. Chon folder chua video", padding=10)
        folder_box.pack(fill="x", pady=6)

        folder_row = ttk.Frame(folder_box)
        folder_row.pack(fill="x")

        ttk.Entry(folder_row, textvariable=self.folder_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )

        ttk.Button(
            folder_row,
            text="Chon folder",
            command=self.choose_folder
        ).pack(side="right")

        list_box = ttk.LabelFrame(main, text="3. Thu tu video se duoc ghep", padding=10)
        list_box.pack(fill="both", expand=True, pady=8)

        list_inner = ttk.Frame(list_box)
        list_inner.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_inner, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_inner,
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
            selectmode=tk.BROWSE,
            height=11
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        output_box = ttk.LabelFrame(main, text="4. File video sau khi ghep", padding=10)
        output_box.pack(fill="x", pady=6)

        output_row = ttk.Frame(output_box)
        output_row.pack(fill="x")

        ttk.Entry(output_row, textvariable=self.output_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )

        ttk.Button(
            output_row,
            text="Chon noi luu",
            command=self.choose_output
        ).pack(side="right")

        mode_box = ttk.LabelFrame(main, text="5. Che do ghep", padding=10)
        mode_box.pack(fill="x", pady=6)

        ttk.Radiobutton(
            mode_box,
            text="Ghep nhanh - khong re-encode",
            variable=self.mode_var,
            value="fast",
            command=self.save_settings
        ).pack(anchor="w")

        ttk.Radiobutton(
            mode_box,
            text="Ghep tuong thich - re-encode H.264/AAC",
            variable=self.mode_var,
            value="compatible",
            command=self.save_settings
        ).pack(anchor="w", pady=(4, 0))

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x", pady=(14, 6))

        self.status = ttk.Label(main, text="San sang", anchor="center")
        self.status.pack(fill="x", pady=(0, 10))

        btns = ttk.Frame(main)
        btns.pack(pady=(4, 18))

        self.merge_btn = ttk.Button(btns, text="GHEP VIDEO", command=self.start_merge)
        self.merge_btn.pack(side="left", padx=5, ipadx=28, ipady=9)

        ttk.Button(btns, text="RESET", command=self.reset).pack(
            side="left", padx=5, ipadx=16, ipady=9
        )

    def save_settings(self):
        save_config({
            "ffmpeg_path": self.ffmpeg_var.get().strip(),
            "update_source": self.update_source_var.get().strip(),
            "mode": self.mode_var.get()
        })

    def choose_update_folder(self):
        folder = filedialog.askdirectory(title="Chon folder dung chung de cap nhat tool")
        if folder:
            self.update_source_var.set(folder)
            self.save_settings()

    def choose_ffmpeg(self):
        path = filedialog.askopenfilename(
            title="Chon file ffmpeg.exe",
            initialdir=app_base_dir(),
            filetypes=[
                ("FFmpeg executable", "ffmpeg.exe"),
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.ffmpeg_var.set(path)
            self.save_settings()

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Chon folder chua video")
        if not folder:
            return
        self.folder_var.set(folder)
        self.load_videos(folder)
        self.output_var.set(os.path.join(folder, "VIDEO_GHEP.mp4"))

    def choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Chon noi luu video",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")]
        )
        if path:
            self.output_var.set(path)

    def load_videos(self, folder):
        self.listbox.delete(0, tk.END)
        files = []

        try:
            for name in os.listdir(folder):
                full = os.path.join(folder, name)
                if not os.path.isfile(full):
                    continue
                if not name.lower().endswith(VIDEO_EXTENSIONS):
                    continue
                if name.lower() == "video_ghep.mp4":
                    continue
                files.append(name)

            files.sort(key=natural_sort_key)
            self.video_files = files

            for i, name in enumerate(files, 1):
                self.listbox.insert(tk.END, f"{i:03d}. {name}")

            self.status.config(text=f"Tim thay {len(files)} video")
        except Exception as e:
            messagebox.showerror("Loi", str(e))

    def start_update(self):
        source = self.update_source_var.get().strip()
        if not source:
            messagebox.showwarning(
                "Chua co nguon cap nhat",
                "Hay chon folder cap nhat dung chung hoac nhap URL manifest.json."
            )
            return

        self.save_settings()
        self.progress.start(10)
        self.status.config(text="Dang kiem tra ban cap nhat...")

        threading.Thread(
            target=self.update_worker,
            args=(source,),
            daemon=True
        ).start()

    def update_worker(self, source):
        try:
            if source.lower().startswith(("http://", "https://")):
                self.update_from_url(source)
            else:
                self.update_from_folder(source)
        except Exception as e:
            self.root.after(0, lambda: self.update_failed(str(e)))

    def update_from_folder(self, folder):
        if not os.path.isdir(folder):
            raise Exception("Folder cap nhat khong ton tai.")

        version_file = os.path.join(folder, "version.txt")
        if not os.path.isfile(version_file):
            raise Exception(
                "Khong tim thay version.txt trong folder cap nhat.\n\n"
                "Folder cap nhat can co:\n"
                "- version.txt\n"
                "- video_joiner_gui_latest.py"
            )

        with open(version_file, "r", encoding="utf-8") as f:
            latest_version = f.read().strip()

        if version_tuple(latest_version) <= version_tuple(APP_VERSION):
            self.root.after(0, lambda: self.no_update(latest_version))
            return

        if getattr(sys, "frozen", False):
            candidate = os.path.join(folder, "video_joiner_gui_latest.exe")
        else:
            candidate = os.path.join(folder, "video_joiner_gui_latest.py")

        if not os.path.isfile(candidate):
            raise Exception("Khong tim thay file tool moi trong folder cap nhat.")

        self.install_update(candidate, latest_version)

    def update_from_url(self, manifest_url):
        with urllib.request.urlopen(manifest_url, timeout=20) as response:
            manifest = json.loads(response.read().decode("utf-8"))

        latest_version = str(manifest.get("version", "")).strip()
        download_url = str(manifest.get("download_url", "")).strip()

        if not latest_version or not download_url:
            raise Exception("manifest.json thieu version hoac download_url.")

        if version_tuple(latest_version) <= version_tuple(APP_VERSION):
            self.root.after(0, lambda: self.no_update(latest_version))
            return

        suffix = ".exe" if getattr(sys, "frozen", False) else ".py"
        temp_file = os.path.join(
            tempfile.gettempdir(),
            f"video_joiner_update_{latest_version}{suffix}"
        )

        urllib.request.urlretrieve(download_url, temp_file)
        self.install_update(temp_file, latest_version)

    def install_update(self, new_file, latest_version):
        current_file = os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else __file__
        )
        base_dir = os.path.dirname(current_file)

        ext = ".exe" if getattr(sys, "frozen", False) else ".py"
        temp_target = os.path.join(base_dir, f"_update_new{ext}")
        shutil.copy2(new_file, temp_target)

        if os.name != "nt":
            raise Exception("Chuc nang update tu dong nay dang duoc toi uu cho Windows.")

        bat_path = os.path.join(
            tempfile.gettempdir(),
            "video_joiner_apply_update.bat"
        )

        current_q = current_file.replace('"', '""')
        temp_q = temp_target.replace('"', '""')

        if getattr(sys, "frozen", False):
            restart_cmd = f'start "" "{current_q}"'
        else:
            python_exe = sys.executable.replace('"', '""')
            restart_cmd = f'start "" "{python_exe}" "{current_q}"'

        bat = (
            "@echo off\n"
            "timeout /t 2 /nobreak >nul\n"
            f'copy /y "{temp_q}" "{current_q}" >nul\n'
            f'{restart_cmd}\n'
            'del "%~f0"\n'
        )

        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat)

        self.root.after(
            0,
            lambda: self.confirm_and_restart_update(bat_path, latest_version)
        )

    def confirm_and_restart_update(self, bat_path, latest_version):
        self.progress.stop()
        self.status.config(text=f"Da tai ban moi v{latest_version}")

        ok = messagebox.askyesno(
            "Co ban cap nhat moi",
            f"Da tim thay phien ban {latest_version}.\n\n"
            "Bam YES de cap nhat ngay.\n"
            "Tool se tu dong dong va mo lai."
        )

        if not ok:
            return

        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.root.destroy()

    def no_update(self, latest_version):
        self.progress.stop()
        self.status.config(text="Dang dung ban moi nhat")
        messagebox.showinfo(
            "Khong can cap nhat",
            f"Ban hien tai: {APP_VERSION}\n"
            f"Ban tren nguon cap nhat: {latest_version}\n\n"
            "Tool dang la ban moi nhat."
        )

    def update_failed(self, error):
        self.progress.stop()
        self.status.config(text="Cap nhat that bai")
        messagebox.showerror("Loi cap nhat", error)

    def validate_ffmpeg(self):
        path = self.ffmpeg_var.get().strip().strip('"')
        if path and os.path.isfile(path):
            return path

        found = auto_find_ffmpeg()
        if found:
            self.ffmpeg_var.set(found)
            self.save_settings()
            return found

        return None

    def start_merge(self):
        folder = self.folder_var.get().strip()
        output = self.output_var.get().strip()
        ffmpeg = self.validate_ffmpeg()

        if not ffmpeg:
            messagebox.showerror(
                "Khong tim thay FFmpeg",
                "Hay bam 'Chon ffmpeg.exe' va chon dung file ffmpeg.exe."
            )
            return

        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Thieu folder", "Hay chon folder chua video.")
            return

        if len(self.video_files) < 2:
            messagebox.showwarning("Khong du video", "Can it nhat 2 video de ghep.")
            return

        if not output:
            messagebox.showwarning("Thieu file output", "Hay chon noi luu video.")
            return

        input_paths = {
            os.path.normcase(os.path.abspath(os.path.join(folder, name)))
            for name in self.video_files
        }

        output_abs = os.path.normcase(os.path.abspath(output))

        if output_abs in input_paths:
            messagebox.showerror(
                "File output khong hop le",
                "File ket qua khong duoc trung ten voi video nguon."
            )
            return

        self.merge_btn.config(state="disabled")
        self.progress.start(10)
        self.status.config(text="Dang ghep video...")

        threading.Thread(
            target=self.merge_worker,
            args=(ffmpeg, folder, output),
            daemon=True
        ).start()

    def merge_worker(self, ffmpeg, folder, output):
        list_file = os.path.join(folder, "_video_concat_list.txt")

        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for name in self.video_files:
                    full = os.path.abspath(os.path.join(folder, name))
                    safe = full.replace("\\", "/").replace("'", r"'\''")
                    f.write(f"file '{safe}'\n")

            if self.mode_var.get() == "fast":
                command = [
                    ffmpeg, "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c", "copy",
                    "-movflags", "+faststart",
                    output
                ]
            else:
                command = [
                    ffmpeg, "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "18",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    output
                ]

            startupinfo = None
            creationflags = 0

            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                startupinfo=startupinfo,
                creationflags=creationflags
            )

            if process.returncode != 0:
                error = process.stderr[-5000:] if process.stderr else "Khong ro loi."
                self.root.after(0, lambda: self.merge_failed(error))
                return

            if not os.path.isfile(output):
                self.root.after(
                    0,
                    lambda: self.merge_failed("FFmpeg khong tao duoc file output.")
                )
                return

            self.root.after(0, lambda: self.merge_success(output))

        except Exception as e:
            self.root.after(0, lambda: self.merge_failed(str(e)))

        finally:
            try:
                if os.path.isfile(list_file):
                    os.remove(list_file)
            except Exception:
                pass

    def merge_success(self, output):
        self.progress.stop()
        self.progress["value"] = 100
        self.merge_btn.config(state="normal")
        self.status.config(text="Ghep video thanh cong!")

        messagebox.showinfo(
            "Thanh cong",
            f"Da ghep {len(self.video_files)} video.\n\n"
            f"File ket qua:\n{output}"
        )

    def merge_failed(self, error):
        self.progress.stop()
        self.merge_btn.config(state="normal")
        self.status.config(text="Ghep video that bai")

        messagebox.showerror(
            "Loi ghep video",
            "Khong the ghep video.\n\n"
            "Neu dang dung 'Ghep nhanh', hay thu 'Ghep tuong thich'.\n\n"
            f"Chi tiet loi:\n{error}"
        )

    def reset(self):
        self.folder_var.set("")
        self.output_var.set("")
        self.video_files = []
        self.listbox.delete(0, tk.END)
        self.progress.stop()
        self.progress["value"] = 0
        self.status.config(text="San sang")

def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass

    VideoJoinerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
