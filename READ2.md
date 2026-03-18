

# GSS-OS

**A text-native operating system control interface for edge LLMs.**

GSS-OS (General Skills Standard - Operating System) is not just another tool wrapper for large models.  
It attempts to rewrite desktop control from **screenshot-heavy navigation + bulky JSON/schema outputs** into:

- **atomic text commands**
- **Grid Domain coordinates**
- **dynamic on-demand libraries**
- **HOW-code tool bootstrapping**
- **Hard Freeze safety review**

> **The goal is not to make the model bigger, but to make the task representation simpler for small models.**

---

## Why GSS-OS

Many GUI agents / computer-use systems can work, but often come with several engineering costs:

- dependence on full-screen screenshots and heavy visual reasoning
- complex structured schema / JSON generation
- bloated prompts and tool descriptions
- poor usability for small local models
- weak true-offline deployment
- weak review boundaries for tool evolution

GSS-OS does not try to deny those systems.  
Instead, it offers a **lighter, faster, and more edge-friendly alternative** for OS control.

---

## In one sentence

Traditional GUI agents often ask the model to:

> **see the full screen → understand the UI → plan actions → emit complex calls**

GSS-OS tries to rewrite the problem into:

> **read minimal task state → emit short atomic text commands → parse and execute locally**

---

## Minimal example

Task:

> Open Notepad, wait for one second, type "Hello human, I am an AI operating system", and select all text.

Model output:

```text
o notepad
sl 1
t Hello human, I am an AI operating system
hk Ctrl+A
```

The runtime parses the commands and executes them as real desktop actions.

---

## Four core modules

### 1. A 16-instruction atomic control set

GSS-OS compresses desktop control into a fixed 16-instruction set, effectively an **AI Assembly Language**:

```text
MOUSE: c <g> | dc <g> | rc <g> | sc <dir> <n> | dr <g1> <g2>
KEY  : hk <combo> | t <text>
PROC : o <path> | k <name> | w <title>
FLOW : sl <sec>
KNOW : ld <lib>
EVO  : hc <name> | mk_lib <lib> | mv <tool> <lib>
COMM : msg <text>
```

Design principles:

- atomicity
- brevity
- predictable generation
- hotkey-first
- small-model friendliness

---

### 2. Grid Domain

GSS-OS does not always ask the model to interpret raw screen pixels.  
Instead, it discretizes the screen into 1–8 adaptive grid layers and turns GUI navigation into a **text-native coordinate selection problem**.

Examples:

```text
c C4
dr A1 D8
```

This allows even non-multimodal small models to perform GUI localization.

---

### 3. Dynamic libraries

The system does not inject all tools and knowledge into context at once.  
Libraries are loaded on demand:

```text
ld lib_web
ld lib_sys
```

This follows the minimal-use-set principle:  
**only the knowledge needed for the current task step should be active.**

---

### 4. HOW-code + Hard Freeze

When existing tools are insufficient, the executor model may emit:

```text
hc img_zip
```

This does **not** immediately run code.  
Instead, it triggers:

1. tool specification generation
2. creator model code generation
3. **Hard Freeze**
4. human review
5. registration only if approved

> Tool creation is not a normal action call.  
> It is a modification of the system's capability boundary.

---

## Why this is friendlier to small models

GSS-OS does not try to "make the model smarter" by force.  
It tries to **reduce the complexity of action representation**.

Compared with heavy GUI agents, it avoids asking the model to simultaneously handle:

- full-screen visual understanding
- long context processing
- complex schema generation
- high-dimensional action regression

Instead, it mainly asks the model to emit short text-native command sequences.

---

## Early empirical profile

Under defined desktop-control tasks, our current early-stage prototype shows:

- **GSS-OS per action**: around **120–180 tokens**
- **heavy frameworks**: often **3000–7000+ tokens**

- **GSS-OS first-action latency**: around **0.3–1.0s (local 7B)**
- **heavy approaches**: often several seconds to minutes

> These are early prototype measurements under defined task settings, not universal claims for all environments.

---

## Safety boundary

GSS-OS relies on:

- whitelist parsing
- atomic instruction constraints
- argument validation
- dynamic library loading control
- Hard Freeze human review
- no unreviewed code entering execution

The most important rule is:

> **The system must remain halted until the user makes an explicit decision.**

---

## Scope and limits

GSS-OS does **not** claim to replace all agent frameworks.  
It is currently best suited for:

- desktop / OS control
- local small-model execution
- low-token / low-latency environments
- offline / air-gapped / privacy-sensitive settings
- auditable execution scenarios

It is **not** primarily designed for:

- complex long structured API orchestration
- full visual semantic understanding
- general-purpose multimodal QA
- replacing all DOM / accessibility-tree systems

For some extraction tasks, screenshots may still be used as a **fallback mechanism**.  
But the principle remains:

> **avoid screenshots for navigation whenever possible.**

---

## Current status

Completed:

- [x] theory launch
- [x] Windows MVP
- [x] model integration
- [x] 16-instruction control chain
- [x] Grid Domain prototype
- [x] Hard Freeze prototype
- [x] paper figures and LaTeX drafts

Next:

- [ ] full GitHub open-source cleanup
- [ ] more stable local runtime
- [ ] Grid + OCR-Light refinement
- [ ] HOW-code registration workflow
- [ ] benchmarks and external reproduction
- [ ] arXiv-ready paper package

---

## Theory package

Current theory includes:

- **GSS-OS overview**
- **GSS from language generation mechanisms**
- **Formal definition of GSS**
- **The Constant-Dalink incompleteness formula**
- **Grid Domain**
- **AI Assembly Language: the 16-instruction set**
- **HOW-code: hard-freeze tool bootstrapping**

A unified theory index will be published soon.

---

## We welcome

We welcome:

- trials
- criticism
- reproduction
- reverse engineering
- benchmark proposals
- PRs
- academic criticism
- safety review suggestions

> What we need most right now is not applause, but real feedback.

---

## License

[MIT](LICENSE)
```

