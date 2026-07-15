"""Page geometry and the single px<->mm transform.

Everything downstream works in page millimeters, y-down (same as SVG).
The only place image pixels are converted to mm is Page.px_to_mm /
Page.mm_to_px. Nothing else may do coordinate math between the two spaces.
"""

from dataclasses import dataclass

import numpy as np

PAGE_SIZES_MM = {
    "letter": (215.9, 279.4),
    "letter-landscape": (279.4, 215.9),
    "a4": (210.0, 297.0),
    "a3": (297.0, 420.0),
    "11x17": (279.4, 431.8),
    "11x17-landscape": (431.8, 279.4),
}


@dataclass(frozen=True)
class Page:
    width_mm: float
    height_mm: float
    margin_mm: float
    # scale/offset mapping working-image pixels -> page mm (image centered
    # in the drawable area, aspect preserved)
    mm_per_px: float = 1.0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0

    @property
    def drawable_mm(self) -> tuple[float, float]:
        return (self.width_mm - 2 * self.margin_mm,
                self.height_mm - 2 * self.margin_mm)

    @staticmethod
    def fit_image(size_name: str, margin_mm: float,
                  img_w_px: int, img_h_px: int) -> "Page":
        w_mm, h_mm = PAGE_SIZES_MM[size_name]
        dw, dh = w_mm - 2 * margin_mm, h_mm - 2 * margin_mm
        s = min(dw / img_w_px, dh / img_h_px)  # mm per px
        ox = margin_mm + (dw - img_w_px * s) / 2
        oy = margin_mm + (dh - img_h_px * s) / 2
        return Page(w_mm, h_mm, margin_mm, s, ox, oy)

    def px_to_mm(self, pts_px: np.ndarray) -> np.ndarray:
        """(N,2) pixel coords -> (N,2) page mm."""
        return pts_px * self.mm_per_px + np.array(
            [self.offset_x_mm, self.offset_y_mm])

    def mm_to_px(self, pts_mm: np.ndarray) -> np.ndarray:
        return (pts_mm - np.array(
            [self.offset_x_mm, self.offset_y_mm])) / self.mm_per_px
