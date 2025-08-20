# lparchive2epub – Development Guidelines

This document captures project-specific knowledge to streamline development, testing, and debugging for advanced contributors.

## Environment and Build/Configuration
- Language/runtime: Python 3.12 (see pyproject.toml).
- Package/Build tool: Poetry.
- CLI entry point: `lparchive2epub = lparchive2epub.main:main` (configured under `[tool.poetry.scripts]`).
- Dependencies of note:
  - Parsing/rendering: beautifulsoup4, ebooklib, tqdm (asyncio variant).
  - Networking and caching: aiohttp, aiohttp-client-cache.
- Dev dependencies: pytest, pytest-asyncio, coverage, blake3.
- Pytest config in pyproject:
  - `--import-mode=importlib` (imports project modules from source without installing a wheel)
  - `pythonpath = "."` (enables `import lparchive2epub.*` from repo root)
  - `asyncio_default_fixture_loop_scope = "session"`

Recommended local setup (Poetry):
- Install with development extras: `poetry install --with dev`
- Activate venv as needed: `poetry shell` (or prefix commands with `poetry run`)

Packaging:
- Build wheel/sdist: `poetry build`
- A PyInstaller script config exists in pyproject under `[tool.poetry-pyinstaller-plugin.scripts]` for a one-file bundle of `lparchive2epub`. If using that plugin, follow its docs; prebuilt artifacts may also be present under `dist/`.

## Running the CLI (Project-specific)
- Usage (from README): `lparchive2epub URL OUTPUT_FILE [--no-cache]`
- Caching behavior:
  - By default, the CLI uses `aiohttp_client_cache.CacheBackend()` via `CachedSession`.
  - `--no-cache` disables caching.
  - Batch script `util/all_archives.py` uses `SQLiteBackend` with `expire_after=-1` (no expiry) and an explicit cache path per item.
- Known limitations are tracked in README (e.g., some LPs fail to download; YouTube-heavy LPs are of limited value for EPUB).

## Testing
- Test framework: pytest (async support via pytest-asyncio).
- Run the full suite (validated):
  - `pytest -q`  => At time of writing: 3 passed, 1 skipped.
  - With Poetry: `poetry run pytest -q`.
- Scope and expectations:
  - Unit/integration tests under `tests/` validate parsing and link-fixing logic using static HTML fixtures located in `tests/resources/`.
  - The async end-to-end test `test_lparchive2epub` is explicitly skipped until an `ebooklib` update (see test body and skip reason). Keep it skipped for deterministic CI unless you’re testing against updated dependencies and have network access.
- Async defaults: The asyncio loop scope for fixtures is `session`. Mark async tests with `@pytest.mark.asyncio` (as used by e2e test).
- Resource loading: Tests typically load HTML via `importlib.resources.files(tests.resources).joinpath(...).read_bytes()`, ensuring no network dependency.
- Running subsets/examples:
  - A single test: `pytest tests/test_lparchive2epub.py::test_extractor_intro -q`
  - Keyword select: `pytest -k extractor -q`
- Coverage (optional): `coverage run -m pytest && coverage report` (or `coverage html`).

### Adding New Tests (Guidelines)
- Prefer offline tests using the bundled static resources or add new deterministic fixtures under `tests/resources/`.
- Avoid hitting the network in tests. If you must run live tests, mark them and skip by default; inject a `CachedSession` to control I/O and ensure clean teardown.
- Import from source using `import lparchive2epub.*` (pytest config already sets `pythonpath = "."`).
- For async functions, use `@pytest.mark.asyncio` and respect the session-scoped loop.

### Demonstrated Example Test (Validated)
The following minimal test was created and executed to validate the testing process. It checks the EPUB CSS item produced by `lparchive2epub.style.get_style_item`.

Example test file contents:

```python
from lparchive2epub.style import get_style_item
from ebooklib import epub


def test_get_style_item_properties():
    item = get_style_item()
    assert item.id == "style_nav"
    assert item.file_name == "style/nav.css"
    assert item.media_type == "text/css"
    assert isinstance(item, epub.EpubItem)
```

Commands used and verified:
- Run just this test: `pytest -q tests/test_guidelines_demo.py`
- Result observed: 1 passed in ~0.02s.

Note: The example file was only used for demonstration during documentation authoring and is not kept in the repo to avoid test noise.

## Debugging and Development Notes
- Caching and reproducibility:
  - CLI default caching uses `aiohttp_client_cache`; clear cache directories or set `--no-cache` when diagnosing I/O issues.
  - Utilities and some tests use an explicit `cache/` directory with SQLite backend files (e.g., `cache/<name>.sqlite`). Remove those to force re-fetch.
- E2E test constraints:
  - `test_lparchive2epub` is skipped with reason "Unable to run until ebooklib update" to avoid flakiness. Unskip only once `ebooklib` supports the required behavior and CI/network are configured.
- Parsing specifics:
  - BeautifulSoup parser used is the built-in `"html.parser"` for consistency (see tests).
  - Link rewriting in `Extractor.fix_links` normalizes relative links and rewrites chapter references; when extending, ensure new patterns don’t regress existing replacements (anchors vs. asset file links are treated differently).
- EPUB generation:
  - Styling is provided by `lparchive2epub.style.get_style_item()`; if altering styles, keep the EPUB item id (`style_nav`) and path (`style/nav.css`) stable unless tests are updated accordingly.
- Batch processing tool:
  - `util/all_archives.py` scrapes the frontpage JS to enumerate LPs and writes failures to an errors log near the output directory. It uses `SQLiteBackend` caching and fully async I/O. When debugging, consider reducing concurrency and ensuring proper cache cleanup/closure.
- Checksums tooling:
  - `calculate_checksums.sh` computes blake3 (`b3sum`) and md5 for all `.epub` files in a directory and prints JSON suitable for updating `tests/resources/all_b3sum.json` if needed.

## Verified Commands Summary
- Install dev deps: `poetry install --with dev`
- Run tests: `pytest -q` (or `poetry run pytest -q`)
- Run a specific test: `pytest tests/test_lparchive2epub.py::test_extractor_intro -q`
- Build artifacts: `poetry build`
- CLI usage: `lparchive2epub <LP_URL> <output.epub> [--no-cache]`
