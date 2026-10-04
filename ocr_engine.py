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
    tokens = text.split()
    fixed_tokens = []
    for token in tokens:
        m = re.match(r'^([A-Za-z]+)([^A-Za-z]*)$', token)
        if m:
            word, punct = m.groups()
            # 只有长度较长的单词才进行检测拆分
            if len(word) >= 7:
                segmented = wordsegment.segment(word)
                if len(segmented) > 1:
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
        识别图像并返回组合好的文本以及按行分块的识别结果
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

        lines = []
        for item in result:
            box, text, score = item[0], item[1], item[2]
            if float(score) > 0.4:
                lines.append(text.strip())

        full_text = " ".join(lines)
        # 优化英语排版（修补被换行断开的连字符）
        full_text = full_text.replace("- ", "").strip()
        # 自动分词修复粘连单词
        full_text = fix_jammed_words(full_text)
        
        return full_text, lines
