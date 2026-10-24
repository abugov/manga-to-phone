import os
import re
import requests
from bs4 import BeautifulSoup

def scrape_chapter_images(chapter_url, output_dir="raw_pages"):
    os.makedirs(output_dir, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": chapter_url
    }
    
    print(f"Fetching chapter page: {chapter_url}")
    resp = requests.get(chapter_url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Look for image tags
    img_urls = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src:
            src = src.strip()
        if src and re.search(r'\.(jpg|jpeg|png|webp)', src, re.I):
            # Filter out icons, logos, avatars
            if any(x in src.lower() for x in ["icon", "logo", "favicon", "avatar", "banner"]):
                continue
            if src not in img_urls:
                img_urls.append(src)
                
    print(f"Found {len(img_urls)} potential page images.")
    return img_urls

if __name__ == "__main__":
    urls = scrape_chapter_images("https://ww12.tokyoghoulre.com/chapter/tokyo-ghoul-chapter-001/")
    print(f"First 5 images:")
    for u in urls[:5]:
        print(" ", u)
