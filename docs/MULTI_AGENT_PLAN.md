# Pulse Multi-Agent Intelligence Plan

> H3 + OpenClaw-inspired learning and agent architecture for Pulse.
> Created: 2026-03-17 | Updated: 2026-03-17 | Status: Active

## Architecture Overview

Two agents, one living brain:

```
┌─────────────────────────────────────────────────────────────┐
│                      Pulse UI (Browser)                      │
│                                                              │
│  ┌────────────────────────┐  ┌────────────────────────────┐ │
│  │   Troubleshooter       │  │      Builder Agent         │ │
│  │   Agent Tab            │  │      Tab                   │ │
│  │                        │  │                            │ │
│  │  Session Memory        │  │  Reads source code         │ │
│  │  Web Search            │  │  Generates diffs           │ │
│  │  Living Brain ←────────│──│─ Learns from outcomes      │ │
│  │  Smart Routing         │  │  Shows approval gate       │ │
│  │  Safety Guardrails     │  │  Applies changes           │ │
│  └────────────────────────┘  └────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                            │
    Ollama/Gemini/Claude         Claude API
    (routed by evidence)         (tool use)
         │
┌────────┴─────────────────────────────────────────┐
│              Living Brain (SQLite)                 │
│                                                    │
│  troubleshooting_facts   -- {symptom, diagnosis,   │
│                              resolution, outcome}  │
│  fact_relations          -- causes, resolves,      │
│                              co-occurs             │
│  knowledge_gaps          -- what AI can't solve    │
│  session_outcomes        -- full session tracking  │
│                                                    │
│  Activation Decay: Hot → Warm → Cool               │
│  Hybrid Search: Vector + FTS5 keyword              │
│  Metabolism: Auto-extract facts after sessions     │
│  Outcome Loop: success/failure → confidence        │
└──────────────────────────────────────────────────┘
```

## Design Principles

1. **Living brain, not dead memory**: The AI gets smarter over time because its CONTEXT improves — high-confidence facts injected first, failed approaches deprioritized, knowledge gaps surfaced. (OpenClaw pattern)
2. **Cost-conscious**: Ollama (free) handles common troubleshooting. Claude only when justified or for Builder.
3. **Approval-first**: Builder always shows diffs. Troubleshooter fixes always need user approval.
4. **Works for anyone**: Should troubleshoot YOUR RTX 5090 today and a grandma's Dell tomorrow. Knowledge is hardware-aware but not hardware-locked.
5. **Incremental**: Each phase is independently useful and testable.

## End Goal

User says "my screen is going black." Pulse:
1. Reads system logs, crashes, event monitor, reliability data, recent installs
2. Checks session memory for what's already been tried
3. Searches the web for current known issues with their specific hardware/driver
4. Queries the living brain for similar past problems and what worked
5. Surfaces knowledge gaps (things it's uncertain about)
6. Diagnoses with confidence based on ALL of this context
7. Suggests fixes ordered by past success rate
8. After fix outcome, updates the brain so it's smarter next time

---

## Phase 1: Working Memory + Web Search ✅ COMPLETE

**Status**: Built and committed (2026-03-17)

### What was built:
- **Session Memory**: SQLite `session_memory` table, per-session key-value store
- **Memory Extraction**: Rule-based extraction of tried fixes, key facts, hardware focus from user messages
- **Memory Injection**: Session memory injected into both analyze + chat AI prompts
- **Hardware Anomaly Detection**: Flags unusual GPU temp, CPU usage, RAM pressure, disk space
- **Web Search**: DuckDuckGo HTML API, hardware-aware queries (GPU model + driver version), results injected into prompt
- **Stop Button**: AbortController-based cancel for in-flight AI requests
- **Session Management**: Create/get/delete/list sessions via API, frontend auto-creates on page load

---

## Phase 2: Living Brain (OpenClaw-Inspired Learning)

**Goal**: Build a genuine learning system where the AI gets measurably smarter over time. Not just storing memories — tracking outcomes, building confidence from evidence, and surfacing what it knows and doesn't know.

**Core insight from OpenClaw**: For API-based models (Ollama, Claude, Gemini), the model never changes — but the context it receives gets smarter. Learning = building better context from tracked outcomes.

### Phase 2A: Troubleshooting Facts Database

**What**: Structured knowledge base of {symptom, diagnosis, resolution, outcome} tuples with confidence scoring. This replaces the basic `patterns` table approach.

**New tables**:
```sql
-- Core facts: what the brain knows
CREATE TABLE IF NOT EXISTS troubleshooting_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symptom TEXT NOT NULL,
    diagnosis TEXT,
    resolution TEXT,
    confidence REAL DEFAULT 0.5,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    activation_tier TEXT DEFAULT 'warm',  -- hot/warm/cool
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    decay_score REAL DEFAULT 1.0,
    hardware_context TEXT,               -- JSON: {gpu, cpu, driver, etc.}
    source TEXT DEFAULT 'session',        -- session/web/manual
    superseded_by INTEGER REFERENCES troubleshooting_facts(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_facts_symptom ON troubleshooting_facts(symptom);
CREATE INDEX IF NOT EXISTS idx_facts_activation ON troubleshooting_facts(activation_tier);
CREATE INDEX IF NOT EXISTS idx_facts_confidence ON troubleshooting_facts(confidence DESC);

-- Relationships between facts
CREATE TABLE IF NOT EXISTS fact_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_fact_id INTEGER NOT NULL,
    target_fact_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,          -- causes, resolves, co-occurs, contradicts
    confidence REAL DEFAULT 0.5,
    observation_count INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_fact_id) REFERENCES troubleshooting_facts(id),
    FOREIGN KEY (target_fact_id) REFERENCES troubleshooting_facts(id)
);
CREATE INDEX IF NOT EXISTS idx_relations_source ON fact_relations(source_fact_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON fact_relations(target_fact_id);
```

**Files to create**:
- `backend/services/brain.py` — Living brain service: fact CRUD, confidence updates, search, context assembly

**Files to modify**:
- `backend/database.py` — Add tables, CRUD methods, FTS5 virtual table for keyword search

**Test criteria**:
- [ ] Facts table created on server start
- [ ] Can create, read, update facts via service
- [ ] Confidence calculation: `success_count / (success_count + failure_count)`
- [ ] Facts have hardware_context linking them to specific setups

### Phase 2B: Session Outcome Tracking

**What**: Track full session outcomes so we know what worked and what didn't. This is the PRIMARY training signal.

**New table**:
```sql
CREATE TABLE IF NOT EXISTS session_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    started_at DATETIME,
    ended_at DATETIME,
    symptoms_reported TEXT,          -- JSON array
    diagnostics_run TEXT,            -- JSON array (what system data was checked)
    diagnosis_reached TEXT,
    resolution_applied TEXT,
    outcome TEXT,                    -- resolved, partial, unresolved, wrong_diagnosis
    user_satisfaction INTEGER,       -- 1-5 (optional)
    ai_provider_used TEXT,
    facts_injected TEXT,             -- JSON array of fact IDs that were used
    hardware_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Session close flow**:
```
User says "that fixed it" or clicks "Resolved" or starts New Chat
  → System records session outcome
  → Triggers metabolism (Phase 2C)
  → Updates fact confidence scores
  → Living brain is now smarter
```

**Files to modify**:
- `backend/database.py` — Add table
- `backend/services/memory.py` — Save session outcome on session close
- `backend/routes/ai.py` — Add outcome endpoint, update session close to record outcome

**Frontend additions**:
- After a fix is tried, ask: "Did this fix the problem?" (Yes/No/Partially)
- On New Chat, if previous session had no outcome: prompt "Was your issue resolved?"

**Test criteria**:
- [ ] Session outcome saved when user reports fix result
- [ ] Session outcome saved when session ends
- [ ] Outcome includes all relevant data (symptoms, diagnosis, resolution, provider)
- [ ] Frontend prompts for outcome when appropriate

### Phase 2C: Metabolism (Fact Extraction)

**What**: After each session ends, automatically extract structured troubleshooting facts using LLM. This is how the brain LEARNS — it digests conversations into reusable knowledge.

**Metabolism flow** (runs on session close):
```
Session ends with outcome
  → Collect: full conversation, diagnosis, fixes tried, outcome
  → Send to Ollama (free):
     "Extract troubleshooting facts from this session.
      Return JSON array: [{
        symptom: 'what the user experienced',
        diagnosis: 'what was wrong',
        resolution: 'what fixed it (or null if unresolved)',
        worked: true/false,
        hardware_relevant: ['gpu', 'driver', 'display']
      }]"
  → Store facts in troubleshooting_facts table
  → If resolution worked: increment success_count on matching fact
  → If resolution failed: increment failure_count
  → Create fact_relations (symptom → diagnosis, diagnosis → resolution)
```

**Deduplication**: Before inserting a new fact, search existing facts for semantic similarity. If >0.85 similar, update the existing fact's counts instead of creating a duplicate.

**Files to create**:
- `backend/services/metabolism.py` — Fact extraction from sessions, dedup, confidence updates

**Files to modify**:
- `backend/services/memory.py` — Trigger metabolism on session close

**Test criteria**:
- [ ] Complete a troubleshooting session → facts automatically extracted
- [ ] Facts include correct symptom/diagnosis/resolution/outcome
- [ ] Duplicate facts are merged (counts updated, not duplicated)
- [ ] Fact relations created correctly
- [ ] Facts visible in the brain (can be queried)

### Phase 2D: Hybrid Search (Vector + FTS5)

**What**: When a new issue comes in, find the most relevant facts from the brain using both semantic similarity (vector) AND keyword matching (FTS5). This ensures "my computer is slow" matches "high CPU usage" (semantic) AND "slow boot" (keyword).

**Implementation**:
```sql
-- FTS5 virtual table for keyword search on facts
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    symptom, diagnosis, resolution,
    content='troubleshooting_facts',
    content_rowid='id'
);
```

**Search pipeline**:
```python
def find_relevant_facts(db, user_description, limit=5):
    # 1. Vector search (semantic similarity)
    vector_results = vector_search(user_description, limit=10)

    # 2. FTS5 keyword search
    keyword_results = fts5_search(user_description, limit=10)

    # 3. Weighted fusion
    combined = {}
    for r in vector_results:
        combined[r.id] = 0.7 * r.score
    for r in keyword_results:
        combined[r.id] = combined.get(r.id, 0) + 0.3 * r.score

    # 4. Apply activation decay
    for fact_id, score in combined.items():
        fact = get_fact(fact_id)
        decay = exponential_decay(fact.last_accessed, half_life=30)
        combined[fact_id] = score * decay * fact.confidence

    # 5. MMR re-ranking for diversity
    return mmr_rerank(combined, lambda_=0.7, limit=limit)
```

**Files to modify**:
- `backend/database.py` — Add FTS5 virtual table, FTS5 search method
- `backend/services/brain.py` — Add hybrid search function
- `backend/services/embeddings.py` — Ensure facts get embedded

**Test criteria**:
- [ ] "my computer is slow" matches "high CPU usage" fact (semantic)
- [ ] "blue screen" matches "BSOD" fact (keyword)
- [ ] Results ranked by combined score (vector + keyword + confidence + decay)
- [ ] Diverse results (not 5 variations of the same fact)

### Phase 2E: Knowledge Gap Detection

**What**: Track what the AI couldn't answer or got wrong. This surfaces uncertainty and helps identify where the brain needs to grow.

**New table**:
```sql
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symptom_description TEXT NOT NULL,
    gap_type TEXT NOT NULL,              -- unknown_symptom, no_resolution, low_confidence, wrong_diagnosis
    frequency INTEGER DEFAULT 1,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    resolution_fact_id INTEGER REFERENCES troubleshooting_facts(id),
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_gaps_type ON knowledge_gaps(gap_type);
CREATE INDEX IF NOT EXISTS idx_gaps_frequency ON knowledge_gaps(frequency DESC);
```

**Gap detection triggers**:
- Session outcome = `unresolved` or `wrong_diagnosis` → log gap
- No matching facts found for a symptom → `unknown_symptom`
- All matching facts have confidence < 0.3 → `low_confidence`
- User corrects the diagnosis → `wrong_diagnosis`

**Prompt injection**:
```
KNOWLEDGE GAPS (areas where I have limited experience):
- "intermittent USB disconnects" — seen 3 times, never resolved
- "DisplayPort audio crackling" — low confidence (2 attempts, 0 successes)

Be transparent about uncertainty for these topics. Ask more questions before diagnosing.
```

**Files to modify**:
- `backend/database.py` — Add table
- `backend/services/brain.py` — Add gap detection and tracking
- `backend/services/metabolism.py` — Create gaps from unresolved sessions

**Test criteria**:
- [ ] Unresolved session creates a knowledge gap
- [ ] Repeated unresolved symptom increments frequency
- [ ] When gap is later resolved, link it to the resolution fact
- [ ] Gaps injected into AI prompt for transparency

### Phase 2F: Smart Context Assembly

**What**: The final piece — when the AI is about to answer, assemble the smartest possible context from ALL brain data. This is where learning MANIFESTS.

**Context assembly order** (injected into every AI call):
```
1. SESSION MEMORY (what's been discussed this session)         -- Phase 1
2. WEB SEARCH RESULTS (current info from the internet)         -- Phase 1
3. RELEVANT FACTS (from living brain, ranked by confidence)    -- Phase 2
4. RESOLUTION HISTORY (what worked for similar problems)       -- Phase 2
5. KNOWLEDGE GAPS (areas of uncertainty)                       -- Phase 2
6. SYSTEM HARDWARE (current readings + anomalies)              -- Existing
7. RELIABILITY EVENTS (recent crashes, installs, updates)      -- Existing
```

**The key rule**: Facts with high success rates go first. Facts that failed get deprioritized. The AI naturally gives better advice because it sees "this fix worked 15/20 times" before "this fix worked 2/10 times."

**Files to modify**:
- `backend/services/brain.py` — `build_brain_context()` function
- `backend/ai/reasoning.py` — Replace current context building with brain-powered assembly
- `backend/services/chat.py` — Use brain context in follow-up chats

**Test criteria**:
- [ ] AI prompt includes relevant facts from the brain
- [ ] High-confidence facts appear before low-confidence
- [ ] Knowledge gaps shown when relevant
- [ ] Context stays within token budget (prioritize, don't dump everything)
- [ ] Facts with 0 successes are deprioritized or excluded

---

## Phase 3: Smart Routing + Conditional Review

**Goal**: Route issues to the best AI provider based on evidence from the living brain, and only invoke expensive review when there's reason to doubt.

### Phase 3A: Evidence-Based Provider Routing

**What**: Replace simple `should_skip_local()` with a routing function that uses brain data.

**Routing signals** (all from the living brain):
1. **Provider track record**: From session_outcomes — which provider resolved similar issues?
2. **Fact confidence**: If matching facts have high confidence → simple case → Ollama. Low confidence → complex → Claude
3. **Knowledge gaps**: If this symptom is a known gap → escalate to smarter provider
4. **Session state**: 2+ failed fixes → escalate
5. **Correction history**: Provider corrected 3+ times for this category → switch

**Files to modify**:
- `backend/ai/providers.py` — Add `route_to_provider()` using brain data
- `backend/services/brain.py` — Add provider performance queries

**Test criteria**:
- [ ] Simple known issue with high-confidence facts → Ollama
- [ ] Known knowledge gap → Claude
- [ ] 2+ failed fixes → provider escalated
- [ ] Routing decision logged with reason

### Phase 3B: Conditional Review (Targeted Supervisor)

**What**: When router flags `needs_review=True`, Claude reviews Ollama's diagnosis.

**Review triggers**:
- Router confidence < 0.5
- Issue matches a knowledge gap
- 3+ failed fixes in session
- No matching facts in brain (novel problem)

**Files to create**:
- `backend/services/review.py` — Conditional review service

**Files to modify**:
- `backend/services/analysis.py` — Add review step when flagged
- `frontend/src/pages/troubleshoot.js` — Show "Reviewed by Claude" badge

**Test criteria**:
- [ ] Review only fires when triggered (~10-20% of calls)
- [ ] Reviewed diagnoses show badge
- [ ] Review corrections fed back into brain as facts

### Phase 3C: Frontend Review Indicator

- Badge: "Reviewed by Claude" on reviewed diagnoses
- Tooltip with review score
- No manual trigger

---

## Phase 4: Builder Agent

**Goal**: A Claude-powered agent in a new tab that can read and modify Pulse's own source code, with diff-based approval gate. (OpenClaw's PI Agent concept)

### Phase 4A: Builder Backend (Tool-Use Agent)

**Builder tools** (exposed to Claude via tool_use):
| Tool | Description |
|------|------------|
| `read_file(path)` | Read a source file |
| `list_files(directory, pattern)` | List files matching a glob |
| `search_code(query, file_pattern)` | Search across codebase |
| `propose_edit(path, old_text, new_text)` | Propose a file edit (queued for approval) |
| `propose_new_file(path, content)` | Propose a new file |
| `propose_delete_file(path)` | Propose file deletion |
| `run_command(command)` | Run whitelisted shell command |
| `get_app_status()` | Get server status, recent errors |

**Safety**:
- All writes go through `propose_*` — nothing applied without approval
- Protected paths: `.env`, `data/*.db`, `.git/`, `venv/`
- Command whitelist: read-only commands only
- Auto-rollback if change crashes server

**Files to create**:
- `backend/agents/__init__.py`
- `backend/agents/builder.py` — Claude API with tool use
- `backend/agents/builder_tools.py` — Tool implementations
- `backend/routes/builder.py` — API endpoints

**Test criteria**:
- [ ] "what files make up the frontend?" → Builder lists them
- [ ] "make the progress bar green" → proposes CSS edit
- [ ] Proposal stored, NOT applied yet
- [ ] Edit .env → blocked

### Phase 4B: Approval Gate UI

**What**: Diff-view in Builder tab for approving/rejecting changes.

- Builder chat + proposals panel
- Each proposal: file path, diff view (red/green), Approve/Reject buttons
- After approval: file written, server restarts if needed
- Auto-rollback on server crash

**Files to create**:
- `frontend/src/pages/builder.js`

**Files to modify**:
- `frontend/index.html` — Add Builder tab
- `frontend/style.css` — Builder styles
- `frontend/src/main.js` — Builder routing
- `backend/app.py` — Register builder blueprint

**Test criteria**:
- [ ] Builder tab in navigation
- [ ] Chat with Builder agent
- [ ] Diff view for proposals
- [ ] Approve → change applied
- [ ] Reject → change discarded
- [ ] Bad change → auto-rollback

### Phase 4C: Builder Context & Safety

- Project file tree loaded at init
- CODEBASE_INDEX.md as context
- Recent git log
- Max 10 proposals per message
- Proposals expire after 1 hour

---

## Phase 5: Nightly Processing + Long-Term Learning

**Goal**: Background processes that run overnight to strengthen the brain — contemplation, decay maintenance, and trend detection.

### Phase 5A: Activation Decay Cron

**What**: Nightly job that ages fact activation scores and transitions tiers.

```python
# Run at 3 AM daily
def nightly_decay(db):
    # Age all facts
    for fact in get_all_facts(db):
        new_decay = exponential_decay(fact.last_accessed, half_life=30)
        update_decay_score(db, fact.id, new_decay)

        # Transition tiers
        days_since = (now - fact.last_accessed).days
        if days_since <= 7:
            tier = 'hot'
        elif days_since <= 30:
            tier = 'warm'
        else:
            tier = 'cool'
        update_activation_tier(db, fact.id, tier)
```

### Phase 5B: Trend Detection

**What**: Analyze accumulated facts to find systemic patterns.

- "GPU crashes increased 3x this month" → proactive warning
- "Driver X has been involved in 5 failed fixes" → auto-create knowledge gap
- "Resolution Y works for symptom A but not symptom B" → create fact_relation

### Phase 5C: Learning Dashboard v2

**What**: Show the brain's state on the Learning tab.

- Facts database browser with confidence bars
- Knowledge gaps list with frequency
- Session outcome history
- Brain growth over time chart
- Activation tier distribution

---

## Implementation Notes

### API Cost Estimates
| Phase | Additional Calls | Est. Cost |
|-------|-----------------|-----------|
| Phase 1 (Memory + Search) | 0-1 small Ollama + web requests | ~$0 |
| Phase 2 (Living Brain) | 1 Ollama call per session close (metabolism) | ~$0 |
| Phase 3 (Routing+Review) | Claude only when triggered (~10-20%) | ~$0.01-0.03/review |
| Phase 4 (Builder) | Claude with tool use per Builder chat | ~$0.05-0.20/conversation |
| Phase 5 (Nightly) | 0 additional | $0 |

### Architecture
- All learning runs on SQLite (no Neo4j needed for single-user)
- FTS5 for keyword search (built into Python sqlite3)
- Existing vector embeddings for semantic search
- Metabolism uses free Ollama calls
- No model fine-tuning needed — learning = better context assembly

### What This Plan Does NOT Do
- No model weight updates (requires self-hosted models, OpenClaw-RL)
- No Neo4j graph database
- No durable workflow engine
- No federation

### OpenClaw Patterns Adopted
| Pattern | Source | Pulse Implementation |
|---------|--------|---------------------|
| Structured fact memory | 12-layer architecture | `troubleshooting_facts` + `fact_relations` tables |
| Outcome-based confidence | OpenClaw-RL (adapted) | success_count / total → confidence score |
| Temporal decay | OpenClaw memory | `e^(-lambda * age_days)` with 30-day half-life |
| Activation tiers | 12-layer architecture | Hot (7d) / Warm (30d) / Cool (30d+) |
| Hybrid search | OpenClaw memory | Vector + FTS5 with weighted fusion |
| Metabolism | 12-layer architecture | LLM fact extraction on session close |
| Knowledge gaps | 12-layer contemplation | Track unresolved symptoms + low-confidence areas |
| PI Agent | OpenClaw core | Builder Agent with file tools + approval gate |
| Skills as markdown | OpenClaw skills | Not adopted (troubleshooting facts serve this purpose) |
| Growth vectors | 12-layer crystallization | Deferred to Phase 5+ (need more data first) |
