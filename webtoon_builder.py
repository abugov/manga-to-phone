import os
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any

class WebtoonBuilder:
    def __init__(self, target_width: int = 800, webp_quality: int = 82):
        self.target_width = target_width
        self.webp_quality = webp_quality

    def process_and_save_chapter(
        self,
        panel_data_list: List[Dict[str, Any]],
        chapter_dir: str,
        manga_title: str = "Tokyo Ghoul",
        chapter_title: str = "Chapter 1: Tragedy",
        chapter_num: int = 1,
        manga_slug: str = "tokyo-ghoul"
    ):
        os.makedirs(chapter_dir, exist_ok=True)
        panels_dir = os.path.join(chapter_dir, "panels")
        os.makedirs(panels_dir, exist_ok=True)
        
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
                
        # 2. Generate Chapter HTML Reader
        self._generate_chapter_reader(chapter_dir, manga_title, chapter_title, chapter_num, panel_records)
        
        # Calculate saved size
        total_size_mb = sum(os.path.getsize(os.path.join(panels_dir, os.path.basename(p["src"]))) for p in panel_records) / (1024 * 1024)
        print(f"[+] Successfully generated Webtoon chapter in: {chapter_dir}")
        print(f"    - {len(panel_records)} WebP panels ({total_size_mb:.2f} MB total)")
        print(f"    - Interactive reader: {os.path.join(chapter_dir, 'index.html')}")
        return panel_records

    def _generate_chapter_reader(self, chapter_dir, manga_title, chapter_title, chapter_num, panels):
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
                f'<img class="{cls_str}" data-idx="{p["idx"]}" loading="lazy" src="{p["src"]}" alt="Panel {p["idx"]}" onclick="openZoomModal(this.src)">'
                f'</div>'
            )
            
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
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
    }}
    /* Top Header Bar */
    header {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 52px;
      background: rgba(14, 14, 14, 0.94);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 12px;
      z-index: 100;
      transition: transform 0.25s ease;
    }}
    header.hidden {{
      transform: translateY(-100%);
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
      margin-top: 52px;
      margin-bottom: 60px;
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
      cursor: zoom-in;
      transition: transform 0.25s ease, max-width 0.25s ease;
      border-radius: 2px;
    }}
    /* Wide panel rotation mode (90 degrees landscape for phone tilting) */
    body.rotate-wide-mode .panel-wrapper[data-wide="true"] {{
      padding: 60px 0;
      overflow: visible;
    }}
    body.rotate-wide-mode .panel-wrapper[data-wide="true"] .webtoon-panel {{
      transform: rotate(90deg) scale(1.15);
      cursor: pointer;
    }}
    /* End of Chapter Section */
    .chapter-end {{
      padding: 50px 20px 90px 20px;
      text-align: center;
      color: #777;
      font-size: 14px;
    }}
    .chapter-end h3 {{
      color: #fff;
      font-size: 18px;
      margin-bottom: 8px;
    }}
    /* Bottom Navigation Bar */
    footer {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 52px;
      background: rgba(14, 14, 14, 0.94);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
      transition: transform 0.25s ease;
    }}
    footer.hidden {{
      transform: translateY(100%);
    }}
    .nav-btn {{
      background: none;
      border: none;
      color: #ccc;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      padding: 8px 16px;
      border-radius: 8px;
    }}
    .nav-btn:active {{
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }}
    /* Zoom Lightbox Modal */
    #zoomModal {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.95);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      overflow: auto;
      touch-action: pan-x pan-y pinch-zoom;
    }}
    #zoomModal.active {{
      display: flex;
    }}
    #zoomImage {{
      max-width: 98vw;
      max-height: 98vh;
      object-fit: contain;
      box-shadow: 0 0 40px rgba(0, 0, 0, 0.9);
      border-radius: 4px;
      cursor: zoom-out;
    }}
    .zoom-hint {{
      position: absolute;
      top: 18px;
      right: 18px;
      background: rgba(30, 30, 30, 0.8);
      color: #fff;
      font-size: 12px;
      padding: 6px 12px;
      border-radius: 20px;
      pointer-events: none;
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
    </div>
  </main>

  <footer id="footer">
    <button class="nav-btn" onclick="window.scrollTo({{ top: 0, behavior: 'smooth' }})">Top</button>
    <button class="nav-btn" onclick="toggleBars()">Toggle UI</button>
    <button class="nav-btn" onclick="window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }})">Bottom</button>
  </footer>

  <!-- Tap-to-Zoom Modal -->
  <div id="zoomModal" onclick="closeZoomModal()">
    <div class="zoom-hint">Tap anywhere to close • Pinch to zoom</div>
    <img id="zoomImage" src="" alt="Zoomed Panel">
  </div>

  <script>
    const header = document.getElementById('header');
    const footer = document.getElementById('footer');
    const progressBar = document.getElementById('progressBar');
    const counter = document.getElementById('counter');
    const panels = document.querySelectorAll('.webtoon-panel');
    const totalPanels = {total};
    const zoomModal = document.getElementById('zoomModal');
    const zoomImage = document.getElementById('zoomImage');
    const rotateToggle = document.getElementById('rotateToggle');

    // UI Bars Auto-hide on scroll
    let uiVisible = true;
    function toggleBars() {{
      uiVisible = !uiVisible;
      header.classList.toggle('hidden', !uiVisible);
      footer.classList.toggle('hidden', !uiVisible);
    }}

    // Toggle 90-degree rotation for wide panels
    let rotateWideMode = false;
    function toggleWideRotation() {{
      rotateWideMode = !rotateWideMode;
      document.body.classList.toggle('rotate-wide-mode', rotateWideMode);
      rotateToggle.classList.toggle('active', rotateWideMode);
    }}

    // Lightbox Zoom
    function openZoomModal(src) {{
      zoomImage.src = src;
      zoomModal.classList.add('active');
    }}
    function closeZoomModal() {{
      zoomModal.classList.remove('active');
      zoomImage.src = '';
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
            chapter_rows.append(
                f'<a href="./{ch["slug"]}/" class="chapter-card">'
                f'  <div class="ch-left">'
                f'    <div class="ch-num">CH. {ch["number"]:02d}</div>'
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
