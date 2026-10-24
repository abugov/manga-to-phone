import os
import glob
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any

class WebtoonBuilder:
    def __init__(self, target_width: int = 800, webp_quality: int = 78):
        self.target_width = target_width
        self.webp_quality = webp_quality

    def process_and_save_chapter(
        self,
        panel_data_list: List[Dict[str, Any]],
        chapter_dir: str,
        manga_title: str = "Tokyo Ghoul",
        chapter_title: str = "Chapter 1: Tragedy",
        chapter_num: Any = 1,
        manga_slug: str = "tokyo-ghoul",
        prev_href: str = None,
        next_href: str = None
    ):
        os.makedirs(chapter_dir, exist_ok=True)
        panels_dir = os.path.join(chapter_dir, "panels")
        os.makedirs(panels_dir, exist_ok=True)
        # Clean any existing panel files to prevent stale panels
        for old_f in glob.glob(os.path.join(panels_dir, "*")):
            try:
                os.remove(old_f)
            except Exception:
                pass
        
        # 1. Save panels as WebP
        panel_records = []
        print(f"Resizing and saving {len(panel_data_list)} panels to WebP (quality={self.webp_quality})...")
        
        for idx, item in enumerate(panel_data_list):
            panel_cv = item["image"]
            p_type = item.get("type", "standard_frame")
            is_wide = item.get("is_wide", False)
            
            p_rgb = cv2.cvtColor(panel_cv, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(p_rgb)
            
            w, h = pil_img.size
            if w > 0 and h > 0:
                scale = self.target_width / float(w)
                new_h = max(int(h * scale), 1)
                resized = pil_img.resize((self.target_width, new_h), Image.Resampling.LANCZOS)
                
                fname = f"panel_{idx+1:04d}.webp"
                fpath = os.path.join(panels_dir, fname)
                resized.save(fpath, "WEBP", quality=self.webp_quality, method=4)
                
                panel_records.append({
                    "src": f"panels/{fname}",
                    "type": p_type,
                    "is_wide": is_wide or (w / float(h) > 1.35),
                    "aspect": round(w / float(h), 2),
                    "idx": idx + 1
                })
                
        # 2. Check for adjacent chapters (prev / next)
        manga_parent_dir = os.path.dirname(chapter_dir)
        if prev_href is None:
            # Fallback auto-detection
            try:
                c_num_int = int(chapter_num)
                has_prev = (c_num_int > 0) and os.path.exists(os.path.join(manga_parent_dir, f"ch{c_num_int - 1:03d}"))
                prev_href = f"../ch{c_num_int - 1:03d}/" if has_prev else "#"
            except (ValueError, TypeError):
                has_prev = False
                prev_href = "#"
        else:
            has_prev = bool(prev_href and prev_href != "#")
            
        if next_href is None:
            try:
                c_num_int = int(chapter_num)
                has_next = os.path.exists(os.path.join(manga_parent_dir, f"ch{c_num_int + 1:03d}"))
                next_href = f"../ch{c_num_int + 1:03d}/" if has_next else "#"
            except (ValueError, TypeError):
                has_next = False
                next_href = "#"
        else:
            has_next = bool(next_href and next_href != "#")
        
        # 3. Generate Chapter HTML Reader
        self._generate_chapter_reader(
            chapter_dir=chapter_dir,
            manga_title=manga_title,
            chapter_title=chapter_title,
            chapter_num=chapter_num,
            panels=panel_records,
            has_prev=has_prev,
            prev_href=prev_href,
            has_next=has_next,
            next_href=next_href
        )
        
        # Calculate saved size
        total_size_mb = sum(os.path.getsize(os.path.join(panels_dir, os.path.basename(p["src"]))) for p in panel_records) / (1024 * 1024)
        print(f"[+] Successfully generated Webtoon chapter in: {chapter_dir}")
        print(f"    - {len(panel_records)} WebP panels ({total_size_mb:.2f} MB total)")
        print(f"    - Interactive reader: {os.path.join(chapter_dir, 'index.html')}")
        return panel_records

    def _generate_chapter_reader(
        self,
        chapter_dir: str,
        manga_title: str,
        chapter_title: str,
        chapter_num: int,
        panels: List[Dict[str, Any]],
        has_prev: bool,
        prev_href: str,
        has_next: bool,
        next_href: str
    ):
        total = len(panels)
        
        # Build panel HTML elements
        panels_html = []
        for p in panels:
            classes = ["webtoon-panel"]
            if p["is_wide"]:
                classes.append("wide-panel")
            if p["type"] == "full_page":
                classes.append("full-page-panel")
                
            cls_str = " ".join(classes)
            panels_html.append(
                f'<div class="panel-wrapper" data-wide="{str(p["is_wide"]).lower()}">'
                f'<img class="{cls_str}" data-idx="{p["idx"]}" loading="lazy" src="{p["src"]}" alt="Panel {p["idx"]}">'
                f'</div>'
            )
            
        prev_disabled = "" if has_prev else "disabled"
        next_disabled = "" if has_next else "disabled"
        
        # End of chapter navigation button
        if has_next:
            end_btn_html = f'<a href="{next_href}" class="end-nav-btn primary">Next Chapter ➔</a>'
        else:
            end_btn_html = f'<a href="../index.html" class="end-nav-btn">Back to Chapters</a>'
            
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover">
  <title>{manga_title} - {chapter_title} - Webtoon Reader</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }}
    body {{
      background-color: #0b0b0b;
      color: #eaeaea;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      overflow-x: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      user-select: none;
      -webkit-user-select: none;
      touch-action: pan-y pinch-zoom;
    }}
    /* Top Header Bar - Always Visible */
    header {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 52px;
      background: rgba(14, 14, 14, 0.96);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 12px;
      z-index: 100;
    }}
    .back-btn {{
      color: #ff4757;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 6px 8px;
      border-radius: 6px;
    }}
    .back-btn:active {{
      background: rgba(255, 255, 255, 0.1);
    }}
    .title-area {{
      text-align: center;
      max-width: 45%;
      overflow: hidden;
    }}
    .manga-name {{
      font-size: 11px;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .chapter-name {{
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .controls {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .rotate-toggle {{
      background: #222;
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #ddd;
      font-size: 11px;
      font-weight: 600;
      padding: 5px 8px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .rotate-toggle.active {{
      background: #ff4757;
      color: #fff;
      border-color: #ff4757;
    }}
    .progress-pill {{
      font-size: 11px;
      font-weight: 600;
      background: #202020;
      padding: 5px 8px;
      border-radius: 8px;
      color: #aaa;
    }}
    /* Top Progress Bar */
    .progress-bar-container {{
      position: fixed;
      top: 52px;
      left: 0;
      right: 0;
      height: 3px;
      background: transparent;
      z-index: 101;
    }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #ff6b81, #ff4757);
      transition: width 0.1s linear;
    }}
    /* Reader Canvas */
    #reader {{
      width: 100%;
      max-width: 760px;
      margin-top: 56px;
      margin-bottom: 74px;
      display: flex;
      flex-direction: column;
      align-items: center;
      background-color: #0b0b0b;
    }}
    .panel-wrapper {{
      width: 100%;
      display: flex;
      justify-content: center;
      margin: 8px 0;
      position: relative;
    }}
    .webtoon-panel {{
      width: 100%;
      height: auto;
      display: block;
      touch-action: pan-y pinch-zoom;
      transition: transform 0.25s ease, max-width 0.25s ease;
      border-radius: 2px;
    }}
    /* Wide panel rotation mode (-90 degrees counter-clockwise for phone tilting) */
    body.rotate-wide-mode .panel-wrapper[data-wide="true"] {{
      height: min(100vw, 760px);
      min-height: min(100vw, 760px);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 24px 0;
      overflow: visible;
    }}
    body.rotate-wide-mode .panel-wrapper[data-wide="true"] .webtoon-panel {{
      transform: rotate(-90deg);
      transform-origin: center center;
      width: min(100vw, 760px);
      height: auto;
      max-width: none;
    }}
    /* End of Chapter Section */
    .chapter-end {{
      padding: 50px 20px 60px 20px;
      text-align: center;
      color: #777;
      font-size: 14px;
      width: 100%;
      max-width: 400px;
    }}
    .chapter-end h3 {{
      color: #fff;
      font-size: 18px;
      margin-bottom: 6px;
    }}
    .end-actions {{
      margin-top: 20px;
      display: flex;
      justify-content: center;
      gap: 12px;
    }}
    .end-nav-btn {{
      background: #222;
      color: #fff;
      text-decoration: none;
      font-size: 14px;
      font-weight: 600;
      padding: 10px 20px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      display: inline-block;
    }}
    .end-nav-btn.primary {{
      background: #ff4757;
      border-color: #ff4757;
    }}
    /* Bottom Chapter Navigation Bar - Always Visible */
    footer {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 56px;
      background: rgba(14, 14, 14, 0.96);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      z-index: 100;
    }}
    .nav-btn {{
      background: #1e1e1e;
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #fff;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
    }}
    .nav-btn:active {{
      background: #2a2a2a;
    }}
    .nav-btn.primary {{
      background: #ff4757;
      border-color: #ff4757;
      color: #fff;
    }}
    .nav-btn.disabled {{
      opacity: 0.3;
      pointer-events: none;
      cursor: default;
    }}
  </style>
</head>
<body>

  <header id="header">
    <a href="../index.html" class="back-btn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
      Chapters
    </a>

    <div class="title-area">
      <div class="manga-name">{manga_title}</div>
      <div class="chapter-name">{chapter_title}</div>
    </div>

    <div class="controls">
      <button id="rotateToggle" class="rotate-toggle" onclick="toggleWideRotation()" title="Rotate wide panels 90 degrees for landscape reading">
        <span>🔄 90°</span>
      </button>
      <div class="progress-pill" id="counter">1/{total}</div>
    </div>
  </header>

  <div class="progress-bar-container">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <main id="reader">
    {''.join(panels_html)}
    
    <div class="chapter-end">
      <h3>End of {chapter_title}</h3>
      <p>Formatted for Mobile Phone Webtoon Viewing</p>
      <div class="end-actions">
        {end_btn_html}
      </div>
    </div>
  </main>

  <footer id="footer">
    <a class="nav-btn {prev_disabled}" href="{prev_href}">‹ Prev Chapter</a>
    <a class="nav-btn" href="../index.html">📑 All Chapters</a>
    <a class="nav-btn primary {next_disabled}" href="{next_href}">Next Chapter ›</a>
  </footer>

  <script>
    const progressBar = document.getElementById('progressBar');
    const counter = document.getElementById('counter');
    const panels = document.querySelectorAll('.webtoon-panel');
    const totalPanels = {total};
    const rotateToggle = document.getElementById('rotateToggle');

    // Toggle 90-degree rotation for wide panels
    let rotateWideMode = false;
    function toggleWideRotation() {{
      rotateWideMode = !rotateWideMode;
      document.body.classList.toggle('rotate-wide-mode', rotateWideMode);
      rotateToggle.classList.toggle('active', rotateWideMode);
    }}

    // Scroll progress & panel counter
    window.addEventListener('scroll', () => {{
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scrollPercent = (scrollTop / (scrollHeight || 1)) * 100;
      progressBar.style.width = Math.min(scrollPercent, 100) + '%';

      const midScreen = window.innerHeight / 2;
      for (let p of panels) {{
        const rect = p.getBoundingClientRect();
        if (rect.top <= midScreen && rect.bottom >= midScreen) {{
          counter.textContent = p.getAttribute('data-idx') + '/' + totalPanels;
          break;
        }}
      }}
    }}, {{ passive: true }});
  </script>
</body>
</html>
"""
        with open(os.path.join(chapter_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

    @staticmethod
    def generate_manga_index(
        manga_dir: str,
        manga_title: str,
        synopsis: str,
        cover_rel_path: str,
        chapters: List[Dict[str, Any]]
    ):
        """Level 2: Generates Manga series page with chapter list."""
        os.makedirs(manga_dir, exist_ok=True)
        
        chapter_rows = []
        for ch in chapters:
            cnum = ch["number"]
            ch_num_display = f"{int(cnum):02d}" if isinstance(cnum, int) or (isinstance(cnum, float) and cnum.is_integer()) else f"{cnum}"
            chapter_rows.append(
                f'<a href="./{ch["slug"]}/" class="chapter-card">'
                f'  <div class="ch-left">'
                f'    <div class="ch-num">CH. {ch_num_display}</div>'
                f'    <div class="ch-info">'
                f'      <div class="ch-title">{ch["title"]}</div>'
                f'      <div class="ch-meta">{ch["panel_count"]} Mobile Panels • Webtoon Format</div>'
                f'    </div>'
                f'  </div>'
                f'  <div class="ch-arrow">➔</div>'
                f'</a>'
            )
            
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>{manga_title} - Chapters - Manga-to-Phone</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }}
    body {{
      background-color: #0b0b0b;
      color: #eaeaea;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px 16px;
    }}
    header {{
      width: 100%;
      max-width: 640px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 24px;
    }}
    .back-link {{
      color: #ff4757;
      text-decoration: none;
      font-size: 14px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .manga-header {{
      width: 100%;
      max-width: 640px;
      display: flex;
      gap: 20px;
      background: #141414;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 28px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }}
    .cover-box {{
      width: 110px;
      min-width: 110px;
      height: 160px;
      border-radius: 10px;
      overflow: hidden;
      background: #222;
    }}
    .cover-box img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .manga-details {{
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .status-tag {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      color: #ff4757;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 800;
      margin-bottom: 8px;
      color: #fff;
    }}
    .synopsis {{
      font-size: 13px;
      color: #888;
      line-height: 1.45;
    }}
    /* Chapter List */
    .chapter-section {{
      width: 100%;
      max-width: 640px;
    }}
    .section-title {{
      font-size: 15px;
      font-weight: 700;
      color: #aaa;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;
    }}
    .chapter-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .chapter-card {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #181818;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 12px;
      padding: 14px 16px;
      text-decoration: none;
      color: inherit;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .chapter-card:active, .chapter-card:hover {{
      transform: translateY(-2px);
      border-color: rgba(255, 71, 87, 0.5);
    }}
    .ch-left {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .ch-num {{
      font-size: 14px;
      font-weight: 800;
      color: #ff4757;
      background: rgba(255, 71, 87, 0.12);
      padding: 6px 10px;
      border-radius: 8px;
    }}
    .ch-title {{
      font-size: 15px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 2px;
    }}
    .ch-meta {{
      font-size: 12px;
      color: #777;
    }}
    .ch-arrow {{
      color: #ff4757;
      font-size: 16px;
    }}
  </style>
</head>
<body>

  <header>
    <a href="../../index.html" class="back-link">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
      Library
    </a>
  </header>

  <div class="manga-header">
    <div class="cover-box">
      <img src="{cover_rel_path}" alt="{manga_title} Cover">
    </div>
    <div class="manga-details">
      <div class="status-tag">Japanese Reading Flow (RTL)</div>
      <h1>{manga_title}</h1>
      <p class="synopsis">{synopsis}</p>
    </div>
  </div>

  <div class="chapter-section">
    <div class="section-title">Chapters ({len(chapters)})</div>
    <div class="chapter-list">
      {''.join(chapter_rows)}
    </div>
  </div>

</body>
</html>
"""
        with open(os.path.join(manga_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    @staticmethod
    def generate_root_library(
        root_dir: str,
        manga_list: List[Dict[str, Any]]
    ):
        """Level 1: Generates main catalog index page."""
        os.makedirs(root_dir, exist_ok=True)
        
        cards = []
        for m in manga_list:
            cards.append(
                f'<a href="{m["url"]}" class="manga-card">'
                f'  <div class="cover-wrap">'
                f'    <img src="{m["cover"]}" alt="{m["title"]} Cover">'
                f'  </div>'
                f'  <div class="card-info">'
                f'    <div class="tag">{m["chapters_count"]} Chapters • Mobile Webtoon</div>'
                f'    <h2 class="manga-title">{m["title"]}</h2>'
                f'    <p class="meta-text">{m["desc"]}</p>'
                f'    <div class="read-btn">'
                f'      <span>View Chapters</span>'
                f'      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>'
                f'    </div>'
                f'  </div>'
                f'</a>'
            )
            
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Manga-to-Phone Webtoon Library</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }}
    body {{
      background-color: #0b0b0b;
      color: #eaeaea;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 16px;
    }}
    header {{
      width: 100%;
      max-width: 600px;
      text-align: center;
      margin-top: 16px;
      margin-bottom: 28px;
    }}
    .badge {{
      display: inline-block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      font-weight: 700;
      background: rgba(255, 71, 87, 0.15);
      color: #ff4757;
      border: 1px solid rgba(255, 71, 87, 0.3);
      padding: 4px 12px;
      border-radius: 20px;
      margin-bottom: 12px;
    }}
    h1 {{
      font-size: 26px;
      font-weight: 800;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #ffffff 0%, #a4b0be 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    p.subtitle {{
      font-size: 14px;
      color: #777;
      line-height: 1.5;
    }}
    .library {{
      width: 100%;
      max-width: 600px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .manga-card {{
      display: flex;
      background: #141414;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      overflow: hidden;
      text-decoration: none;
      color: inherit;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
      transition: transform 0.2s ease, border-color 0.2s ease;
    }}
    .manga-card:hover, .manga-card:active {{
      transform: translateY(-2px);
      border-color: rgba(255, 71, 87, 0.4);
    }}
    .cover-wrap {{
      width: 110px;
      min-width: 110px;
      height: 155px;
      background: #222;
      overflow: hidden;
    }}
    .cover-wrap img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .card-info {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      flex: 1;
    }}
    .tag {{
      font-size: 11px;
      font-weight: 600;
      color: #ff4757;
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .manga-title {{
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 6px;
      line-height: 1.3;
    }}
    .meta-text {{
      font-size: 13px;
      color: #888;
      margin-bottom: 14px;
      line-height: 1.4;
    }}
    .read-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
      color: #ff4757;
    }}
    footer {{
      margin-top: auto;
      padding-top: 40px;
      font-size: 12px;
      color: #555;
      text-align: center;
    }}
  </style>
</head>
<body>

  <header>
    <div class="badge">Mobile Optimized</div>
    <h1>Manga-to-Phone</h1>
    <p class="subtitle">Traditional widescreen manga automatically converted into vertical-scrolling smartphone Webtoons.</p>
  </header>

  <main class="library">
    {''.join(cards)}
  </main>

  <footer>
    <p>Powered by OpenCV &amp; WebP Compression • $0 LLM Cost</p>
  </footer>

</body>
</html>
"""
        with open(os.path.join(root_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
