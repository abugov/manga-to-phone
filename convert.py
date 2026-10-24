#!/usr/bin/env python3
"""
Manga-to-Phone Converter
Converts desktop/wide-format manga pages into vertical-scrolling, mobile-friendly Webtoon format.
"""

import argparse
import glob
import os
import re
import sys
import time
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from panel_extractor import MangaPanelExtractor
from webtoon_builder import WebtoonBuilder

def download_chapter_images(url: str, dest_dir: str):
    os.makedirs(dest_dir, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": url
    }
    print(f"[*] Fetching manga chapter from: {url}")
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    img_urls = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src and re.search(r'\.(jpg|jpeg|png|webp)', src, re.I):
            if any(x in src.lower() for x in ["icon", "logo", "favicon", "avatar", "banner", "advert"]):
                continue
            if src.startswith("//"):
                src = "https:" + src
            if src not in img_urls:
                img_urls.append(src)
                
    print(f"[*] Found {len(img_urls)} chapter pages online.")
    downloaded = []
    for idx, u in enumerate(img_urls):
        ext = os.path.splitext(urlparse(u).path)[1] or ".jpg"
        out_path = os.path.join(dest_dir, f"page_{idx+1:03d}{ext}")
        if not os.path.exists(out_path):
            print(f"  Downloading page {idx+1}/{len(img_urls)}...", end="\r", flush=True)
            try:
                r = requests.get(u, headers=headers, timeout=20)
                if r.status_code == 200:
                    with open(out_path, "wb") as f:
                        f.write(r.content)
                    downloaded.append(out_path)
            except Exception as e:
                print(f"\n  [!] Failed to download {u}: {e}")
        else:
            downloaded.append(out_path)
            
    print(f"\n[+] Successfully saved {len(downloaded)} pages to {dest_dir}")
    return sorted(downloaded)

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def main():
    parser = argparse.ArgumentParser(description="Convert desktop manga pages into vertical phone webtoon format.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="URL of the manga chapter online")
    group.add_argument("--input-dir", type=str, help="Directory containing raw manga page images")
    
    parser.add_argument("--manga-slug", type=str, default="tokyo-ghoul", help="Slug for the manga series (e.g. tokyo-ghoul)")
    parser.add_argument("--manga-title", type=str, default="Tokyo Ghoul", help="Title for the manga series")
    parser.add_argument("--chapter-num", type=int, default=1, help="Chapter number (default: 1)")
    parser.add_argument("--chapter-title", type=str, default="Chapter 1: Tragedy", help="Chapter title")
    parser.add_argument("--order", choices=["rtl", "ltr"], default="rtl", help="Reading order: rtl (Japanese manga) or ltr (Western/Manhwa). Default: rtl")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional limit on number of pages to process for quick testing")
    parser.add_argument("--serve", action="store_true", help="Start local web server to preview on phone/browser after converting")
    parser.add_argument("--port", type=int, default=8000, help="Port for local web server (default: 8000)")
    
    args = parser.parse_args()
    
    # 1. Obtain input image files
    if args.url:
        parsed = urlparse(args.url)
        slug = os.path.basename(parsed.path.strip("/")) or "chapter"
        raw_dir = os.path.join("downloads", slug)
        image_files = download_chapter_images(args.url, raw_dir)
    else:
        raw_dir = args.input_dir
        extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        image_files = []
        for ext in extensions:
            image_files.extend(glob.glob(os.path.join(raw_dir, ext)))
        image_files = sorted(image_files, key=natural_sort_key)
        
    if not image_files:
        print(f"[!] No images found in {raw_dir}")
        sys.exit(1)
        
    if args.max_pages:
        image_files = image_files[:args.max_pages]
        print(f"[*] Processing limited to first {len(image_files)} pages.")
        
    # 2. Extract frames
    print(f"\n[*] Extracting distinctive manga frames (Reading Order: {args.order.upper()})...")
    extractor = MangaPanelExtractor(reading_order=args.order)
    
    all_panel_data = []
    start_time = time.time()
    
    for i, img_path in enumerate(image_files):
        print(f"  Processing page {i+1}/{len(image_files)}: {os.path.basename(img_path)}...", end="\r", flush=True)
        try:
            panels = extractor.extract_panels_from_image(img_path)
            all_panel_data.extend(panels)
        except Exception as e:
            print(f"\n  [!] Error processing {img_path}: {e}")
            
    elapsed = time.time() - start_time
    print(f"\n[+] Extracted {len(all_panel_data)} frames from {len(image_files)} pages in {elapsed:.2f} seconds! (~{elapsed/max(len(image_files),1):.3f}s per page)")
    
    # 3. Build Webtoon Output in 3-Level Hierarchy
    # Level 3: manga/<manga_slug>/ch<num:03d>/
    chapter_slug = f"ch{args.chapter_num:03d}"
    manga_dir = os.path.join("manga", args.manga_slug)
    chapter_dir = os.path.join(manga_dir, chapter_slug)
    
    builder = WebtoonBuilder(target_width=800, webp_quality=82)
    panel_records = builder.process_and_save_chapter(
        panel_data_list=all_panel_data,
        chapter_dir=chapter_dir,
        manga_title=args.manga_title,
        chapter_title=args.chapter_title,
        chapter_num=args.chapter_num,
        manga_slug=args.manga_slug
    )
    
    # Level 2: manga/<manga_slug>/index.html
    cover_rel_path = f"./{chapter_slug}/panels/panel_0001.webp"
    synopsis = "In modern day Tokyo, society lives in fear of Ghouls: mysterious creatures who look exactly like humans yet survive on flesh. Shy college student Ken Kaneki becomes embroiled in this dark world."
    
    chapters_meta = [
        {
            "number": args.chapter_num,
            "title": args.chapter_title,
            "slug": chapter_slug,
            "panel_count": len(panel_records)
        }
    ]
    builder.generate_manga_index(
        manga_dir=manga_dir,
        manga_title=args.manga_title,
        synopsis=synopsis,
        cover_rel_path=cover_rel_path,
        chapters=chapters_meta
    )
    
    # Level 1: index.html (Root Library)
    manga_catalog = [
        {
            "title": args.manga_title,
            "url": f"./manga/{args.manga_slug}/",
            "cover": f"./manga/{args.manga_slug}/{chapter_slug}/panels/panel_0001.webp",
            "chapters_count": len(chapters_meta),
            "desc": "Tokyo Ghoul converted for vertical phone reading with Japanese RTL reading order and wide panel 90° rotation."
        }
    ]
    builder.generate_root_library(
        root_dir=".",
        manga_list=manga_catalog
    )
    
    # 4. Optional server
    if args.serve:
        import socket
        import http.server
        import socketserver
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
        except Exception:
            lan_ip = "127.0.0.1"
        finally:
            s.close()
            
        Handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            print("\n" + "="*60)
            print("  MOBILE WEBTOON LIBRARY READY!")
            print(f"  -> On your computer:  http://localhost:{args.port}/")
            print(f"  -> On your smartphone (same Wi-Fi): http://{lan_ip}:{args.port}/")
            print("="*60 + "\n")
            print("Press Ctrl+C to stop the server.")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")

if __name__ == "__main__":
    main()
