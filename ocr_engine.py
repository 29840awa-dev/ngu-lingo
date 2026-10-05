# -*- coding: utf-8 -*-
"""
本地 RapidOCR 引擎封装：支持快速离线识别屏幕截取图像中的文字，
并内置智能英文黏连词自动分词（解决密集位图字体粘连问题，如 intensebattleofyourlife）
"""
import re
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
import wordsegment

# 初始化预加载英文词频分词模型
wordsegment.load()

def fix_jammed_words(text: str) -> str:
    """
    自动检测并拆分因游戏字体像素紧凑被 OCR 误连在一起的英文单词
    例如: intensebattleofyourlife -> intense battle of your life
    """
    # 针对游戏特有专有词与排版的精准修复
    special_fixes = [
        (r'SOMESETTINGS', 'SOME SETTINGS'),
        (r'MORESETTINGS', 'MORE SETTINGS'),
        (r'FILTERLOOTBYTYPE', 'FILTER LOOT BY TYPE'),
        (r'AutoboostRecycled', 'Autoboost Recycled'),
        (r'AntiFastBarFlicker', 'Anti Fast Bar Flicker'),
        (r'ITOPODPerk', 'ITOPOD Perk'),
        (r'ConfirmationPopups', 'Confirmation Popups'),
        (r'UnassignE/Mon', 'Unassign E/M on'),
        (r'UnassignE/M', 'Unassign E/M'),
        (r'PowerBoost', 'Power Boost')
    ]
    for pattern, repl in special_fixes:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    tokens = text.split()
    fixed_tokens = []
    for token in tokens:
        m = re.match(r'^([A-Za-z]+)([^A-Za-z]*)$', token)
        if m:
            word, punct = m.groups()
            # 只有长度较长的单词才进行通用词频检测拆分
            if len(word) >= 8 and not word.isupper():
                segmented = wordsegment.segment(word)
                if len(segmented) > 1 and all(len(s) > 1 for s in segmented):
                    fixed_tokens.append(" ".join(segmented) + punct)
                    continue
        fixed_tokens.append(token)
    return " ".join(fixed_tokens)

class OCREngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCREngine, cls).__new__(cls)
            cls._instance.ocr = RapidOCR()
        return cls._instance

    def recognize_image(self, img_input):
        """
        识别图像并返回组合好的文本以及按行分块的识别结果。
        智能检测多列界面（如游戏菜单、多栏设置项），支持分栏独立纵向排序与换行保留。
        :param img_input: PIL.Image, numpy.ndarray 或文件路径
        :return: (full_text: str, line_results: list)
        """
        if isinstance(img_input, Image.Image):
            img_np = np.array(img_input)
        elif isinstance(img_input, str):
            img_pil = Image.open(img_input).convert('RGB')
            img_np = np.array(img_pil)
        elif isinstance(img_input, np.ndarray):
            img_np = img_input
        else:
            raise ValueError("Unsupported image input type")

        result, elapse_list = self.ocr(img_np)
        
        if not result:
            return "", []

        boxes = [item for item in result if float(item[2]) > 0.4]
        if not boxes:
            return "", []

        # 智能多列排版检测与分栏
        w = img_np.shape[1]
        cov = np.zeros(w, dtype=int)
        for b in boxes:
            x_min = max(0, int(min(p[0] for p in b[0])))
            x_max = min(w, int(max(p[0] for p in b[0])))
            cov[x_min:x_max] += 1

        col_boundaries = [0]
        in_gap = False
        gap_start = 0
        for x in range(w):
            if cov[x] == 0:
                if not in_gap:
                    in_gap = True
                    gap_start = x
            else:
                if in_gap:
                    in_gap = False
                    # 内部间隙宽度 >= 12 像素视为列分隔线
                    if gap_start > 15 and x < w - 15 and (x - gap_start) >= 12:
                        col_boundaries.append((gap_start + x) // 2)
        col_boundaries.append(w)

        is_multi_column = len(col_boundaries) > 2
        ordered_boxes = []
        if is_multi_column:
            # 多列模式：先按列从左至右，每列内按纵向 Y 从上至下排序
            columns = [[] for _ in range(len(col_boundaries) - 1)]
            for b in boxes:
                x_mid = (min(p[0] for p in b[0]) + max(p[0] for p in b[0])) / 2
                for i in range(len(columns)):
                    if col_boundaries[i] <= x_mid < col_boundaries[i+1]:
                        columns[i].append(b)
                        break
            for col in columns:
                col.sort(key=lambda b: min(p[1] for p in b[0]))
                ordered_boxes.extend(col)
        else:
            # 单列/常规模式：保持从上到下阅读顺序
            ordered_boxes = sorted(boxes, key=lambda b: min(p[1] for p in b[0]))

        lines = [fix_jammed_words(b[1].strip()) for b in ordered_boxes if b[1].strip()]

        if is_multi_column:
            # 多列设置/菜单界面：保留换行结构，以便清晰展示各项
            full_text = "\n".join(lines)
        else:
            # 普通段落/句子描述：按空格拼接并优化连字符排版
            full_text = " ".join(lines)
            full_text = full_text.replace("- ", "").strip()
        
        return full_text, lines
