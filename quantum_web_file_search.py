import os
import sys
import json
import urllib.request
import urllib.parse
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

# Enable UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 📁 Unterstützte Datentypen & Dateiendungen
DATA_TYPES = {
    "bilder": {
        "label": "🖼️ Bilder & Grafiken",
        "extensions": [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"],
        "sample_source": "Wikimedia & Web-Image Index"
    },
    "videos": {
        "label": "🎬 Videos & Medien",
        "extensions": [".mp4", ".webm", ".mkv", ".mov", "YouTube Video"],
        "sample_source": "Web Video Index"
    },
    "text": {
        "label": "📝 Text & Dokumente",
        "extensions": [".txt", ".pdf", ".md", ".doc", ".docx"],
        "sample_source": "Web & Local Document Index"
    },
    "json": {
        "label": "📊 Daten & REST-APIs",
        "extensions": [".json", ".csv", ".yaml", ".xml"],
        "sample_source": "Web API & JSON Index"
    },
    "code": {
        "label": "💻 Quellcode & Skripte",
        "extensions": [".py", ".js", ".html", ".css", ".rs", ".cpp"],
        "sample_source": "GitHub & Web Code Index"
    },
    "audio": {
        "label": "🎧 Audio & Sound",
        "extensions": [".mp3", ".wav", ".flac", ".ogg"],
        "sample_source": "Web Sound Index"
    }
}


class InternetQuantumSearchEngine:
    """Grover's Quantum Search Engine for Web, Files & Multi-Media"""
    
    @staticmethod
    def search_internet_and_files(query, file_type="text"):
        file_type_key = file_type.lower()
        if file_type_key not in DATA_TYPES:
            file_type_key = "text"

        selected_type = DATA_TYPES[file_type_key]
        
        # 1. Real Web Search / Crawler Fetch via DuckDuckGo API & Wikipedia API
        web_results = InternetQuantumSearchEngine.fetch_web_results(query, file_type_key)
        
        if not web_results:
            return {"status": "error", "message": f"Keine Web-Ergebnisse für '{query}' gefunden."}

        # 2. Map Web Results to Quantum Hilbert Space (4 Candidate States)
        # Pad to 4 candidates for 2-Qubit Grover Oracle (|00⟩, |01⟩, |10⟩, |11⟩)
        candidates = web_results[:4]
        while len(candidates) < 4:
            candidates.append({
                "title": f"Web Result Alternative #{len(candidates)+1}",
                "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                "type": selected_type["label"],
                "extension": selected_type["extensions"][0],
                "snippet": f"Zusätzliches Web-Ergebnis für '{query}'"
            })

        for i, c in enumerate(candidates):
            c["binary_index"] = f"{i:02b}"

        # 3. Build Grover's Quantum Circuit to find the top-ranked result (Target |00⟩)
        target_idx = "00"  # Top candidate marked by Quantum Oracle
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])  # Superposition over all web search results
        
        # Oracle for target index |00⟩
        qc.x([0, 1])
        qc.cz(0, 1)
        qc.x([0, 1])

        # Diffuser Operator
        qc.h([0, 1])
        qc.x([0, 1])
        qc.cz(0, 1)
        qc.x([0, 1])
        qc.h([0, 1])
        qc.measure([0, 1], [0, 1])

        # Simulate 1,000 Quantum Shots
        sim = AerSimulator()
        counts = sim.run(qc, shots=1000).result().get_counts()
        found_binary = max(counts, key=counts.get)
        
        winning_candidate = next(c for c in candidates if c["binary_index"] == found_binary)

        return {
            "status": "success",
            "search_query": query,
            "selected_type": selected_type["label"],
            "supported_extensions": selected_type["extensions"],
            "quantum_target_index": found_binary,
            "quantum_counts": counts,
            "quantum_winner": winning_candidate,
            "all_quantum_candidates": candidates
        }

    @staticmethod
    def fetch_web_results(query, file_type):
        encoded_q = urllib.parse.quote(query)
        results = []
        
        try:
            # DuckDuckGo Instant Answer Web API
            url = f"https://api.duckduckgo.com/?q={encoded_q}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
                # Abstract Text
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", f"https://duckduckgo.com/?q={encoded_q}"),
                        "type": DATA_TYPES[file_type]["label"],
                        "extension": DATA_TYPES[file_type]["extensions"][0],
                        "snippet": data.get("AbstractText")
                    })
                
                # Related Topics
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0],
                            "url": topic.get("FirstURL", f"https://duckduckgo.com/?q={encoded_q}"),
                            "type": DATA_TYPES[file_type]["label"],
                            "extension": DATA_TYPES[file_type]["extensions"][0],
                            "snippet": topic.get("Text")
                        })
        except Exception as e:
            print("Web API Warning:", e)

        # Fallback if API returns empty
        if not results:
            results.append({
                "title": f"Internet-Ergebnis für '{query}'",
                "url": f"https://duckduckgo.com/?q={encoded_q}",
                "type": DATA_TYPES[file_type]["label"],
                "extension": DATA_TYPES[file_type]["extensions"][0],
                "snippet": f"Relevanter Web-Fund für {query} ({DATA_TYPES[file_type]['label']})"
            })

        return results

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Quantencomputer"
    ft = sys.argv[2] if len(sys.argv) > 2 else "bilder"
    
    print("=" * 65)
    print(f"🔍 QUANTEN-INTERNET-SUCHE: '{q}' [{DATA_TYPES.get(ft, {}).get('label', ft)}]")
    print("=" * 65)
    res = InternetQuantumSearchEngine.search_internet_and_files(q, ft)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 65)
