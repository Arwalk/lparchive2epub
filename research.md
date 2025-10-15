Title: Replacing batching with a bounded work queue (max 10 active tasks)
Date: 2025-10-15 15:19 local

Summary
This document analyzes the current batching approach in the project and outlines how to replace it with a work-queue-based design that ensures at most 10 concurrently active tasks. The queue approach can provide steadier resource usage, natural backpressure, easier cancellation, and more even progress compared to manual batching.

Where batching is used today
1) lparchive2epub/lib.py::build_update (lines 355–378)
   - Current behavior: downloads images in chunks of 10 and awaits each chunk sequentially.
   - Code excerpt (lib.py 364–371):
     for chunk in batch(data.images, 10):
         tasks = []
         for image in chunk:
             task = asyncio.ensure_future(img_builder(image))
             tasks.append(task)
         images.extend(await asyncio.gather(*tasks))
   - Effect: limits concurrent image fetches to 10 at a time per update page, then processes the next chunk. This does cap concurrency effectively in this function.

2) lparchive2epub/lib.py::do (lines 429–495)
   - Current behavior: builds a list of tasks for all chapters while iterating in batches of 10, then awaits them all once at the end.
   - Code excerpt (lib.py 461–468):
     with tqdm(total=len(intro.chapters), desc="Gathering and building pages") as pbar:
         for chunk in batch(intro.chapters, 10):
             for chapter in chunk:
                 task = asyncio.ensure_future(build_single_page(session, intro, chapter, intro.chapters, pbar))
                 tasks.append(task)
         pages.extend(await asyncio.gather(*tasks))
   - Effect: despite the batching in the outer loop, all tasks are created before awaiting; there is no concurrency cap during execution. The batching here is largely cosmetic and does not limit active tasks.

3) Note: build_intro (lib.py 319–334) uses gather without an explicit limit for intro images. While not called out in the issue, a queue-based limiter could be applied similarly if desired.

Why prefer a work queue over batching
- True concurrency cap: A queue with N workers ensures at most N active tasks regardless of input size.
- Natural backpressure: Producers enqueue work; workers pull at a controlled pace. You do not risk inflating a large list of pending Tasks.
- Streamed completion: Results are produced as soon as items finish, not in fixed-size bursts.
- Easier cancellation/shutdown: Workers can be cancelled or signaled to stop; the queue can be drained or joined.
- Simpler to reason about correctness: The concurrency bound is explicit and centralized, rather than implied by chunk sizes and gather points.

Design options for capping concurrency
A) Work queue with fixed-size worker pool (recommended here)
- Use asyncio.Queue to hold work items and create 10 worker tasks that continuously consume from the queue.
- Push all work items (images or chapters) into the queue, await q.join(), then cancel workers.
- Preserve ordering if needed by carrying indices and assembling results at the end.

B) Semaphore-based wrapper (alternative)
- Wrap each awaitable in a semaphore-limited runner. This also caps concurrency to 10 but doesn’t use a queue; it may be simpler to retrofit, though the issue specifically requests a “work queue.”

C) aiohttp connection limits (complementary)
- Setting ClientSession(connector=aiohttp.TCPConnector(limit=10)) caps concurrent connections, not tasks. This is complementary but not a substitute for application-level task limiting.

Drop-in queue patterns for this repo
Below are patterns tailored to the current code paths. They assume Python 3.12 and the existing async structure.

1) Replacing image batching in build_update with a 10-worker queue
- Goal: replace the manual batch() + gather loop with a queue that ensures <= 10 active fetches.
- Ordering: For replacing image names in HTML, order of downloads is not critical; we can process results as they complete. If you prefer deterministic ordering, store indices and sort at the end (shown below).

Example revision sketch:

async def build_update(session: aiohttp.ClientSession, chapter: Chapters, data: Update, intro: Intro) -> Page:
    update_chapter = epub.EpubHtml(title=str(chapter.txt), file_name=chapter.new_href, lang=intro.language)
    update_chapter.add_item(get_style_item())

    img_builder = functools.partial(_get_image, session)

    q: asyncio.Queue[tuple[int, Image]] = asyncio.Queue()
    results: list[tuple[int, IndexedEpubImage]] = []

    async def worker():
        while True:
            try:
                i, image = await q.get()
                try:
                    res = await img_builder(image)
                    results.append((i, res))
                finally:
                    q.task_done()
            except asyncio.CancelledError:
                break

    # Start 10 workers
    workers = [asyncio.create_task(worker()) for _ in range(10)]

    # Enqueue all images
    for i, image in enumerate(data.images):
        await q.put((i, image))

    # Wait for all work to be done and stop workers
    await q.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    # If deterministic ordering is desired:
    images = [img for _, img in sorted(results, key=lambda x: x[0])]

    for image in images:
        data.content = replace_img_name(data.content, image)

    update_chapter.content = str(data.content)
    return Page(chapter.num, update_chapter, images)

Notes:
- The queue ensures only 10 active _get_image calls at any time.
- results collects outputs for later processing. If ordering is unnecessary, you can append directly and skip sorting.
- Error handling strategy: if _get_image raises (it already retries internally), the exception will propagate; you can capture and store exceptions per index if you prefer to continue.

2) Replacing chapter task creation in do with a 10-worker queue
- Goal: ensure no more than 10 concurrent build_single_page tasks, while preserving the final chapter order and keeping progress updates.
- Ordering: The current code sorts pages at the end anyway. With an index, you can keep deterministic ordering too.

Example revision sketch:

async def do(url: str, file: str, session: aiohttp.ClientSession, writer):
    # ... (setup unchanged up to known_images/add_page)

    writer("building chapters / updates")
    pages_indexed: list[tuple[int, Page]] = []

    q: asyncio.Queue[tuple[int, Chapters]] = asyncio.Queue()

    with tqdm(total=len(intro.chapters), desc="Gathering and building pages") as pbar:
        async def worker():
            while True:
                try:
                    i, chapter = await q.get()
                    try:
                        page = await build_single_page(session, intro, chapter, intro.chapters, pbar)
                        pages_indexed.append((i, page))
                    finally:
                        q.task_done()
                except asyncio.CancelledError:
                    break

        workers = [asyncio.create_task(worker()) for _ in range(10)]

        for i, chapter in enumerate(intro.chapters):
            await q.put((i, chapter))

        await q.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    # Keep the existing ordering logic (or sort by index):
    pages = [p for _, p in sorted(pages_indexed, key=lambda x: x[0])]

    for p in tqdm(pages, desc="Adding pages to book"):
        add_page(known_images, book, toc, spine, p)

    # ... (rest of function unchanged)

Notes:
- pbar.update(1) is still called inside build_single_page; this is safe with multiple concurrent workers.
- This approach never schedules more than 10 build_single_page tasks at a time, reducing peak memory usage and controlling outbound requests.

3) Optional: Applying the queue to build_intro
- If intro image sets are large for some pages, the same queue pattern can cap fetches to 10.

Error handling and retries
- get_resource_with_retries (lib.py 274–291) already contains retry logic for HTTP GET flows, which is used by _get_image and build_single_page paths. The queue workers will therefore benefit from existing retry behavior.
- If you want the entire run to continue even if some items fail, catch exceptions in the worker, record them alongside the index, and proceed. After q.join(), decide whether to re-raise aggregate errors or log and continue.

Cancellation and shutdown
- This pattern cancels workers after q.join(). It’s typically safe; you can also push sentinel values (e.g., None) equal to the number of workers instead of cancelling, if you prefer graceful exits without CancelledError.
- Use return_exceptions=True on the gather that waits for worker cancellation to avoid propagating CancelledError.

Backpressure and memory footprint
- Unlike creating N=all tasks, the queue ensures only 10 tasks are executing at once. Enqueuing can still be O(len(items)) in memory, but the number of actively awaited I/O operations stays bounded.
- If input sets are extremely large and you also want to bound queued items, you can create the queue with a maxsize and await q.put(). That introduces true backpressure to the producer side.

Progress reporting (tqdm)
- Progress bars are updated from within build_single_page, so they reflect per-item completion regardless of worker count.
- If you move updates into the workers, ensure that each completed item calls pbar.update(1) exactly once.

Alternatives: semaphore or TaskGroup
- A simple alternative uses an asyncio.Semaphore to wrap each operation and then awaits asyncio.gather over all coroutines. This is less intrusive but diverges from the work-queue requirement.
- Python 3.12 TaskGroup does not natively expose a concurrency limit; a common pattern is still to use a queue or a semaphore.

A note about util/all_archives.py
- do() currently processes URLs sequentially (lines 82–85). If you later want to apply the same queue pattern to download multiple LPs concurrently with a cap of 10, the same worker/queue structure applies around do_single.

Key takeaways
- build_update: batching currently enforces a limit; replace with a worker queue for smoother streaming and centralized concurrency control.
- do: batching does not limit concurrency; replace with a worker queue to ensure at most 10 active build_single_page tasks.
- The queue approach provides clear concurrency bounds, easier cancellation, and can integrate cleanly with existing progress reporting and retry logic.
