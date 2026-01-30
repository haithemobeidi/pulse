# Work Session Protocol - PC-Inspector

Guidelines for productive development sessions:

## During Session
1. **One feature at a time** - Complete and test fully before moving to next
2. **Commit frequently** - After each working feature
3. **Track changes** - Update handoff document as you work
4. **Test thoroughly** - Dashboard loads, data displays, no errors
5. **Note issues** - Document any problems encountered

## Development Workflow
```
1. Start services: start.bat / start.ps1 / start.sh
2. Make changes to code
3. Test in browser at http://localhost:8080
4. If working: git commit
5. If not working: debug and iterate
```

## Git Commands
```bash
git status              # See what changed
git add <file>          # Stage specific file
git commit -m "msg"     # Commit with message
git log --oneline       # See commit history
```

## Testing Checklist
- [ ] Browser loads dashboard
- [ ] Dashboard shows GPU, monitors, memory, CPU
- [ ] "Collect Data" button works
- [ ] No errors in browser console (F12)
- [ ] No errors in backend window
