# Work Session Protocol - Pulse

Mid-session check-in and development guidelines.

## Quick Status Check
- Review task list progress (TaskList)
- Run `git status` for uncommitted changes
- Verify server is still running: `curl -s http://localhost:5000/api/health`
- Check browser console (F12) for errors

## Development Workflow
```
1. Start server: double-click start-pulse.bat (or run from WSL)
2. Open browser: http://localhost:5000
3. Make code changes
4. Test in browser - verify functionality works
5. If working: commit with descriptive message
6. If broken: debug and iterate
7. Update task list as you complete items
```

## Architecture Reminders
- **Backend**: Python Flask at `backend/app.py` (Windows venv)
- **Frontend**: Vanilla JS/HTML at `frontend/` (served by Flask)
- **Database**: SQLite at `data/system.db`
- **AI Providers**: `backend/ai/providers.py` (Ollama → Gemini → Claude failover)
- **Scanners**: `backend/collectors/` (hardware, monitors, reliability)
- **Learning**: `backend/ai/learning.py` (pattern detection from fix outcomes)

## Key Principles
1. **One feature at a time** - Complete and test fully before moving to next
2. **Commit frequently** - After each working feature, don't pile up changes
3. **User approval required** - Never write/delete without user confirming
4. **Read-only by default** - All system scanners are read-only
5. **Test the full flow** - Describe problem → scan → AI diagnosis → fix approval → outcome

## Testing Checklist
- [ ] Browser loads at http://localhost:5000
- [ ] Troubleshoot page shows provider status badges
- [ ] Can describe a problem and get AI analysis
- [ ] Fix approval/reject buttons work
- [ ] Dashboard shows GPU, monitors, memory, CPU
- [ ] "Collect Data" button works
- [ ] No errors in browser console (F12)
- [ ] No errors in Flask server window

## Code Quality
- Keep files under ~500 lines when possible
- Add comments for complex logic and agent handoffs
- Use existing patterns (BaseCollector for new scanners, providers.py for new AI providers)
- Follow existing naming conventions
