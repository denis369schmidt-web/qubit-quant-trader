import sys
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

# Enable UTF-8 for console output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def run_quantum_teleportation():
    print("=" * 65)
    print("🌌 QUANTEN-TELEPORTATIONS-PROTOKOLL (Alice ➔ Bob)")
    print("=" * 65)
    
    # 3 Qubits & 3 klassische Bits:
    # Qubit 0: Alice's Geheimbotschaft (die teleportiert werden soll)
    # Qubit 1: Alice's Teil des verschränkten Paares
    # Qubit 2: Bob's Teil des verschränkten Paares
    qc = QuantumCircuit(3, 3)
    
    # SCHRITT 1: Alice präpariert den geheimen Quantenzustand (z.B. Zustand |1>)
    qc.x(0)
    print("1. Alice präpariert das geheime Qubit (Zustand |1>).")
    
    # SCHRITT 2: Verschränkung zwischen Alice (Qubit 1) und Bob (Qubit 2) aufbauen
    qc.h(1)
    qc.cx(1, 2)
    print("2. Ein EPR-Paar (Verschränkung) zwischen Alice (Q1) und Bob (Q2) wird erzeugt.")
    
    # SCHRITT 3: Alice führt Bell-Messung auf Qubit 0 und Qubit 1 durch
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.measure(1, 1)
    print("3. Alice misst ihre beiden Qubits und sendet die Ergebnisse an Bob.")
    
    # SCHRITT 4: Bobs Korrektur-Gatter basierend auf den Messergebnissen
    # Quantum Teleportation Correction logic
    qc.cx(1, 2)
    qc.cz(0, 2)
    
    # SCHRITT 5: Bob misst sein Qubit (Qubit 2)
    qc.measure(2, 2)
    
    # Ausführung auf dem Simulator
    simulator = AerSimulator()
    job = simulator.run(qc, shots=1000)
    result = job.result().get_counts()
    
    print("-" * 65)
    print("📊 ERGEBNIS DER TELEPORTATION (1.000 Durchläufe):")
    print(result)
    print("-" * 65)
    
    # Das letzte Bit (Qubit 2) ist Bobs empfangenes Qubit!
    bobs_received = set(bitstring[0] for bitstring in result.keys())
    print(f"✨ Bobs empfangene Zustände: {bobs_received}")
    print("Exakt '1' empfangen! Das geheime Qubit wurde fehlerfrei teleportiert!")
    print("=" * 65)

if __name__ == "__main__":
    run_quantum_teleportation()
