# PC-Inspector Future Features & Ideas

## Phase 2: Advanced Monitoring & Auto-Logging

### 1. Real-Time Metrics Collection
**Goal**: Capture detailed system metrics for performance analysis

**CPU Metrics to Capture**:
- Per-core utilization (all 32 threads on user's system)
- Current frequency vs base/max frequency
- Thermal throttling detection
- Power state changes
- Cache utilization (if available)

**GPU Metrics to Enhance**:
- Per-GPU memory bandwidth
- GPU throttling state
- Driver-level errors from Windows Event Log
- Display timeout events

**Snapshot Enhancement**:
When user logs an issue, automatically capture:
- Current CPU usage per core (1-32)
- Current GPU frequency + throttle state
- Memory pressure (% used)
- Active processes consuming resources
- GPU driver version + recent changes

### 2. Self-Learning Anomaly Detection (Priority: High)

**Automatic Issue Detection**:
- Detect unusual CPU frequency dips (e.g., "frequency dropped from 5.2GHz to 2.8GHz unexpectedly")
- Monitor for thermal throttling patterns
- Track GPU memory spikes
- Detect sustained high memory pressure (>95%)
- Flag rapid fan speed changes (if accessible)

**Implementation Strategy**:
1. Collect 5-minute rolling baseline of normal metrics
2. When metric deviates >2 standard deviations from baseline, flag it
3. Auto-create "System Anomaly Detected" issue with snapshot
4. User can dismiss or confirm as real issue
5. System learns from user feedback

**Example Use Case** (User's Monitor Blackout):
```
Baseline: GPU temp 45-65°C, frequency stable 2.1GHz
Anomaly: GPU temp spike to 85°C + frequency drop to 1.5GHz
→ Auto-capture snapshot
→ User clicks "This caused monitor blackout"
→ System learns correlation: "High temp + freq drop = blackout risk"
```

### 3. Monitor Detection Fallback Options

**Option A: Manual Database**
- User enters monitor model (LG ULTRAGEAR, Alienware AW3425DW, etc.)
- App stores common specifications (resolution, refresh rate, port types)
- Useful for future reference but doesn't fix current detection

**Option B: USB Device Descriptor Query**
- Query USB descriptors for monitor EDID (Extended Display Identification Data)
- More reliable than WMI but requires pyusb library
- Can extract: manufacturer, model, resolution, refresh rate, native port type

**Option C: Registry Lookup**
- Parse Windows registry for display device info
- `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\DISPLAY`
- Combined with WMI might get better results

**Recommended**: Option B (USB EDID) for accuracy + Option C (Registry) as fallback

### 4. Correlation Engine

**Pattern Detection**:
- "Monitor blackouts correlate with GPU temp > 80°C"
- "Blackouts occur 2 minutes after high memory pressure"
- "Issue happens when all 32 cores hit 95%+ utilization"

**Implementation**:
```python
# Pseudo-code
for each_issue:
    get_snapshot_before(issue_timestamp)
    get_snapshot_after(issue_timestamp)

    for each_metric:
        if metric_unusual_before_issue:
            increase_correlation_score(metric, issue_type)

# Provide recommendations
if correlation_score > 0.8:
    recommend("Try [fix] when metric exceeds threshold")
```

### 5. Driver Version Impact Analysis

**Track**:
- Correlate GPU driver updates with issue frequency
- Detect if specific driver versions cause problems
- Suggest driver rollback if pattern detected

**Example**:
```
Driver 591.74 → 0 blackouts (baseline)
Driver 592.06 → 4 blackouts in 3 days
Recommendation: "Driver 592.06 may cause blackouts. Rollback to 591.74?"
```

### 6. Time-Series Analysis Dashboard

**Visualizations**:
- CPU/GPU frequency over time with annotations for issues
- Memory usage trend with issue markers
- Temperature graph with throttling events
- Core utilization heatmap (32 cores over 24h)

**Alerts**:
- Show unusual patterns (sudden spikes, sustained high usage, thermal throttling)
- Highlight correlations with logged issues

## Implementation Priority

**Phase 2.1** (Week 1-2):
- [ ] Per-core CPU utilization capture
- [ ] GPU throttling detection
- [ ] Enhanced snapshot on issue log

**Phase 2.2** (Week 3-4):
- [ ] Basic anomaly detection (2σ baseline)
- [ ] Auto-issue creation for anomalies
- [ ] Manual monitor database fallback

**Phase 2.3** (Week 5-6):
- [ ] USB EDID monitor detection
- [ ] Correlation engine (metrics → issues)
- [ ] Driver version tracking

**Phase 2.4** (Week 7+):
- [ ] Thermal throttling detection
- [ ] Time-series dashboard
- [ ] Advanced pattern recognition

## Technical Notes

**Data Storage**:
- Keep metrics granular (per-second for now, can aggregate later)
- Store in new tables: `performance_samples`, `anomalies`, `correlations`
- Implement data retention policy (keep 30 days raw, 1 year aggregated)

**Performance**:
- Don't capture full metrics every second (too expensive)
- Capture only on-demand (user clicks "Collect Data")
- Background optional: low-frequency sampling (1/minute) if enabled

**AI/Learning**:
- Start with statistical baselines (mean, stddev)
- Migrate to time-series forecasting if needed (e.g., Prophet, ARIMA)
- User feedback loop is critical for accuracy

## User-Specific Use Case: Monitor Blackout Resolution

**Current Progress**:
- Captures GPU, CPU, memory state when issue logged ✓
- Stores monitor configuration ✓

**Next Steps**:
1. Fix monitor detection (EDID or registry)
2. Auto-capture when GPU freq drops or temp spikes
3. Detect pattern: "Blackouts when GPU frequency dips below 2.0GHz for >100ms"
4. Recommend: "Check GPU power supply", "Update drivers", "Adjust power settings"

---

*Last Updated: 2026-01-30*
*MVP Status: Core infrastructure complete, ready for Phase 2 features*
