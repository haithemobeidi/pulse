# End Session Protocol - Pulse

Execute ALL steps to properly close a development session. Do not skip any step.

## 1. Get Actual System Time
```bash
date '+%Y-%m-%d %H:%M:%S %Z'
```
CRITICAL: NEVER guess the time. Always use this command. Use the result for handoff filenames.

## 2. Final Status Check
- Run `git status` to see all changes
- Run `git diff --stat` to see what changed
- Run `git log --oneline -5` to review commits this session

## 3. Update Codebase Index
Update `docs/CODEBASE_INDEX.md`:
- Add entries for any NEW files created this session
- Update descriptions for significantly modified files
- Update the "Last Updated" date at the top

## 4. Create Handoff Document
Create `docs/handoffs/MM-DD-YYYY_HH-MM-SS_EST.md` using actual time from step 1:

```markdown
# Session Handoff: [Date] - [Time] EST

## Session Summary
[1-2 sentence overview of what this session accomplished]

## Accomplishments
- [Specific bullet points of what was done]

## Files Modified/Created
### New Files
- `path/to/file` - Description of what it does

### Modified Files
- `path/to/file` - What was changed and why

## Current Status
**Server**: [Working/Broken]
**AI Providers**: [Which are configured and working]
**Database**: [Tables count, any migrations needed]
**Frontend**: [What pages work, what's missing]
**Known Issues**: [List any bugs]

## Next Steps
1. [Highest priority]
2. [Second priority]
3. [Third priority]

## Technical Notes
[Architecture decisions, gotchas, important context for next session]
```

## 5. Update Master Handoff Index
Add entry to TOP of table in `docs/MASTER_HANDOFF_INDEX.md`:
- Date, Session Focus, Key Accomplishments, Status, Next Priority

## 6. Commit and Push
- Stage relevant files (be specific, don't blindly `git add .`)
- Verify no sensitive files (.env, API keys) are staged
- Create descriptive commit message with type prefix (feat, fix, docs, refactor, chore)
- Push to remote if configured
- Run `git status` to confirm clean working tree

## 7. Report to User
Confirm:
- All handoff documents created
- Codebase index updated
- Changes committed
- Next session priorities
