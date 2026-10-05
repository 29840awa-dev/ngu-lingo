# -*- coding: utf-8 -*-
"""
SQLite 数据库模块：保存生词本、例句、游戏机制解析及复习状态
"""
import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "ngu_vocab.db")

def normalize_text_key(text: str) -> str:
    """归一化英文文本以支持 OCR 容错（剔除 Unity 标签、格式化空白和标点）"""
    if not text:
        return ""
    import re
    # 移除 Unity 标签如 <b>, <color=green>, </b> 等
    clean = re.sub(r'<[^>]+>', '', text)
    # 统一各种单双引号和破折号
    clean = clean.replace("’", "'").replace("“", '"').replace("”", '"').replace("`", "'")
    # 保留纯字母数字并转小写
    return re.sub(r'[^a-zA-Z0-9]+', '', clean).lower()

def clean_unity_tags(text: str) -> str:
    """清除汉化文本中的 Unity 标记代码，呈现干净利落的中文字符"""
    if not text:
        return ""
    import re
    # 清除富文本标签
    clean = re.sub(r'<[^>]+>', '', text)
    # 还原转义换行符
    clean = clean.replace(r'\n', '\n')
    return clean.strip()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocab_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            phonetic TEXT,
            translation TEXT,
            context_sentence TEXT,
            lore_explanation TEXT,
            tag TEXT DEFAULT 'NGU',
            review_count INTEGER DEFAULT 0,
            mastery_level INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_reviewed TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dict_cache (
            word TEXT PRIMARY KEY,
            phonetic TEXT,
            translation TEXT,
            tag TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentence_cache (
            hash TEXT PRIMARY KEY,
            en_text TEXT,
            zh_trans TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_translations (
            en_text TEXT PRIMARY KEY,
            cn_text TEXT,
            norm_en TEXT
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_trans_norm ON game_translations (norm_en);")

    # 自动清理历史遗留被截断带有省略号的残缺释义
    cursor.execute("DELETE FROM dict_cache WHERE translation LIKE '%...' OR translation LIKE '%…'")
    # 自动清理历史遗留的 API 报错信息
    cursor.execute("DELETE FROM sentence_cache WHERE zh_trans LIKE '%LIMIT%' OR zh_trans LIKE '%MYMEMORY%' OR zh_trans LIKE '%EXCEEDED%'")
    conn.commit()

    # 检查并自动载入 NGU 官方汉化补丁语料包 (3,989 条地道文本)
    cursor.execute("SELECT COUNT(*) FROM game_translations")
    gt_count = cursor.fetchone()[0]
    json_path = os.path.join(os.path.dirname(__file__), "game_translations.json")
    if gt_count < 3000 and os.path.exists(json_path):
        try:
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                pairs = json.load(f)
            items = [(en, cn, normalize_text_key(en)) for en, cn in pairs.items() if en and cn]
            cursor.executemany("""
                INSERT OR REPLACE INTO game_translations (en_text, cn_text, norm_en)
                VALUES (?, ?, ?)
            """, items)
            conn.commit()
        except Exception:
            pass

    # 如果是首次启动且生词本为空，插入几个经典的 NGU 示范词卡
    cursor.execute("SELECT COUNT(*) FROM vocab_cards")
    if cursor.fetchone()[0] == 0:
        sample_cards = [
            ("Crappy", "/ˈkræpi/", "蹩脚的、垃圾的、糟糕的 (口语俚语)", "A slightly less crappy helmet.", "NGU 早期装备标志性词缀，作者用来嘲讽传统 RPG 一本正经的破烂新手装。", "幽默与俚语"),
            ("Cap", "/kæp/", "上限；达到上限", "Energy Cap: +10,000", "NGU 核心资源三大维度之一，决定你能同时分配并使用的最大能量/魔法池总量。", "数值机制"),
            ("Respawn", "/ˌriːˈspɔːn/", "怪物重生时间", "Respawn Rate: -5%", "Adventure 冒险模式极品属性，缩短怪物刷新间隔，大幅提高刷怪爆装和升级效率。", "冒险属性"),
            ("Multiplicatively", "/ˌmʌltɪˈplɪkətɪvli/", "乘法叠加 / 按乘数累加", "Increases power multiplicatively by 2%.", "与线性加法 (Additively) 相对，乘法加成随层数指数级爆发增长，是挂机游戏后期数值暴增的关键！", "数学/机制")
        ]
        for w, p, tr, ctx, lore, tag in sample_cards:
            cursor.execute("""
                INSERT INTO vocab_cards (word, phonetic, translation, context_sentence, lore_explanation, tag, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (w, p, tr, ctx, lore, tag, datetime.now()))
        conn.commit()

    conn.close()

def add_vocab_card(word: str, phonetic: str, translation: str, context_sentence: str, lore_explanation: str = "", tag: str = "NGU"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 检查是否已存在同名词汇
    cursor.execute("SELECT id, review_count FROM vocab_cards WHERE LOWER(word) = LOWER(?)", (word.strip(),))
    row = cursor.fetchone()
    if row:
        # 已存在则更新上下文和释义
        cursor.execute("""
            UPDATE vocab_cards 
            SET context_sentence = ?, translation = ?, lore_explanation = ?, tag = ?
            WHERE id = ?
        """, (context_sentence, translation, lore_explanation, tag, row[0]))
        card_id = row[0]
    else:
        cursor.execute("""
            INSERT INTO vocab_cards (word, phonetic, translation, context_sentence, lore_explanation, tag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (word.strip(), phonetic, translation, context_sentence, lore_explanation, tag, datetime.now()))
        card_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return card_id

def get_all_cards(search_query: str = ""):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if search_query:
        q = f"%{search_query.strip()}%"
        cursor.execute("""
            SELECT * FROM vocab_cards 
            WHERE word LIKE ? OR translation LIKE ? OR context_sentence LIKE ?
            ORDER BY created_at DESC
        """, (q, q, q))
    else:
        cursor.execute("SELECT * FROM vocab_cards ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def delete_card(card_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocab_cards WHERE id = ?", (card_id,))
    conn.commit()
    conn.close()

def update_review_progress(card_id: int, remembered: bool):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT review_count, mastery_level FROM vocab_cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()
    if row:
        cnt = row[0] + 1
        level = min(5, row[1] + 1) if remembered else max(0, row[1] - 1)
        cursor.execute("""
            UPDATE vocab_cards 
            SET review_count = ?, mastery_level = ?, last_reviewed = ?
            WHERE id = ?
        """, (cnt, level, datetime.now(), card_id))
        conn.commit()
    conn.close()

def get_cached_word(word: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT word, phonetic, translation, tag FROM dict_cache WHERE LOWER(word) = LOWER(?)", (word.strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        tr = row[2] or ""
        # 如果缓存的历史释义被截断带有省略号，自动放弃并重新拉取完整释义
        if tr.endswith("...") or tr.endswith("…"):
            return None
        return {"word": row[0], "phonetic": row[1] or "", "translation": tr, "tag": row[3] or "词汇"}
    return None

def set_cached_word(word: str, phonetic: str, translation: str, tag: str = "词汇"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO dict_cache (word, phonetic, translation, tag)
        VALUES (?, ?, ?, ?)
    """, (word.strip(), phonetic, translation, tag))
    conn.commit()
    conn.close()

def get_cached_sentence(text: str, prefix: str = ""):
    if not text or not text.strip():
        return None
    import hashlib
    key = f"{prefix}:{text.strip().lower()}" if prefix else text.strip().lower()
    h = hashlib.md5(key.encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT zh_trans FROM sentence_cache WHERE hash = ?", (h,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        val = row[0].strip()
        if "LIMIT EXCEEDED" in val.upper() or "MYMEMORY" in val.upper():
            return None
        return val
    return None

def set_cached_sentence(text: str, trans: str, prefix: str = ""):
    if not text or not text.strip() or not trans or not trans.strip():
        return
    upper_trans = trans.upper()
    if "LIMIT EXCEEDED" in upper_trans or "MYMEMORY" in upper_trans or "ERROR" in upper_trans:
        return
    import hashlib
    key = f"{prefix}:{text.strip().lower()}" if prefix else text.strip().lower()
    h = hashlib.md5(key.encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO sentence_cache (hash, en_text, zh_trans)
        VALUES (?, ?, ?)
    """, (h, text.strip(), trans.strip()))
    conn.commit()
    conn.close()

def get_game_translation(en_text: str):
    """
    从 NGU 官方原生汉化语料库中检索整句翻译（0ms 本地秒出）：
    1. 精确原样匹配
    2. 归一化匹配（消除大小写、OCR换行与空格差异、Unity富文本标签）
    3. 常见标点/尾部字符容错
    """
    if not en_text or not en_text.strip():
        return None
    clean = en_text.strip()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # 1. 优先查原样精准匹配
        cursor.execute("SELECT cn_text FROM game_translations WHERE en_text = ?", (clean,))
        row = cursor.fetchone()
        if row and row[0]:
            return clean_unity_tags(row[0])

        # 2. 查归一化匹配 (大小写、空格、Unity标签容错)
        norm = normalize_text_key(clean)
        if norm:
            cursor.execute("SELECT cn_text FROM game_translations WHERE norm_en = ? LIMIT 1", (norm,))
            row = cursor.fetchone()
            if row and row[0]:
                return clean_unity_tags(row[0])

            # 3. 容错尾部标点符号或轻微截断差异
            if len(norm) >= 12:
                prefix = norm[:min(len(norm), 35)]
                cursor.execute("SELECT cn_text, norm_en FROM game_translations WHERE norm_en LIKE ? LIMIT 1", (f"{prefix}%",))
                row = cursor.fetchone()
                if row and row[0]:
                    # 避免长短悬殊误判
                    db_norm = row[1] or ""
                    if abs(len(db_norm) - len(norm)) <= max(8, int(len(norm) * 0.2)):
                        return clean_unity_tags(row[0])
    except Exception:
        pass
    finally:
        conn.close()
    return None

def get_game_term_note(term: str):
    """
    查询单个单词或短语在游戏中是否有官方汉化专有名词对应
    若有且长度适合，返回其中文汉化译名（供词卡 Lore 字段丰富展示，绝不破坏词典基本释义）
    """
    if not term or not term.strip():
        return None
    clean = term.strip()
    norm = normalize_text_key(clean)
    if not norm or len(norm) < 2:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT cn_text FROM game_translations WHERE norm_en = ? LIMIT 1", (norm,))
        row = cursor.fetchone()
        if row and row[0]:
            clean_cn = clean_unity_tags(row[0])
            # 专有名词/短语翻译通常较简短（<= 30字符）且不与原文完全雷同
            if 0 < len(clean_cn) <= 30 and clean_cn.lower() != clean.lower():
                return clean_cn
    except Exception:
        pass
    finally:
        conn.close()
    return None

def reindex_game_translations():
    """重新全量同步并归一化索引 game_translations 表"""
    json_path = os.path.join(os.path.dirname(__file__), "game_translations.json")
    if not os.path.exists(json_path):
        return 0
    import json
    with open(json_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    items = [(en, cn, normalize_text_key(en)) for en, cn in pairs.items() if en and cn]
    cursor.executemany("INSERT OR REPLACE INTO game_translations (en_text, cn_text, norm_en) VALUES (?, ?, ?)", items)
    conn.commit()
    conn.close()
    return len(items)

# 初始化数据库
init_db()
