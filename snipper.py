# -*- coding: utf-8 -*-
"""
高帧率无卡顿屏幕框选截图组件 (Snipping Tool)
核心机制：
1. 启动时一次性预渲染整屏暗色底图 (dimmed_pixmap)，拖拽选框时 0 开销纯内存 Blit，杜绝数百万像素实时 Alpha 计算卡顿！
2. 完美适配 2.5K/4K 等高分屏缩放 (DPI 125%/150%)，物理/逻辑坐标精准对齐，彻底修复选区画面偏移走形问题。
3. 状态防护：截图窗口激活期间严格互斥，杜绝重复触发与多重遮罩。
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
        # 抓取原始全屏物理位图 (例如 2560x1600)
        self.screen_pixmap = screen.grabWindow(0)

        # 启动时仅合成一次全屏暗色底图，避免拖拽选框时每帧 CPU Alpha 混合计算
        self.dimmed_pixmap = QPixmap(self.screen_pixmap.size())
        dp_painter = QPainter(self.dimmed_pixmap)
        dp_painter.drawPixmap(0, 0, self.screen_pixmap)
        dp_painter.fillRect(self.dimmed_pixmap.rect(), QColor(0, 0, 0, 115))
        dp_painter.end()

        self.is_snipping = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        
        # 唤醒遮罩
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
        
        # 1. 将预先生成的暗色底图快速铺满当前逻辑全屏
        painter.drawPixmap(self.rect(), self.dimmed_pixmap)

        if self.is_snipping:
            rect = self.get_selection_rect()
            if not rect.isEmpty() and rect.width() > 1 and rect.height() > 1:
                # 2. 精准高分屏物理坐标换算：
                # 目标区域 rect 为逻辑坐标，源区域 src_rect 必须按 DPR 放大换算为物理底图坐标！
                dpr = self.dpr or 1.0
                src_rect = QRect(
                    int(round(rect.x() * dpr)),
                    int(round(rect.y() * dpr)),
                    int(round(rect.width() * dpr)),
                    int(round(rect.height() * dpr))
                )
                # 1:1 像素绝对对齐掏空高亮
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
