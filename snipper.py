# -*- coding: utf-8 -*-
"""
高帧率无卡顿屏幕框选截图组件 (Snipping Tool)
解决高分屏 (2.5K/4K, 125%/150% DPI 缩放) 下：
1. 彻底解决画面缩小、右侧与下侧黑边问题 (通过 copy 继承 DPR 并在 p.window 完整覆盖遮罩)；
2. 彻底解决框选内容放大错位问题 (物理源坐标 src_rect 精准 1:1 对齐)；
3. 保持 120 帧极致流畅，0 实时 Alpha 计算开销。
"""
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication, QPixmap
from PyQt6.QtWidgets import QWidget

class SnippingWidget(QWidget):
    snipped = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_snipping = False
        self.screen_pixmap = None
        self.dimmed_pixmap = None
        self.dpr = 1.0

    def start_snip(self):
        """抓取当前屏幕并启动全屏遮罩"""
        if self.isVisible():
            return

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        self.dpr = screen.devicePixelRatio() or 1.0
        # 1. 抓取物理全屏底图 (例如 2560x1600，Qt 已自带设置其 devicePixelRatio 为 1.5)
        self.screen_pixmap = screen.grabWindow(0)

        # 2. 核心修复：直接使用 copy() 完整保留物理分辨率与 DevicePixelRatio！
        # 杜绝新建空白 QPixmap 导致 DPR 降回 1.0 引起的画面缩水和黑边灾难
        self.dimmed_pixmap = self.screen_pixmap.copy()

        # 3. 针对全屏物理区域 p.window() 统一填充暗色半透明，整屏无任何死角与黑边
        dp_painter = QPainter(self.dimmed_pixmap)
        dp_painter.fillRect(dp_painter.window(), QColor(0, 0, 0, 115))
        dp_painter.end()

        self.is_snipping = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        
        self.setGeometry(screen.geometry())
        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_snipping = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_snipping:
            cur_pos = event.pos()
            if cur_pos != self.end_point:
                self.end_point = cur_pos
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_snipping:
            self.is_snipping = False
            rect = self.get_selection_rect()
            self.hide()
            
            # 过滤过小的无效点击
            if rect.width() > 10 and rect.height() > 10 and self.screen_pixmap:
                dpr = self.dpr or 1.0
                src_rect = QRect(
                    int(round(rect.x() * dpr)),
                    int(round(rect.y() * dpr)),
                    int(round(rect.width() * dpr)),
                    int(round(rect.height() * dpr))
                )
                cropped = self.screen_pixmap.copy(src_rect)
                self.snipped.emit(cropped)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.is_snipping = False
            self.hide()
        else:
            super().keyPressEvent(event)

    def get_selection_rect(self):
        top_left = QPoint(
            min(self.start_point.x(), self.end_point.x()),
            min(self.start_point.y(), self.end_point.y())
        )
        bottom_right = QPoint(
            max(self.start_point.x(), self.end_point.x()),
            max(self.start_point.y(), self.end_point.y())
        )
        return QRect(top_left, bottom_right)

    def paintEvent(self, event):
        if not self.screen_pixmap or not self.dimmed_pixmap:
            return

        painter = QPainter(self)
        
        # 1. 绘制暗色底图：(0, 0) 直绘，Qt 自动根据其自带 DPR 1:1 映射铺满全屏，画面不缩小、无黑边
        painter.drawPixmap(0, 0, self.dimmed_pixmap)

        if self.is_snipping:
            rect = self.get_selection_rect()
            if not rect.isEmpty() and rect.width() > 1 and rect.height() > 1:
                # 2. 选区从原始底图中精准采样：源区域换算为物理坐标
                dpr = self.dpr or 1.0
                src_rect = QRect(
                    int(round(rect.x() * dpr)),
                    int(round(rect.y() * dpr)),
                    int(round(rect.width() * dpr)),
                    int(round(rect.height() * dpr))
                )
                # 1:1 严丝合缝高亮呈现，绝不放大或位移
                painter.drawPixmap(rect, self.screen_pixmap, src_rect)

                # 3. 选框高亮边框
                pen = QPen(QColor(0, 229, 255), 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawRect(rect)

                # 4. 尺寸信息提示
                info_text = f"{rect.width()} × {rect.height()} px (松开鼠标开始识别，Esc取消)"
                painter.setFont(QFont("Microsoft YaHei", 9))
                painter.setPen(QColor(255, 255, 255))
                tip_y = max(0, rect.top() - 25)
                painter.fillRect(rect.left(), tip_y, 270, 22, QColor(20, 20, 20, 220))
                painter.drawText(rect.left() + 6, tip_y + 16, info_text)
        else:
            # 初始居中提示
            painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            painter.setPen(QColor(255, 255, 255, 230))
            hint = "按住鼠标左键拖动框选游戏区域，按 ESC 退出"
            text_rect = painter.fontMetrics().boundingRect(hint)
            cx = (self.width() - text_rect.width()) // 2
            cy = 80
            painter.fillRect(cx - 15, cy - 25, text_rect.width() + 30, 36, QColor(0, 0, 0, 190))
            painter.drawText(cx, cy, hint)
