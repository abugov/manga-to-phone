import cv2
import numpy as np
import os
from typing import List, Tuple

class MangaPanelExtractor:
    def __init__(
        self,
        reading_order: str = "rtl",  # "rtl" (Japanese manga) or "ltr" (Western/Manhwa)
        white_thresh: int = 240,
        gutter_ratio: float = 0.93,
        min_gutter_px: int = 4,
        min_panel_area_pct: float = 0.02,
        target_phone_width: int = 800,
        margin_padding: int = 4
    ):
        self.reading_order = reading_order.lower()
        self.white_thresh = white_thresh
        self.gutter_ratio = gutter_ratio
        self.min_gutter_px = min_gutter_px
        self.min_panel_area_pct = min_panel_area_pct
        self.target_phone_width = target_phone_width
        self.margin_padding = margin_padding

    def trim_margins(self, gray: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """Trims excess white background margin around a detected panel."""
        x, y, w, h = bbox
        sub = gray[y:y+h, x:x+w]
        is_content = (sub < self.white_thresh).astype(np.uint8)
        
        row_content = np.any(is_content, axis=1)
        col_content = np.any(is_content, axis=0)
        
        if not np.any(row_content) or not np.any(col_content):
            return bbox
            
        r_indices = np.where(row_content)[0]
        c_indices = np.where(col_content)[0]
        
        # Add padding safely
        p = self.margin_padding
        new_y = max(int(y + r_indices[0] - p), 0)
        new_y2 = min(int(y + r_indices[-1] + 1 + p), gray.shape[0])
        new_x = max(int(x + c_indices[0] - p), 0)
        new_x2 = min(int(x + c_indices[-1] + 1 + p), gray.shape[1])
        
        return (new_x, new_y, new_x2 - new_x, new_y2 - new_y)

    def find_gutters(self, mask: np.ndarray, axis: int, min_thickness: int = 4, thresh_ratio: float = 0.93) -> List[Tuple[int, int]]:
        """
        axis=0: Horizontal gutters (rows)
        axis=1: Vertical gutters (columns)
        """
        ratios = np.mean(mask, axis=1 if axis == 0 else 0)
        is_gutter = ratios >= thresh_ratio
        
        gutters = []
        in_gutter = False
        start = 0
        
        for i, val in enumerate(is_gutter):
            if val and not in_gutter:
                in_gutter = True
                start = i
            elif not val and in_gutter:
                in_gutter = False
                if (i - start) >= min_thickness:
                    gutters.append((start, i - 1))
        if in_gutter and (len(is_gutter) - start) >= min_thickness:
            gutters.append((start, len(is_gutter) - 1))
            
        length = mask.shape[0] if axis == 0 else mask.shape[1]
        valid_gutters = []
        for g_start, g_end in gutters:
            # Exclude outer edge gutters (outer page margin)
            if g_start > 12 and g_end < length - 13:
                valid_gutters.append((g_start, g_end))
                
        return valid_gutters

    def recursive_xy_cut(self, gray: np.ndarray, bbox: Tuple[int, int, int, int], depth: int = 0) -> List[Tuple[int, int, int, int]]:
        x, y, w, h = bbox
        if w < 50 or h < 50 or depth > 8:
            return [bbox]
            
        sub = gray[y:y+h, x:x+w]
        mask = (sub >= self.white_thresh).astype(np.float32)
        
        # 1. Try Horizontal cut first (comics are primarily stacked in horizontal tiers)
        h_gutters = self.find_gutters(mask, axis=0, min_thickness=self.min_gutter_px, thresh_ratio=self.gutter_ratio)
        
        if h_gutters:
            slices = []
            curr_y = 0
            for g_start, g_end in h_gutters:
                # Discard thin horizontal slivers
                if g_start - curr_y >= 70:
                    slices.append((x, y + curr_y, w, g_start - curr_y))
                curr_y = g_end + 1
            if h - curr_y >= 70:
                slices.append((x, y + curr_y, w, h - curr_y))
                
            # If the cut produced valid sub-slices
            if len(slices) > 1:
                panels = []
                for s in slices:
                    panels.extend(self.recursive_xy_cut(gray, s, depth + 1))
                return panels
            
        # 2. Try Vertical cut if no horizontal cut found
        v_gutters = self.find_gutters(mask, axis=1, min_thickness=self.min_gutter_px, thresh_ratio=self.gutter_ratio)
        
        if v_gutters:
            slices = []
            curr_x = 0
            for g_start, g_end in v_gutters:
                # Discard thin vertical slivers (e.g. text margins)
                if g_start - curr_x >= 70:
                    slices.append((x + curr_x, y, g_start - curr_x, h))
                curr_x = g_end + 1
            if w - curr_x >= 70:
                slices.append((x + curr_x, y, w - curr_x, h))
                
            if len(slices) > 1:
                # Japanese manga order: Right to Left!
                # Western/Manhwa order: Left to Right!
                if self.reading_order == "rtl":
                    slices = list(reversed(slices))
                    
                panels = []
                for s in slices:
                    panels.extend(self.recursive_xy_cut(gray, s, depth + 1))
                return panels
            
        # Leaf node: Cannot be split further
        trimmed = self.trim_margins(gray, bbox)
        return [trimmed]

    def is_splash_or_title(self, raw_boxes: List[Tuple[int, int, int, int]], page_w: int, page_h: int) -> bool:
        """Determines if a page is a single splash/cover page rather than a multi-panel grid."""
        if len(raw_boxes) <= 1:
            return True
        # If any box has extreme sliver aspect ratio (e.g. width < 35% and height > 70%),
        # it was falsely cut by background whitespace in splash art.
        sliver_count = 0
        for (_, _, pw, ph) in raw_boxes:
            aspect = float(pw) / float(max(ph, 1))
            if (aspect < 0.35 and ph > 0.7 * page_h) or (aspect > 5.0 and pw > 0.7 * page_w):
                sliver_count += 1
        if sliver_count >= 1 and len(raw_boxes) <= 3:
            return True
        return False

    def extract_panels_from_image(self, img_path: str) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]]]:
        """
        Loads an image, handles 2-page spreads or single splash pages,
        and extracts the cropped panels in reading order.
        """
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {img_path}")
            
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Check for 2-page spread (w/h > 1.25)
        aspect = float(w) / float(h)
        if aspect > 1.25:
            # Check if this 2-page spread has panels or is a single large panoramic splash art
            init_box = self.trim_margins(gray, (0, 0, w, h))
            raw = self.recursive_xy_cut(gray, init_box)
            if self.is_splash_or_title(raw, w, h):
                # Panoramic splash: keep as one or split into right then left page
                half_w = w // 2
                if self.reading_order == "rtl":
                    return [img[:, half_w:], img[:, :half_w]], [(half_w, 0, half_w, h), (0, 0, half_w, h)]
                else:
                    return [img[:, :half_w], img[:, half_w:]], [(0, 0, half_w, h), (half_w, 0, half_w, h)]
                    
            # Has internal panels on the spread:
            half_w = w // 2
            pages = [img[:, half_w:], img[:, :half_w]] if self.reading_order == "rtl" else [img[:, :half_w], img[:, half_w:]]
            all_panels = []
            all_bboxes = []
            for sub_img in pages:
                sub_gray = cv2.cvtColor(sub_img, cv2.COLOR_BGR2GRAY)
                sub_init = self.trim_margins(sub_gray, (0, 0, sub_img.shape[1], sub_img.shape[0]))
                sub_raw = self.recursive_xy_cut(sub_gray, sub_init)
                for (px, py, pw, ph) in sub_raw:
                    if pw * ph >= (sub_img.shape[0] * sub_img.shape[1]) * self.min_panel_area_pct:
                        all_panels.append(sub_img[py:py+ph, px:px+pw])
                        all_bboxes.append((px, py, pw, ph))
            return all_panels, all_bboxes
            
        # Single page:
        init_box = self.trim_margins(gray, (0, 0, w, h))
        raw_boxes = self.recursive_xy_cut(gray, init_box)
        
        # Check if splash/title page:
        if self.is_splash_or_title(raw_boxes, w, h):
            tx, ty, tw, th = init_box
            return [img[ty:ty+th, tx:tx+tw]], [init_box]
            
        total_area = float(w * h)
        panel_images = []
        valid_boxes = []
        
        for (px, py, pw, ph) in raw_boxes:
            if pw * ph >= total_area * self.min_panel_area_pct:
                crop = img[py:py+ph, px:px+pw]
                panel_images.append(crop)
                valid_boxes.append((px, py, pw, ph))
                
        if not panel_images:
            tx, ty, tw, th = init_box
            panel_images.append(img[ty:ty+th, tx:tx+tw])
            valid_boxes.append(init_box)
            
        return panel_images, valid_boxes
