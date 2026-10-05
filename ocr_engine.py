# -*- coding: utf-8 -*-
"""
本地 RapidOCR 引擎封装：支持快速离线识别屏幕截取图像中的文字，
具备高精度水平文本行聚类（Line Clustering）与智能自然阅读排序，
并内置深度英文黏连词修复与排版清洗。
"""
import re
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
import wordsegment
from ngu_knowledge import NGU_GLOSSARY, is_settings_menu_text

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
      - 紧密单词: thisgame -> this game, whomade -> who made, whichis -> which is
      - 常见数字/字母OCR混淆: 5o0 -> 500, 1o0 -> 100
    """
    if not raw_text:
        return ""

    # 0. 移除 OCR 异常控制字符与乱码符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd]', ' ', raw_text)

    # 1. 数字与字母混淆纠错 (如 5o0 -> 500)
    text = re.sub(r'(\d)[oO](\d)', r'\g<1>0\g<2>', text)
    text = re.sub(r'(\d)[oO]\b', r'\g<1>0', text)

    # 2. 游戏特有专有词与排版的先验精准修复
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

    # 3. 标点符号与字母之间缺失空格的规范化修复
    text = re.sub(r'([A-Za-z0-9])([,\.!\?:;])([A-Za-z])', r'\1\2 \3', text)
    text = re.sub(r'([A-Za-z0-9])/([A-Za-z0-9])', r'\1 / \2', text)
    text = re.sub(r'\(([A-Za-z])', r'( \1', text)
    text = re.sub(r'([A-Za-z])\)', r'\1 )', text)

    # 4. 驼峰命名拆分 (e.g. PeopleCall -> People Call)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # 5. 逐词检测与拆分粘连词
    tokens = text.split()
    result_tokens = []
    
    for token in tokens:
        m = re.match(r'^([^A-Za-z0-9]*)([A-Za-z0-9]+(?:\'[A-Za-z0-9]+)?)([^A-Za-z0-9]*)$', token)
        if not m:
            result_tokens.append(token)
            continue
        prefix, word, suffix = m.groups()
        low = word.lower()

        # 如果已经是 NGU 专属术语，直接保留
        if low in NGU_GLOSSARY:
            result_tokens.append(token)
            continue

        # 尝试分词拆分
        segmented = wordsegment.segment(word)
        if len(segmented) > 1:
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
        识别图像并返回结构化文本。
        采用基于垂直几何重叠的水平文本行聚类算法（Line Clustering）：
        - 同一行内的文本块严格自左向右（X递增）按自然语序排列，彻底根治同行动词与主语倒置的问题；
        - 行与行之间按垂直自上向下排列；
        - 支持设置菜单独立换行与自然段落平滑拼接。
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

        # 提取各个检测框几何拓扑属性
        box_data = []
        for item in boxes:
            pts = item[0]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            box_data.append({
                'xmin': min(xs),
                'xmax': max(xs),
                'ymin': min(ys),
                'ymax': max(ys),
                'ymid': (min(ys) + max(ys)) / 2.0,
                'height': max(ys) - min(ys),
                'text': item[1]
            })

        # 初始按 Y 轴中线排序
        box_data.sort(key=lambda b: b['ymid'])

        # 水平行聚类：当两块垂直重叠超过 40% 时归为同一行
        line_groups = []
        for b in box_data:
            placed = False
            for lg in line_groups:
                lg_ymin = min(x['ymin'] for x in lg)
                lg_ymax = max(x['ymax'] for x in lg)
                lg_h = max(1.0, lg_ymax - lg_ymin)
                overlap = min(b['ymax'], lg_ymax) - max(b['ymin'], lg_ymin)
                if overlap > 0.4 * min(b['height'], lg_h):
                    lg.append(b)
                    placed = True
                    break
            if not placed:
                line_groups.append([b])

        # 行间严格按垂直位置从上至下排序
        line_groups.sort(key=lambda lg: sum(b['ymid'] for b in lg) / len(lg))

        # 行内文本块严格按水平位置从左至右（X递增）自然阅读排序
        lines = []
        for lg in line_groups:
            lg.sort(key=lambda b: b['xmin'])
            raw_line = " ".join(b['text'] for b in lg)
            cleaned_line = clean_ocr_text(raw_line)
            if cleaned_line:
                lines.append(cleaned_line)

        # 智能判定：若包含多条配置菜单项，保持换行结构；否则作为连贯自然段落拼接
        if is_settings_menu_text(" ".join(lines)):
            full_text = "\n".join(lines)
        else:
            full_text = " ".join(lines)
            full_text = full_text.replace("- ", "").strip()
            # 跨行排版二次清洗（解决跨行连字与标点问题）
            full_text = clean_ocr_text(full_text)
        
        return full_text, lines
