#!/usr/bin/env python3
"""
Batch Manga-to-Phone Converter
Converts entire manga series chapter-by-chapter into mobile-friendly vertical Webtoons,
with incremental git commits, safe fallbacks, and mobile reading navigation.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from panel_extractor import MangaPanelExtractor
from webtoon_builder import WebtoonBuilder

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://ww12.tokyoghoulre.com/"
}

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def get_chapter_catalog(manga_url: str = "https://ww12.tokyoghoulre.com/manga/tokyo-ghoul/", catalog_cache_path: str = "manga/tokyo-ghoul/catalog.json"):
    if os.path.exists(catalog_cache_path):
        try:
            with open(catalog_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception as e:
            print(f"[*] Warning: Could not read cache {catalog_cache_path}: {e}")

    print(f"[*] Fetching full chapter catalog from {manga_url}...")
    resp = requests.get(manga_url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", href=re.compile(r'/chapter/tokyo-ghoul-chapter-'))

    seen = {}
    for l in links:
        href = l.get("href")
        m = re.search(r'tokyo-ghoul-chapter-([0-9.]+)', href)
        if m:
            ch_str = m.group(1)
            ch_float = float(ch_str)
            text = l.text.strip()
            
            # Format canonical chapter title
            if ch_float == 0:
                title = "Chapter 0: Rize"
                slug = "ch000"
            elif ch_float == 46.5:
                title = "Chapter 46.5"
                slug = "ch046_5"
            else:
                c_int = int(ch_float)
                slug = f"ch{c_int:03d}"
                title = f"Chapter {c_int}"
                
            if ch_float not in seen:
                seen[ch_float] = {
                    "num": ch_float,
                    "num_str": ch_str,
                    "slug": slug,
                    "url": href,
                    "title": title
                }

    catalog = sorted(seen.values(), key=lambda x: x["num"])
    os.makedirs(os.path.dirname(catalog_cache_path), exist_ok=True)
    with open(catalog_cache_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
        
    print(f"[+] Loaded {len(catalog)} chapters in catalog (Ch {catalog[0]['num_str']} to Ch {catalog[-1]['num_str']}).")
    return catalog

def download_chapter_images(chapter_url: str, dest_dir: str, max_workers: int = 5):
    os.makedirs(dest_dir, exist_ok=True)
    chapter_headers = dict(HEADERS)
    chapter_headers["Referer"] = chapter_url

    resp = requests.get(chapter_url, headers=chapter_headers, timeout=25)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    img_urls = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src:
            src = src.strip()
        if src and re.search(r'\.(jpg|jpeg|png|webp)', src, re.I):
            if any(x in src.lower() for x in ["icon", "logo", "favicon", "avatar", "banner", "advert"]):
                continue
            if src.startswith("//"):
                src = "https:" + src
            if src not in img_urls:
                img_urls.append(src)
                
    if not img_urls:
        raise ValueError(f"No manga page images found on {chapter_url}")

    print(f"    Online images found: {len(img_urls)}. Downloading with {max_workers} threads...")
    
    downloaded_map = {}
    
    def download_single(idx, u):
        ext = os.path.splitext(urlparse(u).path)[1] or ".jpg"
        out_path = os.path.join(dest_dir, f"page_{idx+1:03d}{ext}")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
            return idx, out_path
            
        s = requests.Session()
        s.headers.update(chapter_headers)
        for attempt in range(4):
            try:
                r = s.get(u, timeout=20)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(out_path, "wb") as f:
                        f.write(r.content)
                    return idx, out_path
                time.sleep(0.5 * (attempt + 1))
            except Exception:
                time.sleep(0.5 * (attempt + 1))
        return idx, None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_single, i, u) for i, u in enumerate(img_urls)]
        for f in as_completed(futures):
            idx, res_path = f.result()
            if res_path:
                downloaded_map[idx] = res_path

    if len(downloaded_map) < len(img_urls):
        missing = [i+1 for i in range(len(img_urls)) if i not in downloaded_map]
        print(f"    [!] Warning: Missing {len(missing)} pages: {missing}")

    sorted_pages = [downloaded_map[i] for i in sorted(downloaded_map.keys())]
    return sorted_pages

def update_chapter_navigation(chapter_dir: str, prev_href: str, has_prev: bool, next_href: str, has_next: bool):
    index_file = os.path.join(chapter_dir, "index.html")
    if not os.path.exists(index_file):
        return
        
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()

    prev_disabled = "" if has_prev else "disabled"
    next_disabled = "" if has_next else "disabled"

    new_footer = f"""<footer id="footer">
    <a class="nav-btn {prev_disabled}" href="{prev_href}">‹ Prev Chapter</a>
    <a class="nav-btn" href="../index.html">📑 All Chapters</a>
    <a class="nav-btn primary {next_disabled}" href="{next_href}">Next Chapter ›</a>
  </footer>"""

    content = re.sub(r'<footer id="footer">.*?</footer>', new_footer, content, flags=re.DOTALL)
    
    if has_next:
        end_btn = f'<a href="{next_href}" class="end-nav-btn primary">Next Chapter ➔</a>'
    else:
        end_btn = '<a href="../index.html" class="end-nav-btn">Back to Chapters</a>'
    content = re.sub(r'<div class="end-actions">.*?</div>', f'<div class="end-actions">\n        {end_btn}\n      </div>', content, flags=re.DOTALL)

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(content)

def git_commit_and_push(commit_msg: str, push: bool = True):
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if not status.stdout.strip():
        print("    [Git] No changes to commit.")
        return False
        
    subprocess.run(["git", "add", "manga/", "index.html", "convert.py", "scraper.py", "webtoon_builder.py", "batch_convert.py"], check=True)
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    print(f"    [Git] Committed: '{commit_msg}'")
    
    if push:
        print("    [Git] Pushing to origin main...")
        for attempt in range(4):
            res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
            if res.returncode == 0:
                print("    [Git] Push successful!")
                return True
            print(f"    [Git] Push attempt {attempt+1} failed: {res.stderr.strip()}. Pulling rebase and retrying...")
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True)
            time.sleep(2)
        print("    [!] Warning: Push failed after 4 attempts.")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Batch convert manga chapters to mobile Webtoon format.")
    parser.add_argument("--start", type=float, default=0.0, help="Starting chapter number (e.g. 0)")
    parser.add_argument("--end", type=float, default=143.0, help="Ending chapter number (e.g. 143)")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of chapters per git commit & push (default: 5)")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    parser.add_argument("--target-width", type=int, default=750, help="Webtoon panel target width (default: 750)")
    parser.add_argument("--quality", type=int, default=75, help="WebP quality (default: 75)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent image download workers (default: 5)")
    parser.add_argument("--force", action="store_true", help="Re-convert existing chapters")
    args = parser.parse_args()

    manga_slug = "tokyo-ghoul"
    manga_title = "Tokyo Ghoul"
    manga_dir = os.path.join("manga", manga_slug)
    os.makedirs(manga_dir, exist_ok=True)
    
    catalog = get_chapter_catalog()
    target_chapters = [c for c in catalog if args.start <= c["num"] <= args.end]
    print(f"[*] Target chapters to process: {len(target_chapters)} (from Ch {args.start} to Ch {args.end})\n")
    
    # Load or initialize completed chapters registry
    chapters_registry_path = os.path.join(manga_dir, "chapters.json")
    completed_dict = {}
    if os.path.exists(chapters_registry_path):
        try:
            with open(chapters_registry_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
                completed_dict = {e["slug"]: e for e in entries}
        except Exception as e:
            print(f"[!] Warning reading registry: {e}")

    # Check already existing chapter directories
    for c in catalog:
        c_dir = os.path.join(manga_dir, c["slug"])
        panels_dir = os.path.join(c_dir, "panels")
        if os.path.exists(c_dir) and os.path.exists(panels_dir) and not args.force:
            webps = glob.glob(os.path.join(panels_dir, "*.webp"))
            if len(webps) > 0 and c["slug"] not in completed_dict:
                completed_dict[c["slug"]] = {
                    "number": c["num"],
                    "title": c["title"],
                    "slug": c["slug"],
                    "panel_count": len(webps)
                }

    builder = WebtoonBuilder(target_width=args.target_width, webp_quality=args.quality)
    extractor = MangaPanelExtractor(reading_order="rtl")

    newly_converted_in_batch = []
    batch_start_idx = 0

    total_start_time = time.time()

    for idx, ch_meta in enumerate(target_chapters):
        ch_num = ch_meta["num"]
        ch_slug = ch_meta["slug"]
        ch_title = ch_meta["title"]
        ch_url = ch_meta["url"]
        ch_dir = os.path.join(manga_dir, ch_slug)
        panels_dir = os.path.join(ch_dir, "panels")

        is_already_done = (
            not args.force and 
            os.path.exists(ch_dir) and 
            os.path.exists(panels_dir) and 
            len(glob.glob(os.path.join(panels_dir, "*.webp"))) > 0
        )

        print(f"\n[{idx+1}/{len(target_chapters)}] >>> Chapter {ch_meta['num_str']} ({ch_title}) <<<")
        
        if is_already_done:
            print(f"    Already converted ({len(glob.glob(os.path.join(panels_dir, '*.webp')))} panels). Skipping download.")
            continue

        raw_dir = os.path.join("downloads", f"{manga_slug}-{ch_slug}")
        t0 = time.time()

        try:
            # 1. Download
            image_files = download_chapter_images(ch_url, raw_dir, max_workers=args.workers)
            if not image_files:
                print(f"    [!] Error: No pages downloaded for {ch_slug}. Skipping.")
                continue

            # 2. Extract panels
            all_panel_data = []
            review_hints = []
            for img_p in image_files:
                panels, hint = extractor.extract_panels_from_image(img_p)
                all_panel_data.extend(panels)
                if hint.get("is_fallback") or hint.get("confidence") != "high":
                    review_hints.append(hint)

            # Determine prev/next links from the full catalog
            cat_idx = next((i for i, c in enumerate(catalog) if c["slug"] == ch_slug), None)
            prev_slug = catalog[cat_idx - 1]["slug"] if (cat_idx is not None and cat_idx > 0) else None
            next_slug = catalog[cat_idx + 1]["slug"] if (cat_idx is not None and cat_idx < len(catalog) - 1) else None

            prev_href = f"../{prev_slug}/" if prev_slug else "#"
            next_href = f"../{next_slug}/" if next_slug else "#"

            # 3. Build Webtoon panels & Reader
            panel_records = builder.process_and_save_chapter(
                panel_data_list=all_panel_data,
                chapter_dir=ch_dir,
                manga_title=manga_title,
                chapter_title=ch_title,
                chapter_num=ch_num,
                manga_slug=manga_slug,
                prev_href=prev_href,
                next_href=next_href
            )

            # Save review hints
            hints_path = os.path.join(ch_dir, "review_hints.json")
            with open(hints_path, "w", encoding="utf-8") as f:
                json.dump(review_hints, f, indent=2)

            # 4. Clean up downloaded raw pages to save disk space
            shutil.rmtree(raw_dir, ignore_errors=True)

            ch_record = {
                "number": ch_num,
                "title": ch_title,
                "slug": ch_slug,
                "panel_count": len(panel_records)
            }
            completed_dict[ch_slug] = ch_record
            newly_converted_in_batch.append(ch_record)
            
            elapsed = time.time() - t0
            print(f"    [+] Finished {ch_slug} in {elapsed:.1f}s ({len(panel_records)} WebP panels).")

        except Exception as e:
            print(f"    [!] Error converting {ch_slug}: {e}")
            import traceback
            traceback.print_exc()

        # Update navigation between all completed chapters
        sorted_completed = sorted(completed_dict.values(), key=lambda x: x["number"])
        for i, c in enumerate(sorted_completed):
            p_href = f"../{sorted_completed[i-1]['slug']}/" if i > 0 else "#"
            n_href = f"../{sorted_completed[i+1]['slug']}/" if i < len(sorted_completed) - 1 else "#"
            update_chapter_navigation(
                chapter_dir=os.path.join(manga_dir, c["slug"]),
                prev_href=p_href,
                has_prev=(i > 0),
                next_href=n_href,
                has_next=(i < len(sorted_completed) - 1)
            )

        # Save chapters.json
        with open(chapters_registry_path, "w", encoding="utf-8") as f:
            json.dump(sorted_completed, f, indent=2)

        # Regenerate Manga Series index (Level 2)
        cover_rel_path = "./ch000/panels/panel_0001.webp" if os.path.exists(os.path.join(manga_dir, "ch000/panels/panel_0001.webp")) else "./ch001/panels/panel_0001.webp"
        synopsis = "In modern day Tokyo, society lives in fear of Ghouls: mysterious creatures who look exactly like humans yet survive on flesh. Shy college student Ken Kaneki becomes embroiled in this dark world."
        builder.generate_manga_index(
            manga_dir=manga_dir,
            manga_title=manga_title,
            synopsis=synopsis,
            cover_rel_path=cover_rel_path,
            chapters=sorted_completed
        )

        # Regenerate Root Library index (Level 1)
        manga_catalog = [
            {
                "title": manga_title,
                "url": f"./manga/{manga_slug}/",
                "cover": f"./manga/{manga_slug}/{cover_rel_path.lstrip('./')}",
                "chapters_count": len(sorted_completed),
                "desc": "Tokyo Ghoul converted for vertical phone reading with Japanese RTL reading order and wide panel 90° rotation."
            }
        ]
        builder.generate_root_library(
            root_dir=".",
            manga_list=manga_catalog
        )

        # Check if batch limit reached for git commit & push
        if len(newly_converted_in_batch) >= args.batch_size or (idx == len(target_chapters) - 1 and len(newly_converted_in_batch) > 0):
            first_c = newly_converted_in_batch[0]["number"]
            last_c = newly_converted_in_batch[-1]["number"]
            first_str = f"{int(first_c)}" if first_c.is_integer() else f"{first_c}"
            last_str = f"{int(last_c)}" if last_c.is_integer() else f"{last_c}"
            
            if first_str == last_str:
                commit_msg = f"feat(tokyo-ghoul): add chapter {first_str} mobile webtoon"
            else:
                commit_msg = f"feat(tokyo-ghoul): add chapters {first_str}-{last_str} mobile webtoon"
                
            print(f"\n[Batch] Committing batch ({len(newly_converted_in_batch)} chapters: Ch {first_str} to Ch {last_str})...")
            git_commit_and_push(commit_msg, push=(not args.no_push))
            newly_converted_in_batch = []

    total_time = time.time() - total_start_time
    print(f"\n{'='*70}")
    print(f"[✓] Batch conversion complete in {total_time/60:.2f} minutes!")
    print(f"    Total completed chapters in library: {len(completed_dict)}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
