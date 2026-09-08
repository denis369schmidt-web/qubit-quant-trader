import os
import sys
import json
import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Intelligent Data Types Classification & Extensions Map
SMART_DATA_TYPES = {
    "🖼️ Bilder (.png, .jpg, .svg, .webp)": {
        "cat": "images",
        "exts": [".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"],
        "mime": "image"
    },
    "📄 Dokumente (.pdf, .txt, .md, .docx)": {
        "cat": "documents",
        "exts": [".pdf", ".txt", ".md", ".docx", ".epub"],
        "mime": "document"
    },
    "📊 Daten & APIs (.json, .csv, .xml, .yaml)": {
        "cat": "data",
        "exts": [".json", ".csv", ".xml", ".yaml", ".sql"],
        "mime": "data"
    },
    "💻 Code & Skripte (.py, .js, .html, .css, .rs)": {
        "cat": "code",
        "exts": [".py", ".js", ".html", ".css", ".rs", ".cpp"],
        "mime": "code"
    },
    "🎬 Videos & Animationen (.mp4, .webm, .mkv)": {
        "cat": "video",
        "exts": [".mp4", ".webm", ".mkv", ".mov"],
        "mime": "video"
    },
    "🎧 Audio & Sound (.mp3, .wav, .flac)": {
        "cat": "audio",
        "exts": [".mp3", ".wav", ".flac", ".ogg"],
        "mime": "audio"
    },
    "📦 Archive (.zip, .tar, .gz)": {
        "cat": "archive",
        "exts": [".zip", ".tar", ".gz", ".7z"],
        "mime": "archive"
    }
}


class AutonomousSmartDataCrawler:
    """Autonomer, intelligenter Web-Crawler, der Live-Links und Downloads im Netz extrahiert"""

    @staticmethod
    def crawl_and_extract_payloads(query, target_type_label):
        type_meta = SMART_DATA_TYPES.get(target_type_label, SMART_DATA_TYPES["📄 Dokumente (.pdf, .txt, .md, .docx)"])
        allowed_exts = type_meta["exts"]
        
        encoded_query = urllib.parse.quote(query)
        found_resources = []

        # 1. Autonome Live-Suche via DuckDuckGo HTML & API
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}+{allowed_exts[0]}"
            req = urllib.request.Request(ddg_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            with urllib.request.urlopen(req, timeout=6) as response:
                html_body = response.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html_body, 'html.parser')
                
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    # Unpack DuckDuckGo redirect URLs
                    if "/l/?kh=" in href or "uddg=" in href:
                        match = re.search(r'uddg=([^&]+)', href)
                        if match:
                            href = urllib.parse.unquote(match.group(1))
                    
                    title_text = a.get_text(strip=True)
                    if href.startswith("http") and not any(ignored in href for ignored in ["duckduckgo.com", "bing.com", "google.com"]):
                        # Semantic scoring & Extension matching
                        score = 10
                        if any(href.lower().endswith(ext) for ext in allowed_exts):
                            score += 50
                        if query.lower() in href.lower() or query.lower() in title_text.lower():
                            score += 30
                            
                        found_resources.append({
                            "title": title_text if len(title_text) > 3 else f"Extrahierte Ressource für '{query}'",
                            "url": href,
                            "score": score,
                            "ext": next((ext for ext in allowed_exts if href.lower().endswith(ext)), allowed_exts[0])
                        })
        except Exception as e:
            print("Autonomous Crawl Warning:", e)

        # 2. Wikipedia API Live Content Fetcher Fallback / Supplement
        try:
            wiki_url = f"https://de.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages&exintro&explaintext&pithumbsize=600&titles={encoded_query}&format=json"
            req = urllib.request.Request(wiki_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                pages = data.get("query", {}).get("pages", {})
                for p_id, p_info in pages.items():
                    if p_id != "-1":
                        title = p_info.get("title", query)
                        extract = p_info.get("extract", "")
                        img_src = p_info.get("thumbnail", {}).get("source", "")
                        
                        target_url = img_src if (type_meta["cat"] == "images" and img_src) else f"https://de.wikipedia.org/wiki/{encoded_query}"
                        
                        found_resources.append({
                            "title": f"Wikipedia Live Data: {title}",
                            "url": target_url,
                            "content_text": extract[:1000],
                            "score": 40,
                            "ext": type_meta["exts"][0]
                        })
        except Exception:
            pass

        # Sort by relevance score
        found_resources.sort(key=lambda x: x["score"], reverse=True)
        return found_resources


class SmartQuantumGroverRanker:
    """Intelligentes Quantum Grover Ranking-System"""

    @staticmethod
    def execute_smart_fetch(query, target_type_label):
        if not HAS_QISKIT:
            return {"status": "error", "message": "Qiskit missing"}

        output_dir = os.path.join(os.getcwd(), "smart_downloads")
        os.makedirs(output_dir, exist_ok=True)

        # 1. Autonomes Crawling von echten Web-Ressourcen
        crawled_data = AutonomousSmartDataCrawler.crawl_and_extract_payloads(query, target_type_label)

        if not crawled_data:
            # Smart synthetic generation if web blocks connection
            crawled_data = [{
                "title": f"Autonome Datenanalyse für '{query}'",
                "url": f"https://api.wikimedia.org/wiki/{urllib.parse.quote(query)}",
                "content_text": f"Grover Quantum Data Payload für Query '{query}' [{target_type_label}].",
                "score": 30,
                "ext": SMART_DATA_TYPES.get(target_type_label, {}).get("exts", [".txt"])[0]
            }]

        # Prepare top 4 candidates for 2-Qubit Grover Superposition
        candidates = crawled_data[:4]
        while len(candidates) < 4:
            candidates.append({
                "title": f"Alternative Quanten-Datenquelle #{len(candidates)+1}",
                "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                "content_text": f"Zusätzliches Datenfragment #{len(candidates)+1}",
                "score": 20,
                "ext": candidates[0]["ext"]
            })

        for idx, item in enumerate(candidates):
            item["binary_index"] = f"{idx:02b}"

        # 2. Grover's Quantum Circuit Execution
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])  # Equal Superposition
        
        # Oracle for target candidate |00> (highest ranked)
        qc.x([0, 1])
        qc.cz(0, 1)
        qc.x([0, 1])

        # Diffuser Operator (Amplitude Amplification)
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

        # 3. Real Autonomous File Download & Persistence
        safe_query = re.sub(r'[^\w\-_\. ]', '_', query).strip().replace(" ", "_")
        target_ext = winner.get("ext", ".txt")
        file_name = f"smart_{safe_query}_{winner_bin}{target_ext}"
        saved_path = os.path.join(output_dir, file_name)

        downloaded_bytes = 0
        is_live_download = False

        # Attempt Live HTTP Download
        try:
            target_url = winner.get("url", "")
            if target_url.startswith("http"):
                req = urllib.request.Request(target_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=8) as resp, open(saved_path, 'wb') as f:
                    content = resp.read()
                    f.write(content)
                    downloaded_bytes = len(content)
                    is_live_download = True
        except Exception as e:
            # Fallback text saving if binary download fails
            text_content = winner.get("content_text", f"Autonomer Quanten-Download für '{query}'\nURL: {winner.get('url')}")
            with open(saved_path, "w", encoding="utf-8") as f:
                f.write(text_content)
            downloaded_bytes = os.path.getsize(saved_path)

        # Structure Metadata JSON
        meta_json_path = os.path.join(output_dir, f"smart_{safe_query}_{winner_bin}_metadata.json")
        meta_data = {
            "query": query,
            "target_type": target_type_label,
            "quantum_state": f"|{winner_bin}⟩",
            "quantum_confidence_shots": counts.get(winner_bin, 1000),
            "winner_title": winner.get("title"),
            "winner_url": winner.get("url"),
            "saved_file": saved_path,
            "file_size_formatted": f"{downloaded_bytes / 1024:.2f} KB ({downloaded_bytes} Bytes)",
            "is_live_download": is_live_download,
            "timestamp": datetime.datetime.now().isoformat()
        }
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "metadata": meta_data,
            "winner": winner,
            "candidates_count": len(candidates),
            "counts": counts
        }

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Quantencomputer"
    t = sys.argv[2] if len(sys.argv) > 2 else "📄 Dokumente (.pdf, .txt, .md, .docx)"
    res = SmartQuantumGroverRanker.execute_smart_fetch(q, t)
    print("=" * 65)
    print("🧠 AUTONOMER SMART QUANTEN-FETCHER ERGEBNIS:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 65)
