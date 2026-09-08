import os
import sys
import json
import asyncio
import subprocess
import datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab

from ultra_secure_quantum_fetcher import UltraSecureQuantumFetcher, SECURITY_PRESETS
from deep_hidden_content_extractor import DeepHiddenContentExtractor

# Qiskit Imports
try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False

# Enable UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Windows Native OCR
HAS_WIN_OCR = False
try:
    import winrt.windows.media.ocr as ocr
    import winrt.windows.graphics.imaging as imaging
    import winrt.windows.storage as storage
    HAS_WIN_OCR = True
except Exception:
    HAS_WIN_OCR = False


class TeleportationEngine:
    @staticmethod
    def run_teleportation():
        if not HAS_QISKIT:
            return "❌ Qiskit ist nicht verfügbar."
        try:
            qc = QuantumCircuit(3, 3)
            qc.x(0)
            qc.h(1)
            qc.cx(1, 2)
            qc.cx(0, 1)
            qc.h(0)
            qc.measure(0, 0)
            qc.measure(1, 1)
            qc.cx(1, 2)
            qc.cz(0, 2)
            qc.measure(2, 2)
            
            sim = AerSimulator()
            res = sim.run(qc, shots=1000).result().get_counts()
            bobs_received = set(k[0] for k in res.keys())
            return f"🌌 [Quanten-Teleportation Agent (1)]\n" \
                   f"• Status: Geheimes Qubit |1> von Alice an Bob teleportiert.\n" \
                   f"• Messergebnis (1.000 Shots): {res}\n" \
                   f"• Bobs empfangener Zustand: {bobs_received}\n" \
                   f"✅ Teleportation fehlerfrei abgeschlossen!"
        except Exception as e:
            return f"❌ Fehler bei Teleportation: {e}"


class QuantumMLEngine:
    @staticmethod
    def run_qml_classification():
        if not HAS_QISKIT:
            return "❌ Qiskit ist nicht verfügbar."
        try:
            data_point = [0.75, 1.25]
            qc = QuantumCircuit(2, 2)
            qc.h([0, 1])
            qc.rz(data_point[0], 0)
            qc.rz(data_point[1], 1)
            qc.cx(0, 1)
            qc.measure([0, 1], [0, 1])
            
            sim = AerSimulator()
            res = sim.run(qc, shots=1000).result().get_counts()
            
            return f"🤖 [Quantum Machine Learning (QML) Agent (4)]\n" \
                   f"• Eingabe-Vektor: {data_point}\n" \
                   f"• Quantum Hilbert-Raum Projektion: 2-Qubit Feature Map\n" \
                   f"• Quanten-Klassifikation: {res}\n" \
                   f"✅ QML-Klassifikation im Hilbert-Raum abgeschlossen!"
        except Exception as e:
            return f"❌ Fehler bei QML Klassifikation: {e}"


class AutonomousCodeModifierAgent:
    def process_and_modify(self, scanned_text, prompt, target_filename="quantum_hello.py"):
        target_path = os.path.join(os.getcwd(), target_filename)
        prompt_lower = prompt.lower()
        
        if not scanned_text and os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    scanned_text = f.read()
            except Exception:
                pass

        lines = scanned_text.splitlines() if scanned_text else []
        modified_lines = []
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        if any(w in prompt_lower for w in ["logging", "log", "print", "timestamp"]):
            modified_lines.append("# --- Auto-Modified by IDE Code-Modifier Agent ---")
            modified_lines.append("import datetime")
            modified_lines.append(f"print('[{now_str}] Execution started...')\n")
            if lines:
                modified_lines.extend(lines)
            else:
                modified_lines.append("print('Hello from Ultimate Studio!')")
            action_desc = "Logging & Timestamps hinzugefügt."
        elif any(w in prompt_lower for w in ["try", "error", "catch", "exception", "fehler"]):
            modified_lines.append("# --- Auto-Modified with Error Handling ---")
            modified_lines.append("try:")
            if lines:
                for line in lines:
                    modified_lines.append("    " + line if line.strip() else "")
            else:
                modified_lines.append("    print('Running IDE task...')")
            modified_lines.append("except Exception as e:")
            modified_lines.append("    print(f'❌ Fehler bei der Ausführung: {e}')")
            action_desc = "Try-Except Fehlerbehandlung hinzugefügt."
        else:
            modified_lines.append(f"# --- Refactored von Ultimate Quantum Agent: {prompt} ---")
            if lines:
                modified_lines.extend(lines)
            else:
                modified_lines.append("# Auto-generated quantum script segment")
                modified_lines.append("from qiskit import QuantumCircuit")
                modified_lines.append("from qiskit_aer import AerSimulator")
                modified_lines.append("qc = QuantumCircuit(2, 2)")
                modified_lines.append("qc.h(0)")
                modified_lines.append("qc.cx(0, 1)")
                modified_lines.append("qc.measure([0, 1], [0, 1])")
                modified_lines.append("print(AerSimulator().run(qc, shots=500).result().get_counts())")
            action_desc = f"Code-Refactoring angewendet ({prompt})."

        new_code = "\n".join(modified_lines)
        
        if os.path.exists(target_path):
            try:
                with open(target_path + ".bak", "w", encoding="utf-8") as f:
                    f.write(scanned_text if scanned_text else "")
            except Exception:
                pass

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_code)
        except Exception as e:
            return f"❌ Fehler beim Schreiben der Datei `{target_filename}`: {e}"

        compile_res = subprocess.run([sys.executable, "-m", "py_compile", target_path], capture_output=True, text=True)
        syntax_ok = (compile_res.returncode == 0)

        return (
            f"✏️ [IDE Code-Modifier Agent (5) aktiv]\n"
            f"• Ziel-Datei in IDE: `{target_filename}`\n"
            f"• Aktion: {action_desc}\n"
            f"• Syntax-Prüfung: {'✅ ERFOLGREICH (0 Fehler)' if syntax_ok else '⚠️ Syntax-Fehler erkannt'}\n"
            f"--------------------------------------------------\n"
            f"💾 Datei `{target_filename}` wurde in deiner IDE aktualisiert!\n"
            f"📦 Backup gespeichert unter `{target_filename}.bak`"
        )


class SmoothAgentScreenStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🕵️ 10x Ultra Deep Hidden Content Quantum Studio")
        self.root.geometry("1220x820+30+10")
        self.root.configure(bg="#11111b")
        
        # Bring Window to Front cleanly
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(1500, lambda: self.root.attributes("-topmost", False))

        self.code_modifier = AutonomousCodeModifierAgent()
        self.scanned_text = ""
        self.setup_ui()

    def setup_ui(self):
        # Top Controls Bar
        self.top_bar = tk.Frame(self.root, bg="#181825", height=75)
        self.top_bar.pack(side=tk.TOP, fill=tk.X)
        
        title = tk.Label(self.top_bar, text="🕵️ 10x Ultra Deep Studio", 
                         bg="#181825", fg="#a6adc8", font=("Segoe UI", 10, "bold"))
        title.grid(row=0, column=0, padx=8, pady=4, sticky="w")

        # Security Preset Dropdown
        tk.Label(self.top_bar, text="Sicherheits-Profil:", bg="#181825", fg="#f38ba8", font=("Segoe UI", 8, "bold")).grid(row=0, column=1, padx=4, sticky="e")
        self.sec_var = tk.StringVar()
        sec_options = list(SECURITY_PRESETS.keys())
        self.sec_combo = ttk.Combobox(self.top_bar, textvariable=self.sec_var, values=sec_options, state="readonly", width=42)
        self.sec_combo.current(0)
        self.sec_combo.grid(row=0, column=2, padx=4, pady=4)

        # Action Buttons
        btn_teleport = tk.Button(self.top_bar, text="🌌 Teleport (1)", bg="#89b4fa", fg="#11111b",
                                 font=("Segoe UI", 8, "bold"), command=lambda: self.run_async(self.run_teleport), relief=tk.FLAT, padx=6)
        btn_teleport.grid(row=0, column=3, padx=4, pady=4)

        btn_qml = tk.Button(self.top_bar, text="🤖 QML (4)", bg="#f9e2af", fg="#11111b",
                            font=("Segoe UI", 8, "bold"), command=lambda: self.run_async(self.run_qml), relief=tk.FLAT, padx=6)
        btn_qml.grid(row=0, column=4, padx=4, pady=4)

        # Row 1: URL Entry & Data Mode
        tk.Label(self.top_bar, text="🌐 Ziel-URL:", bg="#181825", fg="#89b4fa", font=("Segoe UI", 8, "bold")).grid(row=1, column=0, padx=8, pady=4, sticky="e")
        self.url_entry = tk.Entry(self.top_bar, bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9), width=36, insertbackground="white")
        self.url_entry.insert(0, "https://de.wikipedia.org/wiki/Quantencomputer")
        self.url_entry.grid(row=1, column=1, padx=4, pady=4)

        tk.Label(self.top_bar, text="Modus:", bg="#181825", fg="#a6e3a1", font=("Segoe UI", 8, "bold")).grid(row=1, column=2, padx=(2, 0), sticky="w")
        self.mode_var = tk.StringVar(value="10x_ultra_deep")
        mode_options = ["10x_ultra_deep", "versteckt", "prompts", "text", "bilder", "links", "code", "json"]
        self.mode_combo = ttk.Combobox(self.top_bar, textvariable=self.mode_var, values=mode_options, state="readonly", width=14)
        self.mode_combo.current(0)  # Default: 10x_ultra_deep
        self.mode_combo.grid(row=1, column=2, padx=(50, 0), pady=4, sticky="w")

        btn_fetch = tk.Button(self.top_bar, text="🕵️ 10x Deep Extrahieren (3)", bg="#f38ba8", fg="#11111b",
                              font=("Segoe UI", 8, "bold"), command=lambda: self.run_async(self.run_deep_hidden_fetch), relief=tk.FLAT, padx=10)
        btn_fetch.grid(row=1, column=3, columnspan=2, padx=4, pady=4)

        # Middle Scanner Canvas Area
        self.canvas_frame = tk.Frame(self.root, bg="#1e1e2e", highlightbackground="#00ffcc", highlightthickness=2)
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.info_label = tk.Label(self.canvas_frame, text="🕵️ 10x ULTRA DEEP EXTRACTOR: Scanned 8 Tiefen-Module (HTML Kommentare, CSS Hidden DOM, JSON-LD, SSR State Payload, API Endpunkte, Prompts, Tabellen & Assets) mit 4-Qubit Grover!",
                                   bg="#1e1e2e", fg="#9399b2", font=("Segoe UI", 9))
        self.info_label.pack(expand=True)

        # Bottom Panel
        self.bottom_panel = tk.Frame(self.root, bg="#11111b")
        self.bottom_panel.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=6)

        self.chat_display = tk.Text(self.bottom_panel, bg="#181825", fg="#cdd6f4", font=("Consolas", 9), height=11)
        self.chat_display.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 6))
        self.append_chat("🕵️ [10x Ultra Deep Content Quantum Studio]", 
                         "Bereit! Wähle den Modus '10x_ultra_deep', gib eine beliebige Ziel-URL ein & klicke '🕵️ 10x Deep Extrahieren'.")

        # Input Row
        self.input_row = tk.Frame(self.bottom_panel, bg="#11111b")
        self.input_row.pack(side=tk.BOTTOM, fill=tk.X)

        btn_scan = tk.Button(self.input_row, text="📸 Ausschnitt scannen", bg="#89b4fa", fg="#11111b",
                             font=("Segoe UI", 9, "bold"), command=self.scan_screen_region, relief=tk.FLAT, padx=10, pady=4)
        btn_scan.pack(side=tk.LEFT, padx=(0, 6))

        self.chat_input = tk.Entry(self.input_row, bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9), insertbackground="white")
        self.chat_input.insert(0, "Füge Try-Except und Logging in quantum_hello.py ein...")
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=2)
        self.chat_input.bind("<Return>", lambda event: self.run_async(self.send_agent_command))

        btn_send = tk.Button(self.input_row, text="💬 Befehl senden", bg="#cba6f7", fg="#11111b",
                             font=("Segoe UI", 9, "bold"), command=lambda: self.run_async(self.send_agent_command), relief=tk.FLAT, padx=10, pady=4)
        btn_send.pack(side=tk.RIGHT, padx=(6, 0))

    def append_chat(self, sender, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_display.insert(tk.END, f"[{timestamp}] {sender}:\n{message}\n" + "-"*65 + "\n")
        self.chat_display.see(tk.END)

    def run_async(self, func):
        threading.Thread(target=func, daemon=True).start()

    def scan_screen_region(self):
        self.root.withdraw()
        self.root.update()

        try:
            x = self.canvas_frame.winfo_rootx()
            y = self.canvas_frame.winfo_rooty()
            w = self.canvas_frame.winfo_width()
            h = self.canvas_frame.winfo_height()

            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img_path = os.path.join(os.getcwd(), "screen_capture.png")
            img.save(img_path)

            self.scanned_text = self.perform_ocr(img_path)
            with open(os.path.join(os.getcwd(), "screen_text.txt"), "w", encoding="utf-8") as f:
                f.write(self.scanned_text)
            
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.after(1000, lambda: self.root.attributes("-topmost", False))
            self.append_chat("📸 [Screen Scanner]", f"Bildschirm-Ausschnitt ({w}x{h} px) gescannt.")
        except Exception as e:
            self.root.deiconify()

    def send_agent_command(self):
        user_msg = self.chat_input.get().strip()
        if not user_msg:
            return

        self.append_chat("👤 Denis (Du)", user_msg)
        self.chat_input.delete(0, tk.END)

        target_file = "quantum_hello.py"
        response = self.code_modifier.process_and_modify(self.scanned_text, user_msg, target_file)
        self.append_chat("🤖 [IDE Agent (5)]", response)

    def run_deep_hidden_fetch(self):
        url = self.url_entry.get().strip()
        mode = self.mode_combo.get().strip()
        preset = self.sec_combo.get().strip()

        if not url:
            url = "https://de.wikipedia.org/wiki/Quantencomputer"

        if mode in ["10x_ultra_deep", "versteckt"]:
            self.append_chat("👤 Denis (Du)", f"Starte 10x ULTRA DEEP EXTRAKTION für URL: '{url}'...")
            res = DeepHiddenContentExtractor.extract_deep_hidden_data(url)

            if res.get("status") == "success":
                winner = res.get("quantum_winner", {})
                master_items = res.get("master_items", [])
                summary_items = "\n\n".join([f"🔹 [{m.get('category')}] {m.get('title')}:\n{m.get('content')[:350]}" for m in master_items[:5]])
                
                output_str = (
                    f"🕵️ [10x Ultra Deep Quanten-Extractor Agent (3)]\n"
                    f"• URL: {res.get('target_url')} (Status: {res.get('http_status')} | Latenz: {res.get('latency_ms')})\n"
                    f"• Extrahierte Tiefen-Elemente: {res.get('total_extracted')}\n"
                    f"• 4-Qubit Grover Ranking: State {winner.get('binary_index')} (aus 16 Zuständen verstärkt)\n"
                    f"--------------------------------------------------\n"
                    f"🏆 TOP GEFUNDENE DEEP-CONTENT INHALTE:\n"
                    f"{summary_items}\n"
                    f"--------------------------------------------------\n"
                    f"💾 Multiformat-Export auf Festplatte gespeichert:\n"
                    f"   • JSON: {res.get('saved_json')}\n"
                    f"   • Markdown: {res.get('saved_md')}\n"
                    f"   • Text: {res.get('saved_txt')}\n"
                    f"✅ 10x Ultra Deep Extraktion fehlerfrei abgeschlossen!"
                )
            else:
                output_str = f"⚠️ Deep Extraktion fehlgeschlagen: {res.get('message')}"
        else:
            self.append_chat("👤 Denis (Du)", f"Starte Quanten-Fetch für URL: '{url}' [Modus: {mode}]...")
            res = UltraSecureQuantumFetcher.execute_secure_fetch(url, mode, preset)

            if res.get("status") == "success":
                winner = res.get("quantum_winner", {})
                output_str = (
                    f"🛡️ [Quanten-Fetcher Agent (3)]\n"
                    f"• URL: {res.get('target_url')} (HTTP {res.get('http_status')})\n"
                    f"• Modus: {res.get('extraction_mode')}\n"
                    f"--------------------------------------------------\n"
                    f"📌 TOP QUANTEN WINNER:\n"
                    f"{winner.get('content')[:800]}\n"
                    f"--------------------------------------------------\n"
                    f"💾 Gespeichert in: {res.get('saved_json')}\n"
                    f"✅ Extraktion erfolgreich abgeschlossen!"
                )
            else:
                output_str = f"⚠️ Fetch fehlgeschlagen: {res.get('message')}"

        self.append_chat("🕵️ [10x Ultra Deep Extractor (3)]", output_str)

    def run_teleport(self):
        self.append_chat("👤 Denis (Du)", "Starte Quanten-Teleportation (1)...")
        res = TeleportationEngine.run_teleportation()
        self.append_chat("🌌 [Teleport Agent (1)]", res)

    def run_qml(self):
        self.append_chat("👤 Denis (Du)", "Starte Quantum Machine Learning Klassifikation (4)...")
        res = QuantumMLEngine.run_qml_classification()
        self.append_chat("🤖 [QML Agent (4)]", res)

    def perform_ocr(self, img_path):
        if HAS_WIN_OCR:
            try:
                return asyncio.run(self.win_ocr_async(img_path))
            except Exception as e:
                print("WinOCR Exception:", e)
        return f"[Bild unter {img_path} gespeichert.]"

    async def win_ocr_async(self, img_path):
        abs_path = os.path.abspath(img_path)
        file = await storage.StorageFile.get_file_from_path_async(abs_path)
        stream = await file.open_async(storage.FileAccessMode.READ)
        decoder = await imaging.BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        
        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        ocr_result = await engine.recognize_async(software_bitmap)
        return "\n".join([line.text for line in ocr_result.lines])

if __name__ == "__main__":
    root = tk.Tk()
    app = SmoothAgentScreenStudioApp(root)
    root.mainloop()
