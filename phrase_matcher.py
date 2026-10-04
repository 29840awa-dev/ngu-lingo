# -*- coding: utf-8 -*-
"""
短语与习语匹配器 (Phrase & Idiom Matcher)
支持：
1. 常见动词短语与固定习语（支持代词屈折变化，如 get to your/his/her feet）
2. 游戏与放置系统复合词组（如 set bonus, drop chance, diminishing returns）
3. 2~4 词连续组合在线词典探查与本地 SQLite 缓存
"""
import re
import urllib.parse
import requests
import database

# 核心离线短语与习语库 (涵盖经典搭配与游戏高频词组)
COMMON_PHRASES = [
    # === 经典习惯用语与动词短语 (带正则模式) ===
    {
        "pattern": r"\bget\s+to\s+(?:your|my|his|her|their|our|one's)\s+feet\b",
        "display": "get to one's feet",
        "cn": "站起来；挣扎着站立",
        "type": "固定习语",
        "lore": "指从坐着、躺着或虚弱倒地的状态中站立起来。在 RPG 剧情开场中极常见！"
    },
    {
        "pattern": r"\bdeal(?:\s+massive|\s+extra)?\s+damage\b",
        "display": "deal damage",
        "cn": "造成伤害",
        "type": "战斗短语",
        "lore": "游戏战斗中的核心动作描述，与 take damage (受到伤害) 相对。"
    },
    {
        "pattern": r"\btake(?:\s+massive|\s+extra)?\s+damage\b",
        "display": "take damage",
        "cn": "受到伤害 / 承受伤害",
        "type": "战斗短语",
        "lore": "指自身生命值扣减。"
    },
    {
        "pattern": r"\blevel\s+up\b",
        "display": "level up",
        "cn": "升级 / 等级提升",
        "type": "游戏短语",
        "lore": "角色或技能升级的标志性短语。"
    },
    {
        "pattern": r"\bpick\s+up\b",
        "display": "pick up",
        "cn": "捡起 / 拾取；学会",
        "type": "动词短语",
        "lore": "在游戏中常指捡起战利品 (loot)。"
    },
    {
        "pattern": r"\bset\s+bonus\b",
        "display": "set bonus",
        "cn": "套装效果 / 套装加成",
        "type": "装备短语",
        "lore": "集齐并升满全套同系列装备后激活的专属被动奖励。"
    },
    {
        "pattern": r"\bdrop\s+chance\b",
        "display": "drop chance",
        "cn": "掉落几率 (DC)",
        "type": "属性短语",
        "lore": "打怪掉落战利品的概率。"
    },
    {
        "pattern": r"\brespawn\s+rate\b",
        "display": "respawn rate",
        "cn": "怪物重生速率",
        "type": "冒险短语",
        "lore": "刷怪节奏的核心属性，缩短怪物刷新等待。"
    },
    {
        "pattern": r"\bcooldown\s+reduction\b",
        "display": "cooldown reduction",
        "cn": "冷却缩减 (CDR)",
        "type": "技能短语",
        "lore": "加快技能再次施放的循环时间。"
    },
    {
        "pattern": r"\bdiminishing\s+returns\b",
        "display": "diminishing returns",
        "cn": "边际收益递减",
        "type": "机制短语",
        "lore": "投入越多资源，单位提升效果逐步收窄的数学曲线。"
    },
    {
        "pattern": r"\benergy\s+cap\b",
        "display": "energy cap",
        "cn": "能量上限",
        "type": "NGU系统",
        "lore": "决定你当前能同时分配的能量总池容量。"
    },
    {
        "pattern": r"\benergy\s+power\b",
        "display": "energy power",
        "cn": "能量效率/力量",
        "type": "NGU系统",
        "lore": "决定能量运转与升级项目的推进速度。"
    },
    {
        "pattern": r"\benergy\s+bars\b",
        "display": "energy bars",
        "cn": "能量回复/充能速度",
        "type": "NGU系统",
        "lore": "决定每秒能量充填速度。"
    },
    {
        "pattern": r"\bmagic\s+cap\b",
        "display": "magic cap",
        "cn": "魔法上限",
        "type": "NGU系统",
        "lore": "魔法资源的容量池大小。"
    },
    {
        "pattern": r"\bblood\s+magic\b",
        "display": "blood magic",
        "cn": "血魔法",
        "type": "NGU系统",
        "lore": "献祭魔法获取血液施法的特色系统。"
    },
    {
        "pattern": r"\btime\s+machine\b",
        "display": "time machine",
        "cn": "时光机 (GPS系统)",
        "type": "NGU系统",
        "lore": "随着时间推移大量飙升每秒金币 (GPS) 的挂机系统。"
    },
    {
        "pattern": r"\bgold\s+digger\b",
        "display": "gold digger",
        "cn": "金币挖掘机 / 拜金者",
        "type": "NGU系统",
        "lore": "消耗持续金币以激活属性加成的系统；也是英文里的双关梗。"
    },
    {
        "pattern": r"\bat\s+least\b",
        "display": "at least",
        "cn": "至少；起码",
        "type": "常见介词短语",
        "lore": "表示最低限度或让步。"
    },
    {
        "pattern": r"\bas\s+well\s+as\b",
        "display": "as well as",
        "cn": "以及；而且；不仅…而且…",
        "type": "连词短语",
        "lore": "常用来并列增加额外属性或效果。"
    },
    {
        "pattern": r"\bin\s+order\s+to\b",
        "display": "in order to",
        "cn": "为了；以便",
        "type": "介词短语",
        "lore": "引导目的状语。"
    },
    {
        "pattern": r"\bas\s+soon\s+as\b",
        "display": "as soon as",
        "cn": "一…就…；尽快",
        "type": "连词短语",
        "lore": "常用于条件触发判定。"
    },
    {
        "pattern": r"\bno\s+longer\b",
        "display": "no longer",
        "cn": "不再；已不",
        "type": "副词短语",
        "lore": "表示状态终止。"
    },
    {
        "pattern": r"\bout\s+of\b",
        "display": "out of",
        "cn": "出于；由于；耗尽 / 缺乏",
        "type": "介词短语",
        "lore": "如 out of mana (法力耗尽)。"
    },
    {
        "pattern": r"\bmake\s+sure\b",
        "display": "make sure",
        "cn": "确保；核实",
        "type": "动词短语",
        "lore": "新手指导经常使用的短语。"
    },
    {
        "pattern": r"\bso\s+far\b",
        "display": "so far",
        "cn": "到目前为止；迄今",
        "type": "副词短语",
        "lore": "常用于统计进度或成就阶段。"
    },
    {
        "pattern": r"\bright\s+now\b",
        "display": "right now",
        "cn": "立刻；眼下",
        "type": "时间短语",
        "lore": "强调即时生效。"
    },
    {
        "pattern": r"\beven\s+though\b",
        "display": "even though",
        "cn": "即使；尽管",
        "type": "连词短语",
        "lore": "表示转折与让步。"
    },
    {
        "pattern": r"\bsuch\s+as\b",
        "display": "such as",
        "cn": "例如；诸如",
        "type": "短语介词",
        "lore": "列举范例。"
    },
    {
        "pattern": r"\bup\s+to\b",
        "display": "up to",
        "cn": "多达；由…决定；胜任",
        "type": "介词短语",
        "lore": "如 'increases up to 50%' (最高可达 50%)。"
    },
    {
        "pattern": r"\bbased\s+on\b",
        "display": "based on",
        "cn": "基于；根据",
        "type": "介词短语",
        "lore": "表示数值计算根据某个基准决定。"
    }
]

class PhraseMatcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False

    def detect_phrases(self, sentence: str) -> list:
        """
        在输入的英文句子中自动检测识别所有出现的短语与固定搭配
        返回识别到的短语详情列表
        """
        matches = []
        seen_spans = []

        # 1. 扫描内置高频短语库与正则模式
        for item in COMMON_PHRASES:
            for m in re.finditer(item["pattern"], sentence, re.IGNORECASE):
                span = (m.start(), m.end())
                # 避免重复重叠
                if not any(s[0] <= span[0] and s[1] >= span[1] for s in seen_spans):
                    actual_text = sentence[span[0]:span[1]]
                    matches.append({
                        "phrase": actual_text,
                        "display": item["display"],
                        "cn": item["cn"],
                        "type": item["type"],
                        "lore": item.get("lore", ""),
                        "start": span[0],
                        "end": span[1]
                    })
                    seen_spans.append(span)

        # 2. 如果还有其他未被内置匹配的 2~3 词连续组合，尝试本地 SQLite 缓存
        words = re.findall(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b", sentence)
        for n in [3, 2]: # 优先查 3 词短语，再查 2 词短语
            for i in range(len(words) - n + 1):
                ngram = " ".join(words[i:i+n]).lower()
                cached = database.get_cached_word(ngram)
                if cached:
                    if not any(m["phrase"].lower() == ngram for m in matches):
                        matches.append({
                            "phrase": " ".join(words[i:i+n]),
                            "display": ngram,
                            "cn": cached["translation"],
                            "type": "词组短语",
                            "lore": "",
                            "start": 0,
                            "end": 0
                        })

        return matches

    def fetch_phrase_online(self, phrase_str: str):
        """在线实时查任意自选短语词义"""
        clean_p = phrase_str.strip().lower()
        # 1. 查缓存
        cached = database.get_cached_word(clean_p)
        if cached:
            return cached["translation"]

        # 2. 查有道
        try:
            url = f"https://dict.youdao.com/suggest?num=1&doctype=json&q={urllib.parse.quote(clean_p)}"
            r = self.session.get(url, timeout=2.0)
            if r.status_code == 200:
                entries = r.json().get('data', {}).get('entries', [])
                if entries:
                    explain = entries[0].get('explain', '')
                    database.set_cached_word(clean_p, "", explain, "短语词组")
                    return explain
        except Exception:
            pass

        return None
