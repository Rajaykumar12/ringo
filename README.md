# Ringo

> Ask questions about your own PDFs, slides and spreadsheets. Runs entirely on your machine.

Ringo is a chat app for your own documents. You give it your files — a textbook, a
stack of reports, meeting slides, a spreadsheet — and then just ask questions about
them in plain language.

Every answer tells you where it came from, with clickable references back to the exact
page or slide, so you can check it rather than take its word for it. You can type your
question or speak it, and have the answer read back aloud. You can also show it a
picture and ask about that.

Your documents never leave your machine. They're indexed and stored locally, and only
your question and the relevant excerpts are sent to the language model.

---

## Why you might want it

- **Answers you can check.** Every response cites the page or slide it came from, and
  the citation expands to show you the source text. Made-up references are filtered
  out rather than shown.
- **Reads the formats you already have.** PDF, Word, PowerPoint, Excel, CSV, HTML and
  Markdown — including text inside images, charts and scanned pages.
- **Talk to it.** Ask by voice, get answers read aloud, or stick to typing.
- **Yours to run.** No subscription, no vendor account, no documents uploaded to
  anyone else's server.

---

## Requirements

- [Docker](https://docs.docker.com/get-started/get-docker/) with Compose
- A **free** [Groq API key](https://console.groq.com/keys) — this is the only external
  service, and it's what generates the answers
- Free disk space — the backend image is large because it bundles PyTorch, and about
  320 MB of speech and search models download the first time you run it

---

## Quick start

```bash
git clone https://github.com/Rajaykumar12/ringo.git
cd ringo
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in two values:

```ini
GROQ_API_KEY=your_key_here     # from console.groq.com/keys
ADMIN_API_KEY=pick-any-password # needed to add documents
```

Then start it:

```bash
docker compose up --build
```

Open **http://localhost:8081**. First run takes a few minutes while it downloads the
models; after that it starts in seconds.

### Adding your first document

The app starts with nothing to talk about, so give it something to read:

1. Open the **Documents** panel in the app
2. Paste the `ADMIN_API_KEY` you chose above when it asks
3. Upload a file and wait for it to finish indexing

Now ask it something about the file you just added.

> The admin key exists because the document routes can read out the full text of
> anything you've indexed — it keeps that behind a password rather than open to
> anyone who can reach the app.

---

## Running without Docker

Useful for development. You'll need Python 3.11+ and Node 20+.

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py                  # http://localhost:8000

# Frontend, in a second terminal
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Put `GROQ_API_KEY` in `backend/.env` first. For reading text out of images and scanned
pages you also need Tesseract installed:

```bash
sudo dnf install tesseract tesseract-langpack-eng   # Fedora/RHEL
sudo apt install tesseract-ocr tesseract-ocr-eng    # Ubuntu/Debian
```

It's optional — without it everything still works, you just lose text that's inside
pictures.

---

## How it works

When you ask a question, Ringo searches your documents two ways at once — by keyword
and by meaning — then re-ranks the results so only the most relevant passages are sent
to the language model along with your question. The model answers from those passages
and cites them, and the citations are checked against what was actually retrieved
before you see them.

Documents are split on paragraph and heading boundaries rather than fixed-size blocks,
so a passage doesn't get cut mid-thought. Images inside documents are extracted and
read with OCR, so a chart or a scanned page is searchable too.

For the full picture — the ingestion pipeline, retrieval strategy and project
layout — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Documentation

| | |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | How the pipeline works, and where everything lives |
| [Configuration](docs/CONFIGURATION.md) | Every environment variable |
| [API reference](docs/API.md) | Endpoints, rate limits, streaming format |
| [Deployment](docs/DEPLOYMENT.md) | Running it in production |
| [Contributing](CONTRIBUTING.md) | Dev setup, tests, and how to send a PR |

---

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers dev
setup, how to run the tests, and what CI checks.

---

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026 R Ajay Kumar.
