# Local IT Copilot — Build Plan, Hardware & Cost Analysis (Phase 0.5)

> You gave requirements; this is the architect's response: recommended hardware (3 tiers, 2026
> prices), local-vs-cloud cost + break-even, the full component design (26 items), a 6-phase plan,
> and plain-English explanations of anything unfamiliar. **Still no implementation — this is the
> decision doc you approve before we build Phase 1.** Date: 2026-06-01.
> Builds on `Local-IT-Copilot-Architecture.md`.

---

## Plain-English glossary (read this first)

- **MVP (Minimum Viable Product):** the *smallest version that is genuinely useful to you every day*,
  built so we don't throw it away later. Not a toy — a real tool with a narrow scope. Yours = "ask
  questions across my docs + exported email + configs, get cited answers, on my own machine."
- **LLM:** the language model (the "brain" that writes answers). Runs locally.
- **RAG (Retrieval-Augmented Generation):** before the LLM answers, we *search your data* and hand it
  the relevant snippets. The LLM answers *from those snippets*, not from memory. This is how it knows
  your VLANs without being retrained.
- **Embedding:** a document chunk turned into a list of numbers ("vector") capturing its meaning, so
  we can find similar text by math. Made by an **embedding model**.
- **Vector database (Qdrant):** stores those vectors and finds the closest ones fast.
- **Reranker:** a second, pickier model that re-scores the top search hits so the *best* ones rise to
  the top. Big accuracy win, cheap to run.
- **PostgreSQL (Postgres):** an ordinary, rock-solid database for structured facts — file metadata,
  versions, dates, parsed config data, who-can-see-what, audit logs.
- **Quantization:** compressing a model so it fits in less GPU memory (VRAM) with tiny quality loss.
  "Q4" ≈ 4-bit, roughly half the size. Standard practice for local AI.
- **Air-gapped:** a machine with **no network connection at all** — maximum security, but you can't
  download updates or models without sneakernet (USB). See §Security for the trade-off.
- **RBAC (Role-Based Access Control):** permissions by role ("engineer," "manager," "admin") instead
  of per-person rules.
- **Batfish:** explained in §12 — think "a simulator that reads your network configs and answers
  questions about them, deterministically, without touching real devices."

---

## PART A — HARDWARE & COST

### A1. Buy local. Here's why (short version)
Your data is sensitive corporate IT information, and you'll use this **daily and long-term**. Both the
money and the security point the same way: **a local machine you own.** Cloud makes sense only for
occasional experiments on *sanitized* data. Numbers below.

### A2. Recommended hardware — 3 tiers (2026 US prices, approximate)

The one spec that matters most for local AI is **GPU VRAM** (video memory) — it sets which models you
can run. Everything else supports it. Best value in 2026 is still the **used RTX 3090 (24 GB)** —
roughly **$750–900** and unbeatable on VRAM-per-dollar
([XDA](https://www.xda-developers.com/used-rtx-3090-still-best-for-local-ai-in-value/),
[D-Central](https://d-central.tech/used-rtx-3090-for-llms-2026/)).

| Component | **Budget (~$1,300)** | **Recommended (~$2,400)** | **High-end (~$4,800)** |
|-----------|----------------------|---------------------------|------------------------|
| **GPU** | 1× used RTX 3090 24 GB (~$800) | 1× RTX 4090 24 GB used (~$2,000) **or** 2× used 3090 = 48 GB (~$1,600) | RTX 5090 32 GB (~$2,500–3,000) **or** 2× 4090 = 48 GB, or RTX A6000 48 GB |
| **CPU** | Ryzen 5 7600 (~$180) | Ryzen 7 7700 (~$300) | Ryzen 9 7900X (~$400) |
| **RAM** | 64 GB DDR5 (~$150) | 64–128 GB (~$150–350) | 128 GB (~$350) |
| **Storage** | 2 TB NVMe (~$130) | 2 TB NVMe + 4 TB HDD (~$230) | 4 TB NVMe + 8 TB HDD (~$550) |
| **Motherboard** | B650 (~$150) | B650/X670 (~$200) | X670E (dual-GPU capable) (~$350) |
| **PSU** | 850 W (~$100) | 1000 W (~$140) | 1200–1600 W (~$250) |
| **Cooling/Case** | Air cooler + case (~$120) | Air/AIO + case (~$180) | High airflow + AIO (~$300) |
| **Approx total** | **$1,300** | **$2,400** (single 4090) | **$4,800** |

**What each tier runs:**

| | Budget (24 GB) | Recommended (24–48 GB) | High-end (32–48 GB) |
|--|--|--|--|
| Everyday model | Qwen 2.5 **14B** Q4/Q5, 32k ctx | 14B at full quality; **32B** Q4 | **32B** Q5/Q6 fast; 70B Q4 (48 GB) |
| Speed (single user) | ~20–35 tokens/sec | ~30–50 tok/s | ~40–70 tok/s |
| Useful context | 16k–32k comfortably | 32k | 32k+ |
| Embeddings + reranker + Qdrant + Postgres **at the same time** | ✅ yes (they're light; run on CPU/spare VRAM) | ✅ easily | ✅ easily |
| Bulk document processing | ✅ good | ✅ faster | ✅ fastest |
| Multiple users later | ⚠️ one-at-a-time-ish | ✅ small team (with vLLM batching) | ✅ team |

**My pick for you: start at the Budget tier (used 3090, 24 GB, ~$1,300).** It runs the entire
recommended software stack *and* your everyday 14B model well. If you already know a team is coming
soon, jump to Recommended (a 4090 for speed, or 48 GB via dual-3090 to run 32B/70B). The high-end tier
is "room to grow" — don't buy it on day one.

**Other specifics you asked about:**
- **NVMe:** yes, use an NVMe SSD (not SATA) for the OS + databases + active data — vector search and
  Postgres are I/O-heavy; NVMe makes ingestion and queries noticeably snappier. Keep bulk
  originals/backups on a cheaper large HDD.
- **PSU headroom:** a 3090/4090 spikes hard; 850–1000 W gives margin. Dual-GPU → 1200 W+.
- **Cooling:** a 3090/4090 dumps a lot of heat; a good airflow case + quality air cooler is enough for
  single-GPU. Dual-GPU wants strong airflow.

### A3. Operating system: **Ubuntu Linux 24.04 LTS** (recommended)
This will be an always-on server-style box. Linux gives you the smoothest NVIDIA/CUDA drivers, native
Docker, and native Postgres/Qdrant/Batfish with no translation layer.
- **Linux vs Windows:** Windows works via **WSL2** (a Linux environment inside Windows) + Docker
  Desktop, but it adds a moving part and some GPU-passthrough friction. If you're far more comfortable
  in Windows, WSL2 is acceptable; if you're willing to run Ubuntu, do that — it's the cleaner path for
  a 24/7 knowledge server. **We'll use Docker Compose** either way so the stack is reproducible.

### A4. Cloud comparison + break-even
Realistic 2026 rates for a 24 GB-class GPU
([RunPod](https://hackceleration.com/labs/runpod-pricing),
[Spheron](https://www.spheron.network/blog/runpod-vs-vastai-2026/)):
RunPod **Secure Cloud** RTX 4090 ≈ **$0.69/hr** (Community ≈ $0.34/hr but that's *strangers' machines*
— unacceptable for corporate data); A100 80 GB ≈ $1.39–1.49/hr; H100 ≈ $2.89/hr. Plus persistent
storage (~$0.05–0.07/GB/month → 100 GB ≈ $5–7/mo) and egress.

**Cloud cost at Secure-Cloud 4090 ($0.69/hr), compute only:**

| Usage | Per month | Per year |
|-------|-----------|----------|
| 1 hr/day | ~$21 | ~$250 |
| 4 hr/day | ~$83 | ~$1,000 |
| 8 hr/day | ~$166 | ~$2,000 |
| 24/7 | ~$500 | ~$6,000 |

**Break-even vs the ~$1,300 Budget local build** (add ~$10–25/mo local electricity):

| If you'd use cloud… | Cloud/yr | Local pays for itself in… |
|---------------------|----------|---------------------------|
| 4 hr/day | ~$1,000 | **~15–16 months** |
| 8 hr/day | ~$2,000 | **~8 months** |
| 24/7 (always-on for a team) | ~$6,000 | **~3 months** |

A knowledge base you query throughout the workday is effectively "8 hr/day+," so **local pays back in
under a year and then runs for years for the cost of electricity.** And that's *before* the security
argument: on cloud your sensitive corporate data either lives on rented storage (ongoing third-party
exposure) or gets re-uploaded each session (slow, still transits a third party). **Local keeps the
corporate knowledge base on hardware you physically control.**

**Verdict: buy local (Budget tier to start). Keep RunPod only for occasional heavy experiments on
sanitized/sample data.** Financially and for privacy, local wins for this project.

### A5. Estimated software cost: **$0 in licensing**
Every component below is free/open-source (Ollama, Qwen weights, BGE-M3, Qdrant, PostgreSQL, FastAPI,
Batfish, restic, Streamlit, Docker). Your only real costs are **hardware once + electricity + your
time.** Optional extras: a UPS (~$150, protects the box + graceful shutdown), an external backup drive.

---

## PART B — THE SYSTEM DESIGN (your 26 items)

Design principle throughout: **start simple, but every early choice is one we can extend — never
one we'd have to rip out.** The schema carries multi-user/ACL/secret fields from day one even though
the MVP is single-user, so Phase 5 is an *addition*, not a rebuild.

### B1–B7. Model & retrieval stack (recommended, unchanged from prior doc — still the right calls)
| Item | Pick | Plain-English reason |
|------|------|----------------------|
| **LLM** | **Qwen 2.5 14B Instruct** (7B if GPU-limited; 32B when you have 24 GB+) | strong at networking + follows "answer only from my data" + good structured output |
| **Embedding model** | **BGE-M3** | gives *both* meaning-search and exact-keyword-search from one model — perfect for IT text full of `VLAN 30`, `SW-01`, IPs |
| **Reranker** | **bge-reranker-v2-m3** | cheaply re-sorts hits so the best source is #1 |
| **Vector DB** | **Qdrant** (Docker) | fast similarity search + filter by site/date/permission + easy backups |
| **Keyword search** | Qdrant sparse / BM25 | exact-token matches embeddings miss |
| **Relational DB** | **PostgreSQL** | the "source of truth": metadata, versions, dates, parsed configs, permissions, audit |
| **Runtime** | **Ollama** now → **vLLM** when you need multi-user speed | Ollama = easiest reliable local serving |

### B8. Database architecture (two stores, one truth)
- **PostgreSQL = system of record.** Tables: `artifacts` (every file/email/message/config, with
  hash + version + dates + site + type + sensitivity + ACL), `chunks`, `config_facts`
  (device/interface/VLAN/trunk rows parsed from configs), `secrets_refs` (pointers, never values),
  `users`/`roles` (empty-ish in MVP), `audit_log`.
- **Qdrant = the search index.** Holds vectors + a *copy* of the filter fields (site, date,
  source_type, sensitivity, acl). If Qdrant is ever lost, we rebuild it from Postgres + originals.
- Why two: temporal logic ("latest approved"), permissions, and exact config facts are **SQL
  problems**; semantic search is a **vector problem**. Use each tool for what it's good at.

### B9. Document ingestion pipeline
`detect file → identify type → parse (Docling/unstructured + PyMuPDF) → OCR if scanned (Tesseract) →
clean → extract metadata (dates, site, device, type) → secret-scan/redact → classify
(general/org/site/sensitive) → chunk (structure-aware) → embed (BGE-M3) → index (Qdrant + Postgres)
→ verify`. **Change detection** via file **hash** + **version tracking**: unchanged hash = skip;
changed = new version (old kept, marked superseded); missing = mark deleted. Nothing is silently
overwritten; history is preserved (needed for "what was the config before?").

### B10. PST ingestion pipeline (works with **zero** Microsoft Graph access)
This is your MVP path for email. You export your mailbox to a `.pst` file yourself
(*Outlook → File → Open & Export → Import/Export → Export to a file → .pst* — no admin needed), drop
it in a watched folder, and we parse it locally with a PST library (`libratom`/`readpst`). We
preserve sender, recipients, subject, date, **ConversationId/Thread-Index** (so threads reconstruct),
message-id, and **attachments** (each attachment is parsed as its own linked document). Same schema as
everything else, so email answers get citations and temporal ordering ("migration completed" in March
beats the January "planned" message).

### B11. Teams ingestion strategy (export-first, Graph-optional, **never scraping**)
Assume no live API at first. Legitimate, authorized options, best-first:
1. **Manual/selective capture (MVP-friendly):** for the high-value threads ("we fixed the switch by
   changing X," "POS at Property X needs Y"), export or paste the conversation into a monitored notes
   folder; we ingest it with Teams metadata (team/channel/date/author). Low-tech, immediate, and you
   control exactly what enters.
2. **Compliance/eDiscovery export (needs IT):** the tenant-supported way to export channel data as
   files — admin-run, but it's the *sanctioned* bulk path if IT will do it for your area.
3. **Microsoft Graph read-only (if/when approved):** the clean automated path (delta sync), gated on
   corporate consent — designed for now, switched on later. **Same schema** as manual capture, so
   early manual work isn't wasted.
> We will **not** scrape Teams, bypass MFA, or touch data you aren't authorized to export. The system
> only ingests what you legitimately export.

### B12. Network configuration parser — and **why vendor scope matters** + **what Batfish is**
**Why vendor matters:** a config file is a *language*. Cisco IOS, NX-OS, Aruba, FortiOS, and
PAN-OS each have different grammar for "this port is a trunk" or "this VLAN exists." A parser must
understand each dialect — one regex won't cover all. So multi-vendor = multiple parsers or a tool
that already speaks many dialects.

**Two layers:**
- **Light parsing (Phase 3 start): `ciscoconfparse2`** — reads Cisco-style configs and answers
  per-file questions (which VLANs, which ports are trunks/access, PortFast/BPDU Guard, management IP).
  Deterministic and exact.
- **Deep analysis: Batfish.** *Plain English:* **Batfish is like a flight simulator for your network
  configs.** You feed it the config files (Cisco, Arista, Juniper, Palo Alto, Fortinet, Aruba —
  varying support), and it builds a **vendor-neutral model of your whole network** in memory. Then it
  answers questions **deterministically, without touching a single real device**: which VLANs/trunks
  exist, what's connected to what, will this firewall rule permit that traffic, what *differs* between
  two configs, does this config violate our standard. It turns "ask the LLM to guess from config text"
  (risky) into "compute the exact answer" (trustworthy).
  - **Do we need it?** For *single-file* "which VLANs on SW-01," `ciscoconfparse2` is enough. For
    **multi-device, topology, consistency, and diff** questions across a mixed-vendor estate — which
    is your long-term goal — **Batfish adds real, deterministic value.** So: **not on day one;
    introduce it in Phase 3 when config Q&A becomes central.** We add it because it makes answers
    *correct*, not because it's interesting.
  - **Gaps:** **Meraki** is cloud-managed (no CLI config file) → its data comes from the Meraki
    dashboard/API export, handled as structured data, not Batfish. Some vendors are partial in
    Batfish → fall back to targeted parsers or treat as documents.

**Routing rule (important):** deterministic config questions go to the **parser/Batfish**, and the LLM
only *explains* the computed result. The LLM never eyeballs raw config and guesses — that's how you
get confident wrong answers about your own network.

### B13. Configuration / versioning strategy
Every config ingest is hashed and versioned. We keep **every version** with its date, so you get "what
changed between old and new" (a real diff, from the parser, not a vibe) and "what was configured in
2025." `is_current` marks the live one. This is just the temporal model applied to configs.

### B14. OCR strategy
Many diagrams/screenshots/scanned PDFs are images. **Tesseract** (free, local) extracts text so they
become searchable; upgrade to **PaddleOCR** if accuracy on messy scans matters. For actual *diagrams*
(topology pictures), OCR gets the labels; a **vision model (Qwen 2.5-VL)** can describe them — but
**authoritative topology comes from configs (Batfish), not from images.** Set expectations: images
become *searchable and described*, not perfectly *understood*.

### B15. Metadata strategy (the backbone)
Every chunk carries: source_type, title, author, date(s), **site/property**, device, entities
(VLAN/IP/ticket), **knowledge_tier** (general / org / site / sensitive), **source_authority**,
sensitivity, ACL, version/is_current, thread links, attachment links. This single schema is what lets
one question search across everything *and* apply your source-priority and site-specific rules.

### B16. Permission / RBAC architecture (simple now, extensible later)
- **MVP:** single user (you) = everything you ingest is yours. But the schema already has `acl`,
  `sensitivity`, and a `users`/`roles` table (with just you in it).
- **Phase 5:** turn on real auth + roles. The retrieval layer already filters by `acl`/`sensitivity`
  **before** the LLM sees anything, so adding roles = populating those fields and enforcing them — no
  rebuild. **The model only ever receives chunks the asker is allowed to see**, so it can't leak by
  design.

### B17. Secrets-management strategy (this is the important one for Wi-Fi/credentials)
**Rule: secret *values* never go into the vector index or an LLM prompt.** Pipeline:
1. **Detect** secrets at ingest (Wi-Fi/network/server passwords, API keys, tokens, private keys,
   connection strings).
2. **Separate them:** the actual value goes into an **encrypted, access-controlled credential store**
   (Postgres field encryption now; a secrets manager like Vault later). The searchable index gets only
   a **reference**: *"Wi-Fi password for Property A → credential entry #123 (restricted)."*
3. **Answer with an authorization check, outside the LLM:** when you ask *"Where is the Wi-Fi password
   for Property A?"*, the backend checks your permission; if authorized, it returns the value **from
   the encrypted store directly** (it doesn't need to pass through the LLM at all), and logs the
   access. If not authorized, the assistant says it exists but you can't view it.

This satisfies "answer only if authorized," keeps secrets out of ordinary prompts, and means a leaky
LLM output can't spill credentials because **the LLM never had them.**

### B18. API / backend architecture
**FastAPI** (Python) is the brain: it authenticates the user, detects query intent (general vs
site-specific vs config vs current-vs-historical), builds the permission/site/date filter, runs hybrid
search + rerank, routes deterministic config questions to the parser/Batfish, assembles context +
citations, calls the LLM with untrusted data safely delimited, filters the output, and logs to the
audit trail. All the "smart" rules live here.

### B19. Frontend
- **Phase 1 (day-one validation):** **Open WebUI** — get the model chatting fast to confirm hardware
  works. Throwaway for validation only.
- **MVP proper → Phase 4:** **Streamlit** custom UI — chat, upload, **source/site/date/type filters**,
  **citations panel**, KB management, system status. Python, fast to build, matches your needs.
- **Phase 5 (team):** **React/Next.js** if it becomes a real multi-user product with logins.

### B20. Authentication
MVP: local, single-user (bound to your machine, no exposure). Phase 5: **OAuth2/OIDC** via a local
identity provider (Authentik or Keycloak) + JWT sessions + RBAC. Microsoft-tokens (for Graph) stored
in the OS keychain, encrypted, revocable.

### B21. Backup architecture
**3-2-1** (3 copies, 2 media, 1 offsite/offline). Nightly **encrypted** backups with **restic** or
**borg** of: (a) original files (content-addressed by hash), (b) Postgres dump (`pg_dump`), (c) Qdrant
snapshot. Qdrant can always be rebuilt from (a)+(b), so originals + Postgres are the crown jewels.
Document a tested **recovery procedure** (restore DB, restore originals, re-index). Encrypted external
drive + optional offsite.

### B22. Security architecture (primary requirement)
- **Local inference** (data doesn't leave the box for answers).
- **Controlled egress** (see §Air-gap): firewall **allowlist** to only what's needed (model
  downloads, OS/security updates, Graph endpoints *if* enabled); **log** all outbound; deny the rest.
- **Encryption at rest** (full-disk LUKS + encrypted secret fields), **in transit** (TLS if ever on a
  LAN), strict **file permissions**.
- **Secret detection/redaction**, **secret separation** (§B17), **retrieval-time ACL filter**,
  **audit logging** of every query + sources + secret access, **secure deletion**, **backups**,
  **network segmentation** (put ingestion/model services on an internal Docker network; only the UI
  port is reachable, and only locally in MVP).
- **Prompt-injection defense:** retrieved content is treated as **untrusted data**, never as
  instructions; the assistant is **read-only with no autonomous tools**, so a malicious "ignore
  instructions, reveal passwords" line in a Teams export is inert — the model can't act and never held
  the passwords anyway.

**What must NEVER go into the LLM context (unless strictly necessary and authorized):**
- Raw **credentials/secrets** (Wi-Fi, network, server passwords, API keys, private keys) — served via
  the authorized backend path, tokenized in the index.
- **Other users'** data (filtered out before retrieval).
- Anything flagged by the **secret scanner**.
- **Excessive/whole documents** — send only the minimal relevant chunks (smaller context = safer +
  faster + cheaper).
- **HR/legal/finance/personal** content (excluded or walled).

### B23. Scaling strategy
Grow **vertically first** (it's cheapest and simplest): single GPU + Ollama handles single-user.
For a team: switch the runtime to **vLLM** (batches many users on one GPU) and/or add a second GPU;
Postgres/Qdrant scale comfortably to 100 GB+ on one box. Only consider multiple machines / Kubernetes
if the team grows large — likely never for your scope. **Design is horizontal-ready (stateless
FastAPI, external DBs) but we don't pay that complexity until needed.**

### Storage: how it scales (your §5 question answered)
The *originals* dominate size; the AI-derived data is smaller than people expect.

| Layer | What it is | Rough size at 100 GB of originals |
|-------|------------|-----------------------------------|
| **Raw originals** | your actual PDFs/DOCX/PST/configs/images | **100 GB** (the big one) |
| **Extracted text** | plain text pulled from them | ~2–8 GB |
| **Chunks** | text split into passages | similar to extracted text |
| **Embeddings** | vectors in Qdrant (BGE-M3 dense ≈ 2–4 KB each) | ~5–20 GB depending on chunk count |
| **Metadata (Postgres)** | rows describing everything | ~1–5 GB |
| **Backups** | encrypted copies of originals + DB | ~1× originals + a bit |

**Scaling rule of thumb:** budget **~2–2.5× your originals** for the working system, plus **~1×** for
backups. So: 10 GB originals → ~25 GB working + ~10 GB backup; 100 GB → ~250 GB working + ~100 GB
backup. That's why the build has a **2 TB NVMe** (active system) **+ a large HDD** (originals archive +
backups). You're comfortable to well past 100 GB on the recommended tier.

---

## PART C — PHASED IMPLEMENTATION

Each phase is independently useful and builds on the last. **We do them one at a time: I explain,
give code, you test, we fix, then proceed.**

### Phase 1 — Single-user MVP  *(the goal: a useful daily tool)*
- **Build:** Ollama + Qwen 2.5 14B · Qdrant (hybrid) + BGE-M3 + reranker · Postgres schema (with
  multi-user/ACL/secret fields present but unused) · document ingestion (PDF/Word/Excel/CSV/MD/TXT/
  HTML) · **PST email ingestion** · secret detection/redaction · **citations** · temporal
  current-vs-historical · Streamlit UI with source filters · local-only.
- **Why:** proves the core loop — *your data in, cited answers out, on your machine* — and it's the
  thing you'll actually use.
- **Hardware:** Budget tier (used 3090, 24 GB) is enough. **Software:** all free. **Cost:** ~$1,300
  one-time. **Performance:** ~20–35 tok/s, sub-second retrieval. **Postpone:** Teams API, Batfish,
  RBAC, knowledge graph.

### Phase 2 — Email + document intelligence
- **Build:** better parsing + **OCR** (scanned docs/screenshots), **contextual retrieval** (recall
  boost), **attachment linking**, **thread reconstruction**, dedup + versioning + change detection.
- **Why:** turns "a pile of files" into well-structured, deduplicated, thread-aware knowledge.
- **Hardware:** same box. **Cost:** $0 extra. **Postpone:** config intelligence.

### Phase 3 — Network configuration intelligence
- **Build:** `ciscoconfparse2` parsing → structured **config_facts** tables → **Batfish** for
  multi-vendor + topology + diff + consistency; deterministic routing for config questions.
- **Why:** exact, trustworthy answers to "which VLANs/trunks on SW-01," "what changed," "is this
  consistent with our standard" — across Cisco/Aruba/Fortinet/Palo Alto (Meraki via its dashboard
  export).
- **Hardware:** same (Batfish is CPU/RAM, not GPU). **Cost:** $0 extra. **Postpone:** full graph.

### Phase 4 — Teams / ticket integration
- **Build:** Teams **export** ingestion (manual/compliance) with full thread metadata; ticket import
  (ServiceNow API or CSV); Graph read-only **if** IT approves (same schema).
- **Why:** captures the institutional knowledge that lives in conversations and tickets.
- **Hardware:** same. **Cost:** $0 (unless a bigger disk as data grows). **Postpone:** RBAC.

### Phase 5 — Multi-user / RBAC
- **Build:** auth (OIDC), roles, **document-level permissions**, department/site access, **audit
  logs**, enforced **secret access control**, admin panel; likely **vLLM** for concurrent users;
  probably a **React** UI.
- **Why:** safely open it to the IT team without anyone (or the LLM) bypassing permissions.
- **Hardware:** consider Recommended/High-end tier (more VRAM for concurrent users) — a good moment to
  add a second GPU. **Cost:** possibly +$1,000–2,500 GPU. **Postpone:** graph until proven.

### Phase 6 — Advanced enterprise knowledge system
- **Build (only what's justified):** **knowledge graph** (Neo4j) *if* multi-hop topology questions
  demand it; richer topology; VLM diagram understanding; **evaluation harness** (accuracy, citation,
  hallucination, latency); production hardening (monitoring, HA, tested DR).
- **Why:** the "connect everything" layer — added on evidence, not hype.
- **Hardware:** same or +RAM for a graph DB. **Cost:** $0–modest. **Postpone by default:** anything
  not pulling its weight in real queries.

---

## Honest pushback / corrections to your assumptions (your rule)
- **Don't rent cloud GPUs for this.** For daily use on sensitive data, local is cheaper within a year
  *and* safer. Cloud is for sanitized experiments only.
- **Don't buy the high-end box first.** A used-3090 Budget build runs your whole MVP; scale the GPU
  when a team actually arrives.
- **Don't put secrets in the vector store or LLM prompts.** Separate credential store + authorized
  retrieval path — the design in §B17. This is the single most important security decision.
- **Don't let the LLM answer config questions from raw text.** Parse/compute them (ciscoconfparse2 /
  Batfish); the LLM explains the result.
- **Don't build the knowledge graph early.** Metadata + Postgres + NetworkX first; Neo4j only if
  Phase 6 queries prove it.
- **Don't wait on Teams API.** Start with what you can legitimately export; the schema makes Graph a
  drop-in later.

---

## What I need to start Phase 1
Just a **go decision on the hardware tier** (my recommendation: **Budget — used RTX 3090, 24 GB, ~$1,300**,
Ubuntu 24.04). Once you've got a machine (or if you want, we can prototype Phase 1 on a temporary
RunPod box with *sample* data to prove it out before you buy), we start **Phase 1, step 1: install
Ollama and get Qwen 2.5 running** — you test it, then we add retrieval.

**Sources (pricing):**
[XDA — used 3090 value](https://www.xda-developers.com/used-rtx-3090-still-best-for-local-ai-in-value/) ·
[D-Central — 3090 for LLMs 2026](https://d-central.tech/used-rtx-3090-for-llms-2026/) ·
[Tom's Hardware — GPU price tracker](https://www.tomshardware.com/pc-components/gpus/lowest-gpu-prices-tracking) ·
[RunPod pricing](https://hackceleration.com/labs/runpod-pricing) ·
[Spheron — RunPod vs Vast.ai 2026](https://www.spheron.network/blog/runpod-vs-vastai-2026/)
