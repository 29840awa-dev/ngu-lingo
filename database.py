# -*- coding: utf-8 -*-
"""
SQLite 数据库模块：保存生词本、例句、游戏机制解析及复习状态
"""
import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "ngu_vocab.db")

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
    # 自动清理历史遗留被截断带有省略号的残缺释义
    cursor.execute("DELETE FROM dict_cache WHERE translation LIKE '%...' OR translation LIKE '%…'")
    conn.commit()

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

def get_cached_sentence(text: str):
    if not text or not text.strip():
        return None
    import hashlib
    h = hashlib.md5(text.strip().lower().encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT zh_trans FROM sentence_cache WHERE hash = ?", (h,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_cached_sentence(text: str, trans: str):
    if not text or not text.strip() or not trans or not trans.strip():
        return
    import hashlib
    h = hashlib.md5(text.strip().lower().encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO sentence_cache (hash, en_text, zh_trans)
        VALUES (?, ?, ?)
    """, (h, text.strip(), trans.strip()))
    conn.commit()
    conn.close()

# 初始化数据库
init_db()
