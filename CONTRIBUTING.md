# Octave: Contribution Guidelines

Thank you for your interest in contributing to Octave. Octave is a high-performance, context-aware spatial interface driven by a multimodal Dual-Brain architecture. 

To maintain the stability of the underlying PyTorch inference engines and the C++ Win32 motor layer, we enforce strict architectural boundaries and development standards. Please review this document comprehensively before submitting a Pull Request.

---

## 1. Architectural Boundaries

Octave relies on a strictly decoupled microservice-style architecture. When contributing, ensure your modifications respect these isolation boundaries:

### The Sensory Brain (Python / ML Layer)
- **Responsibilities:** Asynchronous inference using PyTorch (LSTMs & FFNNs), MediaPipe hand tracking, and offline Vosk NLP.
- **Constraints:** Modifying the inference layer must not introduce blocking operations that exceed the `<15ms` IPC latency budget. 
- **Tensor Shapes & Topologies:** If modifying the PyTorch models, respect the established topologies:
  - **Static Models (FFNN):** Built on 126-dimensional landmark features (`126 -> 128 -> 64 -> num_classes`) with ReLU and Dropout.
  - **Dynamic Models (LSTM):** Built on 30-frame temporal windows over 126-dimensional features with 2 LSTM layers (hidden size 64).
- **Transfer Learning Rules:** Custom gesture modifications must respect the Dataset Merging pipeline. Do not introduce logic that overwrites `default_mapping.json` or `default_model.pth`.

### The Motor Brain (C++ / Win32 Layer)
- **Responsibilities:** Context-aware routing via the Windows Audio Session API, TCP Socket consumption, and OS-level input execution.
- **Constraints:** The Motor Brain operates on strict **5ms polling intervals**. Any changes to cursor heuristics (Heisenberg click-freezing, 1-Euro smoothing) must be mathematically validated to prevent cursor jitter or drift.
- **Context Routing:** If extending the Context Provider, ensure your logic correctly classifies foreground applications into the existing schema: `Browser`, `Media`, `Editor`, `Design`, `Presentation`, `Conferencing`, `Gaming`, or `Desktop`.

### The MLOps Dashboard (React / Electron)
- **Responsibilities:** Real-time gesture management, autonomous retraining orchestration, and hot-swapping PyTorch models with zero downtime.
- **Constraints:** The UI must maintain strict state isolation between Default and Custom gesture buckets. Do not reintroduce heuristic name-matching.

---

## 2. IPC Topology Rules

When modifying cross-layer communication, adhere to the established TCP socket architecture:
- **Port `50555` (C++ Engine <-> Python Service):** Handles raw gesture events, voice triggers, and model training status. Do not send UI state JSONs through this port.
- **Port `50556` (Electron Main <-> C++ Engine):** Handles orchestration requests (`list_gestures`, `upsert_gesture`, `set_mode`). The UI must **never** talk directly to the Python service. The C++ Engine remains the sole orchestration authority.

---

## 3. Development Setup

### Python / ML Subsystem
We strictly lock dependencies to prevent Tensor shape mismatches during Transfer Learning. 
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### C++ / OS Execution Subsystem
Octave's motor layer is currently Windows-only due to deep Win32 and IAudioSessionManager2 integrations. You must compile the binary in `Release` mode to ensure latency benchmarks are met.
```bash
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

### Electron / UI Subsystem
```bash
cd ui
npm install
npm run dev
```

---

## 4. Pull Request Standards

We utilize [Conventional Commits](https://www.conventionalcommits.org/) to maintain a clean Git history. All PR titles must follow this standard.

**Acceptable Prefixes:**
- `feat(ml):` (Changes to PyTorch/Inference logic)
- `feat(cpp):` (Changes to Win32/Motor logic)
- `feat(ui):` (Changes to React/Electron dashboard)
- `fix(...):` (Bug fixes)
- `docs:` (Documentation updates)

**Submission Checklist:**
1. Fork the repository and create a feature branch (`feat/your-feature`).
2. Ensure you have not accidentally tracked `.pth` model files without Git LFS.
3. Validate that your changes do not break the `<5ms` IPC socket bridge.
4. Open a PR with a detailed breakdown of your architectural changes.

---

## 5. Good First Issues
If you are familiarizing yourself with the codebase, check the GitHub Issues tab for the `good first issue` label. These issues typically involve UI state refinements or extending the C++ Context Router to support new Windows applications.
