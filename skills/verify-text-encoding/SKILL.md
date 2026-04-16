---
name: verify-text-encoding
description: Run after any Edit or Write that introduces or modifies multi-byte UTF-8 text in source files. Detects U+FFFD replacement chars and common mojibake patterns from UTF-8 corruption — Edit can break multi-byte characters when context boundaries split a byte sequence.
allowed-tools: Read, Bash, Grep
---

# verify-text-encoding

## Goal

Catch encoding corruption (U+FFFD, mojibake) in multi-byte UTF-8 strings BEFORE the user notices a `?` in the UI or a broken commit lands. Covers Cyrillic, CJK (Chinese/Japanese/Korean), Arabic, Hebrew, accented Latin, and any other non-ASCII Unicode text.

## Input

- `files` — list of file paths that were just edited.
- If not provided → derive from `git diff --name-only HEAD` and filter to the project's source extensions (`.ts`, `.tsx`, `.jsx`, `.js`, `.css`, `.scss`, `.md`, `.json`, `.vue`, `.svelte`, `.py`).

## Steps

1. **Resolve the file list.**
   - If caller passed `files` → use it directly.
   - Otherwise: `git diff --name-only HEAD` and filter.
   - If the resulting list is empty → exit with `PASS: nothing to verify`.

2. **U+FFFD scan (byte-level, Python — NOT grep).**
   - The replacement char is the 3-byte sequence `EF BF BD`. Plain `grep` won't reliably surface it.
   - For each file:
     ```bash
     python3 -c "
     import sys
     data = open(sys.argv[1], 'rb').read()
     try:
         txt = data.decode('utf-8')
     except UnicodeDecodeError as e:
         print(f'DECODE_ERROR: {e}'); sys.exit(2)
     idx = txt.find('\ufffd')
     if idx == -1:
         print('OK')
     else:
         start = max(0, idx - 20)
         end = min(len(txt), idx + 20)
         print(f'FFFD at offset {idx}: ...{txt[start:end]!r}...')
     " <path>
     ```

3. **Mojibake pattern scan (Grep).**
   - Look for common UTF-8-mis-decoded markers that appear when multi-byte text is double-encoded or decoded with the wrong charset:
     - `Ð[°-ÿ]` (Cyrillic double-encoding, `а`-range)
     - `Ñ[€-ÿ]` (Cyrillic double-encoding, `р`-range)
     - `â€™`, `â€œ`, `â€\x9d` (smart-quote mojibake)
     - `Â ` (non-breaking-space mojibake)
     - `Ã[€-¿]` (Latin-1 double-encoding of accented characters)
     - `\xC3\xA3\xC2` (triple-encoded UTF-8 marker)
   - Use `Grep` with `output_mode: "content"` and `-n` so the report includes line numbers.

4. **Multi-byte character presence check.**
   - For each file, verify that expected non-ASCII characters are intact by scanning for valid multi-byte sequences in the relevant ranges:
     - Cyrillic: U+0400..U+04FF
     - CJK Unified Ideographs: U+4E00..U+9FFF
     - Arabic: U+0600..U+06FF
     - Hebrew: U+0590..U+05FF
     - Accented Latin: U+00C0..U+024F
   - If the file previously contained characters in these ranges (per `git show HEAD:<file>`) but no longer does, flag as a potential encoding loss.

5. **Report and HALT on findings.**
   - Do **not** silently rewrite the file. The user needs to see the corruption and decide how to recover (often: re-apply the edit, or restore the file from git).
   - HALT means: emit the FAIL report, do not call any further Edit/Write tools, return control to the parent agent.

## Output Format

**PASS:**
```
PASS — verified <N> files, no FFFD or mojibake
```

**FAIL:**
```
FAIL — encoding corruption detected

| File                  | Issue              | Offset / Line | Context              |
| --------------------- | ------------------ | ------------- | -------------------- |
| src/.../foo.tsx       | U+FFFD             | offset 1234   | `...text�here...`    |
| src/.../bar.tsx       | mojibake (double)  | line 42       | `Ã¤Â¸Â­Ã¦â€"â€¡`    |

Recommendation: revert with `git checkout -- <file>` and re-apply the change in a single Write call instead of an Edit, or use Python to write the bytes directly.
```

## Learnings

- (Updated automatically after each run)
