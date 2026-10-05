# -*- coding: utf-8 -*-
"""
NGU Lingo Companion - 主界面窗口
包含：按词点读气泡块 (Word Chips)、智能短语识别 (Phrase Detection)、
实时取词解析、生词本管理、挂机微测验、NGU 百科词典
"""
import io
import os
import re
import random
from PIL import Image

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QBuffer, QIODevice, QPoint, QRect, QSize, QEvent, QObject
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QTabWidget, QListWidget,
    QListWidgetItem, QFrame, QScrollArea, QMessageBox, QCheckBox,
    QFileDialog, QSplitter, QLayout, QSizePolicy
)
from audio_service import AudioService

from snipper import SnippingWidget
from ocr_engine import OCREngine, fix_jammed_words
from translator import TranslationService
from phrase_matcher import PhraseMatcher
from ngu_knowledge import NGU_GLOSSARY, detect_ngu_terms
import database

# 智能双模滚动区组件：
# 1. 当内部没有滚动条（内容未超出）时，鼠标在此区域滚动直接驱动最外层主页面滚动！
# 2. 当内部出现滚动条（内容超出）时，在此区域滚动只驱动内部滚动条，并防止外层大页面联动跳动！
class IsolatedScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.viewport() and event.type() == QEvent.Type.Wheel:
            sb = self.verticalScrollBar()
            if sb and sb.maximum() > 0:
                # 内部有滚动条：内部独立滚动，防止穿透
                delta = event.angleDelta().y()
                if delta != 0:
                    step = (delta // 15) * 22
                    sb.setValue(sb.value() - step)
                event.accept()
                return True
            else:
                # 内部没有滚动条：直接将滚轮事件传递给最外侧滚动条！
                p = self.parent()
                while p:
                    if isinstance(p, QScrollArea):
                        outer_sb = p.verticalScrollBar()
                        if outer_sb and outer_sb.maximum() > 0:
                            delta = event.angleDelta().y()
                            step = (delta // 15) * 25
                            outer_sb.setValue(outer_sb.value() - step)
                            event.accept()
                            return True
                    p = p.parent()
                return False
        return super().eventFilter(obj, event)

class IsolatedWheelFilter(QObject):
    def __init__(self, target_widget):
        super().__init__(target_widget)
        self.target = target_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            sb = self.target.verticalScrollBar()
            if sb and sb.maximum() > 0:
                delta = event.angleDelta().y()
                if delta != 0:
                    step = (delta // 15) * 20
                    sb.setValue(sb.value() - step)
                event.accept()
                return True
            else:
                # 无内层滚动条时，转发给外层主滚动条
                p = self.target.parent()
                while p:
                    if isinstance(p, QScrollArea):
                        outer_sb = p.verticalScrollBar()
                        if outer_sb and outer_sb.maximum() > 0:
                            delta = event.angleDelta().y()
                            step = (delta // 15) * 25
                            outer_sb.setValue(outer_sb.value() - step)
                            event.accept()
                            return True
                    p = p.parent()
                return False
        return super().eventFilter(obj, event)

# 自动折行的流式布局组件 (FlowLayout)
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.m_spacing = spacing

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.m_spacing

        for item in self.itemList:
            nextX = x + item.sizeHint().width() + spacing
            if nextX - spacing > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spacing
                nextX = x + item.sizeHint().width() + spacing
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()


# 后台 OCR 与翻译线程 (增加短语识别)
class ProcessWorker(QThread):
    # full_text, translation, ngu_matches, words_detail, phrases_detail
    finished = pyqtSignal(str, str, list, list, list)
    error = pyqtSignal(str)

    def __init__(self, pil_image, ocr_engine, trans_service, phrase_matcher):
        super().__init__()
        self.pil_image = pil_image
        self.ocr_engine = ocr_engine
        self.trans_service = trans_service
        self.phrase_matcher = phrase_matcher

    def run(self):
        try:
            full_text, lines = self.ocr_engine.recognize_image(self.pil_image)
            if not full_text:
                self.finished.emit("", "未检测到清晰英文字符，请重新框选", [], [], [])
                return

            # 整句翻译
            trans_result = self.trans_service.translate_sentence(full_text)
            
            # 检测 NGU 机制与梗
            ngu_matches = self.trans_service.analyze_ngu_context(full_text)

            # 智能短语与固定搭配检测
            phrases_detail = self.phrase_matcher.detect_phrases(full_text)
            
            # 单词拆解与释义（并发多线程）
            words = self.trans_service.extract_words(full_text)
            words_detail = self.trans_service.batch_get_word_details(words)

            self.finished.emit(full_text, trans_result, ngu_matches, words_detail, phrases_detail)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGU Lingo Companion - 放置游戏英语伴侣")
        self.setMinimumSize(390, 480)
        self.resize(440, 520)
        
        # 初始化服务
        self.ocr_engine = OCREngine()
        self.trans_service = TranslationService()
        self.phrase_matcher = PhraseMatcher()
        self.tts = AudioService(self)
        
        # 截图浮层
        self.snipper = SnippingWidget()
        self.snipper.snipped.connect(self.on_image_snipped)

        # 缓存当前取词数据
        self.current_sentence = ""
        self.current_words_detail = []
        self.current_phrases = []
        self.current_quiz_card = None
        self.word_detail_map = {}
        self.active_chip_btn = None
        self.active_word_detail = None

        self.init_ui()
        self.apply_dark_theme()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. 顶部操作栏 (精简短语，杜绝截断挤压)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        
        self.btn_snip = QPushButton("✂️ 截屏 (Alt+Q)")
        self.btn_snip.setObjectName("btn_snip")
        self.btn_snip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_snip.clicked.connect(self.start_snip_capture)
        top_bar.addWidget(self.btn_snip, stretch=1)

        self.btn_speak = QPushButton("🔊 朗读")
        self.btn_speak.setObjectName("btn_top_speak")
        self.btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speak.clicked.connect(self.speak_current_text)
        top_bar.addWidget(self.btn_speak)

        self.cb_top = QCheckBox("📌 置顶")
        self.cb_top.setChecked(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.cb_top.stateChanged.connect(self.toggle_always_on_top)
        top_bar.addWidget(self.cb_top)

        main_layout.addLayout(top_bar)

        # 2. 核心分页标签 (短名称，全显无箭头)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")

        # Tab 1: 查词
        self.tab_inspector = QWidget()
        self.init_inspector_tab()
        self.tabs.addTab(self.tab_inspector, "🔍 查词")

        # Tab 2: 生词本
        self.tab_notebook = QWidget()
        self.init_notebook_tab()
        self.tabs.addTab(self.tab_notebook, "📚 生词本")

        # Tab 3: 测验
        self.tab_quiz = QWidget()
        self.init_quiz_tab()
        self.tabs.addTab(self.tab_quiz, "⚡ 测验")

        # Tab 4: 百科
        self.tab_glossary = QWidget()
        self.init_glossary_tab()
        self.tabs.addTab(self.tab_glossary, "📖 百科")

        main_layout.addWidget(self.tabs)

        # 底部状态栏
        self.status_label = QLabel("提示：点击上方“框选游戏取词”或按下快捷键 Alt+Q 框选 NGU IDLE 任意区域")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        main_layout.addWidget(self.status_label)

        # 初始加载生词与测验
        self.load_notebook_cards()
        self.next_quiz_card()

    # ================= Tab 1: 实时解析 =================
    def init_inspector_tab(self):
        tab_vbox = QVBoxLayout(self.tab_inspector)
        tab_vbox.setContentsMargins(0, 0, 0, 0)
        tab_vbox.setSpacing(0)

        # 1. 最外层主全景滚动区 (Outer Scroll Area)
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setObjectName("inspector_scroll")
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.inspector_content = QWidget()
        self.inspector_content.setObjectName("inspector_content")
        layout = QVBoxLayout(self.inspector_content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(9)

        # 原文输入/展示区
        orig_header = QHBoxLayout()
        orig_header.setContentsMargins(0, 0, 0, 0)
        lbl_orig = QLabel("英文原文:")
        lbl_orig.setStyleSheet("font-weight: bold; color: #4fc3f7; font-size: 12px;")
        orig_header.addWidget(lbl_orig)
        orig_header.addStretch()

        self.btn_retranslate = QPushButton("🔄 重新翻译")
        self.btn_retranslate.setObjectName("btn_retranslate_inline")
        self.btn_retranslate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_retranslate.clicked.connect(self.manual_retranslate)
        orig_header.addWidget(self.btn_retranslate)
        layout.addLayout(orig_header)

        self.text_en = QTextEdit()
        self.text_en.setPlaceholderText("框选截取到的英文会在此显示，也可以直接粘贴...")
        self.text_en.setFixedHeight(90)
        self.text_en.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_en.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.text_en)

        lbl_zh = QLabel("整句释义:")
        lbl_zh.setStyleSheet("font-weight: bold; color: #81c784; font-size: 12px;")
        layout.addWidget(lbl_zh)

        self.text_zh = QTextEdit()
        self.text_zh.setReadOnly(True)
        self.text_zh.setFixedHeight(75)
        self.text_zh.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_zh.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.text_zh)

        # 核心功能 1：按词点读气泡块 (Word Chips)
        lbl_chips_title = QLabel("🧩 句子单词块 (点击任意单词即时查词与发音):")
        lbl_chips_title.setStyleSheet("font-weight: bold; color: #00e5ff; font-size: 13px;")
        layout.addWidget(lbl_chips_title)

        # 单词气泡专属滚动区：空间大幅扩充至 150~280px，并搭载防穿透独立滚轮
        self.chips_scroll = IsolatedScrollArea()
        self.chips_scroll.setWidgetResizable(True)
        self.chips_scroll.setObjectName("chips_scroll")
        self.chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chips_scroll.setMinimumHeight(150)
        self.chips_scroll.setMaximumHeight(280)
        self.chips_container = QWidget()
        self.chips_container.setObjectName("chips_container")
        self.chips_layout = FlowLayout(self.chips_container, margin=6, spacing=6)
        self.chips_scroll.setWidget(self.chips_container)
        layout.addWidget(self.chips_scroll)

        # 为原文和释义输入框同样安装滚轮防穿透滤镜
        self.text_en_filter = IsolatedWheelFilter(self.text_en)
        self.text_en.viewport().installEventFilter(self.text_en_filter)
        self.text_zh_filter = IsolatedWheelFilter(self.text_zh)
        self.text_zh.viewport().installEventFilter(self.text_zh_filter)

        # 核心功能 2：智能短语/固定搭配展示区 (Phrase Chips)
        self.phrases_box = QFrame()
        self.phrases_box.setObjectName("phrases_box")
        pb_layout = QVBoxLayout(self.phrases_box)
        pb_layout.setContentsMargins(10, 8, 10, 8)
        pb_layout.setSpacing(6)
        
        lbl_phrases_title = QLabel("🔗 识别到的短语 / 固定搭配 (点击查看完整短语解析):")
        lbl_phrases_title.setStyleSheet("font-weight: bold; color: #ffb74d; font-size: 13px;")
        pb_layout.addWidget(lbl_phrases_title)

        self.phrases_container = QWidget()
        self.phrases_layout = FlowLayout(self.phrases_container, margin=2, spacing=6)
        pb_layout.addWidget(self.phrases_container)
        self.phrases_box.hide()
        layout.addWidget(self.phrases_box)

        # 核心功能 3：点击单词或短语后的即时详情卡片 (Active Inspector)
        self.active_word_frame = QFrame()
        self.active_word_frame.setObjectName("active_word_frame")
        aw_layout = QVBoxLayout(self.active_word_frame)
        aw_layout.setContentsMargins(10, 8, 10, 8)
        aw_layout.setSpacing(6)

        aw_header = QHBoxLayout()
        aw_header.setSpacing(6)
        
        left_box = QHBoxLayout()
        left_box.setSpacing(6)
        self.lbl_aw_word = QLabel("📌 查词详情")
        self.lbl_aw_word.setStyleSheet("font-size: 15px; font-weight: bold; color: #00e5ff;")
        left_box.addWidget(self.lbl_aw_word)

        self.lbl_aw_phonetic = QLabel("")
        self.lbl_aw_phonetic.setStyleSheet("color: #90a4ae; font-size: 11px;")
        self.lbl_aw_phonetic.hide()
        left_box.addWidget(self.lbl_aw_phonetic)

        self.lbl_aw_tag = QLabel("")
        self.lbl_aw_tag.setStyleSheet("background: #37474f; color: #80deea; padding: 1px 6px; border-radius: 3px; font-size: 10px;")
        self.lbl_aw_tag.hide()
        left_box.addWidget(self.lbl_aw_tag)
        left_box.addStretch()
        aw_header.addLayout(left_box, stretch=1)

        right_btns = QHBoxLayout()
        right_btns.setSpacing(5)
        self.btn_aw_speak = QPushButton("🔊 朗读")
        self.btn_aw_speak.setProperty("class", "card_action_btn")
        self.btn_aw_speak.clicked.connect(self.speak_active_word)
        self.btn_aw_speak.hide()
        right_btns.addWidget(self.btn_aw_speak)

        self.btn_aw_add = QPushButton("➕ 收藏")
        self.btn_aw_add.setProperty("class", "card_action_btn")
        self.btn_aw_add.setStyleSheet("background-color: #00695c; border-color: #00897b;")
        self.btn_aw_add.clicked.connect(self.add_active_word_to_db)
        self.btn_aw_add.hide()
        right_btns.addWidget(self.btn_aw_add)
        aw_header.addLayout(right_btns)

        aw_layout.addLayout(aw_header)

        self.lbl_aw_meaning = QLabel("在上方点击任意单词或短语块，这里会立刻展示词性、发音与地道释义。")
        self.lbl_aw_meaning.setStyleSheet("color: #e0e0e0; font-size: 12px; line-height: 1.4;")
        self.lbl_aw_meaning.setWordWrap(True)
        self.lbl_aw_meaning.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        aw_layout.addWidget(self.lbl_aw_meaning)

        # 短语关联推荐行
        self.related_phrase_box = QWidget()
        rpb_layout = QHBoxLayout(self.related_phrase_box)
        rpb_layout.setContentsMargins(0, 2, 0, 0)
        self.lbl_related_title = QLabel("💡 关联短语:")
        self.lbl_related_title.setStyleSheet("color: #ffb74d; font-size: 12px; font-weight: bold;")
        rpb_layout.addWidget(self.lbl_related_title)
        self.btn_related_jump = QPushButton("")
        self.btn_related_jump.setProperty("class", "related_jump_btn")
        rpb_layout.addWidget(self.btn_related_jump)
        rpb_layout.addStretch()
        self.related_phrase_box.hide()
        aw_layout.addWidget(self.related_phrase_box)

        self.lbl_aw_lore = QLabel("")
        self.lbl_aw_lore.setStyleSheet("color: #ffd54f; font-size: 12px; background: #2b261b; padding: 6px; border-radius: 4px; line-height: 1.3;")
        self.lbl_aw_lore.setWordWrap(True)
        self.lbl_aw_lore.hide()
        aw_layout.addWidget(self.lbl_aw_lore)

        layout.addWidget(self.active_word_frame)

        # NGU 梗与机制解析横幅 (动态隐藏/展示)
        self.lore_frame = QFrame()
        self.lore_frame.setObjectName("lore_frame")
        lore_layout = QVBoxLayout(self.lore_frame)
        self.lbl_lore_title = QLabel("💡 NGU IDLE 专属机制与梗解析:")
        self.lbl_lore_title.setStyleSheet("font-weight: bold; color: #ffca28; font-size: 13px;")
        self.lbl_lore_content = QLabel("暂未检测到特殊游戏机制")
        self.lbl_lore_content.setWordWrap(True)
        self.lbl_lore_content.setStyleSheet("color: #fff9c4; font-size: 12px; line-height: 1.4;")
        lore_layout.addWidget(self.lbl_lore_title)
        lore_layout.addWidget(self.lbl_lore_content)
        self.lore_frame.hide()
        layout.addWidget(self.lore_frame)

        # 全部词汇拆解列表 (直接平铺在外层大滚动区内，极大释放空间，不再局促)
        lbl_words = QLabel("📋 全部词汇与短语拆解清单:")
        lbl_words.setStyleSheet("font-weight: bold; color: #ba68c8; font-size: 13px;")
        layout.addWidget(lbl_words)

        self.words_container = QWidget()
        self.words_container.setObjectName("words_container")
        self.words_layout = QVBoxLayout(self.words_container)
        self.words_layout.setContentsMargins(0, 0, 0, 0)
        self.words_layout.setSpacing(6)
        self.words_layout.addStretch()
        layout.addWidget(self.words_container)

        # 完成外层滚动区装载
        self.inspector_scroll.setWidget(self.inspector_content)
        tab_vbox.addWidget(self.inspector_scroll)

    # ================= Tab 2: 生词本 =================
    def init_notebook_tab(self):
        layout = QVBoxLayout(self.tab_notebook)
        layout.setContentsMargins(6, 8, 6, 6)

        search_bar = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 搜索单词、短语、释义或例句...")
        self.input_search.textChanged.connect(self.load_notebook_cards)
        search_bar.addWidget(self.input_search)

        self.btn_export = QPushButton("📥 导出生词")
        self.btn_export.clicked.connect(self.export_cards)
        search_bar.addWidget(self.btn_export)
        layout.addLayout(search_bar)

        self.notebook_scroll = QScrollArea()
        self.notebook_scroll.setWidgetResizable(True)
        self.notebook_scroll.setObjectName("notebook_scroll")
        self.notebook_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notebook_container = QWidget()
        self.notebook_container.setObjectName("notebook_container")
        self.notebook_layout = QVBoxLayout(self.notebook_container)
        self.notebook_layout.setContentsMargins(4, 4, 4, 4)
        self.notebook_layout.setSpacing(8)
        self.notebook_layout.addStretch()
        self.notebook_scroll.setWidget(self.notebook_container)
        layout.addWidget(self.notebook_scroll)

    # ================= Tab 3: 挂机微测验 =================
    def init_quiz_tab(self):
        layout = QVBoxLayout(self.tab_quiz)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        title = QLabel("⚡ 放置挂机间隙微测验 (单词与短语)")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00e5ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.quiz_card = QFrame()
        self.quiz_card.setObjectName("quiz_card")
        card_layout = QVBoxLayout(self.quiz_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        self.lbl_quiz_word = QLabel("点击下方开始按钮进行测验")
        self.lbl_quiz_word.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        self.lbl_quiz_word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_quiz_word)

        self.lbl_quiz_context = QLabel("")
        self.lbl_quiz_context.setStyleSheet("font-size: 12px; color: #aaaaaa; font-style: italic;")
        self.lbl_quiz_context.setWordWrap(True)
        self.lbl_quiz_context.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_quiz_context)

        self.lbl_quiz_answer = QLabel("")
        self.lbl_quiz_answer.setStyleSheet("font-size: 14px; color: #81c784; font-weight: bold;")
        self.lbl_quiz_answer.setWordWrap(True)
        self.lbl_quiz_answer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_quiz_answer.hide()
        card_layout.addWidget(self.lbl_quiz_answer)

        layout.addWidget(self.quiz_card, stretch=1)

        self.btn_show_answer = QPushButton("👀 查看答案 (翻牌)")
        self.btn_show_answer.clicked.connect(self.show_quiz_answer)
        layout.addWidget(self.btn_show_answer)

        btn_row = QHBoxLayout()
        self.btn_mastered = QPushButton("✅ 记住了 (+掌握度)")
        self.btn_mastered.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_mastered.clicked.connect(lambda: self.record_quiz_result(True))
        self.btn_mastered.setEnabled(False)

        self.btn_forgot = QPushButton("❌ 没记住 (重新复习)")
        self.btn_forgot.setStyleSheet("background-color: #c62828; color: white;")
        self.btn_forgot.clicked.connect(lambda: self.record_quiz_result(False))
        self.btn_forgot.setEnabled(False)

        btn_row.addWidget(self.btn_forgot)
        btn_row.addWidget(self.btn_mastered)
        layout.addLayout(btn_row)

        self.btn_next_quiz = QPushButton("🎲 下一个词条")
        self.btn_next_quiz.clicked.connect(self.next_quiz_card)
        layout.addWidget(self.btn_next_quiz)

    # ================= Tab 4: NGU 放置百科 =================
    def init_glossary_tab(self):
        layout = QVBoxLayout(self.tab_glossary)
        layout.setContentsMargins(6, 8, 6, 6)

        search = QLineEdit()
        search.setPlaceholderText("🔍 搜索 NGU 术语与短语 (如 cap, power, rebirth, drop chance)...")
        layout.addWidget(search)

        glossary_scroll = QScrollArea()
        glossary_scroll.setWidgetResizable(True)
        glossary_scroll.setObjectName("glossary_scroll")
        glossary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        glossary_container = QWidget()
        glossary_container.setObjectName("glossary_container")
        glossary_layout = QVBoxLayout(glossary_container)
        glossary_layout.setContentsMargins(4, 4, 4, 4)
        glossary_layout.setSpacing(6)
        glossary_layout.addStretch()
        glossary_scroll.setWidget(glossary_container)
        layout.addWidget(glossary_scroll)

        def populate(kw=""):
            while glossary_layout.count() > 1:
                child = glossary_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            kw_low = kw.lower().strip()
            insert_idx = 0
            for key, val in NGU_GLOSSARY.items():
                if not kw_low or kw_low in key or kw_low in val['cn'].lower() or kw_low in val['lore'].lower():
                    card = QFrame()
                    card.setObjectName("glossary_card")
                    card.setStyleSheet("""
                        #glossary_card {
                            background-color: #1a1c26;
                            border: 1px solid #333649;
                            border-radius: 6px;
                        }
                    """)
                    cl = QVBoxLayout(card)
                    cl.setContentsMargins(8, 7, 8, 7)
                    cl.setSpacing(3)
                    
                    header = QHBoxLayout()
                    t = QLabel(f"<b>{val['word']}</b> <font color='#888'>{val.get('phonetic', '')}</font>")
                    t.setStyleSheet("font-size: 13px; color: #4fc3f7;")
                    t.setWordWrap(True)
                    tag = QLabel(val.get('type', '机制'))
                    tag.setStyleSheet("background: #37474f; color: #80deea; padding: 1px 5px; border-radius: 3px; font-size: 10px;")
                    header.addWidget(t, stretch=1)
                    header.addWidget(tag)
                    cl.addLayout(header)

                    cn = QLabel(f"<b>释义:</b> {val['cn']}")
                    cn.setStyleSheet("color: #e0e0e0; font-size: 12px;")
                    cn.setWordWrap(True)
                    cl.addWidget(cn)

                    lore = QLabel(f"<b>机制与梗:</b> {val['lore']}")
                    lore.setStyleSheet("color: #ffca28; font-size: 12px;")
                    lore.setWordWrap(True)
                    cl.addWidget(lore)

                    glossary_layout.insertWidget(insert_idx, card)
                    insert_idx += 1

        search.textChanged.connect(populate)
        populate()

    # ================= 业务逻辑：截图与OCR =================
    def start_snip_capture(self):
        self.status_label.setText("正在框选游戏区域... (按住鼠标左键拖拽，Esc退出)")
        self.snipper.start_snip()

    def on_image_snipped(self, pixmap):
        self.show()
        self.raise_()
        self.activateWindow()

        self.status_label.setText("⚡ 正在分析图像并提取文字与短语...")
        self.tabs.setCurrentIndex(0)
        self.text_en.setPlainText("正在识别中，请稍候...")
        self.text_zh.setPlainText("正在翻译中...")

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        pixmap.save(buffer, "PNG")
        pil_img = Image.open(io.BytesIO(buffer.data()))

        self.worker = ProcessWorker(pil_img, self.ocr_engine, self.trans_service, self.phrase_matcher)
        self.worker.finished.connect(self.on_process_finished)
        self.worker.error.connect(self.on_process_error)
        self.worker.start()

    def on_process_finished(self, full_text, translation, ngu_matches, words_detail, phrases_detail):
        self.current_sentence = full_text
        self.current_words_detail = words_detail
        self.current_phrases = phrases_detail
        
        # 建立词典缓存映射
        self.word_detail_map = {}
        for d in words_detail:
            self.word_detail_map[d["word"].lower()] = d

        self.text_en.setPlainText(full_text)
        self.text_zh.setPlainText(translation)
        
        status_msg = f"识别完成，提取到 {len(words_detail)} 个词汇"
        if phrases_detail:
            status_msg += f"，检测到 {len(phrases_detail)} 个短语！"
        self.status_label.setText(status_msg)

        # 1. 渲染点击单词气泡块 (Word Chips)
        self.render_word_chips(full_text)

        # 2. 渲染智能短语块 (Phrase Chips)
        self.render_phrase_chips(phrases_detail)

        # 3. 展示 NGU 专属梗解析
        if ngu_matches:
            lore_texts = []
            for m in ngu_matches:
                lore_texts.append(f"【{m['word']}】: {m['lore']}")
            self.lbl_lore_content.setText("\n\n".join(lore_texts))
            self.lore_frame.show()
        else:
            self.lore_frame.hide()

        # 4. 刷新下方完整单词与短语卡片列表
        self.render_word_and_phrase_cards(words_detail, phrases_detail)

    def on_process_error(self, err_msg):
        self.status_label.setText(f"处理失败: {err_msg}")

    # ================= 渲染可点击的单词气泡块 =================
    def render_word_chips(self, sentence: str):
        while self.chips_layout.count() > 0:
            item = self.chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|[^\s\w]", sentence)
        first_word_chip = None

        for token in tokens:
            if re.match(r"[A-Za-z]", token):
                btn = QPushButton(token)
                btn.setProperty("class", "word_chip")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, w=token, b=btn: self.on_word_chip_clicked(w, b))
                self.chips_layout.addWidget(btn)
                if not first_word_chip:
                    first_word_chip = (token, btn)
            else:
                punct_lbl = QLabel(token)
                punct_lbl.setStyleSheet("color: #888888; font-size: 13px; font-weight: bold; padding: 2px 0px;")
                self.chips_layout.addWidget(punct_lbl)

        # 默认优先展示识别到的短语，若无短语则展示第一个单词
        if not self.current_phrases and first_word_chip:
            self.on_word_chip_clicked(first_word_chip[0], first_word_chip[1], play_sound=False)

    # ================= 渲染可点击的短语块 (Phrase Chips) =================
    def render_phrase_chips(self, phrases_detail):
        while self.phrases_layout.count() > 0:
            item = self.phrases_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not phrases_detail:
            self.phrases_box.hide()
            return

        self.phrases_box.show()
        first_phrase_btn = None
        for p in phrases_detail:
            btn = QPushButton(f"🔗 {p['phrase']} ({p['cn']})")
            btn.setProperty("class", "phrase_chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, item=p, b=btn: self.on_phrase_chip_clicked(item, b))
            self.phrases_layout.addWidget(btn)
            if not first_phrase_btn:
                first_phrase_btn = (p, btn)

        # 优先默认展示短语详情
        if first_phrase_btn:
            self.on_phrase_chip_clicked(first_phrase_btn[0], first_phrase_btn[1], play_sound=False)

    def on_phrase_chip_clicked(self, phrase_item, btn, play_sound=True):
        """点击短语块，更新选中高亮状态并展示短语解析"""
        if self.active_chip_btn:
            old_class = "phrase_chip" if "🔗" in self.active_chip_btn.text() else "word_chip"
            self.active_chip_btn.setProperty("class", old_class)
            self.active_chip_btn.style().unpolish(self.active_chip_btn)
            self.active_chip_btn.style().polish(self.active_chip_btn)

        self.active_chip_btn = btn
        btn.setProperty("class", "phrase_chip_active")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

        self.active_word_detail = {
            "word": phrase_item["phrase"],
            "phonetic": "",
            "cn": phrase_item["cn"],
            "lore": phrase_item.get("lore", ""),
            "type": phrase_item.get("type", "固定短语")
        }

        self.lbl_aw_word.setText(phrase_item["phrase"])
        self.lbl_aw_tag.setText(phrase_item.get("type", "短语"))
        self.lbl_aw_tag.show()
        self.btn_aw_speak.show()
        self.btn_aw_add.show()

        meaning_text = f"<b>短语释义:</b> {phrase_item['cn']}"
        if phrase_item.get("display") and phrase_item["display"] != phrase_item["phrase"]:
            meaning_text += f"<br><font color='#80deea'>(原型: {phrase_item['display']})</font>"
        self.lbl_aw_meaning.setText(meaning_text)

        self.related_phrase_box.hide()

        if phrase_item.get("lore"):
            self.lbl_aw_lore.setText(f"💡 <b>短语解析:</b> {phrase_item['lore']}")
            self.lbl_aw_lore.show()
        else:
            self.lbl_aw_lore.hide()

        if play_sound:
            self.tts.say(phrase_item["phrase"])

    def on_word_chip_clicked(self, word: str, btn: QPushButton, play_sound: bool = True):
        """点击单词块，更新选中高亮状态并展示释义卡片"""
        if self.active_chip_btn:
            old_class = "phrase_chip" if "🔗" in self.active_chip_btn.text() else "word_chip"
            self.active_chip_btn.setProperty("class", old_class)
            self.active_chip_btn.style().unpolish(self.active_chip_btn)
            self.active_chip_btn.style().polish(self.active_chip_btn)

        self.active_chip_btn = btn
        btn.setProperty("class", "word_chip_active")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

        low = word.lower()
        detail = self.word_detail_map.get(low) or self.trans_service.get_word_detail(word)
        self.active_word_detail = detail

        self.lbl_aw_word.setText(detail["word"])
        if detail.get("phonetic"):
            self.lbl_aw_phonetic.setText(detail["phonetic"])
            self.lbl_aw_phonetic.show()
        else:
            self.lbl_aw_phonetic.hide()

        self.lbl_aw_tag.setText(detail.get("type", "词汇"))
        self.lbl_aw_tag.show()
        self.btn_aw_speak.show()
        self.btn_aw_add.show()

        cn_text = detail['cn'].replace('\n', '<br>')
        self.lbl_aw_meaning.setText(f"<b>释义:</b><br>{cn_text}" if '\n' in detail['cn'] else f"<b>释义:</b> {cn_text}")

        # 检查该词是否属于检测到的某个短语
        matched_phrase = next((p for p in self.current_phrases if low in p["phrase"].lower()), None)
        if matched_phrase:
            self.btn_related_jump.setText(f"🔗 {matched_phrase['phrase']} ({matched_phrase['cn']})")
            # 断开旧连接并绑定新跳转
            try:
                self.btn_related_jump.clicked.disconnect()
            except Exception:
                pass
            self.btn_related_jump.clicked.connect(lambda _, p=matched_phrase: self.jump_to_phrase(p))
            self.related_phrase_box.show()
        else:
            self.related_phrase_box.hide()
        
        if detail.get("lore"):
            self.lbl_aw_lore.setText(f"💡 <b>游戏机制/梗:</b> {detail['lore']}")
            self.lbl_aw_lore.show()
        else:
            self.lbl_aw_lore.hide()

        if play_sound:
            self.tts.say(detail["word"])

    def jump_to_phrase(self, phrase_item):
        self.on_phrase_chip_clicked(phrase_item, self.btn_related_jump, play_sound=True)

    def speak_active_word(self):
        if self.active_word_detail:
            self.tts.say(self.active_word_detail["word"])

    def add_active_word_to_db(self):
        if self.active_word_detail:
            self.save_word_to_db(self.active_word_detail)

    # ================= 词汇与短语拆解清单列表 =================
    def render_word_and_phrase_cards(self, words_detail, phrases_detail):
        while self.words_layout.count() > 1:
            item = self.words_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. 如果有短语，优先将短语作为高亮卡片置顶展示
        insert_idx = 0
        if phrases_detail:
            for p in phrases_detail:
                card = QFrame()
                card.setObjectName("phrase_card")
                cl = QHBoxLayout(card)
                cl.setContentsMargins(10, 8, 10, 8)

                left = QVBoxLayout()
                h = QHBoxLayout()
                w_lbl = QLabel(f"<b>🔗 {p['phrase']}</b>")
                w_lbl.setStyleSheet("font-size: 14px; color: #ffb74d;")
                h.addWidget(w_lbl)
                tag_lbl = QLabel(p.get("type", "短语"))
                tag_lbl.setStyleSheet("background: #bf360c; color: #ffe0b2; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;")
                h.addWidget(tag_lbl)
                h.addStretch()
                left.addLayout(h)

                cn_text = f"<b>短语释义:</b> {p['cn']}"
                if p.get("display") and p["display"] != p["phrase"]:
                    cn_text += f" <font color='#80deea'>(原型: {p['display']})</font>"
                cn_lbl = QLabel(cn_text)
                cn_lbl.setStyleSheet("color: #e0e0e0; font-size: 12px;")
                left.addWidget(cn_lbl)

                if p.get("lore"):
                    lore_lbl = QLabel(f"💡 {p['lore']}")
                    lore_lbl.setStyleSheet("color: #ffd54f; font-size: 11px;")
                    lore_lbl.setWordWrap(True)
                    left.addWidget(lore_lbl)

                cl.addLayout(left, stretch=1)

                right = QVBoxLayout()
                btn_play = QPushButton("🔊 朗读")
                btn_play.setProperty("class", "card_action_btn")
                btn_play.clicked.connect(lambda _, text=p["phrase"]: self.tts.say(text))
                right.addWidget(btn_play)

                btn_add = QPushButton("➕ 收藏")
                btn_add.setProperty("class", "card_action_btn")
                btn_add.setStyleSheet("background-color: #e65100; border-color: #ff9800;")
                btn_add.clicked.connect(lambda _, item=p: self.save_word_to_db({
                    "word": item["phrase"],
                    "phonetic": "",
                    "cn": item["cn"],
                    "lore": item.get("lore", ""),
                    "type": item.get("type", "短语")
                }))
                right.addWidget(btn_add)
                right.addStretch()

                cl.addLayout(right)
                self.words_layout.insertWidget(insert_idx, card)
                insert_idx += 1

        # 2. 单词列表
        for idx, item in enumerate(words_detail):
            card = QFrame()
            card.setObjectName("word_card")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            left = QVBoxLayout()
            w_line = QHBoxLayout()
            w_lbl = QLabel(f"<b>{item['word']}</b>")
            w_lbl.setStyleSheet("font-size: 14px; color: #4fc3f7;")
            w_line.addWidget(w_lbl)

            if item.get("phonetic"):
                p_lbl = QLabel(item["phonetic"])
                p_lbl.setStyleSheet("color: #888888; font-size: 11px;")
                w_line.addWidget(p_lbl)

            tag_lbl = QLabel(item.get("type", "词汇"))
            tag_lbl.setStyleSheet("background: #263238; color: #80cbc4; padding: 1px 4px; border-radius: 3px; font-size: 10px;")
            w_line.addWidget(tag_lbl)
            w_line.addStretch()
            left.addLayout(w_line)

            cn_text = item["cn"].replace('\n', '<br>')
            cn_lbl = QLabel(f"<b>释义:</b><br>{cn_text}" if '\n' in item["cn"] else f"<b>释义:</b> {cn_text}")
            cn_lbl.setStyleSheet("color: #e0e0e0; font-size: 12px; line-height: 1.3;")
            cn_lbl.setWordWrap(True)
            cn_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            left.addWidget(cn_lbl)

            if item.get("lore"):
                lore_lbl = QLabel(f"💡 {item['lore']}")
                lore_lbl.setStyleSheet("color: #ffd54f; font-size: 11px;")
                lore_lbl.setWordWrap(True)
                left.addWidget(lore_lbl)

            card_layout.addLayout(left, stretch=1)

            # 右侧操作按钮
            right = QVBoxLayout()
            btn_play = QPushButton("🔊 朗读")
            btn_play.setProperty("class", "card_action_btn")
            btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_play.clicked.connect(lambda _, w=item["word"]: self.tts.say(w))
            right.addWidget(btn_play)

            btn_add = QPushButton("➕ 收藏")
            btn_add.setProperty("class", "card_action_btn")
            btn_add.setStyleSheet("background-color: #00695c; border-color: #00897b;")
            btn_add.setToolTip("收入生词本")
            btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add.clicked.connect(lambda _, it=item: self.save_word_to_db(it))
            right.addWidget(btn_add)
            right.addStretch()

            card_layout.addLayout(right)

            self.words_layout.insertWidget(insert_idx + idx, card)

    def save_word_to_db(self, item):
        database.add_vocab_card(
            word=item["word"],
            phonetic=item.get("phonetic", ""),
            translation=item["cn"],
            context_sentence=self.current_sentence,
            lore_explanation=item.get("lore", ""),
            tag=item.get("type", "NGU")
        )
        self.status_label.setText(f"已将「{item['word']}」保存到生词本！")
        self.load_notebook_cards()

    def manual_retranslate(self):
        raw_text = self.text_en.toPlainText().strip()
        if not raw_text:
            return
        text = fix_jammed_words(raw_text)
        if text != raw_text:
            self.text_en.setPlainText(text)
        self.current_sentence = text
        trans = self.trans_service.translate_sentence(text)
        self.text_zh.setPlainText(trans)
        
        matches = self.trans_service.analyze_ngu_context(text)
        if matches:
            lore_texts = [f"【{m['word']}】: {m['lore']}" for m in matches]
            self.lbl_lore_content.setText("\n\n".join(lore_texts))
            self.lore_frame.show()
        else:
            self.lore_frame.hide()

        phrases_detail = self.phrase_matcher.detect_phrases(text)
        words = self.trans_service.extract_words(text)
        words_detail = self.trans_service.batch_get_word_details(words)
        
        self.current_phrases = phrases_detail
        self.word_detail_map = {d["word"].lower(): d for d in words_detail}
        self.render_word_chips(text)
        self.render_phrase_chips(phrases_detail)
        self.render_word_and_phrase_cards(words_detail, phrases_detail)

    def speak_current_text(self):
        text = self.text_en.toPlainText().strip()
        if text:
            self.tts.say(text)

    def toggle_always_on_top(self, state):
        on_top = bool(state)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.show()

    # ================= 生词本管理 =================
    def load_notebook_cards(self):
        while self.notebook_layout.count() > 1:
            child = self.notebook_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.input_search.text()
        cards = database.get_all_cards(query)

        insert_idx = 0
        for c in cards:
            card = QFrame()
            card.setObjectName("notebook_card")
            card.setStyleSheet("""
                #notebook_card {
                    background-color: #1a1c26;
                    border: 1px solid #333649;
                    border-radius: 6px;
                }
                #notebook_card:hover {
                    border-color: #00e5ff;
                }
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 7, 8, 7)
            cl.setSpacing(4)

            top = QHBoxLayout()
            top.setSpacing(4)
            w_lbl = QLabel(f"<b>{c['word']}</b> <font color='#888'>{c['phonetic'] or ''}</font>")
            w_lbl.setStyleSheet("font-size: 13px; color: #4fc3f7;")
            w_lbl.setWordWrap(True)
            top.addWidget(w_lbl, stretch=1)

            btn_tts = QPushButton("🔊")
            btn_tts.setProperty("class", "card_action_btn")
            btn_tts.setToolTip("朗读发音")
            btn_tts.setFixedWidth(28)
            btn_tts.clicked.connect(lambda _, w=c['word']: self.tts.say(w))
            top.addWidget(btn_tts)

            btn_del = QPushButton("🗑️")
            btn_del.setProperty("class", "card_action_btn")
            btn_del.setStyleSheet("background-color: #5d1010; border-color: #791a1a;")
            btn_del.setToolTip("从生词本删除")
            btn_del.setFixedWidth(28)
            btn_del.clicked.connect(lambda _, cid=c['id']: self.delete_vocab(cid))
            top.addWidget(btn_del)
            cl.addLayout(top)

            trans_text = c['translation'].replace('\n', '<br>')
            trans = QLabel(f"<b>释义:</b><br>{trans_text}" if '\n' in c['translation'] else f"<b>释义:</b> {trans_text}")
            trans.setStyleSheet("color: #e0e0e0; font-size: 12px; line-height: 1.3;")
            trans.setWordWrap(True)
            trans.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cl.addWidget(trans)

            if c['context_sentence']:
                ctx = QLabel(f"<b>游戏中例句:</b> {c['context_sentence']}")
                ctx.setStyleSheet("color: #90caf9; font-size: 11px;")
                ctx.setWordWrap(True)
                cl.addWidget(ctx)

            if c['lore_explanation']:
                lore = QLabel(f"<b>机制/短语解析:</b> {c['lore_explanation']}")
                lore.setStyleSheet("color: #ffe082; font-size: 11px;")
                lore.setWordWrap(True)
                cl.addWidget(lore)

            self.notebook_layout.insertWidget(insert_idx, card)
            insert_idx += 1

    def delete_vocab(self, card_id):
        database.delete_card(card_id)
        self.load_notebook_cards()

    def export_cards(self):
        cards = database.get_all_cards()
        if not cards:
            QMessageBox.information(self, "提示", "生词本当前为空，先去游戏里多收录几个词吧！")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出生词本", "NGU_生词本.md", "Markdown (*.md);;CSV (*.csv)")
        if not file_path:
            return

        if file_path.endswith(".csv"):
            with open(file_path, "w", encoding="utf-8-sig") as f:
                f.write("Word,Translation,Context,Lore\n")
                for c in cards:
                    f.write(f'"{c["word"]}","{c["translation"]}","{c["context_sentence"]}","{c["lore_explanation"]}"\n')
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# NGU IDLE 英语学习生词与短语本\n\n")
                for c in cards:
                    f.write(f"### {c['word']}\n")
                    f.write(f"- **释义**: {c['translation']}\n")
                    if c['context_sentence']:
                        f.write(f"- **游戏原句**: {c['context_sentence']}\n")
                    if c['lore_explanation']:
                        f.write(f"- **机制/短语解析**: {c['lore_explanation']}\n")
                    f.write("\n")
        
        QMessageBox.information(self, "成功", f"生词本已成功导出至:\n{file_path}")

    # ================= 挂机微测验 =================
    def next_quiz_card(self):
        cards = database.get_all_cards()
        if not cards:
            self.lbl_quiz_word.setText("生词本为空")
            self.lbl_quiz_context.setText("请先在实时解析页面将遇到的单词或短语点击【➕ 收藏】加入生词本！")
            self.lbl_quiz_answer.hide()
            self.btn_mastered.setEnabled(False)
            self.btn_forgot.setEnabled(False)
            return

        self.current_quiz_card = random.choice(cards)
        self.lbl_quiz_word.setText(self.current_quiz_card['word'])
        if self.current_quiz_card['context_sentence']:
            masked_sentence = self.current_quiz_card['context_sentence'].replace(
                self.current_quiz_card['word'], "_____"
            )
            self.lbl_quiz_context.setText(f"语境填空:\n\"{masked_sentence}\"")
        else:
            self.lbl_quiz_context.setText("")

        self.lbl_quiz_answer.hide()
        self.btn_show_answer.setEnabled(True)
        self.btn_mastered.setEnabled(False)
        self.btn_forgot.setEnabled(False)

    def show_quiz_answer(self):
        if not self.current_quiz_card:
            return
        ans_text = f"【释义】 {self.current_quiz_card['translation']}"
        if self.current_quiz_card['lore_explanation']:
            ans_text += f"\n【机制/梗】 {self.current_quiz_card['lore_explanation']}"
        self.lbl_quiz_answer.setText(ans_text)
        self.lbl_quiz_answer.show()
        self.btn_mastered.setEnabled(True)
        self.btn_forgot.setEnabled(True)
        self.tts.say(self.current_quiz_card['word'])

    def record_quiz_result(self, remembered: bool):
        if self.current_quiz_card:
            database.update_review_progress(self.current_quiz_card['id'], remembered)
        self.next_quiz_card()

    # ================= 皮肤与样式 =================
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            #btn_snip {
                background-color: #00838f;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 5px;
                border: 1px solid #00acc1;
            }
            #btn_snip:hover {
                background-color: #00acc1;
            }
            #btn_top_speak {
                padding: 5px 8px;
                font-size: 12px;
                border-radius: 5px;
            }
            #btn_retranslate_inline {
                background-color: #242838;
                color: #00e5ff;
                border: 1px solid #00acc1;
                font-size: 11px;
                padding: 2px 7px;
                border-radius: 4px;
            }
            #btn_retranslate_inline:hover {
                background-color: #00acc1;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2e303e;
                color: #ffffff;
                border: 1px solid #3e4256;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3e4256;
            }
            .card_action_btn {
                padding: 2px 5px;
                font-size: 11px;
                min-width: 26px;
                height: 22px;
                border-radius: 4px;
                background-color: #303346;
                border: 1px solid #484c66;
            }
            .card_action_btn:hover {
                background-color: #40445c;
                border-color: #00e5ff;
            }
            .word_chip {
                background-color: #282a38;
                color: #ffffff;
                border: 1px solid #42465e;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
            }
            .word_chip:hover {
                background-color: #35384d;
                border-color: #00e5ff;
            }
            .word_chip_active {
                background-color: #0f3442;
                color: #00e5ff;
                border: 2px solid #00e5ff;
                padding: 3px 9px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            .phrase_chip {
                background-color: #3e2617;
                color: #ffcc80;
                border: 1px solid #ff9800;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
            }
            .phrase_chip:hover {
                background-color: #4e321d;
                border-color: #ffb74d;
                color: #ffffff;
            }
            .phrase_chip_active {
                background-color: #5d2b09;
                color: #ffffff;
                border: 2px solid #ff9800;
                padding: 3px 9px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            .related_jump_btn {
                background-color: #372818;
                color: #ffb74d;
                border: 1px dashed #ff9800;
                padding: 2px 6px;
                font-size: 11px;
                border-radius: 4px;
            }
            .related_jump_btn:hover {
                background-color: #4e3820;
                color: #ffffff;
            }
            #chips_container {
                background-color: #16161c;
                border: 1px solid #2e3040;
                border-radius: 6px;
                padding: 5px;
            }
            #phrases_box {
                background-color: #241c16;
                border: 1px solid #5a3818;
                border-radius: 6px;
                padding: 5px;
            }
            #active_word_frame {
                background-color: #232533;
                border: 1px solid #00acc1;
                border-radius: 6px;
            }
            #phrase_card {
                background-color: #2d211a;
                border: 1px solid #ff9800;
                border-radius: 6px;
            }
            #word_card {
                background-color: #252530;
                border: 1px solid #333344;
                border-radius: 6px;
            }
            #quiz_card {
                background-color: #23232e;
                border: 2px dashed #00b0ff;
                border-radius: 10px;
            }
            QTextEdit, QLineEdit {
                background-color: #16161a;
                border: 1px solid #33333f;
                border-radius: 4px;
                padding: 5px;
                color: #f0f0f0;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #33333f;
                background-color: #1e1e24;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #18181c;
                color: #a0a0a0;
                padding: 5px 8px;
                font-size: 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #282832;
                color: #00e5ff;
                font-weight: bold;
            }
            #lore_frame {
                background-color: #2d261e;
                border: 1px solid #ffb300;
                border-radius: 6px;
                padding: 8px;
            }
            #inspector_scroll, #chips_scroll, #notebook_scroll, #glossary_scroll {
                border: none;
                background-color: transparent;
            }
            #inspector_content, #notebook_container, #glossary_container {
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #141419;
                width: 7px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #3c4056;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00e5ff;
            }
            QScrollBar:horizontal {
                height: 0px !important;
                max-height: 0px !important;
                border: none;
                background: transparent;
            }
            QScrollBar::handle:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px !important;
                height: 0px !important;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
