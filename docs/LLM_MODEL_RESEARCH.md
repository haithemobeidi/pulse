# Pulse LLM Model Research: Multi-Model Architecture for PC Troubleshooting

> Created: 2026-03-25 | Updated: 2026-03-25 | Status: Research Complete
> Hardware: RTX 5090 (32GB VRAM), Ryzen 9 9950X3D, 96GB DDR5-6000

---

## Table of Contents

1. [Model Profiles](#1-model-profiles)
2. [Head-to-Head Comparisons](#2-head-to-head-comparisons)
3. [Multi-Model Coordination Architecture](#3-multi-model-coordination-architecture)
4. [Key Questions Answered](#4-key-questions-answered)
5. [Task Routing Recommendations](#5-task-routing-recommendations)
6. [Implementation Strategy for Pulse](#6-implementation-strategy-for-pulse)
7. [Sources](#7-sources)

---

## 1. Model Profiles

### 1.1 Qwen 2.5:32B (Currently Installed - Local)

| Attribute | Details |
|-----------|---------|
| **Parameters** | 32.5B (dense) |
| **Architecture** | Dense transformer, Qwen 2.5 generation |
| **Context Window** | 128K tokens |
| **Thinking Mode** | No (standard instruction-following only) |
| **VRAM Usage (Q4_K_M)** | ~22-24 GB on RTX 5090 |
| **Est. Tokens/sec on RTX 5090** | ~50-60 tok/s |
| **License** | Apache 2.0 |

**Strengths:**
- Solid general-purpose instruction following
- Good coding and structured output generation
- Stable and well-tested in Ollama ecosystem
- Fits comfortably in 32GB VRAM with Q4_K_M

**Weaknesses:**
- Superseded by Qwen3:32B across nearly all benchmarks
- No thinking/reasoning mode toggle
- Weaker reasoning compared to Qwen3 generation
- No MoE efficiency benefits

**Verdict for Pulse:** **RETIRE.** Two generations behind now. Qwen3:32B is strictly better, and Qwen3.5:35B is another leap ahead. Remove with `ollama rm qwen2.5:32b` to free disk space (~20GB).

---

### 1.2 Qwen3:32B (Pulling Now - Local)

| Attribute | Details |
|-----------|---------|
| **Parameters** | 32.8B (dense) |
| **Architecture** | Dense transformer, Qwen3 generation |
| **Context Window** | 128K tokens |
| **Thinking Mode** | Yes -- hybrid thinking/non-thinking toggle |
| **VRAM Usage (Q4_K_M)** | ~22-24 GB on RTX 5090 |
| **Est. Tokens/sec on RTX 5090** | ~45-61 tok/s (non-thinking), slower with thinking enabled |
| **License** | Apache 2.0 |

**Strengths:**
- Significant benchmark improvements over Qwen2.5:32B across the board
- **Hybrid thinking mode**: Can toggle between deep reasoning (thinking) and fast response (non-thinking) within a single model
- Strong reasoning: GPQA 53.5%, competitive with much larger models
- Excellent instruction following and structured JSON output
- Tool/function calling support
- Fits fully in 32GB VRAM -- no CPU offload needed
- Non-thinking mode delivers fast responses (~50+ tok/s) for simple queries
- Thinking mode provides step-by-step reasoning for complex diagnosis

**Weaknesses:**
- Thinking mode adds latency (model generates internal reasoning tokens before responding)
- At Q4_K_M quantization, leaves only ~8-10 GB headroom for KV cache at long context
- Dense architecture means all 32B parameters active for every token (more compute than MoE)
- Slightly behind Llama 3.3 70B on some coding benchmarks

**Verdict for Pulse:** Primary workhorse model. Use thinking mode for complex diagnosis, non-thinking mode for quick data gathering and classification. This should be the default model for most Pulse operations.

---

### 1.3 Qwen3:30B-A3B (MoE - Local)

| Attribute | Details |
|-----------|---------|
| **Parameters** | 30B total, **3B active** per token |
| **Architecture** | Mixture of Experts (128 experts, top-k routing) |
| **Context Window** | 128K tokens |
| **Thinking Mode** | Yes -- same hybrid toggle as Qwen3:32B |
| **VRAM Usage (Q4_K_M)** | ~19-21 GB on RTX 5090 |
| **Est. Tokens/sec on RTX 5090** | ~80-120 tok/s (only 3B params computed per token) |
| **License** | Apache 2.0 |

**Strengths:**
- Extremely fast inference -- only 3B parameters activate per token despite 30B total knowledge
- Benchmarks surprisingly competitive with the dense 32B: ArenaHard 91.0 (vs QwQ-32B 89.5), AIME'24 80.4
- Lower VRAM than dense 32B (all expert weights loaded but only fraction computed)
- Can run alongside another model in VRAM if needed
- Thinking mode available for complex tasks
- Ideal for high-throughput, lower-latency operations

**Weaknesses:**
- MoE models are harder to quantize effectively -- quality degrades more at lower bit widths
- Some Ollama users report low GPU utilization and inconsistent speed on certain configurations
- Slightly less reliable on nuanced, multi-step reasoning compared to dense 32B
- Expert routing overhead adds complexity
- Less tested in production compared to dense models

**Verdict for Pulse:** Speed specialist. Use for high-frequency, lower-complexity tasks: data gathering prompts, quick classification, keyword extraction, fact extraction from system logs. Its speed advantage (potentially 2x faster than dense 32B) makes it ideal for pipeline stages where you need many fast calls rather than one deep reasoning call.

---

### 1.4 Qwen 3.5:35B-A3B (NEW - Newest Generation - Local)

| Attribute | Details |
|-----------|---------|
| **Parameters** | 35B total, **3B active** per token |
| **Architecture** | Hybrid Gated DeltaNet + MoE (3:1 linear-to-full attention ratio) |
| **Context Window** | **256K tokens** (2x Qwen3's 128K) |
| **Multimodal** | **Yes — text + image + video** (native, not bolted on) |
| **Thinking Mode** | Yes — hybrid thinking/non-thinking toggle |
| **VRAM Usage (Q4_K_M)** | ~22 GB on RTX 5090 |
| **Est. Tokens/sec on RTX 5090** | ~194 tok/s (only 3B active params) |
| **Languages** | 201 (up from ~100 in Qwen3) |
| **Release** | February 2026 (newest model in this lineup) |
| **License** | Apache 2.0 |

**Strengths:**
- **Full generation ahead of Qwen3** — new architecture, better benchmarks across the board
- **Surpasses Qwen3-235B-A22B** despite activating far fewer parameters
- Native multimodal — can analyze screenshots, error dialogs, BSOD photos directly
- 256K context window — double Qwen3, enough for massive system logs
- Extremely fast inference (~194 tok/s) with only 3B active params
- Gated DeltaNet architecture = near-linear compute scaling for long contexts
- SWE-bench Verified: 69.2 (coding), GPQA Diamond: 81.7 (9B model!)
- Tool/function calling support
- Fits comfortably in 32GB VRAM with room for KV cache

**Weaknesses:**
- Newest model — less community testing/feedback than Qwen3 models
- MoE quantization concerns (same as 30B-A3B — quality may degrade at lower quants)
- 3B active params may still trail dense 32B on some nuanced reasoning tasks
- Ollama support may have early bugs

**Verdict for Pulse:** **This should be the new primary workhorse**, replacing Qwen3:32B for most tasks. It's faster, has 2x context, native multimodal (screenshot analysis!), and benchmarks higher than the previous-gen flagship. The multimodal capability alone is transformative for PC troubleshooting — users can send photos of error screens. Keep Qwen3:32B as dense reasoning fallback for tasks where MoE's 3B active params aren't sufficient.

**Pull command:** `ollama pull qwen3.5:35b`

---

### 1.5 Llama 3.3:70B-Instruct-Q4_K_M (Already Installed - Local)

| Attribute | Details |
|-----------|---------|
| **Parameters** | 70.6B (dense) |
| **Architecture** | Dense transformer, Meta Llama 3.3 |
| **Context Window** | 131K tokens |
| **Thinking Mode** | No (instruction-following only) |
| **VRAM Usage (Q4_K_M)** | ~40-42 GB (exceeds 32GB -- requires CPU offload) |
| **Est. Tokens/sec on RTX 5090** | ~15-25 tok/s (partial GPU offload to 96GB system RAM) |
| **License** | Llama 3.3 Community License |

**Strengths:**
- Largest local model available -- highest raw capability ceiling
- Strongest coding performance among the local models (10.7 coding index)
- Excellent instruction following and tool use
- Large context window (131K)
- Well-tested, mature ecosystem

**Weaknesses:**
- **Does not fit in 32GB VRAM** -- Q4_K_M file is ~40GB, requires significant CPU offload
- CPU offload drastically reduces speed (15-25 tok/s vs 60+ for 32B models)
- No thinking/reasoning mode
- Slow time-to-first-token due to partial offload (~9x slower prompt processing when partially offloaded)
- Uses significant system RAM (~40-50GB) alongside VRAM

**Verdict for Pulse:** Heavy hitter for escalation only. The speed penalty from CPU offload is severe. Use this model only when Qwen3:32B (with thinking) fails to produce a satisfactory diagnosis. Its coding strength makes it useful for generating complex PowerShell/batch fix scripts. Do NOT use for routine queries -- the 3-4x speed penalty is not worth it for simple tasks.

**Important consideration:** You cannot run Llama 3.3 70B and any 32B model simultaneously. Loading Llama 70B consumes all 32GB VRAM plus system RAM. Ollama will need to unload the 32B model first, adding model swap latency (~10-15 seconds).

---

### 1.6 Gemini 2.5 Pro (Cloud - Google Subscription)

| Attribute | Details |
|-----------|---------|
| **Parameters** | Undisclosed (estimated 1T+ MoE) |
| **Architecture** | MoE, Google proprietary |
| **Context Window** | 1M tokens (2M planned) |
| **Thinking Mode** | Built-in deep reasoning |
| **API Pricing** | ~$1.25/M input, $10.00/M output tokens |
| **Tokens/sec** | ~80-150 tok/s (cloud-dependent) |
| **Subscription** | User has existing Google subscription |

**Strengths:**
- Massive 1M token context window -- can ingest entire system logs, event histories, reliability records in a single call
- Strong multimodal capabilities (text, image, video) -- could analyze screenshot of error dialogs
- Built-in Google Search tool use and function calling
- High throughput from Google's infrastructure
- Context caching available (50% cost reduction on repeated prompts)
- Free tier available for lower usage
- Excellent at synthesizing large volumes of information

**Weaknesses:**
- Cloud dependency -- requires internet, adds latency
- Privacy concern -- system data sent to Google servers
- Cost accumulates with heavy usage
- Rate limits on subscription tier
- Less consistent than Claude for precise structured output
- Can hallucinate on niche PC hardware issues

**Verdict for Pulse:** Large context specialist and secondary fallback. Best used when Pulse needs to analyze massive context (full system history, multiple log files, extended conversation threads). Also excellent as a research model -- querying for known issues with specific hardware/driver combinations. The subscription means marginal cost is low.

---

### 1.7 Claude (Anthropic - Pay-Per-Use)

| Attribute | Details |
|-----------|---------|
| **Parameters** | Undisclosed |
| **Architecture** | Dense transformer, Anthropic proprietary |
| **Context Window** | 200K standard, 1M with Opus 4.6/Sonnet 4.6 |
| **Thinking Mode** | Extended thinking (Opus/Sonnet 4.6) |
| **API Pricing** | Sonnet 4.6: $3/$15 per M tokens; Opus 4.6: $5/$25 per M tokens |
| **Tokens/sec** | ~50-100 tok/s (cloud-dependent) |

**Strengths:**
- Best-in-class instruction following and structured output generation
- Extremely reliable JSON output formatting (critical for Pulse's structured analysis)
- Strong reasoning with extended thinking mode
- Excellent at multi-step diagnosis chains
- Most reliable at following complex system prompts
- Best safety/refusal calibration -- won't generate dangerous system commands
- 1M context now available at standard pricing (Opus 4.6, Sonnet 4.6)

**Weaknesses:**
- Most expensive option by far ($3-25 per million tokens)
- Pay-per-use means every call costs money
- Cloud dependency and latency
- Privacy concerns with system diagnostic data
- No multimodal image analysis for error screenshots (text-only for API)
- Rate limits can throttle heavy usage

**Verdict for Pulse:** Premium escalation and quality assurance. Use Claude when (a) local models produce low-confidence diagnoses, (b) the issue involves complex multi-step reasoning that local models struggle with, or (c) you need the most reliable structured output for critical fix generation. Sonnet 4.6 offers the best cost/quality ratio for most escalation scenarios. Reserve Opus 4.6 for truly complex cases.

---

## 2. Head-to-Head Comparisons

### 2.1 Qwen3:32B vs Qwen3:30B-A3B

| Dimension | Qwen3:32B (Dense) | Qwen3:30B-A3B (MoE) |
|-----------|-------------------|----------------------|
| **Speed** | ~50-60 tok/s | ~80-120 tok/s |
| **Reasoning Quality** | Higher (all 32B active) | Slightly lower (3B active) |
| **ArenaHard** | ~91+ | 91.0 |
| **VRAM** | ~22-24 GB | ~19-21 GB |
| **Quantization Tolerance** | Excellent | Worse (MoE degrades more) |
| **Best For** | Complex diagnosis, deep reasoning | Fast classification, data extraction |
| **Simultaneous Loading** | Possible with MoE (tight) | Possible with dense 32B (tight) |

**Key Insight:** These two models are complementary, not competing. The dense 32B handles quality-critical reasoning while the MoE 30B-A3B handles speed-critical pipeline stages. On the RTX 5090 with 32GB VRAM, you likely cannot run both simultaneously at full quality -- combined they would need ~43 GB. However, Ollama's model swapping is fast between models of similar size (~2-3 seconds).

### 2.2 Qwen3:32B vs Llama 3.3:70B

| Dimension | Qwen3:32B | Llama 3.3:70B |
|-----------|-----------|---------------|
| **Speed on RTX 5090** | ~50-60 tok/s | ~15-25 tok/s |
| **Reasoning** | Strong (thinking mode) | Strong (raw capability) |
| **Coding** | Good | Better (10.7 coding index) |
| **VRAM Fit** | Yes (22-24 GB) | No (requires ~40GB, CPU offload) |
| **Model Swap** | Fast | Slow (10-15s to load/unload) |
| **Thinking Mode** | Yes | No |

**Key Insight:** Qwen3:32B with thinking mode enabled likely matches or exceeds Llama 3.3 70B's reasoning quality while being 2-4x faster on your hardware. The 70B model's advantage is primarily in code generation. For Pulse, Qwen3:32B should be the default, with Llama 70B reserved for complex script generation only.

### 2.3 Local Models vs Cloud Models

| Dimension | Local (Ollama) | Gemini | Claude |
|-----------|---------------|--------|--------|
| **Cost per query** | $0.00 | $0.001-0.05 | $0.003-0.15 |
| **Latency** | 50-200ms TTFT | 500-2000ms | 500-3000ms |
| **Privacy** | Full local | Data sent to Google | Data sent to Anthropic |
| **Availability** | Always (no internet needed) | Internet required | Internet required |
| **Context Window** | 128K | 1M | 200K-1M |
| **Quality Ceiling** | Good-Excellent | Excellent | Excellent-Best |
| **Structured Output** | Good | Good | Best |

---

## 3. Multi-Model Coordination Architecture

### 3.1 Recommended Architecture: Intelligent Orchestrator Pattern

```
                    User Query: "My screen keeps going black" [+ optional screenshot]
                                    |
                                    v
                    ┌───────────────────────────────┐
                    │     PULSE ORCHESTRATOR         │
                    │     (Python/Flask logic)       │
                    │                                │
                    │  1. Classify task complexity    │
                    │  2. Check for images/multimodal │
                    │  3. Select model(s)            │
                    │  4. Route request              │
                    │  5. Aggregate results           │
                    │  6. Assess confidence           │
                    │  7. Escalate if needed          │
                    └──────┬───────┬───────┬─────────┘
                           |       |       |
                  ┌────────┘       |       └────────┐
                  v                v                v
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │  TIER 1:     │ │  TIER 1B:    │ │  TIER 2:     │
        │  Primary     │ │  Batch       │ │  Dense       │
        │              │ │  Worker      │ │  Fallback    │
        │ qwen3.5:35b  │ │ qwen3:30b-   │ │ qwen3:32b    │
        │ (MoE+DeltaN) │ │ a3b (MoE)    │ │ (dense)      │
        │              │ │              │ │              │
        │ - Diagnose   │ │ - Extract    │ │ - Nuanced    │
        │ - Chat       │ │ - Summarize  │ │   reasoning  │
        │ - Screenshots│ │ - Metabolism │ │ - When MoE   │
        │ - Classify   │ │ - Log parse  │ │   isn't      │
        │ - Fix gen    │ │ - Batch jobs │ │   enough     │
        │              │ │              │ │              │
        │ ~194 tok/s   │ │ ~100 tok/s   │ │ ~50 tok/s    │
        │ MULTIMODAL   │ │ FREE         │ │ FREE         │
        │ 256K ctx     │ │ 128K ctx     │ │ 128K ctx     │
        │ FREE         │ │              │ │              │
        └──────────────┘ └──────────────┘ └──────────────┘
                                                |
                                    ┌───────────┴───────────┐
                                    v                       v
                          ┌──────────────┐       ┌──────────────┐
                          │  TIER 3:     │       │  TIER 4:     │
                          │  Cloud       │       │  Heavy Local │
                          │              │       │              │
                          │ Gemini 2.5   │       │ llama3.3:70b │
                          │ Pro          │       │              │
                          │ Claude       │       │ - Complex    │
                          │ Sonnet 4.6   │       │   scripts    │
                          │              │       │ - Slow swap  │
                          │ - 2nd opinion│       │ - 15-25 t/s  │
                          │ - Large ctx  │       │              │
                          │ - Safety rev │       └──────────────┘
                          │ $$           │
                          └──────────────┘
```

### 3.2 Pipeline Flow for a Typical Diagnosis

```
Step 1: CLASSIFY (qwen3.5:35b, non-thinking)
  Input:  User symptom + basic hardware context [+ screenshot if provided]
  Output: {category: "display", urgency: "high", complexity: "medium"}
  Time:   ~0.3 seconds (194 tok/s)
  Cost:   FREE
  Note:   Only model that can process screenshots natively

Step 2: GATHER CONTEXT (qwen3:30b-a3b, non-thinking) — runs in parallel
  Input:  Classification + raw system data
  Output: Relevant facts extracted, key log entries identified
  Time:   ~1-2 seconds
  Cost:   FREE
  Note:   Batch worker runs while primary stays free for user interaction

Step 3: QUERY BRAIN (no LLM needed)
  Input:  Symptom keywords + hardware fingerprint
  Output: Similar past cases, confidence scores, known fixes
  Time:   ~50ms
  Cost:   FREE

Step 4: DIAGNOSE (qwen3.5:35b, thinking mode)
  Input:  Classified symptom + extracted context + brain facts + web search results
  Output: Structured diagnosis with confidence score, reasoning chain
  Time:   ~3-10 seconds (thinking mode, but fast at 194 tok/s)
  Cost:   FREE
  Fallback: If thinking mode diagnosis is low confidence, escalate to qwen3:32b
            (dense 32B active params may catch what MoE's 3B missed)

Step 5: CONFIDENCE CHECK (orchestrator logic)
  If confidence >= 0.7: Present diagnosis to user
  If confidence 0.4-0.7: Escalate to Gemini for second opinion
  If confidence < 0.4: Escalate to Claude for deep analysis

Step 6: GENERATE FIX (qwen3.5:35b or llama3.3:70b for complex scripts)
  Input:  Confirmed diagnosis + user's specific hardware
  Output: Step-by-step fix with PowerShell commands
  Time:   ~2-8 seconds
  Cost:   FREE (or $$ if cloud escalation was needed)

Step 7: REVIEW (optional, for high-risk fixes)
  Model:  Claude Sonnet 4.6
  Input:  Proposed fix + system context
  Output: Safety review, potential risks, approval/modification
  Cost:   ~$0.01-0.05 per review

Step 8: METABOLISM (qwen3:30b-a3b, non-thinking) — runs after session close
  Input:  Full conversation, diagnosis, fixes tried, outcome
  Output: Structured facts for brain storage
  Time:   ~2-5 seconds
  Cost:   FREE
  Note:   Batch worker handles this asynchronously
```

### 3.3 VRAM Management Strategy

With 32GB VRAM on the RTX 5090, the strategy must account for model loading/unloading:

```
PRIMARY CONFIGURATION (most of the time):
  Loaded: qwen3:32b (Q4_K_M) = ~23 GB
  Available: ~9 GB for KV cache
  Swap to MoE: ~2-3 seconds

SPEED CONFIGURATION (batch processing, data extraction):
  Loaded: qwen3:30b-a3b (Q4_K_M) = ~20 GB
  Available: ~12 GB for KV cache
  Swap to dense: ~2-3 seconds

HEAVY CONFIGURATION (rare, complex script generation):
  Loaded: llama3.3:70b (Q4_K_M) = ~40 GB (32 VRAM + 8-10 system RAM offload)
  Available: Minimal KV cache headroom
  Swap back: ~10-15 seconds
```

**Ollama Configuration Recommendations:**
```bash
# Set in environment or Ollama config
OLLAMA_MAX_LOADED_MODELS=1        # Only one large model at a time
OLLAMA_NUM_PARALLEL=4             # Allow 4 parallel requests to loaded model
OLLAMA_KEEP_ALIVE=10m             # Keep model loaded for 10 minutes
OLLAMA_FLASH_ATTENTION=1          # Enable flash attention for better VRAM efficiency
```

---

## 4. Key Questions Answered

### Q1: Can Ollama models coordinate with each other?

**Yes, absolutely.** Ollama exposes a REST API on port 11434 that supports the OpenAI-compatible `/v1/chat/completions` endpoint. Your Flask orchestrator can call different models by simply changing the `model` parameter in the API request:

```python
# Call the MoE model for fast classification
response1 = requests.post("http://localhost:11434/v1/chat/completions", json={
    "model": "qwen3:30b-a3b",
    "messages": [{"role": "user", "content": "Classify this symptom..."}]
})

# Call the dense model for deep reasoning
response2 = requests.post("http://localhost:11434/v1/chat/completions", json={
    "model": "qwen3:32b",
    "messages": [{"role": "user", "content": "Diagnose based on: ..."}]
})
```

**Caveat:** Only one large model fits in VRAM at a time. If you call a different model than the currently loaded one, Ollama will unload the current model and load the new one (~2-15 seconds depending on model size). For the Qwen3 32B and 30B-A3B models, this swap is fast (~2-3 seconds). For swapping to/from Llama 70B, expect 10-15 seconds.

**Optimization:** Use `OLLAMA_KEEP_ALIVE` to control how long a model stays loaded. Design your pipeline so that all calls to the same model happen in a batch before switching.

### Q2: Can cloud models call local models?

**Not directly, but your orchestrator can bridge them.** Cloud APIs (Claude, Gemini) cannot make HTTP calls to your localhost:11434. However, your Flask orchestrator sits in the middle and can:

1. Send a request to Claude API
2. Receive Claude's response (which might include a recommendation like "run this diagnostic command")
3. Forward that to a local Ollama model for execution/refinement
4. Send the local model's output back to Claude for review

This is the standard **orchestrator pattern** -- your Python code is the coordinator, not the models themselves.

### Q3: Can local models call cloud models?

**Same answer -- through the orchestrator.** Local Ollama models do not have built-in ability to make HTTP calls to external APIs. However, Qwen3 models support **function/tool calling**, which means:

1. You define a tool like `escalate_to_cloud(query, reason)` in the model's tool schema
2. The local model decides it needs cloud help and generates a tool call
3. Your orchestrator intercepts the tool call and routes it to Gemini/Claude
4. The cloud response is fed back to the local model

This is the most elegant approach -- the local model self-assesses its confidence and explicitly requests escalation when needed.

### Q4: What is the best architecture for multi-model coordination?

**The Tiered Orchestrator pattern** is the best fit for Pulse. Here is why each alternative was considered and rejected:

| Architecture | Description | Why Not for Pulse |
|-------------|-------------|-------------------|
| **Chain Pattern** | Model A -> Model B -> Model C sequentially | Too rigid. Not all queries need all models. |
| **Peer-to-Peer** | Models communicate directly | Not possible with Ollama (no inter-model comms) |
| **Router Only** | Smart router sends to one model | Misses the value of multi-stage analysis |
| **Tiered Orchestrator** | Classify -> Route -> Escalate | **Best fit.** Matches Pulse's existing failover architecture, adds intelligence. |

The Tiered Orchestrator is essentially an evolution of Pulse's existing `providers.py` failover system. Instead of `Ollama preferred -> Gemini fallback -> Claude backup` (which is dumb failover), it becomes `MoE fast -> Dense reasoning -> Cloud escalation` (which is intelligent routing based on task complexity and confidence).

### Q5: Which model should handle each troubleshooting stage?

See the complete routing table in Section 5 below.

---

## 5. Task Routing Recommendations

### Primary Routing Table (Revised with Qwen 3.5)

| Task | Model | Mode | Rationale |
|------|-------|------|-----------|
| **Symptom Classification** | qwen3.5:35b | Non-thinking | Fast (194 tok/s), simple task, multimodal if screenshot included. |
| **Urgency Assessment** | qwen3.5:35b | Non-thinking | Binary/categorical output, speed matters. |
| **Log Parsing / Extraction** | qwen3:30b-a3b | Non-thinking | Structured extraction task, high throughput. Keeps 3.5 free. |
| **Fact Extraction for Brain** | qwen3:30b-a3b | Non-thinking | Template-based extraction, speed over depth. Batch worker. |
| **Screenshot/Image Analysis** | qwen3.5:35b | Non-thinking | **Only local model with native multimodal.** |
| **Similar Case Matching** | No LLM (embeddings) | N/A | Use TF-IDF/vector search in Living Brain. |
| **Primary Diagnosis** | qwen3.5:35b | Thinking | Core reasoning task. 256K context + thinking mode. |
| **Differential Diagnosis** | qwen3:32b | Thinking | Dense fallback for nuanced multi-hypothesis reasoning. |
| **Fix Generation (simple)** | qwen3.5:35b | Non-thinking | Registry edits, settings changes, simple commands. |
| **Fix Generation (complex scripts)** | llama3.3:70b | N/A | PowerShell scripts, multi-step procedures. Best coding model. |
| **Fix Safety Review** | Claude Sonnet 4.6 | N/A | Critical safety check. Most reliable instruction following. |
| **Large Context Analysis** | Gemini 2.5 Pro | N/A | Full system history analysis. 1M token context. |
| **Web Research Synthesis** | Gemini 2.5 Pro | N/A | Synthesize web search results about known issues. |
| **Second Opinion (low confidence)** | Gemini 2.5 Pro | N/A | When local diagnosis confidence is 0.4-0.7. |
| **Complex Escalation** | Claude Sonnet 4.6 | N/A | When local + Gemini both have low confidence. |
| **User Chat (conversational)** | qwen3.5:35b | Non-thinking | Natural conversation, follow-up questions. Fast. |
| **Summary Generation** | qwen3:30b-a3b | Non-thinking | Summarize session for brain storage. Batch worker. |
| **Knowledge Gap Detection** | qwen3.5:35b | Thinking | Requires reasoning about what is unknown. |
| **Brain Metabolism (nightly)** | qwen3:30b-a3b | Non-thinking | Batch processing of stored facts. Speed matters. |

### Revised Model Hierarchy

```
TIER 1 — PRIMARY (qwen3.5:35b)              ~194 tok/s, 22GB VRAM, FREE
  Most tasks. Multimodal. 256K context. Thinking mode for complex diagnosis.

TIER 1B — BATCH WORKER (qwen3:30b-a3b)      ~100 tok/s, 20GB VRAM, FREE
  Parallel extraction, metabolism, log parsing. Keeps Tier 1 free for user.

TIER 2 — DENSE FALLBACK (qwen3:32b)         ~50 tok/s, 23GB VRAM, FREE
  When MoE's 3B active params aren't enough. Dense reasoning safety net.

TIER 3 — HEAVY LOCAL (llama3.3:70b)          ~20 tok/s, 40GB+ (offload), FREE
  Complex script generation only. Swap penalty: ~10-15 seconds.

TIER 4 — CLOUD (Gemini 2.5 Pro)             ~100 tok/s, $0.001-0.05/call
  Large context, second opinions, web research synthesis.

TIER 5 — PREMIUM CLOUD (Claude Sonnet 4.6)  ~80 tok/s, $0.01-0.15/call
  Safety review, complex escalation, structured output.
```

### Escalation Decision Matrix

```
                    Local Confidence Score

  HIGH (>0.7)       MEDIUM (0.4-0.7)       LOW (<0.4)
  ─────────────     ──────────────────     ────────────
  Present to        Escalate to            Escalate to
  user directly     Gemini 2.5 Pro         Claude Sonnet 4.6
                    for second opinion     for deep analysis

  Cost: $0          Cost: ~$0.01-0.03      Cost: ~$0.03-0.10

  If Gemini also                           If Claude also
  low confidence:                          low confidence:
  → Claude Sonnet                          → Flag as knowledge
                                             gap in Brain
```

### Cost Projection (per 100 troubleshooting sessions)

| Scenario | Local Calls | Gemini Calls | Claude Calls | Est. Cost |
|----------|-------------|-------------|-------------|-----------|
| **Mostly routine issues** | ~500 | ~10 | ~2 | ~$0.50 |
| **Mixed complexity** | ~400 | ~50 | ~15 | ~$3.00 |
| **Mostly novel/complex** | ~300 | ~80 | ~40 | ~$8.00 |

This is dramatically cheaper than sending everything to Claude ($50-150 per 100 sessions).

---

## 6. Implementation Strategy for Pulse

### Phase 1: Smart Router (Replaces Dumb Failover)

Replace the current `providers.py` failover chain with an intelligent router:

```python
# Current: dumb failover
# Ollama (any model) -> Gemini -> Claude

# New: intelligent routing with Qwen 3.5 as primary
class ModelRouter:
    def route(self, task_type: str, complexity: str, confidence: float = None,
              has_image: bool = False):
        """Select the optimal model for a given task."""

        # Multimodal — only qwen3.5 handles images locally
        if has_image:
            return "qwen3.5:35b"

        # Batch/extraction tasks — use the batch worker to keep primary free
        if task_type in ["extract", "summarize", "metabolism", "log_parse"]:
            return "qwen3:30b-a3b"  # Batch worker tier

        # Primary tasks — qwen3.5 is the new workhorse
        if task_type in ["classify", "diagnose", "chat", "fix_simple",
                         "knowledge_gap", "urgency"]:
            return "qwen3.5:35b"  # Primary tier (fast + 256K ctx)

        # Dense fallback — when MoE 3B active isn't enough
        if task_type == "diagnose_complex" or complexity == "high":
            return "qwen3:32b"  # Dense reasoning fallback

        # Complex scripting — llama's coding strength
        if task_type == "fix_complex":
            return "llama3.3:70b-instruct-q4_K_M"  # Heavy local tier

        # Cloud escalation
        if task_type == "large_context" or (confidence and 0.4 <= confidence < 0.7):
            return "gemini-2.5-pro"  # Cloud tier 1

        if confidence and confidence < 0.4:
            return "claude-sonnet-4.6"  # Cloud tier 2

        return "qwen3.5:35b"  # Default
```

### Phase 2: Pipeline Stages

Break the monolithic `analyze` call into discrete pipeline stages:

```
classify() -> gather_context() -> query_brain() -> diagnose() -> assess_confidence() -> generate_fix()
```

Each stage independently routed to the optimal model.

### Phase 3: Self-Escalation via Tool Calling

Give Qwen3:32B a tool definition for `request_escalation`:

```python
tools = [{
    "type": "function",
    "function": {
        "name": "request_escalation",
        "description": "Request a more capable cloud model when you are uncertain about the diagnosis",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why escalation is needed"},
                "specific_question": {"type": "string", "description": "What the cloud model should analyze"}
            },
            "required": ["reason", "specific_question"]
        }
    }
}]
```

This allows the local model to self-assess and escalate intelligently rather than relying solely on the orchestrator's confidence threshold.

### Phase 4: Model Warm-Up and Preloading

Implement predictive model loading:

```python
# After classification, if diagnosis is likely needed next,
# preload qwen3:32b while gathering context
async def smart_preload(classification_result):
    if classification_result["complexity"] in ["medium", "high"]:
        # Start loading qwen3:32b in background
        await ollama_preload("qwen3:32b")
```

---

## 7. Sources

### Model Benchmarks and Comparisons
- [Qwen3 30B A3B vs Qwen3 32B Comparison](https://llm-stats.com/models/compare/qwen3-30b-a3b-vs-qwen3-32b)
- [Qwen3: Think Deeper, Act Faster (Official Blog)](https://qwenlm.github.io/blog/qwen3/)
- [Qwen/Qwen3-30B-A3B on Hugging Face](https://huggingface.co/Qwen/Qwen3-30B-A3B)
- [Qwen3 30B-A3B vs Qwen3 32B: Is the MoE Model Really Worth It?](https://kaitchup.substack.com/p/qwen3-30b-a3b-vs-qwen3-32b-is-the)
- [Qwen 3 Benchmarks, Comparisons, Model Specifications](https://dev.to/best_codes/qwen-3-benchmarks-comparisons-model-specifications-and-more-4hoa)
- [Qwen3 30B A3B vs Qwen3 32B on Artificial Analysis](https://artificialanalysis.ai/models/comparisons/qwen3-30b-a3b-instruct-reasoning-vs-qwen3-32b-instruct)
- [Llama 3.3 70B vs Qwen3 32B Comparison](https://blog.galaxy.ai/compare/llama-3-3-70b-instruct-vs-qwen3-32b)
- [Qwen3 32B vs Llama 3.3 70B on Artificial Analysis](https://artificialanalysis.ai/models/comparisons/qwen3-32b-instruct-reasoning-vs-llama-3-3-instruct-70b)
- [Qwen2.5 72B vs Qwen3 32B Comparison](https://llm-stats.com/models/compare/qwen-2.5-72b-instruct-vs-qwen3-32b)
- [Qwen3 Features and Comparisons (DataCamp)](https://www.datacamp.com/blog/qwen3)

### Hardware Benchmarks and VRAM
- [Ollama VRAM Requirements: Complete 2026 Guide](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)
- [2x RTX 5090 Ollama Benchmark](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090-2)
- [RTX 5090 Ollama Benchmark: Extreme Performance](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090)
- [RTX 5090 LLM Benchmark Results](https://www.hardware-corner.net/rtx-5090-llm-benchmarks/)
- [RTX 5090 vs 4090 Local LLM Inference Benchmarks](https://vipinpg.com/blog/benchmarking-rtx-5090-vs-4090-for-local-llm-inference-real-world-tokensecond-gains-with-ollama-and-lm-studio/)
- [Best GPUs for Local LLM Inference 2025](https://localllm.in/blog/best-gpus-llm-inference-2025)
- [VRAM Calculator](https://apxml.com/tools/vram-calculator)
- [Qwen3 MoE 30b-a3b GPU Utilization Issue (Ollama GitHub)](https://github.com/ollama/ollama/issues/10458)

### Multi-Model Orchestration
- [Multiple Local LLMs 2026: Multi-Model Setup (SitePoint)](https://www.sitepoint.com/multiple-local-llms-setup-2026/)
- [OllamaFlow - Scale Your Ollama Infrastructure](https://ollamaflow.com/)
- [Ollama Setup 2026 (SitePoint)](https://www.sitepoint.com/ollama-setup-guide-2026/)
- [Ollama Multi-Agent Orchestrator](https://ollama.com/erukude/multiagent-orchestrator)
- [LLM Agent Orchestration with LangChain (IBM)](https://www.ibm.com/think/tutorials/llm-agent-orchestration-with-langchain-and-granite)
- [Local LLMs vs Cloud APIs: Hybrid AI Cost Strategy](https://www.marchingdogs.com/blogs/technology/local-llms-vs-cloud-apis-our-hybrid-approach-to-ai-cost-control-2)
- [MCP Architecture Patterns for Multi-Agent AI Systems (IBM)](https://developer.ibm.com/articles/mcp-architecture-patterns-ai-systems/)
- [Multi-Agent and Multi-LLM Architecture Guide 2025](https://collabnix.com/multi-agent-and-multi-llm-architecture-complete-guide-for-2025/)
- [5 Patterns for Scalable LLM Service Integration](https://latitude.so/blog/5-patterns-for-scalable-llm-service-integration)

### Cloud Model Pricing and Capabilities
- [Gemini Developer API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini 2.5 Pro on OpenRouter](https://openrouter.ai/google/gemini-2.5-pro)
- [Gemini 2.5 Pro Analysis (Artificial Analysis)](https://artificialanalysis.ai/models/gemini-2-5-pro)
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Opus 4.6 and Sonnet 4.6 1M Context at Standard Pricing](https://signals.aktagon.com/articles/2026/03/claude-opus-4.6-and-sonnet-4.6-now-feature-1m-context-window-at-standard-pricing/)
- [Claude Opus 4.6 1M Context Window Guide](https://karangoyal.cc/blog/claude-opus-4-6-1m-context-window-guide)

### Ollama Thinking Mode
- [Qwen3-32B Thinking Mode on Ollama (HuggingFace Discussion)](https://huggingface.co/Qwen/Qwen3-32B/discussions/9)
- [Ollama Thinking Capabilities Documentation](https://docs.ollama.com/capabilities/thinking)
- [Qwen3:32B on Ollama Library](https://ollama.com/library/qwen3:32b)
- [Setup and Fine-Tune Qwen 3 with Ollama (Codecademy)](https://www.codecademy.com/article/qwen-3-ollama-setup-and-fine-tuning)
