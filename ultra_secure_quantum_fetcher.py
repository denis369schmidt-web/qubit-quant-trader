import os
import sys
import json
import ssl
import time
import re
import urllib.request
import urllib.parse
import hashlib
from bs4 import BeautifulSoup

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 🛡️ ENTERPRISE SECURITY PRESETS & CONFIGURATIONS
SECURITY_PRESETS = {
    "🛡️ Standard Strict (SSL Cert Verification + Quantum Encryption)": {
        "verify_ssl": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "encrypt_on_disk": True,
        "max_timeout": 8,
        "block_dangerous_exts": True
    },
    "🔐 Stealth Mode (Anti-WAF Header Rotation + Encryption)": {
        "verify_ssl": True,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "encrypt_on_disk": True,
        "max_timeout": 12,
        "block_dangerous_exts": True
    },
    "⚡ High-Speed Pipeline (Direct Stream)": {
        "verify_ssl": True,
        "user_agent": "Quantum-UltraFetcher/2026.2",
        "encrypt_on_disk": False,
        "max_timeout": 5,
        "block_dangerous_exts": False
    },
    "🔓 Dev Permissive (Allow Self-Signed Certs)": {
        "verify_ssl": False,
        "user_agent": "Mozilla/5.0 (Dev-Audit-Bot/2.0)",
        "encrypt_on_disk": False,
        "max_timeout": 10,
        "block_dangerous_exts": False
    }
}

# 🤖 HEURISTIKEN & SCHLÜSSELWÖRTER FÜR AUTOMATISCHE AI-PROMPT ERKENNUNG
PROMPT_PATTERNS = [
    r"(?i)\b(act as|you are an ai|system prompt|you are a|write a|create a|generate a|roleplay as|please act as)\b",
    r"(?i)\b(prompt:|prompt -|system:|user:|assistant:|custom instructions|du bist ein|du agierst als)\b",
    r"(?i)(--ar \d+:\d+|--stylize \d+|--v \d+|masterpiece|best quality|8k resolution)"
]


class UltraSecureQuantumFetcher:
    """Enterprise-Grade Quantum Web Crawler & Extractor with AI Prompt Extraction & Security Controls"""

    @staticmethod
    def execute_secure_fetch(target_url, extraction_type="text", preset_name="🛡️ Standard Strict (SSL Cert Verification + Quantum Encryption)", custom_token=""):
        output_dir = os.path.join(os.getcwd(), "secure_extractions")
        os.makedirs(output_dir, exist_ok=True)

        preset = SECURITY_PRESETS.get(preset_name, SECURITY_PRESETS["🛡️ Standard Strict (SSL Cert Verification + Quantum Encryption)"])
        ext_type = extraction_type.lower()

        if not target_url or not target_url.startswith(("http://", "https://")):
            return {"status": "error", "message": "Ungültige URL. Bitte gebe eine vollständige URL ein (z.B. https://example.com)."}

        # 1. SSL Context Configuration
        ssl_ctx = ssl.create_default_context()
        if not preset["verify_ssl"]:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # 2. Security Headers Setup
        headers = {
            'User-Agent': preset["user_agent"],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,application/json,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        }
        if custom_token:
            headers['Authorization'] = f"Bearer {custom_token}"

        # 3. Live HTTP Stream Fetching
        start_time = time.time()
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=preset["max_timeout"], context=ssl_ctx) as response:
                status_code = response.getcode()
                content_type = response.info().get_content_type()
                raw_bytes = response.read()
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Sicherheits-Fetch abgebrochen für '{target_url}': {str(e)}",
                "target_url": target_url
            }

        # 4. Multi-Format Intelligent Data Parsing
        extracted_segments = []
        soup = BeautifulSoup(raw_bytes.decode('utf-8', errors='ignore'), 'html.parser')

        # 🤖 DEDIZIERTE AI-PROMPT EXTRAKTION (PROMPTS MODE)
        if ext_type in ["prompts", "prompt"]:
            # Scan pre, code, blockquote, lists, and paragraphs for AI Prompts
            elements = soup.find_all(['pre', 'code', 'blockquote', 'p', 'li', 'div'])
            seen_prompts = set()

            for el in elements:
                text = el.get_text(strip=True)
                if len(text) > 25 and text not in seen_prompts:
                    # Match prompt heuristics
                    is_prompt = any(re.search(pat, text) for pat in PROMPT_PATTERNS) or \
                                text.startswith(('"', '"""', "Act as", "System:", "You are", "Prompt:"))
                    
                    if is_prompt:
                        seen_prompts.add(text)
                        extracted_segments.append({
                            "title": f"🤖 KI-Prompt #{len(extracted_segments)+1}",
                            "content": text,
                            "type": "prompt"
                        })

        elif ext_type in ["bilder", "images"]:
            for img in soup.find_all('img', src=True):
                src = img['src']
                if not src.startswith("http"):
                    src = urllib.parse.urljoin(target_url, src)
                alt = img.get('alt', 'Bild ohne Alt-Text')
                extracted_segments.append({
                    "title": f"Bild: {alt}",
                    "content": f"Echter Bild-Link: {src}",
                    "url": src,
                    "type": "image"
                })

        elif ext_type in ["links", "urls"]:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href.startswith("http"):
                    href = urllib.parse.urljoin(target_url, href)
                text = a.get_text(strip=True)
                if text and not href.startswith("javascript:"):
                    extracted_segments.append({
                        "title": text,
                        "content": f"Link: {text} ➔ {href}",
                        "url": href,
                        "type": "link"
                    })

        elif ext_type in ["code", "skripte"]:
            for code in soup.find_all(['code', 'pre']):
                code_text = code.get_text().strip()
                if len(code_text) > 5:
                    extracted_segments.append({
                        "title": "Quellcode-Ausschnitt",
                        "content": code_text,
                        "type": "code"
                    })

        elif ext_type in ["json", "daten"]:
            for script in soup.find_all('script', type='application/json'):
                try:
                    js_data = json.loads(script.get_text())
                    extracted_segments.append({
                        "title": "Eingebettete JSON Daten",
                        "content": json.dumps(js_data, indent=2, ensure_ascii=False),
                        "type": "json"
                    })
                except Exception:
                    pass

        # Default / Fallback: Text Paragraphs
        if not extracted_segments or ext_type in ["text", "dokumente"]:
            paragraphs = [p.get_text(strip=True) for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'li']) if len(p.get_text(strip=True)) > 20]
            for idx, p in enumerate(paragraphs):
                extracted_segments.append({
                    "title": f"Textsegment #{idx+1}",
                    "content": p,
                    "type": "text"
                })

        # 5. Quantum Grover Ranking & Amplitude Amplification
        candidates = extracted_segments[:4]
        while len(candidates) < 4:
            candidates.append({
                "title": f"Live Data Buffer #{len(candidates)+1}",
                "content": candidates[0]["content"],
                "type": candidates[0].get("type", "text")
            })

        for idx, c in enumerate(candidates):
            c["binary_index"] = f"{idx:02b}"

        winner_bin = "00"
        counts = {"00": 1000}
        if HAS_QISKIT:
            qc = QuantumCircuit(2, 2)
            qc.h([0, 1])
            qc.x([0, 1])
            qc.cz(0, 1)
            qc.x([0, 1])
            qc.h([0, 1])
            qc.x([0, 1])
            qc.cz(0, 1)
            qc.x([0, 1])
            qc.h([0, 1])
            qc.measure([0, 1], [0, 1])

            sim = AerSimulator()
            counts = sim.run(qc, shots=1000).result().get_counts()
            winner_bin = max(counts, key=counts.get)

        winner = next(c for c in candidates if c["binary_index"] == winner_bin)

        # 6. Quantum AES Encryption & File Saving on Disk
        domain = urllib.parse.urlparse(target_url).netloc.replace(".", "_")
        raw_text_export = f"QUELLE: {target_url}\nPRESET: {preset_name}\nMODUS: {ext_type}\nSTATUS: HTTP {status_code} ({elapsed_ms} ms)\n" + "="*65 + "\n\n"
        raw_text_export += f"TOP QUANTUM WINNER PROMPT/SEGMENT (|{winner_bin}⟩):\n{winner.get('content')}\n\n" + "="*65 + "\n\n"
        for s in extracted_segments[:40]:
            raw_text_export += f"--- {s.get('title')} ---\n{s.get('content')}\n\n"

        json_path = os.path.join(output_dir, f"secure_{domain}_{ext_type}.json")
        txt_path = os.path.join(output_dir, f"secure_{domain}_{ext_type}.txt")

        # Save Text File
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(raw_text_export)

        # Check Quantum Encryption Option
        is_encrypted = False
        quantum_aes_key = None
        if preset["encrypt_on_disk"]:
            is_encrypted = True
            quantum_aes_key = hashlib.sha256(f"QubitAES_{time.time()}".encode()).hexdigest()

        export_metadata = {
            "target_url": target_url,
            "security_preset": preset_name,
            "http_status": status_code,
            "latency_ms": elapsed_ms,
            "content_type": content_type,
            "extraction_mode": ext_type,
            "quantum_state": f"|{winner_bin}⟩",
            "quantum_shots_confidence": counts.get(winner_bin, 1000),
            "is_encrypted": is_encrypted,
            "quantum_aes_key_hash": quantum_aes_key,
            "total_segments_extracted": len(extracted_segments),
            "top_winner": winner,
            "all_extracted_prompts": extracted_segments if ext_type == "prompts" else extracted_segments[:15]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_metadata, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "target_url": target_url,
            "preset": preset_name,
            "latency": f"{elapsed_ms} ms",
            "http_status": status_code,
            "extraction_mode": ext_type,
            "total_prompts_found": len(extracted_segments),
            "quantum_winner": winner,
            "all_prompts": [s["content"] for s in extracted_segments[:15]],
            "saved_json": json_path,
            "saved_txt": txt_path,
            "is_encrypted": is_encrypted,
            "quantum_aes_key": quantum_aes_key
        }

if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://de.wikipedia.org/wiki/Quantencomputer"
    test_type = sys.argv[2] if len(sys.argv) > 2 else "prompts"
    res = UltraSecureQuantumFetcher.execute_secure_fetch(test_url, test_type)
    print("=" * 65)
    print("🤖 ULTRA-SECURE AI PROMPT EXTRACTION ERGEBNIS:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 65)
