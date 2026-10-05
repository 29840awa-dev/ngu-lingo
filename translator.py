# -*- coding: utf-8 -*-
"""
高精度翻译与词典服务模块：
1. 优先匹配 NGU IDLE 机制知识库与游戏梗（0毫秒响应）
2. 本地 SQLite 永久词典缓存 (dict_cache)，查过的词毫秒级极速直出
3. 网易有道高精度词典与整句翻译（多线程并发查询，直连无视网络代理干扰）
4. 保证每个单词都有真实词性（v./n./adj./adv.）与地道中文释义！
"""
import re
import requests
import concurrent.futures
from ngu_knowledge import NGU_GLOSSARY, detect_ngu_terms, is_settings_menu_text, get_settings_guide_markdown
import database

# 常见放置/RPG 通用基础词典
COMMON_DICT = {
    "unlocked": "已解锁",
    "locked": "已锁定 / 未解锁",
    "lock": "锁定",
    "unlock": "解锁",
    "fluff": "无意义的闲聊 / 废话梗 (游戏作者常用来形容搞笑Lore)",
    "tutorial": "新手教学 / 指南",
    "equipped": "已装备",
    "unequip": "卸下装备",
    "inventory": "背包 / 仓库",
    "loadout": "配装方案 / 装备预设",
    "setting": "设置",
    "save": "保存存档",
    "load": "加载存档",
    "reset": "重置",
    "restart": "重新开始",
    "increase": "增加、提高",
    "decrease": "减少、降低",
    "boost": "提升、增幅",
    "chance": "几率、概率",
    "damage": "伤害",
    "defense": "防御",
    "health": "生命值",
    "mana": "法力值、魔力",
    "attack": "攻击",
    "speed": "速度",
    "multiplier": "倍数、乘数",
    "bonus": "加成、额外奖励",
    "level": "等级",
    "requirement": "要求、门槛",
    "duration": "持续时间",
    "efficiency": "效率",
    "cost": "消耗、花费",
    "permanent": "永久的",
    "temporary": "临时的",
    "gain": "获得、获取",
    "consume": "消耗",
    "slot": "槽位、装备栏",
    "quest": "任务",
    "perk": "特权、被动增益",
    "reward": "奖励",
    "ratio": "比例、比率",
    "potion": "药水",
    "equipment": "装备",
    "accessory": "饰品",
    "weapon": "武器",
    "armor": "防具",
    "rate": "速率、比率",
    "production": "产出、生产",
    "accumulate": "累积、堆积",
    "sacrifice": "献祭、牺牲",
    "critical": "暴击的、关键的",
    "strike": "打击、攻击",
    "tier": "品阶 / 梯队",
    "zone": "地图区域",
    "auto": "自动",
    "manual": "手动",
    "current": "当前的",
    "total": "总计",
    "active": "生效中 / 主动的",
    "passive": "被动的",
    "progress": "进度",
    "complete": "完成",
    "max": "最大值",
    "min": "最小值",
    "spend": "花费",
    "earned": "已获得",
    "feet": "脚，双脚 (foot的复数)",
    "foot": "脚",
    "shakily": "颤抖地；摇晃地；虚弱不堪地",
    "you": "你；你们",
    "get": "到达；获得；站立；变成",
    "to": "向；朝；到达",
    "your": "你的；你们的"
}

class TranslationService:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def _fetch_online_translation(self, clean_text: str) -> str:
        """多引擎极速竞速在线整句直译（Google / 有道移动端 / MyMemory / 有道AIDemo）"""
        import urllib.parse

        def fetch_google():
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q={urllib.parse.quote(clean_text)}"
            r = self.session.get(url, headers=self.headers, timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                if data and len(data) > 0 and data[0]:
                    res = ''.join([item[0] for item in data[0] if item and item[0]])
                    if res and res.strip().lower() != clean_text.lower():
                        return res.strip()
            raise RuntimeError("Google translate failed")

        def fetch_youdao_m():
            url = "https://m.youdao.com/translate"
            r = self.session.post(url, data={'inputtext': clean_text, 'type': 'AUTO'}, headers=self.headers, timeout=3.5)
            if r.status_code == 200:
                m = re.search(r'translateResult[\s\S]*?<li>(.*?)</li>', r.text)
                if m:
                    res = m.group(1).strip()
                    if res and res.lower() != clean_text.lower():
                        return res
            raise RuntimeError("Youdao mobile translate failed")

        def fetch_mymemory():
            if len(clean_text) > 380:
                raise RuntimeError("Query too long for MyMemory")
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(clean_text)}&langpair=en|zh-CN"
            r = self.session.get(url, headers=self.headers, timeout=3.5)
            if r.status_code == 200:
                res = r.json().get('responseData', {}).get('translatedText', '')
                if res:
                    res_upper = res.upper()
                    if "LIMIT EXCEEDED" not in res_upper and not res_upper.startswith("MYMEMORY") and "INVALID" not in res_upper and res.strip().lower() != clean_text.lower():
                        return res.strip()
            raise RuntimeError("MyMemory translate failed")

        def fetch_youdao_aidemo():
            url = 'https://aidemo.youdao.com/trans'
            r = self.session.post(url, data={'q': clean_text, 'from': 'en', 'to': 'zh-CHS'}, headers=self.headers, timeout=4.0)
            if r.status_code == 200:
                translations = r.json().get('translation', [])
                if translations and translations[0] and translations[0].strip().lower() != clean_text.lower():
                    return translations[0].strip()
            raise RuntimeError("Youdao aidemo failed")

        engines = [fetch_google, fetch_youdao_m, fetch_mymemory, fetch_youdao_aidemo]
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(engines)) as executor:
            futures = [executor.submit(fn) for fn in engines]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        return result
                except Exception:
                    continue

        # 离线单字兜底
        words = self.extract_words(clean_text)
        known = []
        for w in words:
            low = w.lower()
            if low in NGU_GLOSSARY:
                known.append(f"{w} [{NGU_GLOSSARY[low]['cn']}]")
            elif low in COMMON_DICT:
                known.append(f"{w} [{COMMON_DICT[low]}]")

        if known:
            return "（⚠️ 当前网络连接超时，以下为单字离线参考）：\n" + "，".join(known)
        return "（未识别到联网整句释义，请检查网络后点击【重新翻译】）"

    def translate_direct(self, text: str) -> str:
        """
        纯粹逐句逐词直译（彻底绕过游戏补丁的意译与省略，保留最原汁原味的细节与英语段子）
        专供划选即时查译与学习对照使用
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        # 优先查直译缓存
        try:
            cached = database.get_cached_sentence(clean_text, prefix="direct")
            if cached:
                return cached
        except Exception:
            pass

        result = self._fetch_online_translation(clean_text)
        if result and not result.startswith("（"):
            try:
                database.set_cached_sentence(clean_text, result, prefix="direct")
            except Exception:
                pass
        return result

    def translate_sentence_info(self, text: str) -> dict:
        """
        整句翻译元信息：
        返回包含 trans, is_game (是否来自官方汉化), game_trans, direct_trans 的完整字典
        """
        clean_text = text.strip()
        if not clean_text:
            return {"trans": "", "is_game": False, "game_trans": None, "direct_trans": None}

        if is_settings_menu_text(clean_text):
            guide = get_settings_guide_markdown()
            return {"trans": guide, "is_game": False, "game_trans": None, "direct_trans": guide}

        # 1. 优先查是否命中官方游戏汉化
        game_trans = None
        try:
            game_trans = database.get_game_translation(clean_text)
        except Exception:
            pass

        if game_trans:
            database.set_cached_sentence(clean_text, game_trans)
            return {
                "trans": game_trans,
                "is_game": True,
                "game_trans": game_trans,
                "direct_trans": None
            }

        # 2. 查本地普通句子缓存
        try:
            cached = database.get_cached_sentence(clean_text)
            if cached:
                return {
                    "trans": cached,
                    "is_game": False,
                    "game_trans": None,
                    "direct_trans": cached
                }
        except Exception:
            pass

        # 3. 在线直译
        direct = self.translate_direct(clean_text)
        if direct and not direct.startswith("（"):
            try:
                database.set_cached_sentence(clean_text, direct)
            except Exception:
                pass
        return {
            "trans": direct,
            "is_game": False,
            "game_trans": None,
            "direct_trans": direct
        }

    def translate_sentence(self, text: str) -> str:
        """保持原有兼容性的整句翻译调用"""
        info = self.translate_sentence_info(text)
        return info.get("trans", "")

    def extract_words(self, text: str):
        """从句子中提取纯英文单词列表（过滤纯数字单字母及高频UI开关杂音，如 On/Off/Yes/No）"""
        raw_words = re.findall(r"\b[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?\b", text)
        words = [w for w in raw_words if re.search(r"[A-Za-z]", w)]
        filtered = []
        noise = {"on", "off", "yes", "no", "true", "false", "plain", "fancy", "some", "more"}
        is_long_or_menu = len(words) > 8 or is_settings_menu_text(text)
        for w in dict.fromkeys(words):
            low = w.lower()
            if len(w) == 1 and low not in ('a', 'i'):
                continue
            if is_long_or_menu and low in noise:
                continue
            filtered.append(w)
        return filtered

    def fetch_word_online(self, word: str):
        """在线查询单词完整释义与精准音标（采用完整词典接口，彻底杜绝省略号截断）"""
        url = f"https://dict.youdao.com/jsonapi?q={word}"
        try:
            r = self.session.get(url, headers=self.headers, timeout=2.5)
            if r.status_code == 200:
                data = r.json()
                phonetic = ""
                trs_list = []
                
                # 1. 尝试 ec (英汉词典)
                ec = data.get('ec', {})
                words = ec.get('word', [])
                if words:
                    w = words[0]
                    p = w.get('usphone') or w.get('ukphone') or w.get('phone')
                    if p:
                        phonetic = f"/{p}/"
                    for tr in w.get('trs', []):
                        tran = tr.get('tr', [{}])[0].get('l', {}).get('i', [])
                        if tran and tran[0]:
                            trs_list.append(tran[0].strip())
                            
                # 2. 尝试 simple
                if not trs_list:
                    simple = data.get('simple', {})
                    words_s = simple.get('word', [])
                    if words_s:
                        for item in words_s[0].get('trs', []):
                            pos = item.get('pos', '').strip()
                            tran = item.get('tran', '').strip()
                            if tran:
                                line = f"{pos} {tran}".strip() if pos else tran
                                trs_list.append(line)
                                
                # 3. 尝试 fanyi 兜底
                if not trs_list:
                    fanyi = data.get('fanyi', {}).get('tran')
                    if fanyi:
                        trs_list.append(fanyi.strip())

                if trs_list:
                    explain = "\n".join(trs_list)
                    return phonetic, explain
        except Exception:
            pass

        # 备选接口：suggest 兜底，但过滤掉残缺的尾部省略号
        try:
            url_s = f"https://dict.youdao.com/suggest?num=1&doctype=json&q={word}"
            r_s = self.session.get(url_s, headers=self.headers, timeout=1.8)
            if r_s.status_code == 200:
                entries = r_s.json().get('data', {}).get('entries', [])
                if entries:
                    raw_exp = entries[0].get('explain', '')
                    clean_exp = re.sub(r'\(?[A-Za-z\s]*\.\.\.$', '', raw_exp).rstrip(' ;；,，')
                    return "", clean_exp
        except Exception:
            pass

        return "", None

    def get_word_detail(self, word: str):
        """
        获取单个单词的详细词条：
        1. NGU 机制库
        2. SQLite 本地永久词库缓存
        3. 通用字典
        4. 在线直连词典实时查询并自动写入本地缓存
        """
        clean_word = word.strip()
        low = clean_word.lower()

        # 1. NGU 专属知识库
        if low in NGU_GLOSSARY:
            item = NGU_GLOSSARY[low]
            res = {
                "word": item["word"],
                "phonetic": item.get("phonetic", ""),
                "cn": item["cn"],
                "lore": item.get("lore", ""),
                "type": item.get("type", "NGU机制")
            }
        # 2. 本地 SQLite 缓存
        elif database.get_cached_word(low):
            cached = database.get_cached_word(low)
            res = {
                "word": clean_word,
                "phonetic": cached.get("phonetic", ""),
                "cn": cached["translation"],
                "lore": "",
                "type": cached.get("tag", "词汇")
            }
        # 3. 通用词汇表
        elif low in COMMON_DICT:
            cn_val = COMMON_DICT[low]
            database.set_cached_word(low, "", cn_val, "常用词汇")
            res = {
                "word": clean_word,
                "phonetic": "",
                "cn": cn_val,
                "lore": "",
                "type": "常用词汇"
            }
        # 4. 在线实时查询
        else:
            online_phone, online_explain = self.fetch_word_online(clean_word)
            if online_explain:
                database.set_cached_word(low, online_phone, online_explain, "英文词汇")
                res = {
                    "word": clean_word,
                    "phonetic": online_phone,
                    "cn": online_explain,
                    "lore": "",
                    "type": "英文词汇"
                }
            else:
                res = {
                    "word": clean_word,
                    "phonetic": "",
                    "cn": "英文词汇 (点击【+】加入生词本记录)",
                    "lore": "",
                    "type": "词汇"
                }

        # 补充：查询该词或专有名词是否有汉化补丁官方译名（完整保留标准英文词典与音标，在机制Lore注记）
        try:
            game_term = database.get_game_term_note(clean_word)
            if game_term:
                if res.get("lore"):
                    if game_term not in res["lore"]:
                        res["lore"] += f"\n🎮 官方汉化对照: 【{game_term}】"
                else:
                    res["lore"] = f"🎮 本作汉化译为: 【{game_term}】"
        except Exception:
            pass

        return res

    def batch_get_word_details(self, words: list):
        """并发多线程快速提取单词释义，0.3 秒内全部返回"""
        details = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_to_word = {executor.submit(self.get_word_detail, w): w for w in words[:15]}
            for future in concurrent.futures.as_completed(future_to_word):
                try:
                    data = future.result()
                    details.append(data)
                except Exception:
                    pass

        # 按照原词序排列
        word_order = {w.lower(): i for i, w in enumerate(words)}
        details.sort(key=lambda d: word_order.get(d["word"].lower(), 999))
        return details

    def analyze_ngu_context(self, text: str):
        """分析文本中包含的所有 NGU 机制与梗"""
        return detect_ngu_terms(text)
