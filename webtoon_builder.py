import os
import cv2
import numpy as np
from PIL import Image
from typing import List

class WebtoonBuilder:
    def __init__(self, target_width: int = 800, gutter_height: int = 24, bg_color: tuple = (18, 18, 18)):
        self.target_width = target_width
        self.gutter_height = gutter_height
        self.bg_color = bg_color  # Dark background for comfortable reading

    def process_and_save_chapter(
        self,
        all_panels: List[np.ndarray],
        output_dir: str,
        chapter_title: str = "Manga Chapter"
    ):
        os.makedirs(output_dir, exist_ok=True)
        panels_dir = os.path.join(output_dir, "panels")
        strips_dir = os.path.join(output_dir, "strips")
        os.makedirs(panels_dir, exist_ok=True)
        os.makedirs(strips_dir, exist_ok=True)
        
        # 1. Scale and save individual panel images
        panel_filenames = []
        pil_panels = []
        
        print(f"Resizing and saving {len(all_panels)} extracted panels...")
        for idx, panel_cv in enumerate(all_panels):
            p_rgb = cv2.cvtColor(panel_cv, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(p_rgb)
            
            # Scale to target_width
            w, h = pil_img.size
            if w > 0 and h > 0:
                scale = self.target_width / float(w)
                new_h = max(int(h * scale), 1)
                resized = pil_img.resize((self.target_width, new_h), Image.Resampling.LANCZOS)
                
                fname = f"panel_{idx+1:04d}.jpg"
                fpath = os.path.join(panels_dir, fname)
                resized.save(fpath, quality=90)
                
                panel_filenames.append(f"panels/{fname}")
                pil_panels.append(resized)
                
        # 2. Stitch into vertical strips (chunks up to ~6000px high for optimal mobile GPU texture performance)
        strip_filenames = []
        max_strip_height = 6000
        current_chunk = []
        current_h = 0
        
        strip_idx = 1
        for p in pil_panels:
            p_h = p.size[1] + self.gutter_height
            if current_chunk and (current_h + p_h > max_strip_height):
                # Save current strip
                s_name = self._save_strip(current_chunk, current_h, strip_idx, strips_dir)
                strip_filenames.append(f"strips/{s_name}")
                strip_idx += 1
                current_chunk = [p]
                current_h = p_h
            else:
                current_chunk.append(p)
                current_h += p_h
                
        if current_chunk:
            s_name = self._save_strip(current_chunk, current_h, strip_idx, strips_dir)
            strip_filenames.append(f"strips/{s_name}")
            
        # 3. Generate HTML5 Mobile Reader
        self._generate_html_reader(output_dir, chapter_title, panel_filenames, strip_filenames)
        print(f"Successfully generated Webtoon output in: {output_dir}")
        print(f"  - {len(panel_filenames)} panels")
        print(f"  - {len(strip_filenames)} vertical strips")
        print(f"  - Interactive reader: {os.path.join(output_dir, 'index.html')}")

    def _save_strip(self, pil_list, total_h, strip_idx, strips_dir):
        canvas_h = total_h + self.gutter_height
        canvas = Image.new("RGB", (self.target_width, canvas_h), (255, 255, 255))
        y = self.gutter_height // 2
        for p in pil_list:
            canvas.paste(p, (0, y))
            y += p.size[1] + self.gutter_height
            
        fname = f"strip_{strip_idx:03d}.jpg"
        canvas.save(os.path.join(strips_dir, fname), quality=90)
        return fname

    def _generate_html_reader(self, output_dir, chapter_title, panel_files, strip_files):
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>{chapter_title} - Mobile Webtoon Reader</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }}
    body {{
      background-color: #0d0d0d;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      overflow-x: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }}
    /* Top Header Bar */
    header {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 52px;
      background: rgba(18, 18, 18, 0.92);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      z-index: 100;
      transition: transform 0.25s ease;
    }}
    header.hidden {{
      transform: translateY(-100%);
    }}
    .title {{
      font-size: 15px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 70%;
    }}
    .progress-pill {{
      font-size: 12px;
      font-weight: 500;
      background: #2a2a2a;
      padding: 4px 10px;
      border-radius: 12px;
      color: #ff4757;
    }}
    /* Progress bar */
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
    /* Reader Container */
    #reader {{
      width: 100%;
      max-width: 680px;
      margin-top: 52px;
      margin-bottom: 60px;
      display: flex;
      flex-direction: column;
      align-items: center;
      background-color: #121212;
      box-shadow: 0 0 30px rgba(0, 0, 0, 0.8);
    }}
    .webtoon-panel {{
      width: 100%;
      height: auto;
      display: block;
      margin: 8px 0;
      background: #1a1a1a;
      transition: opacity 0.3s ease;
    }}
    .webtoon-panel:first-child {{
      margin-top: 0;
    }}
    /* Bottom Navigation Bar */
    footer {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 54px;
      background: rgba(18, 18, 18, 0.92);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
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
      color: #fff;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      padding: 8px 16px;
      border-radius: 8px;
    }}
    .nav-btn:active {{
      background: #2a2a2a;
    }}
    /* End of Chapter banner */
    .chapter-end {{
      padding: 40px 20px 80px 20px;
      text-align: center;
      color: #888;
      font-size: 14px;
    }}
    .chapter-end h3 {{
      color: #fff;
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>

  <header id="header">
    <div class="title">{chapter_title}</div>
    <div class="progress-pill" id="counter">1 / {len(panel_files)}</div>
  </header>

  <div class="progress-bar-container">
    <div class="progress-bar" id="progressBar"></div>
  </div>

  <main id="reader">
    {''.join([f'<img class="webtoon-panel" data-idx="{i+1}" loading="lazy" src="{f}" alt="Panel {i+1}">' for i, f in enumerate(panel_files)])}
    
    <div class="chapter-end">
      <h3>End of Chapter</h3>
      <p>Formatted for Mobile Phone Webtoon Viewing</p>
    </div>
  </main>

  <footer id="footer">
    <button class="nav-btn" onclick="window.scrollTo({{ top: 0, behavior: 'smooth' }})">Top</button>
    <button class="nav-btn" onclick="toggleBars()">Toggle UI</button>
    <button class="nav-btn" onclick="window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }})">Bottom</button>
  </footer>

  <script>
    let lastScroll = 0;
    const header = document.getElementById('header');
    const footer = document.getElementById('footer');
    const progressBar = document.getElementById('progressBar');
    const counter = document.getElementById('counter');
    const panels = document.querySelectorAll('.webtoon-panel');
    const totalPanels = {len(panel_files)};

    let uiVisible = true;
    function toggleBars() {{
      uiVisible = !uiVisible;
      header.classList.toggle('hidden', !uiVisible);
      footer.classList.toggle('hidden', !uiVisible);
    }}

    window.addEventListener('click', (e) => {{
      // Tap center of screen to toggle UI bars
      if (e.target.tagName !== 'BUTTON') {{
        toggleBars();
      }}
    }});

    window.addEventListener('scroll', () => {{
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scrollPercent = (scrollTop / (scrollHeight || 1)) * 100;
      
      progressBar.style.width = Math.min(scrollPercent, 100) + '%';

      // Update current panel count based on viewport
      let currentIdx = 1;
      const midScreen = window.innerHeight / 2;
      for (let p of panels) {{
        const rect = p.getBoundingClientRect();
        if (rect.top <= midScreen && rect.bottom >= midScreen) {{
          currentIdx = p.getAttribute('data-idx');
          break;
        }}
      }}
      counter.textContent = currentIdx + ' / ' + totalPanels;
    }}, {{ passive: true }});
  </script>
</body>
</html>
"""
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)
