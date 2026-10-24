# Manga-to-Phone Webtoon Converter 📱📖

Convert traditional desktop/wide-format manga pages into vertical-scrolling, mobile-friendly Webtoon format for smartphones.

## Key Features

- **Automated Panel Detection**: Uses a fast Recursive X-Y Cut computer vision algorithm that segments manga panels along horizontal and vertical gutters in milliseconds.
- **$0 LLM Cost & Instant Speed**: Runs 100% locally with pure Python, OpenCV, and Pillow. Processes an entire 47-page chapter (~176 panels) in **under 0.5 seconds**.
- **Japanese Manga Reading Order (RTL)**: Automatically preserves traditional Japanese reading flow (Top-to-Bottom, Right-to-Left within each tier/row). Also supports Western comics / Manhwa (`--order ltr`).
- **Splash & Spread Handling**: Distinguishes between cover/splash art, 2-page spreads, and multi-panel pages.
- **Mobile Webtoon Output**:
  - Individual mobile-optimized panel images scaled to standard phone screen widths (800px).
  - Vertical strip images with smooth gutter spacing.
  - **Standalone Interactive HTML5 Mobile Reader** (`index.html`) with continuous vertical scrolling, dark OLED theme, panel counter, and touch support.
- **Direct Chapter Scraping**: Pass any online manga chapter URL directly to download and convert in one command.

---

## Quickstart

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Convert from an Online URL
```bash
python convert.py --url "https://ww12.tokyoghoulre.com/chapter/tokyo-ghoul-chapter-001/" --output-dir tokyo_ghoul_ch1
```

### 3. Convert from a Local Folder of Images
```bash
python convert.py --input-dir path/to/manga_pages --output-dir converted_webtoon
```

### 4. Preview on your Phone / Browser
Add the `--serve` flag to immediately launch a local server and read the chapter on your phone over Wi-Fi:
```bash
python convert.py --input-dir downloads/tokyo-ghoul-chapter-001 --output-dir output_webtoon_full --serve
```
This prints a local network URL (e.g. `http://192.168.1.X:8000/`) that you can open right in Safari or Chrome on your phone!

---

## CLI Options

| Flag | Description | Default |
|---|---|---|
| `--url <URL>` | URL of the manga chapter online to download & convert | - |
| `--input-dir <PATH>` | Local folder containing raw manga page images | - |
| `--output-dir <PATH>` | Output folder for panels, strips, and HTML reader | `output_webtoon` |
| `--order <rtl\|ltr>` | Reading order: `rtl` (Japanese manga) or `ltr` (Western/Manhwa) | `rtl` |
| `--max-pages <N>` | Limit processing to first N pages (for testing) | All |
| `--serve` | Start local HTTP server to read on phone/browser | Disabled |
| `--port <PORT>` | Server port when `--serve` is active | `8000` |
