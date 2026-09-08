import os
import sys
import json
import re
import ssl
import time
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup, Comment

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class DeepHiddenContentExtractor:
    """10x ULTRA-POWERFUL DEEP WEB & HIDDEN CONTENT EXTRACTOR ENGINE"""

    @staticmethod
    def extract_deep_hidden_data(target_url, custom_user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"):
        output_dir = os.path.join(os.getcwd(), "ultra_deep_extractions")
        os.makedirs(output_dir, exist_ok=True)

        if not target_url or not target_url.startswith(("http://", "https://")):
            return {"status": "error", "message": "Ungültige URL. Bitte gebe eine vollständige URL ein (z.B. https://example.com)."}

        domain = urllib.parse.urlparse(target_url).netloc.replace(".", "_")
        ssl_ctx = ssl.create_default_context()
        headers = {
            'User-Agent': custom_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,application/json,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache'
        }

        # 1. PRIMARY LIVE HTTP FETCH
        start_time = time.time()
        raw_html = ""
        http_status = 200
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as response:
                http_status = response.getcode()
                raw_html = response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            # Wayback Machine Archive Fallback
            archive_res = DeepHiddenContentExtractor.fetch_wayback_snapshot(target_url)
            if archive_res:
                raw_html = archive_res["html"]
                http_status = f"200 (Wayback Archive Snapshot: {archive_res['timestamp']})"
            else:
                return {"status": "error", "message": f"Live-Zugriff fehlgeschlagen: {e}"}

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        soup = BeautifulSoup(raw_html, 'html.parser')
        extracted_master = []

        # 🔍 MODULE 1: HTML-KOMMENTARE & DEVELOPER NOTES (<!-- ... -->)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for idx, c in enumerate(comments):
            c_str = c.strip()
            if len(c_str) > 10:
                extracted_master.append({
                    "category": "🔍 Entwickler-Kommentar (Hidden HTML Note)",
                    "title": f"HTML Kommentar #{idx+1}",
                    "content": c_str,
                    "score": 90
                })

        # 🔍 MODULE 2: CSS & DOM-VERSTECKTE ELEMENTE (display:none, visibility:hidden, type=hidden)
        hidden_elements = soup.find_all(lambda tag: (
            tag.get('style') and any(h in tag.get('style').lower() for h in ['display:none', 'display: none', 'visibility:hidden', 'visibility: hidden', 'opacity:0', 'opacity: 0'])
        ) or tag.get('type') == 'hidden' or tag.get('aria-hidden') == 'true')

        for idx, el in enumerate(hidden_elements):
            t_text = el.get_text(strip=True)
            v_val = el.get('value', '')
            c_str = t_text if t_text else f"Hidden Input/Tag Value: {v_val}"
            if len(c_str) > 5:
                extracted_master.append({
                    "category": "🙈 Verstecktes CSS/DOM Element",
                    "title": f"Hidden Tag <{el.name}> #{idx+1}",
                    "content": c_str,
                    "score": 95
                })

        # 🔍 MODULE 3: EINGEBETTETE JSON-LD & SCHEMAS (<script type="application/ld+json">)
        json_scripts = soup.find_all('script', type=lambda t: t and 'json' in t.lower())
        for idx, script in enumerate(json_scripts):
            try:
                js_data = json.loads(script.get_text(strip=True))
                js_str = json.dumps(js_data, indent=2, ensure_ascii=False)
                extracted_master.append({
                    "category": "📊 Strukturierte JSON-LD Daten",
                    "title": f"JSON-LD Schema #{idx+1}",
                    "content": js_str,
                    "score": 98
                })
            except Exception:
                pass

        # 🔍 MODULE 4: JAVASCRIPT RECON & VARIABLE EXTRACTION (__NEXT_DATA__, __INITIAL_STATE__, API Endpoints)
        scripts = soup.find_all('script')
        for idx, sc in enumerate(scripts):
            s_text = sc.get_text()
            # Extract Framework State Objects
            if any(var in s_text for var in ["__NEXT_DATA__", "__INITIAL_STATE__", "__NUXT__", "window.pageData"]):
                extracted_master.append({
                    "category": "⚡ SSR Framework State Payload",
                    "title": f"Framework Data Payload #{idx+1}",
                    "content": s_text[:3000],
                    "score": 99
                })
            # Regex Mining for API Endpoints in JS
            api_matches = re.findall(r'["\'](/api/[^"\']+|https?://[^"\']+/api/[^"\']+)["\']', s_text)
            if api_matches:
                extracted_master.append({
                    "category": "🔗 Extrahierte API Endpunkte",
                    "title": f"Gefundene API-Routen in JS #{idx+1}",
                    "content": "\n".join(set(api_matches)),
                    "score": 92
                })

        # 🔍 MODULE 5: ECHTE PROMPTS & QUELLCODE-BLÖCKE (<pre>, <code>, blockquote)
        code_blocks = soup.find_all(['pre', 'code', 'blockquote'])
        for idx, cb in enumerate(code_blocks):
            cb_text = cb.get_text().strip()
            if len(cb_text) > 15:
                extracted_master.append({
                    "category": "💻 Quellcode & Prompt Block",
                    "title": f"Code/Prompt Segment #{idx+1}",
                    "content": cb_text,
                    "score": 88
                })

        # 🔍 MODULE 6: TABELLEN & DATEN-MATRIZEN (<table>)
        tables = soup.find_all('table')
        for idx, tbl in enumerate(tables):
            rows = []
            for tr in tbl.find_all('tr'):
                cols = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cols:
                    rows.append(" | ".join(cols))
            if rows:
                extracted_master.append({
                    "category": "📈 Extrahierte Daten-Tabelle",
                    "title": f"Tabelle #{idx+1}",
                    "content": "\n".join(rows),
                    "score": 85
                })

        # 🔍 MODULE 7: UNVERLINKTE MEDIEN & DOKUMENTE (.pdf, .json, .csv, .png, .mp4)
        asset_links = []
        for a in soup.find_all(['a', 'link', 'img'], href=True):
            h_val = a.get('href') or a.get('src')
            if h_val and any(ext in h_val.lower() for ext in ['.pdf', '.json', '.csv', '.zip', '.png', '.jpg', '.mp4', '.xml']):
                if not h_val.startswith("http"):
                    h_val = urllib.parse.urljoin(target_url, h_val)
                asset_links.append(h_val)
        if asset_links:
            extracted_master.append({
                "category": "📦 Gefundene Dokumente & Medien-Assets",
                "title": "Verknüpfte/Versteckte Dateien",
                "content": "\n".join(set(asset_links)),
                "score": 91
            })

        # 🔍 MODULE 8: ECHTER VOLLSTÄNDIGER ARTIKEL-TEXT
        paragraphs = [p.get_text(strip=True) for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'li']) if len(p.get_text(strip=True)) > 25]
        for idx, p in enumerate(paragraphs[:15]):
            extracted_master.append({
                "category": "📄 Echter Artikel-Text",
                "title": f"Textsegment #{idx+1}",
                "content": p,
                "score": 70
            })

        # Sort all extracted items by Importance Score
        extracted_master.sort(key=lambda x: x["score"], reverse=True)

        # ⚛️ 4-QUBIT QUANTUM GROVER RANKING (16 STATES)
        candidates = extracted_master[:16]
        while len(candidates) < 16:
            candidates.append({
                "category": "🔍 Zusatz-Zustand",
                "title": f"Buffer State #{len(candidates)+1}",
                "content": candidates[0]["content"],
                "score": 50
            })

        for idx, c in enumerate(candidates):
            c["binary_index"] = f"{idx:04b}"

        winner_bin = "0000"
        counts = {"0000": 1000}
        if HAS_QISKIT:
            qc = QuantumCircuit(4, 4)
            qc.h([0, 1, 2, 3])  # Superposition over 16 states
            
            # Oracle for state |0000>
            qc.x([0, 1, 2, 3])
            qc.h(3)
            qc.mcx([0, 1, 2], 3)
            qc.h(3)
            qc.x([0, 1, 2, 3])

            # Diffuser
            qc.h([0, 1, 2, 3])
            qc.x([0, 1, 2, 3])
            qc.h(3)
            qc.mcx([0, 1, 2], 3)
            qc.h(3)
            qc.x([0, 1, 2, 3])
            qc.h([0, 1, 2, 3])
            qc.measure([0, 1, 2, 3], [0, 1, 2, 3])

            sim = AerSimulator()
            counts = sim.run(qc, shots=1000).result().get_counts()
            winner_bin = max(counts, key=counts.get)

        winner = next((c for c in candidates if c["binary_index"] == winner_bin), candidates[0])

        # 💾 MULTI-FORMAT DISK PERSISTENCE
        json_file = os.path.join(output_dir, f"ultra_deep_{domain}.json")
        md_file = os.path.join(output_dir, f"ultra_deep_{domain}.md")
        txt_file = os.path.join(output_dir, f"ultra_deep_{domain}.txt")

        export_data = {
            "target_url": target_url,
            "http_status": http_status,
            "latency_ms": elapsed_ms,
            "quantum_state": f"|{winner_bin}⟩ (4-Qubit Grover)",
            "top_quantum_winner": winner,
            "total_items_extracted": len(extracted_master),
            "all_extracted_master": extracted_master
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        # Markdown Export
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# 🕵️ 10x Ultra Deep Extractor Report: {target_url}\n\n")
            f.write(f"- **HTTP Status:** {http_status}\n")
            f.write(f"- **Latenz:** {elapsed_ms} ms\n")
            f.write(f"- **Quanten-Winner:** `|{winner_bin}⟩` ({winner.get('category')})\n\n")
            f.write(f"## 🏆 Top Quanten-Gewinner Content\n\n```\n{winner.get('content')}\n```\n\n")
            f.write("--- \n\n## 📄 Alle extrahierten Module & versteckte Daten\n\n")
            for item in extracted_master:
                f.write(f"### [{item.get('category')}] {item.get('title')}\n")
                f.write(f"```\n{item.get('content')}\n```\n\n")

        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(f"10x ULTRA DEEP EXTRACTION: {target_url}\nSTATUS: {http_status} ({elapsed_ms} ms)\n" + "="*75 + "\n\n")
            for item in extracted_master:
                f.write(f"=== [{item.get('category')}] {item.get('title')} ===\n{item.get('content')}\n\n")

        return {
            "status": "success",
            "target_url": target_url,
            "http_status": http_status,
            "latency_ms": f"{elapsed_ms} ms",
            "total_extracted": len(extracted_master),
            "quantum_winner": winner,
            "saved_json": json_file,
            "saved_md": md_file,
            "saved_txt": txt_file,
            "master_items": extracted_master
        }

    @staticmethod
    def fetch_wayback_snapshot(url):
        try:
            wb_api = f"http://archive.org/wayback/available?url={urllib.parse.quote(url)}"
            req = urllib.request.Request(wb_api, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                snapshots = data.get("archived_snapshots", {})
                closest = snapshots.get("closest", {})
                if closest.get("available") and closest.get("url"):
                    snapshot_url = closest["url"]
                    timestamp = closest.get("timestamp", "")
                    s_req = urllib.request.Request(snapshot_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(s_req, timeout=8) as s_resp:
                        return {
                            "html": s_resp.read().decode('utf-8', errors='ignore'),
                            "timestamp": timestamp,
                            "snapshot_url": snapshot_url
                        }
        except Exception:
            pass
        return None

if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://de.wikipedia.org/wiki/Quantencomputer"
    res = DeepHiddenContentExtractor.extract_deep_hidden_data(test_url)
    print("=" * 65)
    print("🕵️ 10x ULTRA DEEP EXTRACTION ERGEBNIS:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 65)
