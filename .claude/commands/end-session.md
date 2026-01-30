# End Session Protocol - PC-Inspector

Execute these steps to properly close a development session:

## 1. Final Status Check
- Run `git status` to see all changes
- Test the application one more time
- Verify no errors in console

## 2. Create Handoff Document
Create `docs/handoffs/MM-DD-YYYY_HH-MM-SS_TZ.md`:

```markdown
# Session Handoff: [Date] - [Time] TZ

## Session Summary
[1-2 sentence overview]

---

## Accomplishments
- Bullet list of what was done

---

## Files Modified/Created
### New Files
- file1
- file2

### Modified Files
- file3
- file4

---

## Current Status
[What's working, what's not]

---

## Next Steps
[Prioritized list of what to do next]

---

## Technical Notes
[Important details for next session]
```

## 3. Update Master Handoff Index
Add entry to `docs/MASTER_HANDOFF_INDEX.md`:
- Date, Focus, Accomplishments, Status, Next Priority

## 4. Git Commit
```bash
git add .
git commit -m "type: description"
git log --oneline  # Verify
```

## 5. Verify
- All changes committed
- Handoff document complete
- Master index updated
