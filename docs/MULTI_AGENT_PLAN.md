# Pulse Multi-Agent Intelligence Plan

> H3-inspired learning and agent architecture adapted for Pulse's Python/Flask/SQLite stack.
> Created: 2026-03-17 | Status: Active

## Architecture Overview

Two agents, one app:

```
┌─────────────────────────────────────────────────────────┐
│                    Pulse UI (Browser)                    │
│                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │   Troubleshooter     │  │      Builder Agent       │ │
│  │   Agent Tab          │  │      Tab                 │ │
│  │                      │  │                          │ │
│  │  "My GPU keeps       │  │  "Make the progress bar  │ │
│  │   crashing"          │  │   green instead of blue" │ │
│  │                      │  │                          │ │
│  │  Context-aware       │  │  Reads source code       │ │
│  │  Session memory      │  │  Generates diffs         │ │
│  │  Dynamic HW context  │  │  Shows approval gate     │ │
│  │  Resolution paths    │  │  Applies changes         │ │
│  │  Smart routing       │  │  Restarts server         │ │
│  └──────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
         │                            │
    Ollama/Gemini/Claude         Claude API
    (routed by evidence)         (tool use)
```

## Design Principles

1. **Cost-conscious**: Ollama (free) handles common troubleshooting. Claude only when justified or for Builder.
2. **Latency-aware**: Never double response time without clear benefit.
3. **Approval-first**: Builder always shows diffs for approval. Troubleshooter fixes always need approval.
4. **Data-sparse**: Single user generates ~2-5 issues/week. Features must work with small datasets.
5. **Incremental**: Each phase is independently useful and testable.

---

## Phase 1: Working Memory (Session Context)

**Goal**: The Troubleshooter remembers what's been discussed, what's been tried, and what failed within a session. Currently every chat message rebuilds context from scratch.

### Phase 1A: Session Memory Storage

**What**: SQLite table + service to store structured session state.

**New table**:
```sql
CREATE TABLE IF NOT EXISTS session_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, key)
);
```

**Standard memory keys**:
| Key | Type | Purpose |
|-----|------|---------|
| `issue_summary` | string | One-line summary of current problem |
| `tried_fixes` | JSON array | `[{fix, outcome, timestamp}]` |
| `key_facts` | JSON array | Important facts discovered during conversation |
| `diagnostic_state` | string | `gathering_info`, `diagnosing`, `trying_fixes`, `resolved` |
| `hardware_focus` | JSON array | Which components are relevant (`["gpu", "display"]`) |
| `abnormal_readings` | JSON array | Hardware readings that seem unusual for context |

**Files to create**:
- `backend/services/memory.py` — Session memory CRUD + extraction logic

**Files to modify**:
- `backend/database.py` — Add table creation in migration, add CRUD methods

**Test criteria**:
- [ ] Session memory table exists after server start
- [ ] Can create, read, update, delete memory entries via service
- [ ] Memory persists across multiple chat messages in same session
- [ ] New session starts with clean memory

### Phase 1B: Memory Injection into Prompts

**What**: Automatically build a memory context section and inject it into every AI call during a chat session.

**Prompt injection format**:
```
SESSION MEMORY (what you know so far — use this to avoid repeating yourself):
- Issue: Monitor keeps going black during gaming
- State: trying_fixes
- Tried: [1] "Update GPU driver" → FAILED | [2] "DDU clean install" → FAILED
- Key facts: Started after driver 595.76 update, only in fullscreen, temps normal at 68°C
- Hardware focus: GPU (RTX 5090), Display (AW3425DW via DisplayPort)
- Abnormal: GPU usage 98% at idle (expected: <5%)

DO NOT suggest fixes already marked as FAILED above. Build on what you know.
```

**Files to modify**:
- `backend/services/chat.py` — Build memory context, inject into system prompt
- `backend/ai/reasoning.py` — Accept optional session_id, include memory in `analyze_issue()`

**Test criteria**:
- [ ] Start chat, describe a problem → AI responds
- [ ] Tell AI "I tried that, didn't work"
- [ ] AI's next response does NOT suggest the same fix
- [ ] Memory section visible in server logs (for debugging)

### Phase 1C: Memory Extraction (Rule-Based + AI)

**What**: After each user message and AI response, extract structured facts into session memory automatically.

**Rule-based extraction patterns**:
- "I tried X" / "X didn't work" / "already did X" → add to `tried_fixes`
- "it started when..." / "it only happens when..." → add to `key_facts`
- "it's fine now" / "that fixed it" → update `diagnostic_state` to `resolved`
- Hardware component mentions → update `hardware_focus`

**AI-assisted extraction** (optional, Ollama — free):
- After rule-based extraction, if the message is complex, send a small prompt to Ollama:
  ```
  Extract structured facts from this conversation turn.
  Return JSON: {issue_summary, new_facts[], fix_attempted, fix_outcome, hardware_mentioned[]}
  Only return fields that have new information. Return {} if nothing new.
  ```
- Only fires if rule-based extraction found nothing but the message is >50 words

**Context-aware hardware checks**:
- When hardware_focus is set, compare current readings against baselines
- Flag abnormal readings: "GPU at 80% but user hasn't mentioned gaming"
- AI can then ask: "I notice your GPU usage is at 80% — are you running a game right now? That's higher than typical idle."

**Files to modify**:
- `backend/services/memory.py` — Add extraction functions (rule-based + AI)
- `backend/services/chat.py` — Call extraction after each conversation turn
- `backend/services/analysis.py` — Call extraction after initial analysis

**Test criteria**:
- [ ] Say "my screen goes black during games" → `issue_summary` populated, `hardware_focus` includes gpu/display
- [ ] Say "I already updated my drivers" → appears in `tried_fixes`
- [ ] Say "it started after the last Windows update" → appears in `key_facts`
- [ ] High GPU usage at idle → AI proactively asks about it
- [ ] Memory extraction doesn't add duplicate entries

---

## Phase 2: Smart Routing + Conditional Review

**Goal**: Route issues to the best AI provider based on evidence, and only invoke expensive review when there's reason to doubt the primary diagnosis.

### Phase 2A: Evidence-Based Provider Routing

**What**: Replace simple `should_skip_local()` with a routing function that uses historical data.

**Routing signals**:
1. **Correction history**: If Ollama was corrected 3+ times for this issue category → route to Claude
2. **Fix success rates**: From `fix_effectiveness` patterns — which provider's suggestions work?
3. **Complexity score**: Keywords matched across categories, description length, similar past issues found
4. **Session state**: 2+ failed fixes in session → escalate to better provider
5. **Hardware anomalies**: Abnormal readings flagged in session memory → higher complexity

**Routing decision**:
```python
@dataclass
class RoutingDecision:
    provider: str           # "ollama", "gemini", "claude"
    confidence: float       # How confident routing is (0-1)
    needs_review: bool      # Should a second provider check the output?
    reason: str             # Why this routing was chosen
```

**Files to modify**:
- `backend/ai/providers.py` — Add `route_to_provider()` function, replace `should_skip_local()`
- `backend/ai/learning.py` — Add method to get correction stats by provider + issue category

**Test criteria**:
- [ ] Simple known issue → routes to Ollama, no review
- [ ] Issue type with 3+ Ollama corrections → routes to Claude
- [ ] 2+ failed fixes in session → provider escalated
- [ ] Routing decision logged with reason

### Phase 2B: Conditional Review (Targeted Supervisor)

**What**: When router flags `needs_review=True`, a second AI reviews the primary diagnosis. NOT on every call — only when triggered.

**Review triggers** (any one fires review):
- Router confidence < 0.5
- Issue category has >40% correction rate for primary provider
- 3+ failed fixes in current session (from working memory)
- No similar past issues found (novel problem)

**Review flow**:
```
Primary AI generates diagnosis
  → Router says needs_review=True
  → Send to Claude/Gemini:
     "Review this diagnosis. Rate 1-10.
      If < 7, provide corrected diagnosis.
      If >= 7, approve with notes."
  → If corrected: use corrected version, log the correction
  → If approved: use original, add "Reviewed ✓" badge
```

**Files to create**:
- `backend/services/review.py` — Conditional review service

**Files to modify**:
- `backend/services/analysis.py` — Add review step when flagged
- `backend/services/chat.py` — Add review step when flagged
- `backend/routes/ai.py` — Include review metadata in response

**Test criteria**:
- [ ] Normal diagnosis → no review call (check server logs)
- [ ] Force a review trigger → second call happens, result is better or approved
- [ ] Review metadata returned in API response
- [ ] Review only fires ~10-20% of the time, not on every call

### Phase 2C: Frontend Review Indicator

**What**: Show whether a diagnosis was reviewed and by whom.

- Small badge: "✓ Reviewed by Claude" or provider icon
- Tooltip with review score
- No manual trigger (automatic based on routing)

**Files to modify**:
- `frontend/src/pages/troubleshoot.js` — Show review badge on AI responses

**Test criteria**:
- [ ] Reviewed diagnosis shows badge
- [ ] Non-reviewed diagnosis shows nothing (no clutter)
- [ ] Badge tooltip shows score

---

## Phase 3: Builder Agent

**Goal**: A Claude-powered agent accessible from within Pulse's UI that can read and modify Pulse's own source code, with an approval gate before changes are applied.

### Phase 3A: Builder Backend (Tool-Use Agent)

**What**: A Claude API integration using tool use (function calling) that gives Claude access to Pulse's filesystem.

**Builder tools** (exposed to Claude via tool_use):
| Tool | Description |
|------|------------|
| `read_file(path)` | Read a source file from the Pulse project |
| `list_files(directory, pattern)` | List files matching a glob pattern |
| `search_code(query, file_pattern)` | Search for text/regex across codebase |
| `propose_edit(path, old_text, new_text)` | Propose a file edit (queued for approval) |
| `propose_new_file(path, content)` | Propose a new file (queued for approval) |
| `propose_delete_file(path)` | Propose file deletion (queued for approval) |
| `run_command(command)` | Run a shell command (read-only: git status, pip list, etc.) |
| `get_app_status()` | Get current server status, recent errors, config |

**Key constraints**:
- All write operations go through `propose_*` — nothing is applied directly
- `run_command` is sandboxed: whitelist of safe commands only (no rm, no pip install without approval)
- Builder cannot modify `.env`, `data/system.db`, or files outside the project directory
- Builder has read access to entire project, write access via approval gate only

**Builder system prompt**:
```
You are the Pulse Builder Agent. You can read, understand, and modify the Pulse
PC Troubleshooting application's source code.

The app is a Python/Flask backend + vanilla JS frontend served at localhost:5000.
Backend: backend/ (Flask blueprints, services, AI modules)
Frontend: frontend/ (HTML, CSS, JS modules)

When the user asks you to change something:
1. Read the relevant files to understand current implementation
2. Plan the minimal change needed
3. Use propose_edit/propose_new_file to suggest changes
4. Explain what you changed and why

RULES:
- Always read before editing — understand existing code first
- Make minimal changes — don't refactor what wasn't asked about
- Never modify .env, database files, or files outside this project
- Explain your changes in plain language
- If a change requires a server restart, tell the user
```

**Files to create**:
- `backend/agents/__init__.py` — Agent module init
- `backend/agents/builder.py` — Builder agent: Claude API with tool use, conversation management
- `backend/agents/builder_tools.py` — Tool implementations (read, search, propose, etc.)
- `backend/routes/builder.py` — API endpoints for builder chat + approval

**API endpoints**:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/builder/chat` | POST | Send message to Builder, get response |
| `/api/builder/history` | GET | Get Builder conversation history |
| `/api/builder/proposals` | GET | Get pending change proposals |
| `/api/builder/proposals/<id>/approve` | POST | Approve a proposed change |
| `/api/builder/proposals/<id>/reject` | POST | Reject a proposed change |
| `/api/builder/proposals/approve-all` | POST | Approve all pending changes |
| `/api/builder/clear` | POST | Clear Builder conversation |

**Test criteria**:
- [ ] Send "what files make up the frontend?" → Builder reads and lists them
- [ ] Send "make the progress bar green" → Builder reads CSS, proposes an edit
- [ ] Proposal is stored, NOT applied yet
- [ ] Can retrieve pending proposals via API

### Phase 3B: Approval Gate UI

**What**: A diff-view interface in the Builder tab where the user sees proposed changes and can approve/reject them.

**UI components**:
- Builder chat (left side or top) — conversation with the agent
- Proposals panel (right side or bottom) — pending changes with diffs
- Each proposal shows:
  - File path
  - Diff view (red/green, like GitHub)
  - "Approve" / "Reject" buttons
  - "Approve All" button when multiple proposals
- After approval: changes are applied, server restarts if needed, success/failure notification

**Change application flow**:
```
User approves proposal
  → Backend writes the file change
  → If Python file changed: restart Flask server
  → If frontend file changed: browser auto-reloads (existing heartbeat system)
  → Show success/failure notification
  → If failure: auto-rollback the change, show error
```

**Rollback mechanism**:
- Before applying any change, copy the original file to `data/builder_backups/{timestamp}_{filename}`
- If change causes server crash (health check fails within 10s): auto-rollback
- User can also manually rollback from the proposals history

**Files to create**:
- `frontend/src/pages/builder.js` — Builder page with chat + proposals UI

**Files to modify**:
- `frontend/index.html` — Add Builder tab
- `frontend/style.css` — Builder page styles (chat, diff view, approval buttons)
- `frontend/src/main.js` — Builder page routing
- `frontend/src/api/client.js` — Builder API endpoint wrappers
- `backend/routes/builder.py` — Add approval execution logic (apply changes, backup, rollback)
- `backend/app.py` — Register builder blueprint

**Test criteria**:
- [ ] Builder tab appears in navigation
- [ ] Can chat with Builder agent
- [ ] Proposed changes appear in diff view
- [ ] Approve → change is applied to actual file
- [ ] Reject → change is discarded
- [ ] Python file change → server restarts
- [ ] Frontend file change → browser reloads
- [ ] Bad change → auto-rollback, error shown
- [ ] Backup files created in data/builder_backups/

### Phase 3C: Builder Context & Safety

**What**: Give the Builder awareness of the full project structure and add safety guardrails.

**Project context** (loaded once at Builder init):
- File tree of the project (generated, cached)
- CODEBASE_INDEX.md content
- Recent git log (last 10 commits)
- Current git status
- Server health status

**Safety guardrails**:
- File path validation: must be within project directory
- Protected paths: `.env`, `data/*.db`, `.git/`, `venv/`, `node_modules/`
- Max file size for new files: 50KB (prevents accidental large file creation)
- Max proposals per message: 10 (prevents runaway agent)
- Command whitelist for `run_command`: `git status`, `git log`, `git diff`, `pip list`, `python --version`, `ls`, `cat` (read-only)
- Approval timeout: proposals expire after 1 hour if not acted on

**Files to modify**:
- `backend/agents/builder.py` — Add project context loading, safety validation
- `backend/agents/builder_tools.py` — Add path validation, command whitelist

**Test criteria**:
- [ ] Builder knows the project structure without being told
- [ ] Try to edit .env → blocked with explanation
- [ ] Try to delete database → blocked
- [ ] Propose more than 10 changes → capped with warning
- [ ] Run `rm -rf /` → blocked by command whitelist
- [ ] Builder references CODEBASE_INDEX.md for context

---

## Phase 4: Resolution Paths + Adaptive Behavior

**Goal**: Track multi-step fix sequences and adapt AI behavior based on accumulated evidence.

### Phase 4A: Resolution Path Tracking

**What**: When a user tries multiple fixes in a session, link them into an ordered sequence with outcomes.

**New table**:
```sql
CREATE TABLE IF NOT EXISTS resolution_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    issue_type TEXT,
    issue_summary TEXT,
    steps TEXT NOT NULL,          -- JSON: [{fix_title, action_type, outcome, order}]
    final_outcome TEXT,           -- "resolved", "unresolved", "abandoned"
    total_steps INTEGER,
    successful_step INTEGER,     -- Which step resolved it (null if unresolved)
    hardware_hash TEXT,
    provider_used TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Files to modify**:
- `backend/database.py` — Add table, CRUD methods
- `backend/services/memory.py` — Save resolution path when session ends or issue resolves
- `backend/services/fixes.py` — Feed fix outcomes into resolution path

**Test criteria**:
- [ ] Multi-step troubleshooting session → resolution path saved
- [ ] Path includes correct step order and per-step outcomes
- [ ] Resolved sessions mark which step fixed it

### Phase 4B: Path Matching + Injection

**What**: When a new issue comes in, find similar past resolution paths and inject the successful sequence.

**Prompt injection**:
```
SUGGESTED APPROACH (from a similar resolved issue):
Past issue: "Monitor blackouts during gaming" (resolved in 3 steps)
  1. [FAILED] Update GPU driver → did not help
  2. [FAILED] DDU clean install → still happening
  3. [RESOLVED] Roll back to driver 590.18
Confidence: 72% | Consider following this sequence.
```

**Files to modify**:
- `backend/services/matching.py` — Add `find_similar_resolution_paths()`
- `backend/ai/reasoning.py` — Inject matched paths into analysis prompt

**Test criteria**:
- [ ] New issue similar to past resolved issue → path injected in prompt
- [ ] AI references the suggested approach in its response
- [ ] Non-similar issues → no path injected (no false matches)

### Phase 4C: Provider Performance + Confidence Calibration

**What**: Track how well each provider performs per issue category. Compare AI confidence vs actual outcomes.

**New table**:
```sql
CREATE TABLE IF NOT EXISTS provider_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    issue_category TEXT NOT NULL,
    total_diagnoses INTEGER DEFAULT 0,
    corrections INTEGER DEFAULT 0,
    fixes_suggested INTEGER DEFAULT 0,
    fixes_resolved INTEGER DEFAULT 0,
    avg_stated_confidence REAL DEFAULT 0,
    avg_actual_success REAL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, issue_category)
);
```

**Files to modify**:
- `backend/database.py` — Add table
- `backend/services/analysis.py` — Record performance after each diagnosis
- `backend/routes/corrections.py` — Update on correction
- `backend/ai/learning.py` — Confidence calibration factor

**Test criteria**:
- [ ] Performance table populates after diagnoses
- [ ] Correction rate tracked per provider per category
- [ ] Stated confidence vs actual success rate visible

### Phase 4D: Learning Dashboard Update

**What**: Show all new data on the Learning tab.

- Session memory stats
- Resolution paths with step visualization
- Provider performance comparison
- Confidence calibration (stated vs actual)
- Routing decision history

**Files to modify**:
- `backend/routes/system.py` — Add endpoints for new data
- `frontend/src/pages/learning.js` — Add new sections

**Test criteria**:
- [ ] Learning tab shows session memory stats
- [ ] Resolution paths displayed with step sequences
- [ ] Provider performance visible
- [ ] Confidence calibration chart

---

## Implementation Notes

### API Cost Estimates
| Phase | Additional Calls | Est. Cost |
|-------|-----------------|-----------|
| Phase 1 (Memory) | 0-1 small Ollama (free) | ~$0 |
| Phase 2 (Routing+Review) | Claude only when triggered (~10-20%) | ~$0.01-0.03/review |
| Phase 3 (Builder) | Claude with tool use per Builder chat | ~$0.05-0.20/conversation |
| Phase 4 (Paths+Perf) | 0 additional | $0 |

### Architecture Impact
- No new external dependencies (Claude API already integrated)
- All new tables follow existing SQLite migration pattern
- All new services follow existing blueprint/service architecture
- Builder agent uses Claude's native tool_use — no custom agent framework needed
- Frontend changes are additive (new tab, no breaking changes)

### What This Plan Does NOT Do
- No Neo4j/graph database — SQLite sufficient for single-user
- No durable workflow engine — Python threading adequate
- No separate hardware agents — one master troubleshooter with dynamic context
- No federation — single instance
- No full H3 playbook system — resolution paths are the practical equivalent

### Future Phases (when data/need supports it)
- **Full Playbooks**: Auto-generate from resolution paths after 50+ resolved issues
- **Proactive Monitoring**: Background agent checking system health on a schedule
- **Builder Auto-Mode**: Let Builder apply changes without approval (user opt-in)
- **Builder Testing**: Builder runs tests before proposing changes
