# Development Guidelines for AI Agents (CLAUDE.md)

This project converts widescreen manga into mobile-friendly vertical Webtoons using simple, fast computer vision.

---

## ⚠️ Anti-Overengineering Mandate

**Do NOT vibe-code endless heuristic edge cases.**  
Manga panel layouts vary wildly. Attempting to add ad-hoc `if/elif/else` patches for every unusual panel will quickly turn this codebase into unmaintainable spaghetti that breaks other manga.

Follow these strict rules:

### 1. Safe Fallbacks > Chopped Art
* A clean **Full-Page panel** (with phone zoom) or a **Wide Frame** (with 90° rotation) is **infinitely better** than a flawed cut that slices through a character's face or dialogue balloon.
* Falling back to `full_page` or keeping a tier as a `horizontal_frame` is a **feature**, not a failure.

### 2. Never Add Hardcoded One-Off Hacks
* **Forbidden**: Page-number checks (`if page == 4:`), arbitrary magic coordinate offsets, or convoluted multi-pass contour clustering intended for a single page.
* **Allowed**: Universal principles based on gutters (whitespace bands) and tiers.

### 3. Raise Ambiguities to the User
* If a page extraction is ambiguous, unusual, or triggered a fallback:
  1. The CLI will emit a `💡 [HINTS FOR LLM / DEVELOPER REVIEW]` message.
  2. **Do NOT guess or invent custom heuristics.**
  3. **Raise the ambiguity directly to the USER.** Show the user the page number, the issue, and provide 2–3 clear choices (e.g., leave as full-page with zoom, adjust global gutter threshold, or allow manual crop coordinates).

### 4. Repository & Scale Architecture
* **Single-Repo Limit**: A GitHub repository can only host **one** GitHub Pages site (1 GB limit).
* **Scaling Strategy (Hub-and-Spoke)**:
  * `manga-to-phone` is the **Converter Engine & Main Catalog**.
  * When adding new manga series to avoid consuming the shared 1 GB quota, create dedicated repositories (e.g. `abugov/manga-tokyo-ghoul`), each getting its own independent 1 GB GitHub Pages quota and deploy action.
  * The main library simply links to each dedicated manga GitHub Pages URL.

### 5. Media Standards
* **WebP Only**: Always encode panels to `.webp` (quality 82, method 4). Never commit uncompressed PNGs or duplicate strips.
* **Target Width**: Standardized to 800px width.
