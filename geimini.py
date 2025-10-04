import os
import json
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import queue
from PIL import Image, ImageTk

class SubtitleExtractorUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SubtitleCat 字幕猫 v1.0.1")
        self.is_translating = False
        self.stop_translation = False
        self.is_extracting = False

        # 尝试设置窗口图标
        try:
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            ico_path = os.path.join(base_path, "logo.ico")
            png_path = os.path.join(base_path, "logo.png")
            if os.path.exists(ico_path):
                try:
                    self.root.iconbitmap(ico_path)
                except Exception:
                    try:
                        img = tk.PhotoImage(file=ico_path)
                        self.root.iconphoto(False, img)
                        self._icon_image = img
                    except Exception:
                        pass
            elif os.path.exists(png_path):
                try:
                    img = tk.PhotoImage(file=png_path)
                    self.root.iconphoto(False, img)
                    self._icon_image = img
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ 设置窗口图标失败: {e}")

        # 配置
        self.default_languages = ['eng']
        self.current_dir = tk.StringVar()
        self.file_vars = {}
        self.srt_vars = {}
        self.srt_map = {}
        self.subtitle_info = {}
        self.log_queue = queue.Queue()
        self.dialog_queue = queue.Queue()
        self.api_keys = []
        self.target_language = "中文"
        self.api_keys_file = "api_keys.json"
        self.language_map = {
            "中文": "zh",
            "英文": "en",
            "韩文": "ko",
            "日文": "ja"
        }

        self.load_api_keys()

        # 目录显示
        frame_top = tk.Frame(root)
        frame_top.pack(fill="x", padx=10, pady=5)
        tk.Label(frame_top, text=" 当前目录:").pack(side="left")
        self.dir_label = tk.Label(frame_top, textvariable=self.current_dir, width=50, anchor="w")
        self.dir_label.pack(side="left", padx=5)

        # 列表框区域
        frame_lists = tk.Frame(root)
        frame_lists.pack(fill="both", expand=True, padx=10, pady=5)

        # 左边：视频文件
        frame_videos = tk.LabelFrame(frame_lists, text="")
        frame_videos.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        frame_videos_top = tk.Frame(frame_videos)
        frame_videos_top.pack(fill="x")
        tk.Label(frame_videos_top, text="视频文件").pack(side="left")
        self.extract_button = tk.Button(frame_videos_top, text="提取字幕", command=self.extract_subtitles, width=10, height=1)
        self.extract_button.pack(side="right", padx=5)
        tk.Button(frame_videos_top, text="默认语言", command=self.set_default_languages, width=10, height=1).pack(side="right", padx=5)
        tk.Button(frame_videos_top, text="选择目录", command=self.select_directory, width=10, height=1).pack(side="right", padx=5)
        self.select_all_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame_videos, text="全选", variable=self.select_all_var, command=self.toggle_select_all).pack(anchor="w")

        # 视频文件滚动区域
        self.video_canvas = tk.Canvas(frame_videos, highlightthickness=0)
        self.video_scrollbar = tk.Scrollbar(frame_videos, orient="vertical")
        self.video_scrollbar.config(command=self.video_canvas.yview)
        self.video_canvas.config(yscrollcommand=self.video_scrollbar.set)
        self.video_scrollbar.pack(side="right", fill="y")
        self.video_canvas.pack(side="left", fill="both", expand=True)
        self.video_frame = tk.Frame(self.video_canvas)
        self.video_window = self.video_canvas.create_window((0, 0), window=self.video_frame, anchor="nw")
        self.video_frame.bind("<Configure>", self._update_video_scrollregion)
        self.video_canvas.bind("<Configure>", lambda e: self._update_video_scrollregion())

        # 右边：字幕文件
        frame_srt = tk.LabelFrame(frame_lists, text="")
        frame_srt.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        frame_srt_top = tk.Frame(frame_srt)
        frame_srt_top.pack(fill="x")
        tk.Label(frame_srt_top, text="字幕文件").pack(side="left")
        self.translate_button = tk.Button(frame_srt_top, text="翻译字幕", command=self.translate_subtitles, width=10, height=1)
        self.translate_button.pack(side="right", padx=5)
        tk.Button(frame_srt_top, text="目标语言", command=self.set_target_language, width=10, height=1).pack(side="right", padx=5)
        tk.Button(frame_srt_top, text="管理秘钥", command=self.manage_api_keys, width=10, height=1).pack(side="right", padx=5)
        self.select_all_srt_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame_srt, text="全选", variable=self.select_all_srt_var, command=self.toggle_select_all_srt).pack(anchor="w")

        # 字幕文件滚动区域
        self.srt_canvas = tk.Canvas(frame_srt, highlightthickness=0)
        self.srt_scrollbar = tk.Scrollbar(frame_srt, orient="vertical")
        self.srt_scrollbar.config(command=self.srt_canvas.yview)
        self.srt_canvas.config(yscrollcommand=self.srt_scrollbar.set)
        self.srt_scrollbar.pack(side="right", fill="y")
        self.srt_canvas.pack(side="left", fill="both", expand=True)
        self.srt_frame = tk.Frame(self.srt_canvas)
        self.srt_window = self.srt_canvas.create_window((0, 0), window=self.srt_frame, anchor="nw")
        self.srt_frame.bind("<Configure>", self._update_srt_scrollregion)
        self.srt_canvas.bind("<Configure>", lambda e: self._update_srt_scrollregion())

        # 日志区域容器
        self.log_container = tk.Frame(self.root)
        self.log_container.pack(fill="x", padx=15, pady=5)

        # 日志框，固定高度（6 * 2 = 12）
        self.log_text = tk.Text(self.log_container, height=12, state="disabled", borderwidth=0, highlightthickness=0)
        self.log_text.pack(side="left", fill="x", expand=True)

        # 初始化 logo 和一键翻译按钮
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        png_path = os.path.join(base_path, "logo.png")
        self._init_log_logo_and_button(png_path)

        self.check_log_queue()

    def _init_log_logo_and_button(self, png_path):
        if not os.path.exists(png_path):
            self.log("⚠️ 未找到 logo.png")
            return

        # 外层 Frame，包含 logo 和按钮
        logo_outer = tk.Frame(self.log_container)
        logo_outer.pack(side="right", pady=5)
        
        # 左侧边框
        left_border_width = 10
        tk.Frame(logo_outer, width=left_border_width).pack(side="left")

        # logo 和按钮的垂直容器
        logo_button_container = tk.Frame(logo_outer)
        logo_button_container.pack(side="right", padx=5)

        # logo Canvas
        self.log_logo_canvas = tk.Canvas(logo_button_container, highlightthickness=0)
        self.log_logo_canvas.pack(side="top", pady=(0, 5))

        # 一键翻译按钮，动态宽度稍后设置
        self.one_click_button = tk.Button(
            logo_button_container,
            text="一键翻译",
            command=self.one_click_translate,
            font=("微软雅黑", 14, "bold")
        )
        self.one_click_button.pack(side="top")

        # 加载并处理 logo 图像
        self.original_logo_img = Image.open(png_path).convert("RGBA")
        alpha = 195
        r, g, b, a = self.original_logo_img.split()
        a = a.point(lambda p: p * alpha // 255)
        self.original_logo_img.putalpha(a)

        def resize_logo(event):
            # 获取日志框高度并限制 logo 最大高度
            h = min(self.log_text.winfo_height() - 30, 100)
            img_ratio = self.original_logo_img.width / self.original_logo_img.height
            new_h = max(h, 1)
            new_w = int(new_h * img_ratio)
            resized = self.original_logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.log_logo_img = ImageTk.PhotoImage(resized)
            self.log_logo_canvas.config(width=new_w, height=new_h)
            self.log_logo_canvas.delete("all")
            self.log_logo_canvas.create_image(new_w//2, new_h//2, image=self.log_logo_img, anchor="center")
            # 设置按钮宽度与 logo 等宽（转换为 Tkinter 字符单位，1像素约0.1字符）
            approx_char_width = new_w // 10
            self.one_click_button.config(width=max(approx_char_width, 10))

        self.log_text.bind("<Configure>", resize_logo)
        self.root.after(100, lambda: resize_logo(tk.Event()))

    def load_api_keys(self):
        try:
            if os.path.exists(self.api_keys_file):
                with open(self.api_keys_file, 'r', encoding='utf-8') as f:
                    self.api_keys = json.load(f)
        except Exception as e:
            self.log(f"⚠️ 加载API密钥失败: {e}")
            self.api_keys = []

    def save_api_keys(self):
        try:
            with open(self.api_keys_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, ensure_ascii=False, indent=2)
            self.log(f"✔ API密钥已保存到 {self.api_keys_file}")
        except Exception as e:
            self.log(f"❌ 保存API密钥失败: {e}")

    def _update_video_scrollregion(self, event=None):
        self.video_canvas.configure(scrollregion=self.video_canvas.bbox("all"))

    def _update_srt_scrollregion(self, event=None):
        self.srt_canvas.configure(scrollregion=self.srt_canvas.bbox("all"))

    def log(self, msg: str):
        self.log_queue.put(msg)
        self.root.after(0, self._process_single_log)

    def _process_single_log(self):
        try:
            msg = self.log_queue.get_nowait()
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
            self.root.update_idletasks()
        except queue.Empty:
            pass

    def check_log_queue(self):
        max_messages_per_cycle = 10
        for _ in range(max_messages_per_cycle):
            self._process_single_log()
        self.root.after(50, self.check_log_queue)

    def select_directory(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.current_dir.set(dir_path)
            self.refresh_video_files()

    def refresh_video_files(self):
        for widget in self.video_frame.winfo_children():
            widget.destroy()
        for widget in self.srt_frame.winfo_children():
            widget.destroy()
        self.file_vars.clear()
        self.srt_vars.clear()
        self.srt_map.clear()
        self.subtitle_info.clear()

        if not self.current_dir.get():
            return

        # 扫描所有子目录中的视频文件
        video_files = []
        for root, _, files in os.walk(self.current_dir.get()):
            for f in files:
                if f.lower().endswith((".mp4", ".mkv")):
                    # 存储相对路径以显示子目录结构
                    rel_path = os.path.relpath(os.path.join(root, f), self.current_dir.get())
                    video_files.append(rel_path)
        video_files.sort()

        for f in video_files:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(self.video_frame, text=f, variable=var)
            cb.pack(anchor="w")
            self.file_vars[f] = var

            # 检查对应的字幕文件
            srt_path = os.path.splitext(os.path.join(self.current_dir.get(), f))[0] + ".srt"
            if os.path.exists(srt_path):
                srt_file = srt_path
            else:
                srt_file = "未找到字幕"
            self.srt_map[f] = srt_file

        # 扫描字幕文件
        srt_files = []
        for root, _, files in os.walk(self.current_dir.get()):
            for f in files:
                if f.lower().endswith((".srt")):
                    srt_files.append(os.path.relpath(os.path.join(root, f), self.current_dir.get()))
        srt_files.sort()
        for f in srt_files:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(self.srt_frame, text=f, variable=var)
            cb.pack(anchor="w")
            self.srt_vars[f] = var

        self.video_canvas.configure(scrollregion=self.video_canvas.bbox("all"))
        self.srt_canvas.configure(scrollregion=self.srt_canvas.bbox("all"))

    def toggle_select_all(self):
        for var in self.file_vars.values():
            var.set(self.select_all_var.get())

    def toggle_select_all_srt(self):
        for var in self.srt_vars.values():
            var.set(self.select_all_srt_var.get())

    def probe_subtitles(self, video_path):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE  # 完全隐藏
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "s",
                 "-show_entries", "stream=index:stream_tags=language,title",
                 "-of", "default=noprint_wrappers=1", video_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, startupinfo=startupinfo
            )
            lines = result.stdout.strip().splitlines()
            subs = []
            current = {}
            for line in lines:
                if line.startswith("index="):
                    if current:
                        subs.append(current)
                    current = {"index": line.split("=")[1]}
                elif line.startswith("TAG:language="):
                    current["lang"] = line.split("=")[1]
                elif line.startswith("TAG:title="):
                    current["title"] = line.split("=", 1)[1]
            if current:
                subs.append(current)
            return subs
        except Exception as e:
            self.log(f"⚠️ ffprobe 出错: {e}")
            return []

    def subtitle_selection_dialog(self, subs, response_queue=None, default_eng=True):
        win = tk.Toplevel(self.root)
        win.title("选择字幕流")
        selected_vars = []
        sub_vars = {}

        for sub in subs:
            var = tk.BooleanVar(value=default_eng and sub.get("lang") == "eng")
            desc = f"流 {sub.get('index')} - 语言:{sub.get('lang','?')} 标题:{sub.get('title','')}"
            cb = tk.Checkbutton(win, text=desc, variable=var)
            cb.pack(anchor="w")
            sub_vars[sub['index']] = var
            selected_vars.append(var)

        def confirm():
            selected_indices = [sub['index'] for sub in subs if sub_vars[sub['index']].get()]
            if not selected_indices:
                messagebox.showwarning("提示", "请至少选择一个字幕流")
                return
            if response_queue:
                response_queue.put(selected_indices)
            else:
                selected_langs = [sub['lang'] for sub in subs if sub_vars[sub['index']].get()]
                self.default_languages = list(set(selected_langs))
                self.log(f"✔ 默认语言已设置为 {', '.join(self.default_languages)}")
            win.destroy()

        tk.Button(win, text="确定", command=confirm, height=1).pack(pady=5)

        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2 - win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2 - win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        win.transient(self.root)
        win.grab_set()
        win.wait_window()

    def set_default_languages(self):
        if not self.current_dir.get():
            messagebox.showwarning("警告", "请先选择目录")
            return
        video_files = [f for f in self.file_vars if self.file_vars[f].get()]
        if not video_files:
            video_files = list(self.file_vars.keys())
        if not video_files:
            messagebox.showinfo("提示", "没有视频文件")
            return
        first_video = os.path.join(self.current_dir.get(), video_files[0])
        subs = self.probe_subtitles(first_video)
        if not subs:
            self.log("❌ 没找到字幕流")
            return
        self.subtitle_selection_dialog(subs, default_eng=True)

    def manage_api_keys(self):
        win = tk.Toplevel(self.root)
        win.title("管理你的Gemini API key")
        win.geometry("480x260")
        win.minsize(360, 200)

        listbox = tk.Listbox(win, height=6)
        listbox.pack(padx=10, pady=(10, 5), fill="both", expand=True)

        for key in self.api_keys:
            listbox.insert(tk.END, key)

        frame_input = tk.Frame(win)
        frame_input.pack(fill="x", padx=10, pady=(0, 5))
        entry = tk.Entry(frame_input)
        entry.pack(fill="x", expand=True)

        button_frame = tk.Frame(win)
        button_frame.pack(fill="x", padx=10, pady=(5, 10))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        def add_key():
            key = entry.get().strip()
            if not key:
                messagebox.showwarning("提示", "请输入有效的API密钥")
                return
            listbox.insert(tk.END, key)
            self.api_keys.append(key)
            self.save_api_keys()
            entry.delete(0, tk.END)
            self.log(f"✔ 已添加API密钥: {key[:4]}...")

        def delete_selected():
            selected = listbox.curselection()
            if not selected:
                messagebox.showwarning("提示", "请先选择一个API密钥")
                return
            index = selected[0]
            listbox.delete(index)
            self.api_keys.pop(index)
            self.save_api_keys()
            self.log(f"✔ 已删除API密钥: {index + 1}")

        def confirm_and_close():
            win.destroy()

        btn_add = tk.Button(button_frame, text="添加秘钥", command=add_key)
        btn_delete = tk.Button(button_frame, text="删除选中", command=delete_selected)
        btn_ok = tk.Button(button_frame, text="确定退出", command=confirm_and_close)

        btn_add.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        btn_delete.grid(row=0, column=1, sticky="ew", padx=5)
        btn_ok.grid(row=0, column=2, sticky="ew", padx=(5, 0))

        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2 - win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2 - win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        win.transient(self.root)
        win.grab_set()
        win.wait_window()

    def set_target_language(self):
        win = tk.Toplevel(self.root)
        win.title("选择目标语言")
        languages = ["中文", "英文", "韩文", "日文"]
        selected_lang = tk.StringVar(value=self.target_language)

        for lang in languages:
            rb = tk.Radiobutton(win, text=lang, variable=selected_lang, value=lang)
            rb.pack(anchor="w")
            if lang == self.target_language:
                rb.select()

        def confirm():
            self.target_language = selected_lang.get()
            self.log(f"✔ 目标语言已设置为: {self.target_language}")
            win.destroy()

        tk.Button(win, text="确定", command=confirm, width=10, height=1).pack(pady=5)

        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2 - win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2 - win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        win.transient(self.root)
        win.grab_set()
        win.wait_window()

    def show_subtitle_selection_dialog(self, subs, response_queue):
        self.subtitle_selection_dialog(subs, response_queue, default_eng=False)

    def run_translation(self, selected_srt, target_lang_code):
        from translate import translate_files
        try:
            translate_files(selected_srt, target_lang_code, log=self.log, stop_flag=lambda: self.stop_translation)
        except Exception as e:
            self.log(f"❌ 翻译过程中发生错误: {e}")
        finally:
            self.is_translating = False
            self.stop_translation = False
            self.translate_button.config(text="翻译字幕", state="normal")
            self.one_click_button.config(text="一键翻译", state="normal")
            self.root.after(0, self.refresh_video_files)

    def translate_subtitles(self):
        if self.is_translating:
            self.stop_translation = True
            self.log("⚠️ 停止翻译...")
            return

        if not self.current_dir.get():
            messagebox.showwarning("警告", "请先选择目录")
            return

        selected_srt = [os.path.abspath(os.path.join(self.current_dir.get(), f)) for f, v in self.srt_vars.items() if v.get()]
        if not selected_srt:
            messagebox.showinfo("提示", "没有选中任何字幕文件")
            return
        if not self.api_keys:
            messagebox.showwarning("警告", "请先设置API密钥")
            return
        if not self.target_language:
            messagebox.showwarning("警告", "请先设置目标语言")
            return

        self.save_api_keys()

        self.is_translating = True
        self.stop_translation = False
        self.translate_button.config(text="停止", state="normal")
        self.one_click_button.config(text="停止", state="normal")
        target_lang_code = self.language_map.get(self.target_language, "zh")
        threading.Thread(target=self.run_translation, args=(selected_srt, target_lang_code), daemon=True).start()

    def run_extraction(self, selected_files, callback=None):
        for idx, f in enumerate(selected_files, start=1):
            if self.stop_translation:
                self.log("⚠️ 提取被停止")
                break
            video_path = os.path.abspath(os.path.join(self.current_dir.get(), f))
            subs = self.probe_subtitles(video_path)
            if not subs:
                self.log(f"❌ {f} 没找到字幕流")
                continue

            matching_streams = [sub for sub in subs if sub.get('lang') in self.default_languages]
            if matching_streams:
                to_extract = matching_streams
            else:
                self.log(f"需要用户为 {f} 选择字幕流")
                response_queue = queue.Queue()
                self.root.after(0, lambda: self.show_subtitle_selection_dialog(subs, response_queue))
                selected_indices = response_queue.get()
                to_extract = [sub for sub in subs if sub['index'] in selected_indices]

            for sub in to_extract:
                if self.stop_translation:
                    self.log("⚠️ 提取被停止")
                    break
                subtitle_lang = sub.get('lang', 'unknown')
                srt_path = os.path.splitext(video_path)[0] + f".{subtitle_lang}.srt"
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i", video_path,
                    "-map", f"0:{sub['index']}",
                    "-c:s", "srt",
                    srt_path
                ]
                self.log(f"[{idx}] {' '.join(cmd)}")
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    subprocess.run(cmd, check=True, startupinfo=startupinfo)
                except subprocess.CalledProcessError as e:
                    self.log(f"❌ 提取失败: {f} ({subtitle_lang})，错误: {e}")

        self.log("✔ 所有提取任务完成")
        self.is_extracting = False
        self.extract_button.config(state="normal")
        self.one_click_button.config(state="normal")
        self.root.after(0, self.refresh_video_files)
        if callback:
            callback()

    def extract_subtitles(self):
        if self.is_extracting:
            messagebox.showinfo("提示", "正在提取字幕，请等待完成")
            return

        if not self.current_dir.get():
            messagebox.showwarning("警告", "请先选择目录")
            return
        selected_files = [f for f, v in self.file_vars.items() if v.get()]
        if not selected_files:
            messagebox.showinfo("提示", "没有选中任何视频文件")
            return

        if not self.default_languages:
            messagebox.showwarning("警告", "请先设置默认语言")
            return

        self.extract_button.config(state="disabled")
        self.is_extracting = True
        threading.Thread(target=self.run_extraction, args=(selected_files,), daemon=True).start()

    def one_click_translate(self):
        if self.is_extracting or self.is_translating:
            self.stop_translation = True
            self.log("⚠️ 停止一键翻译...")
            return

        if not self.current_dir.get():
            messagebox.showwarning("警告", "请先选择目录")
            return
        selected_files = [f for f, v in self.file_vars.items() if v.get()]
        if not selected_files:
            messagebox.showinfo("提示", "没有选中任何视频文件")
            return
        if not self.api_keys:
            messagebox.showwarning("警告", "请先设置API密钥")
            return
        if not self.target_language:
            messagebox.showwarning("警告", "请先设置目标语言")
            return

        self.save_api_keys()
        self.is_extracting = True
        self.is_translating = True
        self.stop_translation = False
        self.one_click_button.config(text="停止", state="normal")
        self.extract_button.config(state="disabled")
        self.translate_button.config(state="disabled")

        def after_extraction():
            selected_srt = [os.path.abspath(os.path.join(self.current_dir.get(), f)) for f, v in self.srt_vars.items() if v.get()]
            if not selected_srt:
                self.log("❌ 没有找到字幕文件进行翻译")
                self.is_translating = False
                self.one_click_button.config(text="一键翻译", state="normal")
                self.extract_button.config(state="normal")
                self.translate_button.config(state="normal")
                return
            target_lang_code = self.language_map.get(self.target_language, "zh")
            self.run_translation(selected_srt, target_lang_code)

        threading.Thread(target=self.run_extraction, args=(selected_files, after_extraction), daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")
    app = SubtitleExtractorUI(root)
    root.mainloop()
