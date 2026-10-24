import cv2
import numpy as np
import os
from typing import List, Tuple, Dict, Any

class MangaPanelExtractor:
    def __init__(
        self,
        reading_order: str = "rtl",  # "rtl" (Japanese manga) or "ltr" (Western/Manhwa)
        white_thresh: int = 235,
        gutter_ratio: float = 0.93,
        min_gutter_px: int = 5,
        min_tier_height: int = 140,
        min_panel_width: int = 110,
        target_phone_width: int = 800
    ):
        self.reading_order = reading_order.lower()
        self.white_thresh = white_thresh
        self.gutter_ratio = gutter_ratio
        self.min_gutter_px = min_gutter_px
        self.min_tier_height = min_tier_height
        self.min_panel_width = min_panel_width
        self.target_phone_width = target_phone_width

    def _trim_content_bounds(self, img: np.ndarray, gray: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Trims outer margins from page."""
        h, w = gray.shape[:2]
        is_white = (gray >= self.white_thresh).astype(np.uint8)
        row_content = np.any(is_white == 0, axis=1)
        col_content = np.any(is_white == 0, axis=0)
        
        if not np.any(row_content) or not np.any(col_content):
            return img, gray
            
        r_idx = np.where(row_content)[0]
        c_idx = np.where(col_content)[0]
        
        y_min, y_max = max(0, r_idx[0] - 2), min(h, r_idx[-1] + 3)
        x_min, x_max = max(0, c_idx[0] - 2), min(w, c_idx[-1] + 3)
        
        return img[y_min:y_max, x_min:x_max], gray[y_min:y_max, x_min:x_max]

    def _find_gutters(self, mask: np.ndarray, axis: int, min_thickness: int = 5, thresh_ratio: float = 0.93) -> List[Tuple[int, int]]:
        """Finds contiguous gutter bands along horizontal (axis=0) or vertical (axis=1)."""
        ratios = np.mean(mask, axis=1 if axis == 0 else 0)
        is_gutter = ratios >= thresh_ratio
        
        gutters = []
        in_g = False
        start = 0
        for i, val in enumerate(is_gutter):
            if val and not in_g:
                in_g = True
                start = i
            elif not val and in_g:
                in_g = False
                if (i - start) >= min_thickness:
                    gutters.append((start, i - 1))
        if in_g and (len(is_gutter) - start) >= min_thickness:
            gutters.append((start, len(is_gutter) - 1))
            
        length = mask.shape[0] if axis == 0 else mask.shape[1]
        valid = [g for g in gutters if g[0] > 35 and g[1] < length - 35]
        return valid

    def extract_panels_from_image(self, img_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extracts distinctive frames from manga page.
        Returns:
            panels: list of dicts with extracted panel images and metadata
            hint: dict with confidence, fallback status, and hints for LLM/user
        """
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {img_path}")
            
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bname = os.path.basename(img_path)
        
        # 1. Check for 2-page spread (w / h > 1.25)
        if (w / float(h)) > 1.25:
            half_w = w // 2
            if self.reading_order == "rtl":
                pages = [img[:, half_w:], img[:, :half_w]]
            else:
                pages = [img[:, :half_w], img[:, half_w:]]
                
            spread_panels = []
            for sub_img in pages:
                sub_h, sub_w = sub_img.shape[:2]
                aspect = sub_w / float(sub_h)
                spread_panels.append({
                    "type": "spread",
                    "image": sub_img,
                    "aspect": aspect,
                    "is_wide": aspect > 1.4
                })
            hint = {
                "page": bname,
                "status": "trivial",
                "is_fallback": False,
                "reason": "2-page spread detected (w/h > 1.25); split into two pages in reading order.",
                "confidence": "high"
            }
            return spread_panels, hint

        # 2. Check for solid/blank page (like pure black scene transitions)
        is_all_white = np.mean(gray >= self.white_thresh) > 0.99
        is_all_dark = np.mean(gray <= 20) > 0.95
        if is_all_white or is_all_dark:
            hint = {
                "page": bname,
                "status": "fallback",
                "is_fallback": True,
                "reason": "Solid dark/blank scene transition page; kept as full_page.",
                "confidence": "high"
            }
            return [{
                "type": "full_page",
                "image": img,
                "aspect": w / float(h),
                "is_wide": False
            }], hint

        # 3. Trim page margins
        content_img, content_gray = self._trim_content_bounds(img, gray)
        ch, cw = content_gray.shape[:2]
        
        # 4. Look for horizontal gutters across content
        white_mask = (content_gray >= self.white_thresh).astype(np.float32)
        overall_white = np.mean(white_mask)
        valid_h_gutters = self._find_gutters(white_mask, axis=0, min_thickness=self.min_gutter_px, thresh_ratio=self.gutter_ratio)
        
        # Check if page is overwhelmingly white or has too many text gutters (TOC/credits)
        if overall_white > 0.80 or len(valid_h_gutters) > 5:
            aspect = cw / float(ch)
            hint = {
                "page": bname,
                "status": "fallback",
                "is_fallback": True,
                "reason": f"Table of Contents / text list detected (white ratio={overall_white:.2f}, gutters={len(valid_h_gutters)}); kept as full_page.",
                "confidence": "high"
            }
            return [{
                "type": "full_page",
                "image": content_img,
                "aspect": aspect,
                "is_wide": aspect > 1.4
            }], hint
        
        # Split into horizontal tiers
        tier_slices = []
        curr_y = 0
        for (g_start, g_end) in valid_h_gutters:
            if g_start - curr_y >= self.min_tier_height:
                tier_slices.append((curr_y, g_start))
                curr_y = g_end + 1
        if ch - curr_y >= self.min_tier_height:
            tier_slices.append((curr_y, ch))
            
        # If no valid tiers or only 1 tier: Full-page splash/illustration!
        if len(tier_slices) < 2:
            aspect = cw / float(ch)
            hint = {
                "page": bname,
                "status": "fallback",
                "is_fallback": True,
                "reason": "No horizontal gutters found; page is a single full-page illustration or splash cover.",
                "confidence": "high"
            }
            return [{
                "type": "full_page",
                "image": content_img,
                "aspect": aspect,
                "is_wide": aspect > 1.4
            }], hint
            
        # 5. Process each tier
        panels = []
        has_invalid_sliver = False
        merged_tiers_count = 0
        
        for (ty1, ty2) in tier_slices:
            tier_img = content_img[ty1:ty2, :]
            tier_gray = content_gray[ty1:ty2, :]
            th, tw = tier_gray.shape[:2]
            
            tier_mask = (tier_gray >= self.white_thresh).astype(np.float32)
            valid_v_gutters = self._find_gutters(tier_mask, axis=1, min_thickness=self.min_gutter_px, thresh_ratio=self.gutter_ratio)
            
            # If no vertical gutters: this tier is a wide horizontal frame!
            if not valid_v_gutters:
                aspect = tw / float(th)
                panels.append({
                    "type": "horizontal_frame",
                    "image": tier_img,
                    "aspect": aspect,
                    "is_wide": True
                })
                merged_tiers_count += 1
                continue
                
            # If there are vertical gutters, split tier into columns
            col_slices = []
            curr_x = 0
            for (vgs, vge) in valid_v_gutters:
                if vgs - curr_x >= self.min_panel_width:
                    col_slices.append((curr_x, vgs))
                    curr_x = vge + 1
            if tw - curr_x >= self.min_panel_width:
                col_slices.append((curr_x, tw))
                
            # Check for thin slivers (false cuts)
            for (cx1, cx2) in col_slices:
                if (cx2 - cx1) < self.min_panel_width:
                    has_invalid_sliver = True
                    break
                    
            # Japanese manga order: Right-to-Left within tier
            if self.reading_order == "rtl":
                col_slices = list(reversed(col_slices))
                
            for (cx1, cx2) in col_slices:
                crop = tier_img[:, cx1:cx2]
                pw = cx2 - cx1
                aspect = pw / float(th)
                ptype = "wide_frame" if aspect > 1.4 else "standard_frame"
                panels.append({
                    "type": ptype,
                    "image": crop,
                    "aspect": aspect,
                    "is_wide": aspect > 1.4
                })
                
        # If any tier produced invalid slivers, fall back to full page
        if has_invalid_sliver:
            aspect = cw / float(ch)
            hint = {
                "page": bname,
                "status": "fallback",
                "is_fallback": True,
                "reason": "Unusual narrow slivers detected (< 110px). Fell back to full_page to avoid cutting artwork.",
                "confidence": "medium"
            }
            return [{
                "type": "full_page",
                "image": content_img,
                "aspect": aspect,
                "is_wide": aspect > 1.4
            }], hint
            
        # Clean successful multi-panel extraction
        hint = {
            "page": bname,
            "status": "trivial",
            "is_fallback": False,
            "reason": f"Clean extraction: {len(tier_slices)} tiers, {len(panels)} panels (wide frames: {merged_tiers_count}).",
            "confidence": "high"
        }
        return panels, hint
