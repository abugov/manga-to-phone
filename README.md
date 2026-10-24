# Manga-to-Phone Webtoon Converter 📱📖

Convert traditional desktop/wide-format manga pages into vertical-scrolling, mobile-friendly Webtoons for smartphones.

## Key Features

- **Distinct Frame Detection**: Accurately extracts manga frames along horizontal tiers and vertical gutters using computer vision.
- **Full Page & Splash Art Preservation**: Intelligently identifies covers, title graphics, 2-page spreads, and TOC pages, keeping them intact as full pages rather than chopping them up.
- **Wide Panels & 90° Rotation**: Wide horizontal panels are preserved with their original aspect ratio. The reader includes a **🔄 90° toggle** to rotate wide panels for landscape reading when turning the phone, plus **tap-to-zoom** for inspection.
- **WebP Compression**: Panels are compressed to modern `.webp` format (~13 MB per chapter, saving over 50% vs JPEG) with crisp text and line art.
- **3-Level Navigation Hierarchy**:
  1. **Library Catalog** (`index.html`)
  2. **Manga Series Page** (`manga/<slug>/index.html`) with synopsis and chapter list
  3. **Mobile Webtoon Reader** (`manga/<slug>/ch<num>/index.html`) with continuous vertical scrolling, progress bar, panel counter, and zoom modal.
- **$0 LLM Cost & Instant Speed**: Runs 100% locally with pure Python, OpenCV, and Pillow. Processes a 47-page chapter (~144 panels) in **0.39 seconds**.

---

## Live Demo (GitHub Pages)

- **Library Catalog:** [https://abugov.github.io/manga-to-phone/](https://abugov.github.io/manga-to-phone/)
- **Tokyo Ghoul Series Index:** [https://abugov.github.io/manga-to-phone/manga/tokyo-ghoul/](https://abugov.github.io/manga-to-phone/manga/tokyo-ghoul/)
- **Chapter 1 Webtoon Reader:** [https://abugov.github.io/manga-to-phone/manga/tokyo-ghoul/ch001/](https://abugov.github.io/manga-to-phone/manga/tokyo-ghoul/ch001/)

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
python convert.py --url "https://ww12.tokyoghoulre.com/chapter/tokyo-ghoul-chapter-001/" --manga-slug tokyo-ghoul --chapter-num 1
```

### 3. Convert from a Local Folder of Images
```bash
python convert.py --input-dir downloads/tokyo-ghoul-chapter-001 --manga-slug tokyo-ghoul --chapter-num 1
```

### 4. Preview on Smartphone over Wi-Fi
```bash
python convert.py --input-dir downloads/tokyo-ghoul-chapter-001 --serve
```
This prints a local Wi-Fi URL (e.g. `http://192.168.1.X:8000/`) that you can open right in Safari or Chrome on your phone.
