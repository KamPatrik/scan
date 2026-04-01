"""
Image preview widget with zoom, pan, and histogram display.
Provides real-time preview of scan results and processing adjustments.
"""

import logging
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageQt

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QRubberBand, QToolBar, QStatusBar,
)
from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QSize, pyqtSignal, QTimer,
)
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QColor, QBrush,
    QWheelEvent, QMouseEvent, QAction, QIcon,
    QTransform, QLinearGradient, QPainterPath,
)

from . import theme as T

logger = logging.getLogger(__name__)


class HistogramWidget(QWidget):
    """
    Displays RGB + Luminance histogram overlay with gradient fills and grid.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setMaximumHeight(160)
        self._hist_data = None
        self._show_red = True
        self._show_green = True
        self._show_blue = True
        self._show_luminance = True
        self.setStyleSheet(f"""
            HistogramWidget {{
                background-color: {T.BG_BASE};
                border-top: 1px solid {T.BORDER};
            }}
        """)

    def set_histogram(self, hist_data: dict):
        """Set histogram data dict with 'red', 'green', 'blue', 'luminance' arrays."""
        self._hist_data = hist_data
        self.update()

    def clear(self):
        self._hist_data = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_x = 4
        margin_top = 4
        margin_bottom = 6

        # Draw background
        painter.fillRect(0, 0, w, h, QColor(T.BG_BASE))

        draw_w = w - 2 * margin_x
        draw_h = h - margin_top - margin_bottom

        # Draw subtle grid lines
        grid_pen = QPen(QColor(255, 255, 255, 15))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = margin_top + int(draw_h * i / 4)
            painter.drawLine(margin_x, y, w - margin_x, y)
        for i in range(1, 4):
            x = margin_x + int(draw_w * i / 4)
            painter.drawLine(x, margin_top, x, h - margin_bottom)

        if not self._hist_data:
            # Draw placeholder text
            painter.setPen(QColor(T.FG_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No histogram data")
            painter.end()
            return

        # Find global max for scaling
        all_max = 1
        for key in ["red", "green", "blue", "luminance"]:
            if key in self._hist_data and self._hist_data[key] is not None:
                m = np.max(self._hist_data[key])
                if m > all_max:
                    all_max = m

        channels = []
        if self._show_luminance and "luminance" in self._hist_data:
            channels.append(("luminance", QColor(200, 200, 200, 40), QColor(200, 200, 200, 90)))
        if self._show_red and "red" in self._hist_data:
            channels.append(("red", QColor(220, 60, 60, 30), QColor(220, 60, 60, 120)))
        if self._show_green and "green" in self._hist_data:
            channels.append(("green", QColor(60, 200, 60, 30), QColor(60, 200, 60, 120)))
        if self._show_blue and "blue" in self._hist_data:
            channels.append(("blue", QColor(60, 80, 220, 30), QColor(60, 80, 220, 120)))

        bin_width = draw_w / 256.0
        baseline_y = h - margin_bottom

        for key, fill_color, line_color in channels:
            data = self._hist_data[key]
            if data is None:
                continue

            normalized = data.astype(float) / all_max

            # Build filled path
            path = QPainterPath()
            path.moveTo(margin_x, baseline_y)
            for i in range(256):
                x = margin_x + i * bin_width
                bar_h = normalized[i] * draw_h
                path.lineTo(x, baseline_y - bar_h)
            path.lineTo(margin_x + 255 * bin_width, baseline_y)
            path.closeSubpath()

            # Gradient fill
            grad = QLinearGradient(0, margin_top, 0, baseline_y)
            grad.setColorAt(0, fill_color)
            grad.setColorAt(1, QColor(fill_color.red(), fill_color.green(), fill_color.blue(), 5))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

            # Draw top edge line
            edge_path = QPainterPath()
            edge_path.moveTo(margin_x, baseline_y)
            for i in range(256):
                x = margin_x + i * bin_width
                bar_h = normalized[i] * draw_h
                edge_path.lineTo(x, baseline_y - bar_h)

            pen = QPen(line_color)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(edge_path)

        painter.end()


class ScanPreviewView(QGraphicsView):
    """
    Zoomable, pannable preview of scanned images.
    Supports rubber-band crop selection and before/after split view.
    """

    crop_changed = pyqtSignal(float, float, float, float)  # left, top, right, bottom (normalized)
    pixel_info = pyqtSignal(int, int, int, int, int)  # x, y, r, g, b

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._before_pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._image: Optional[Image.Image] = None
        self._before_image: Optional[Image.Image] = None
        self._zoom_factor = 1.0
        self._min_zoom = 0.05
        self._max_zoom = 20.0
        self._panning = False
        self._pan_start = QPointF()
        self._crop_mode = False
        self._crop_rect = None  # Normalized (0-1)
        self._before_after_mode = False
        self._split_position = 0.5  # 0-1, position of split line
        self._dragging_split = False

        # Setup view
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor(T.BG_BASE)))
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_image(self, image: Optional[Image.Image]):
        """Display a PIL Image in the preview."""
        self._image = image
        self._scene.clear()
        self._pixmap_item = None

        if image is None:
            return

        # Before/after split view
        if self._before_after_mode and self._before_image:
            self._redraw_split_view()
            return

        # Convert PIL Image to QPixmap
        qimage = self._pil_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)

        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        # Draw crop overlay if active
        if self._crop_rect:
            self._draw_crop_overlay()

        # Fit in view on first load
        self.fit_in_view()

    def _pil_to_qimage(self, pil_image: Image.Image) -> QImage:
        """Convert PIL Image to QImage."""
        if pil_image.mode == "RGB":
            data = pil_image.tobytes("raw", "RGB")
            qimage = QImage(
                data, pil_image.width, pil_image.height,
                3 * pil_image.width, QImage.Format.Format_RGB888
            )
            return qimage.copy()  # Copy to own the data
        elif pil_image.mode == "L":
            data = pil_image.tobytes("raw", "L")
            qimage = QImage(
                data, pil_image.width, pil_image.height,
                pil_image.width, QImage.Format.Format_Grayscale8
            )
            return qimage.copy()
        elif pil_image.mode == "RGBA":
            data = pil_image.tobytes("raw", "RGBA")
            qimage = QImage(
                data, pil_image.width, pil_image.height,
                4 * pil_image.width, QImage.Format.Format_RGBA8888
            )
            return qimage.copy()
        else:
            # Fallback: convert to RGB
            rgb = pil_image.convert("RGB")
            return self._pil_to_qimage(rgb)

    def fit_in_view(self):
        """Fit the entire image in the view."""
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_factor = self.transform().m11()

    def zoom_actual(self):
        """Set zoom to 100% (1:1 pixel mapping)."""
        self.resetTransform()
        self._zoom_factor = 1.0

    def zoom_in(self):
        """Zoom in by 25%."""
        self._apply_zoom(1.25)

    def zoom_out(self):
        """Zoom out by 25%."""
        self._apply_zoom(0.8)

    def _apply_zoom(self, factor: float):
        new_zoom = self._zoom_factor * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self.scale(factor, factor)
            self._zoom_factor = new_zoom

    def get_zoom_percent(self) -> int:
        return int(self._zoom_factor * 100)

    def set_crop_mode(self, enabled: bool):
        self._crop_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_before_after_mode(self, enabled: bool, before_image: Optional[Image.Image] = None):
        """Toggle before/after split view."""
        self._before_after_mode = enabled
        self._before_image = before_image
        if self._image:
            self.set_image(self._image)  # Redraw

    def set_split_position(self, pos: float):
        """Set split line position (0-1)."""
        self._split_position = max(0.05, min(0.95, pos))
        if self._before_after_mode and self._image:
            self._redraw_split_view()

    def set_crop_rect(self, left: float, top: float,
                      right: float, bottom: float):
        """Set crop rectangle in normalized coordinates (0-1)."""
        self._crop_rect = (left, top, right, bottom)
        if self._image:
            self._draw_crop_overlay()

    def _redraw_split_view(self):
        """Draw the before/after split view."""
        if not self._image or not self._before_image:
            return

        w, h = self._image.size
        split_x = int(w * self._split_position)

        # Create composite: before on left, after on right
        composite = self._before_image.copy()
        after_crop = self._image.crop((split_x, 0, w, h))
        composite.paste(after_crop, (split_x, 0))

        qimage = self._pil_to_qimage(composite)
        pixmap = QPixmap.fromImage(qimage)

        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        # Draw split line
        pen = QPen(QColor(255, 255, 0, 200))
        pen.setWidth(2)
        self._scene.addLine(split_x, 0, split_x, h, pen)

        # Labels
        from PyQt6.QtGui import QFont as _QFont
        font = _QFont("Segoe UI", 10, _QFont.Weight.Bold)

        before_text = self._scene.addSimpleText("BEFORE", font)
        before_text.setBrush(QBrush(QColor(255, 255, 255, 180)))
        before_text.setPos(10, 10)

        after_text = self._scene.addSimpleText("AFTER", font)
        after_text.setBrush(QBrush(QColor(255, 255, 0, 200)))
        after_text.setPos(split_x + 10, 10)

    def _draw_crop_overlay(self):
        """Draw semi-transparent overlay outside crop area."""
        if not self._pixmap_item or not self._crop_rect:
            return

        bounds = self._pixmap_item.boundingRect()
        w = bounds.width()
        h = bounds.height()

        left, top, right, bottom = self._crop_rect
        crop_rect = QRectF(left * w, top * h,
                           (right - left) * w, (bottom - top) * h)

        # Draw darkened areas outside crop
        overlay_color = QColor(0, 0, 0, 128)
        pen = QPen(QColor(255, 255, 0, 200))
        pen.setWidth(2)

        # Top
        self._scene.addRect(0, 0, w, crop_rect.top(),
                            QPen(Qt.PenStyle.NoPen), QBrush(overlay_color))
        # Bottom
        self._scene.addRect(0, crop_rect.bottom(), w, h - crop_rect.bottom(),
                            QPen(Qt.PenStyle.NoPen), QBrush(overlay_color))
        # Left
        self._scene.addRect(0, crop_rect.top(), crop_rect.left(),
                            crop_rect.height(),
                            QPen(Qt.PenStyle.NoPen), QBrush(overlay_color))
        # Right
        self._scene.addRect(crop_rect.right(), crop_rect.top(),
                            w - crop_rect.right(), crop_rect.height(),
                            QPen(Qt.PenStyle.NoPen), QBrush(overlay_color))

        # Crop border
        self._scene.addRect(crop_rect, pen)

    # ── Mouse Events ────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        """Zoom with scroll wheel."""
        degrees = event.angleDelta().y() / 8
        steps = degrees / 15
        factor = 1.0 + steps * 0.1
        self._apply_zoom(factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.LeftButton:
            # Handle split view dragging
            if self._before_after_mode and self._image:
                scene_pos = self.mapToScene(event.pos())
                w = self._image.size[0]
                split_x = w * self._split_position
                if abs(scene_pos.x() - split_x) < 20:
                    self._dragging_split = True
                    return
            # Handle crop mode
            if self._crop_mode and self._image:
                scene_pos = self.mapToScene(event.pos())
                w, h = self._image.size
                self._crop_start = (
                    max(0, min(1, scene_pos.x() / w)),
                    max(0, min(1, scene_pos.y() / h)),
                )
                self._rubber_band = QRubberBand(
                    QRubberBand.Shape.Rectangle, self
                )
                self._rubber_band.setGeometry(
                    int(event.pos().x()), int(event.pos().y()), 0, 0
                )
                self._rubber_band.show()
                return
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
        elif self._dragging_split and self._image:
            scene_pos = self.mapToScene(event.pos())
            w = self._image.size[0]
            self._split_position = max(0.05, min(0.95, scene_pos.x() / w))
            self._redraw_split_view()
        elif self._crop_mode and hasattr(self, '_rubber_band') and self._rubber_band:
            from PyQt6.QtCore import QRect, QPoint
            origin = self.mapFromScene(self.mapToScene(event.pos()))
            # Update rubber band (visual only)
            pass
        else:
            # Report pixel info
            scene_pos = self.mapToScene(event.pos())
            if self._image:
                x, y = int(scene_pos.x()), int(scene_pos.y())
                if 0 <= x < self._image.width and 0 <= y < self._image.height:
                    pixel = self._image.getpixel((x, y))
                    if isinstance(pixel, tuple) and len(pixel) >= 3:
                        self.pixel_info.emit(x, y, pixel[0], pixel[1], pixel[2])
                    elif isinstance(pixel, int):
                        self.pixel_info.emit(x, y, pixel, pixel, pixel)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._dragging_split:
            self._dragging_split = False
        elif self._crop_mode and hasattr(self, '_rubber_band') and self._rubber_band:
            # Finalize crop selection
            scene_pos = self.mapToScene(event.pos())
            if self._image and hasattr(self, '_crop_start'):
                w, h = self._image.size
                end_x = max(0, min(1, scene_pos.x() / w))
                end_y = max(0, min(1, scene_pos.y() / h))
                sx, sy = self._crop_start
                left = min(sx, end_x)
                top = min(sy, end_y)
                right = max(sx, end_x)
                bottom = max(sy, end_y)
                if right - left > 0.01 and bottom - top > 0.01:
                    self._crop_rect = (left, top, right, bottom)
                    self.crop_changed.emit(left, top, right, bottom)
                    self.set_image(self._image)  # Redraw with crop overlay
            self._rubber_band.hide()
            self._rubber_band = None
        else:
            super().mouseReleaseEvent(event)


class PreviewPanel(QWidget):
    """
    Complete preview panel with image view, histogram, and info bar.
    """

    crop_changed = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._image: Optional[Image.Image] = None
        self._before_image: Optional[Image.Image] = None  # For before/after

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        toolbar.setStyleSheet(T.toolbar_style())

        self._act_fit = QAction(f"{T.ICON_FIT} Fit", self)
        self._act_fit.setToolTip("Fit image in view")
        self._act_fit.triggered.connect(self._on_fit)
        toolbar.addAction(self._act_fit)

        self._act_100 = QAction("1:1", self)
        self._act_100.setToolTip("Zoom to 100%")
        self._act_100.triggered.connect(self._on_zoom_100)
        toolbar.addAction(self._act_100)

        self._act_zoom_in = QAction(T.ICON_ZOOM_IN, self)
        self._act_zoom_in.setToolTip("Zoom In")
        self._act_zoom_in.triggered.connect(self._on_zoom_in)
        toolbar.addAction(self._act_zoom_in)

        self._act_zoom_out = QAction(T.ICON_ZOOM_OUT, self)
        self._act_zoom_out.setToolTip("Zoom Out")
        self._act_zoom_out.triggered.connect(self._on_zoom_out)
        toolbar.addAction(self._act_zoom_out)

        toolbar.addSeparator()

        self._zoom_label = QLabel("  100%  ")
        self._zoom_label.setStyleSheet(T.label_style_secondary())
        toolbar.addWidget(self._zoom_label)

        toolbar.addSeparator()

        self._info_label = QLabel("")
        self._info_label.setStyleSheet(T.label_style_secondary())
        toolbar.addWidget(self._info_label)

        toolbar.addSeparator()

        # Before/After toggle
        self._act_before_after = QAction(f"{T.ICON_COMPARE} B/A", self)
        self._act_before_after.setToolTip("Toggle Before/After split view")
        self._act_before_after.setCheckable(True)
        self._act_before_after.toggled.connect(self._on_toggle_before_after)
        toolbar.addAction(self._act_before_after)

        # Crop mode toggle
        self._act_crop = QAction(f"{T.ICON_CROP} Crop", self)
        self._act_crop.setToolTip("Draw crop selection on preview")
        self._act_crop.setCheckable(True)
        self._act_crop.toggled.connect(self._on_toggle_crop)
        toolbar.addAction(self._act_crop)

        layout.addWidget(toolbar)

        # Preview view
        self._view = ScanPreviewView(self)
        self._view.pixel_info.connect(self._on_pixel_info)
        layout.addWidget(self._view, 1)

        # Histogram
        self._histogram = HistogramWidget(self)
        layout.addWidget(self._histogram)

        # Pixel info bar
        self._pixel_label = QLabel(f"  {T.ICON_DOT}  Ready")
        self._pixel_label.setStyleSheet(T.pixel_label_style())
        self._pixel_label.setFixedHeight(24)
        layout.addWidget(self._pixel_label)

    def set_image(self, image: Optional[Image.Image]):
        """Set the preview image."""
        self._image = image
        self._view.set_image(image)
        self._update_info()

        if image:
            from .image_processor import ImageProcessor
            hist = ImageProcessor.get_histogram(image)
            self._histogram.set_histogram(hist)
        else:
            self._histogram.clear()

    def get_image(self) -> Optional[Image.Image]:
        return self._image

    def update_histogram(self, image: Image.Image):
        """Update just the histogram display."""
        from .image_processor import ImageProcessor
        hist = ImageProcessor.get_histogram(image)
        self._histogram.set_histogram(hist)

    def _update_info(self):
        if self._image:
            w, h = self._image.size
            mode = self._image.mode
            self._info_label.setText(
                f"  {w} × {h}  |  {mode}  |  "
                f"{self._view.get_zoom_percent()}%"
            )
        else:
            self._info_label.setText("  No image")

    def _on_fit(self):
        self._view.fit_in_view()
        self._update_info()

    def _on_zoom_100(self):
        self._view.zoom_actual()
        self._update_info()

    def _on_zoom_in(self):
        self._view.zoom_in()
        self._update_info()

    def _on_zoom_out(self):
        self._view.zoom_out()
        self._update_info()

    def _on_pixel_info(self, x: int, y: int, r: int, g: int, b: int):
        self._pixel_label.setText(
            f"  X: {x}  Y: {y}  |  R: {r}  G: {g}  B: {b}  |  "
            f"#{r:02x}{g:02x}{b:02x}"
        )

    def _on_toggle_before_after(self, checked: bool):
        """Toggle the before/after split comparison view."""
        if checked and self._before_image:
            self._view.set_before_after_mode(True, self._before_image)
        else:
            self._view.set_before_after_mode(False)
            if self._image:
                self._view.set_image(self._image)

    def _on_toggle_crop(self, checked: bool):
        """Toggle crop selection mode."""
        self._view.set_crop_mode(checked)

    def set_before_image(self, image: Optional[Image.Image]):
        """Set the 'before' image for comparison view."""
        self._before_image = image

    def get_view(self) -> ScanPreviewView:
        """Access the underlying view for direct manipulation."""
        return self._view
