Title: Implementation Plan — Option A (Bounded work queue with 10 workers)
Date: 2025-10-15 15:30 local

Context
This plan translates the Option A design from research.md into an actionable implementation roadmap. Option A replaces existing batching patterns with a bounded work queue using asyncio.Queue and a fixed pool of 10 workers to ensure at most 10 active tasks at any time.

Goals
- Cap concurrency to a maximum of 10 active tasks for images and chapter processing.
- Maintain functional behavior and user-visible output (same book contents, ordering, metadata, styling).
- Improve memory profile and resource usage versus unbounded task creation.
- Keep progress reporting (tqdm) accurate and responsive.

Non-goals
- No CLI/UX changes (command-line flags and behavior remain the same by default).
- No network fetching logic refactors beyond the concurrency control.
- No change to EPUB style identifiers or paths.
- No change to caching behavior by default.

Assumptions and Constraints
- Python 3.12; uses beautifulsoup4, aiohttp, tqdm.asyncio, ebooklib; tests run with pytest.
- Existing retry logic in get_resource_with_retries remains the primary error-handling mechanism for I/O.
- Ordering of final pages must be preserved; image replacement must remain correct.

High-level Approach
- Introduce a reusable worker-queue pattern: enqueue work items (with indices where ordering matters), run 10 workers, await q.join(), then cancel workers and await their shutdown with return_exceptions=True.
- Apply this pattern to:
  1) build_update (images per update)
  2) do (chapters/pages)
  3) Optional: build_intro (intro images)

Configuration
- Define a module-level constant in lparchive2epub/lib.py: CONCURRENCY_LIMIT = 10.
- Optionally read from environment variable LP2E_CONCURRENCY (int) during initialization to ease local tuning; default to 10 if unset/invalid. This keeps user-facing CLI unchanged while enabling internal overrides during development.

Detailed Design and Code Changes
1) build_update: replace batching with queue workers
- Current: batch(images, 10) with per-batch gather.
- New pattern:
  - Create asyncio.Queue[(int, Image)] and list[tuple[int, IndexedEpubImage]] results.
  - Start N=CONCURRENCY_LIMIT workers; each pulls (i, image), awaits _get_image(session, image), appends (i, result), then q.task_done().
  - Enqueue all images with enumerate.
  - await q.join(), cancel workers, await gather(workers, return_exceptions=True).
  - Reconstruct ordered images = [img for _, img in sorted(results)].
  - Perform replace_img_name for each image; set update_chapter.content and return Page as today.
- Error handling: rely on get_resource_with_retries inside _get_image; if an exception escapes, it will bubble. If we decide to continue on some failures, catch per-item exceptions in the worker and record them for later reporting (out of scope for initial step).

2) do: limit concurrent build_single_page tasks to 10
- Current: collects all tasks (effectively unbounded) despite iterating in batches; then await gather(*tasks).
- New pattern:
  - Create asyncio.Queue[(int, Chapters)] and list[tuple[int, Page]] pages_indexed.
  - Under the existing tqdm context (pbar), start N workers.
  - Each worker pulls (i, chapter), awaits build_single_page(session, intro, chapter, intro.chapters, pbar), appends (i, page), q.task_done().
  - Enqueue all (i, chapter) with enumerate(intro.chapters).
  - await q.join(), cancel workers, await gather(workers, return_exceptions=True).
  - Set pages = [p for _, p in sorted(pages_indexed, key=lambda x: x[0])]. Keep existing sorting or indexing—index sort is deterministic and sufficient.
  - Proceed with add_page loop unchanged.
- Progress: build_single_page already calls pbar.update(1); safe across workers.

3) Optional: build_intro concurrency cap
- Mirror build_update approach for intro.images if the set can be large; otherwise retain existing gather for simplicity.

Worker Lifecycle and Cancellation
- Ensure q.task_done() is called in a finally block.
- After q.join(), cancel all workers and await them with return_exceptions=True to swallow CancelledError.
- Consider sentinel-based shutdown if we prefer clean exits without cancellation (not required for initial implementation).

Ordering Guarantees
- Use index-carrying queue items and reconstruct ordered results post-join to preserve deterministic behavior.
- Page comparison currently supports sorting; explicit indexing removes reliance on implicit ordering behaviors.

Resource Limits (Complementary)
- Do not change aiohttp connector limits in this step. If needed later, we can pass TCPConnector(limit=CONCURRENCY_LIMIT) to further cap connections, but it is complementary to the task-level queue.

Testing Strategy
- Run existing test suite: pytest -q (expect ~3 passed, 1 skipped per guidelines).
- Regression checks:
  - Tests in tests/test_lparchive2epub.py covering extractor/link rewriting should remain unaffected.
  - Ensure no new warnings/errors from tqdm with concurrent updates.
- Add an offline unit test (optional) for a small helper function if one is introduced (e.g., a queue runner) to verify ordering and limit (use dummy coroutines and counters).
- Manual smoke test: generate a small EPUB locally via CLI for a known small LP URL; verify pages and images present; check output file opens.

Performance Validation (Optional, Dev)
- Compare runtime against current version on a mid-size LP.
- Observe memory (RSS) and ensure that active tasks plateau around 10 under load.

Risk Assessment and Mitigations
- Deadlock risk if q.task_done() not called: always wrap in try/finally.
- Ordering drift: ensure index-based reconstruction and/or maintain final sorted(pages) call.
- Progress miscount: keep updates inside build_single_page only once per chapter.
- Exception propagation: let exceptions surface so failures are not silently ignored; optionally collect and aggregate later.

Implementation Steps (Phased)
1) Introduce CONCURRENCY_LIMIT constant and optional env read. (Small)
2) Implement build_update queue pattern; basic verification on a small sample. (Small)
3) Implement do queue pattern; verify progress bar usability; ensure pages order preserved. (Medium)
4) Optional: implement build_intro queue pattern if needed. (Small)
5) Run tests and linting; adjust as needed. (Small)
6) Document changes in README (brief note about internal concurrency control). (Tiny)

Acceptance Criteria
- Concurrency never exceeds 10 active tasks in build_update and do under typical operation.
- All existing tests pass (no new failures; e2e test remains skipped).
- Output EPUB contents are functionally equivalent (same number of pages/images; ordering preserved).
- No regressions in progress display or metadata.

Rollback Plan
- Changes are localized to lparchive2epub/lib.py; revert to pre-change batching/gather loops if issues arise.
- Keep changes in minimal, small commits to allow easy reversion.

Timeline (Estimate)
- Day 1 (2–4 hours): Implement build_update and do queue patterns; basic local verification.
- Day 1 (1 hour): Tests and small fixes; optional build_intro update if warranted.
- Day 1 (0.5 hour): Documentation touch-ups and PR polish.

Ownership and Review
- Primary: current contributor.
- Review: 1 peer for concurrency and ordering correctness; optional second review for performance.
