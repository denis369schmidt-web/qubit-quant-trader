import sys
import json
import hashlib

try:
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    HAS_QISKIT = True
except Exception:
    HAS_QISKIT = False

# Enable UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamische Wissens- & Content-Datenbank für freie Schlagwortsuche
DYNAMIC_CONTENT_DATABASE = [
    {
        "binary_index": "00",
        "keywords": ["security", "krypto", "pqc", "passkey", "zero trust", "sicherheit", "aes", "passwort", "hash"],
        "title": "🛡️ Post-Quantum Security & Zero Trust Architecture",
        "category": "Cybersecurity",
        "content": "Sicherheits-Leitfaden für quantensichere Verschlüsselung (PQC), FIDO2 Passkeys und Zero-Trust Identity Verification.",
        "tags": ["Security", "Cryptography", "Identity"]
    },
    {
        "binary_index": "01",
        "keywords": ["python", "code", "dev", "qiskit", "script", "anwendungsentwicklung", "programmierung", "ide", "vscode"],
        "title": "🐍 Modern Python & Quantum Software Engineering",
        "category": "Software Engineering",
        "content": "Praktische Code-Pipeline mit Qiskit, Asyncio, FastAPI und automatisierter IDE-Integration für Entwickler.",
        "tags": ["Python", "Qiskit", "Development"]
    },
    {
        "binary_index": "10",
        "keywords": ["cloud", "devops", "docker", "kubernetes", "hpc", "serverless", "infrastruktur", "network", "web"],
        "title": "☁️ Cloud Native & Platform Engineering 2026",
        "category": "Infrastructure",
        "content": "Interne Entwicklerplattformen (IDP), Edge Computing und heterogene HPC-Architekturen (CPU + GPU + QPU).",
        "tags": ["Cloud", "DevOps", "Edge"]
    },
    {
        "binary_index": "11",
        "keywords": ["denis", "ai", "ki", "agent", "grover", "quanten", "quantum", "ml", "suche", "lernen"],
        "title": "⚛️ Quantum AI & Autonomous Multi-Agent Systems",
        "category": "Quantum Artificial Intelligence",
        "content": "Chief Architect Denis Schmidt - Autonome Multi-Agenten-Systeme und Grover-Quantensuch-Beschleunigung.",
        "tags": ["Quantum AI", "Grover", "Agents"]
    }
]


class FreeKeywordGroverSearch:
    """Grover's Quantum Search Engine for FREE User Input Keywords"""
    
    @staticmethod
    def search(user_keyword=""):
        if not HAS_QISKIT:
            return {"status": "error", "message": "Qiskit missing"}

        if not user_keyword or not user_keyword.strip():
            user_keyword = "Quanten"

        keyword_clean = user_keyword.strip().lower()

        # 1. Match Keyword against Database
        matched_item = None
        for item in DYNAMIC_CONTENT_DATABASE:
            if any(k in keyword_clean or keyword_clean in k for k in item["keywords"]) or \
               keyword_clean in item["title"].lower() or \
               keyword_clean in item["content"].lower() or \
               any(keyword_clean in tag.lower() for tag in item["tags"]):
                matched_item = item
                break
                
        # Dynamic fallback for brand new custom keywords
        if not matched_item:
            hash_val = int(hashlib.md5(keyword_clean.encode()).hexdigest(), 16)
            idx_num = hash_val % 4
            bin_idx = f"{idx_num:02b}"
            matched_item = {
                "binary_index": bin_idx,
                "keywords": [keyword_clean],
                "title": f"🔍 Dynamischer Quanten-Treffer für '{user_keyword}'",
                "category": "Benutzerdefinierte Suche",
                "content": f"Echtzeit-Quantensuchtreffer für das freie Schlagwort '{user_keyword}' im Zustandsraum |{bin_idx}⟩.",
                "tags": [user_keyword, "CustomKeyword"]
            }

        target_idx = matched_item["binary_index"]

        # 2. Build Grover's Quantum Circuit dynamically
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])  # Superposition over all database states
        
        # Oracle for target binary index
        if target_idx == "11":
            qc.cz(0, 1)
        elif target_idx == "00":
            qc.x([0, 1])
            qc.cz(0, 1)
            qc.x([0, 1])
        elif target_idx == "01":
            qc.x(0)
            qc.cz(0, 1)
            qc.x(0)
        elif target_idx == "10":
            qc.x(1)
            qc.cz(0, 1)
            qc.x(1)

        # Grover Diffuser Operator
        qc.h([0, 1])
        qc.x([0, 1])
        qc.cz(0, 1)
        qc.x([0, 1])
        qc.h([0, 1])
        qc.measure([0, 1], [0, 1])

        # 3. Simulate 1,000 Quantum Shots
        sim = AerSimulator()
        counts = sim.run(qc, shots=1000).result().get_counts()
        found_binary = max(counts, key=counts.get)
        hit_rate = (counts.get(found_binary, 0) / 1000) * 100

        return {
            "status": "success",
            "user_keyword": user_keyword,
            "quantum_target_index": target_idx,
            "quantum_measured_index": found_binary,
            "hit_rate_percent": f"{hit_rate:.1f}%",
            "quantum_counts": counts,
            "retrieved_content": matched_item
        }

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "Security"
    res = FreeKeywordGroverSearch.search(kw)
    print(json.dumps(res, indent=2, ensure_ascii=False))
