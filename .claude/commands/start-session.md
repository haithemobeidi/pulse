# Start Session Protocol - Pulse

Execute these steps to initialize a development session:

## 1. Context Review
- Read `docs/MASTER_HANDOFF_INDEX.md` for session history
- Read the most recent handoff from `docs/handoffs/`
- Read `docs/CODEBASE_INDEX.md` for file inventory and architecture overview

## 2. Status Check
- Run `git status` to check for uncommitted changes
- Run `git log --oneline -10` to see recent commits
- Verify database exists at `data/system.db`

## 3. Environment Verification
- Verify Windows Python venv exists (`venv/Scripts/python.exe`)
- Check `.env` file has required keys (GEMINI_API_KEY at minimum)
- Check if Ollama is reachable: `curl -s http://172.21.0.1:11434/api/tags`
- Test server can start: run `start-pulse.bat` from Windows or `powershell.exe -Command "cd 'C:\Users\haith\Documents\Vibe Projects\pc-inspector'; $env:PYTHONPATH='.'; .\venv\Scripts\python.exe -m backend.app"` from WSL

## 4. AI Provider Check
- Verify at least one AI provider is configured (Ollama, Gemini, or Claude)
- Report which providers are available

## 5. Session Summary
Provide:
- **Last session focus**: What was accomplished (from handoff)
- **Current status**: What's working, what needs fixing
- **Next priorities**: From backlog or previous handoff
- **Known issues**: Any bugs or blockers
- **Task list**: Create tasks for this session's planned work

## Important Notes
- This project runs on Windows Python (not WSL Python) via `venv/Scripts/python.exe`
- Frontend is served by Flask at `http://localhost:5000`
- PowerShell commands from WSL use `powershell.exe -Command "..."`
- Ollama runs on Windows, reachable from WSL at `http://172.21.0.1:11434`
- NEVER modify or delete system data without user approval
