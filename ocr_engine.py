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
from ngu_knowledge import NGU_GLOSSARY

# 初始化预加载英文词频分词模型
wordsegment.load()

def clean_ocr_text(raw_text: str) -> str:
    """
    全自动检测并拆分因游戏位图字体紧凑、缺少空格或标点粘连被 OCR 误连在一起的英文单词
    解决案例：
      - 标点缺失空格: short.Youcanusetheleftandrightarrowson -> short. You can use the left and right arrows on
      - 符号粘连: navigate/spamthrough -> navigate / spam through
      - 括号粘连: (Usethearrowkeys -> (Use the arrow keys
      - 驼峰粘连: PeopleCall / GladYou / WhoMade -> People Call / Glad You / Who Made
      - 紧密单词: thisgame -> this game, whomade -> who made, gladyou -> glad you
    """
    if not raw_text:
        return ""

    # 0. 移除 OCR 异常控制字符与乱码符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]', ' ', raw_text)

    # 1. 游戏特有专有词与排版的先验精准修复
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
        (r'PowerBoost', 'Power Boost'),
        (r'\b(4|G)for short\b', '4G for short'),
        (r'\barrow son\b', 'arrows on'),
        (r'\barrowson\b', 'arrows on'),
        (r'\blet\'sbegin\b', "let's begin"),
        (r'\bletsbegin\b', "let's begin")
    ]
    for pattern, repl in special_fixes:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 2. 标点符号与字母之间缺失空格的规范化修复
    # 句号、逗号、问号、叹号、冒号、分号后紧跟字母 -> 补全空格 (e.g. short.You -> short. You, game.People -> game. People)
    text = re.sub(r'([A-Za-z0-9])([,\.!\?:;])([A-Za-z])', r'\1\2 \3', text)
    # 斜杠两端补全空格 (e.g. navigate/spam -> navigate / spam)
    text = re.sub(r'([A-Za-z0-9])/([A-Za-z0-9])', r'\1 / \2', text)
    # 括号与前后单词粘连 (e.g. (Use -> ( Use, tutorial!) -> tutorial! ))
    text = re.sub(r'\(([A-Za-z])', r'( \1', text)
    text = re.sub(r'([A-Za-z])\)', r'\1 )', text)

    # 3. 驼峰命名拆分 (e.g. PeopleCall -> People Call, GladYou -> Glad You, Whomade -> Who made)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # 4. 逐词检测与拆分粘连词
    tokens = text.split()
    result_tokens = []
    
    for token in tokens:
        # 分离前缀标点、主体词、后缀标点 (e.g. '(thisgame.' -> '(', 'thisgame', '.')
        m = re.match(r'^([^A-Za-z0-9]*)([A-Za-z0-9]+(?:\'[A-Za-z0-9]+)?)([^A-Za-z0-9]*)$', token)
        if not m:
            result_tokens.append(token)
            continue
        prefix, word, suffix = m.groups()
        low = word.lower()

        # 如果已经是词表已知单词或 NGU 专属术语，且长度不算过长，直接保留
        if low in NGU_GLOSSARY or (low in wordsegment.UNIGRAMS and len(word) < 14):
            result_tokens.append(token)
            continue

        # 尝试分词拆分
        segmented = wordsegment.segment(word)
        if len(segmented) > 1:
            # 校验拆分出来的词是否合理 (每个小词在词频库中，或是极短合法代词)
            if all(s in wordsegment.UNIGRAMS for s in segmented):
                if word[0].isupper():
                    fixed_word = segmented[0].capitalize() + (' ' + ' '.join(segmented[1:]) if len(segmented) > 1 else '')
                else:
                    fixed_word = ' '.join(segmented)
                # 修复固定搭配
                fixed_word = re.sub(r'\barrow son\b', 'arrows on', fixed_word)
                result_tokens.append(f'{prefix}{fixed_word}{suffix}')
                continue

        result_tokens.append(token)

    # 清理多余空格，保证标点排版地道自然
    clean = ' '.join(result_tokens)
    clean = re.sub(r'\s+([,\.!\?:;\)])', r'\1', clean)
    clean = re.sub(r'(\()\s+', r'\1', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)
    return clean.strip()

def fix_jammed_words(text: str) -> str:
    """兼容旧接口"""
    return clean_ocr_text(text)

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

        lines = [clean_ocr_text(b[1].strip()) for b in ordered_boxes if b[1].strip()]

        if is_multi_column:
            # 多列设置/菜单界面：保留换行结构，以便清晰展示各项
            full_text = "\n".join(lines)
        else:
            # 普通段落/句子描述：按空格拼接并优化连字符排版
            full_text = " ".join(lines)
            full_text = full_text.replace("- ", "").strip()
            # 跨行跨框二次排版清洗
            full_text = clean_ocr_text(full_text)
        
        return full_text, lines
