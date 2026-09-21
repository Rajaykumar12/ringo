# Contributing to Ringo

Thanks for taking an interest. Issues and pull requests are welcome.

---

## Getting set up

Run the stack once with Docker to confirm your environment works
(see the [README](README.md)), then switch to running the two halves directly.
You get hot reload and a much faster loop.

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py                     # http://localhost:8000

# Frontend, in a second terminal
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

In dev the frontend defaults to `http://localhost:8000` for the API with no
configuration, and the backend's default `ALLOWED_ORIGINS` already permits
`localhost:5173`.

OCR needs Tesseract installed on the host, covered in
[docs/CONFIGURATION.md](docs/CONFIGURATION.md). It is optional. Without it documents
still index, minus text from images inside them.

---

## Running the checks

```bash
cd backend  && pytest          # 106 tests
cd frontend && npm run lint    # eslint
cd frontend && npm run build   # tsc -b + vite build
```

**`pytest` needs `GROQ_API_KEY` set to something**, even a dummy value:

```bash
GROQ_API_KEY=test-key pytest
```

`main.py` checks for the key at import time and raises, so pytest cannot even
collect `tests/test_main.py` without one. No test makes a network call, so the value
is never used.

---

## What CI enforces

`.github/workflows/ci.yml` runs on every push to `main` and every pull request, as
two parallel jobs:

- **backend**: installs dependencies, audits them for known CVEs (`pip-audit`), runs `pytest`
- **frontend**: `npm ci`, audits dependencies (`npm audit --audit-level=high`), lints, and type-checks + builds

A PR needs all of these green.

---

## Dependency policy

Pillow is pinned ahead of its transitive floor deliberately: it parses attacker-supplied
bytes on the unauthenticated `/chat/image` route and during OCR of images embedded in
uploaded documents, making it the most exposed parser in the stack. `aiohttp`, `anyio`
and `cryptography` carry `>=` security floors for the same reason. They're transitive,
but the versions upstream would otherwise resolve to have open advisories.

### Known audit exceptions

The Python audit carries `--ignore-vuln` entries. Both are **unfixable, not unimportant.**
A step that always fails gets muted, which is worse than a narrow, documented exception:

| Advisory | Package | Why it can't be fixed |
|---|---|---|
| `PYSEC-2026-311`, `-3813`, `-3814`, `-3815` | chromadb | No fixed version published upstream. Re-check on every chromadb bump. |
| `PYSEC-2026-3447` | setuptools | Fixed in 83.0.0, but `torch` pins `setuptools<82`, so no torch-compatible release carries the fix. Build tooling, not request-path code. Drop when torch relaxes the pin. |

`npm audit` gates at `--audit-level=high`, so two **moderate** react-router advisories
are reported without failing the build. Fixing them requires react-router-dom v7, a
breaking major upgrade. Neither is reachable in this app as written: every `navigate()`
call targets a hardcoded literal (no user-controlled redirect target), and the second
advisory applies only to SSR hydration, which a Vite SPA does not use. Worth scheduling
the v7 migration, not worth an emergency.

If you add an exception, put the advisory ID, the package, the reason, and the
condition under which it can be dropped in the table above.

---

## Pull requests

- Keep commits focused: one concern per commit, single-line messages.
- Add a test for behaviour changes. The suite has good coverage of the RAG helpers,
  response sanitization, and request validation; follow the patterns in
  `backend/tests/`.
- If you change an endpoint, its rate limit, or an environment variable, update
  [docs/API.md](docs/API.md) or [docs/CONFIGURATION.md](docs/CONFIGURATION.md) in the
  same PR. Those tables are kept accurate against the code and are easy to let rot.
- Security-relevant code (request validation, the citation/image sanitizers, admin
  gating) has comments explaining *why* the guard exists. Preserve that reasoning if
  you touch it. Several of those invariants are not obvious from the code alone.

## Architecture orientation

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) has the pipeline diagrams, the document
ingestion flow, and a file-by-file map of the project.
