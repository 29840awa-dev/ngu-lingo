# -*- coding: utf-8 -*-
"""
屏幕框选截图组件 (Snipping Tool)
适配 Windows 高分屏缩放 (DPI Scaling / DevicePixelRatio 125%/150%)
解决框选错位、画面放大、黑屏或无响应的问题
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
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_snipping = False
        self.screen_pixmap = None
        self.dpr = 1.0

    def start_snip(self):
        """重新抓取当前屏幕并启动全屏遮罩"""
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.dpr = screen.devicePixelRatio()
            self.screen_pixmap = screen.grabWindow(0)
            self.setGeometry(screen.geometry())
        else:
            self.dpr = 1.0

        self.is_snipping = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        
        self.showFullScreen()
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
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_snipping:
            self.is_snipping = False
            rect = self.get_selection_rect()
            self.hide()
            
            # 过滤过小的无效点击
            if rect.width() > 10 and rect.height() > 10 and self.screen_pixmap:
                # 必须将逻辑坐标换算为高分屏物理像素坐标截取
                dpr = self.dpr or 1.0
                src_rect = QRect(
                    int(rect.x() * dpr),
                    int(rect.y() * dpr),
                    int(rect.width() * dpr),
                    int(rect.height() * dpr)
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
        if not self.screen_pixmap:
            return

        painter = QPainter(self)
        
        # 1. 将物理底图缩放绘制到逻辑全屏大小上，确保 1:1 对齐
        painter.drawPixmap(self.rect(), self.screen_pixmap)
        
        # 2. 绘制深色半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self.is_snipping:
            rect = self.get_selection_rect()
            if not rect.isEmpty():
                # 3. 换算物理像素切片，将选区真实高亮还原（修复150%缩放错位问题）
                dpr = self.dpr or 1.0
                src_rect = QRect(
                    int(rect.x() * dpr),
                    int(rect.y() * dpr),
                    int(rect.width() * dpr),
                    int(rect.height() * dpr)
                )
                painter.drawPixmap(rect, self.screen_pixmap, src_rect)

                # 4. 选框高亮边框
                pen = QPen(QColor(0, 229, 255), 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawRect(rect)

                # 5. 尺寸信息提示
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
