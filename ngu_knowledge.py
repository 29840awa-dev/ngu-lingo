# -*- coding: utf-8 -*-
"""
NGU IDLE 专属术语、俚语、梗与游戏机制知识库
"""

NGU_GLOSSARY = {
    # === 核心资源与基础系统 ===
    "energy": {
        "word": "Energy",
        "phonetic": "/ˈenədʒi/",
        "pos": "n.",
        "cn": "能量",
        "lore": "NGU 的三大基础资源之一。用于训练技能、强化、血魔法等，受 Cap、Power、Bars 三重属性控制。",
        "type": "核心系统"
    },
    "magic": {
        "word": "Magic",
        "phonetic": "/ˈmædʒɪk/",
        "pos": "n.",
        "cn": "魔法",
        "lore": "Boss 37 后解锁的第二大基础资源。机制与 Energy 类似，用于更高级的 Ritual、血魔法和特殊 NGU 技能。",
        "type": "核心系统"
    },
    "r3": {
        "word": "Res3 / R3",
        "phonetic": "",
        "pos": "n.",
        "cn": "第三资源 (Resource 3)",
        "lore": "中后期解锁的第三种神秘资源，消耗速率非常高，用于解锁 Hack 系统。",
        "type": "核心系统"
    },
    "cap": {
        "word": "Cap",
        "phonetic": "/kæp/",
        "pos": "n./v.",
        "cn": "上限；达到上限",
        "lore": "在 NGU 中指能量/魔法的【容量上限】(Maximum Energy/Magic Pool)。例如 Energy Cap 决定了你一共能同时分配多少能量。",
        "type": "数值机制"
    },
    "power": {
        "word": "Power",
        "phonetic": "/ˈpaʊə(r)/",
        "pos": "n.",
        "cn": "功率 / 力量 / 效率",
        "lore": "在 E/M 栏中指【产出与运转速度效率】；在 Adventure 栏中指你的【基础攻击力】(Power)。",
        "type": "数值机制"
    },
    "bars": {
        "word": "Bars",
        "phonetic": "/bɑːz/",
        "pos": "n.",
        "cn": "充能条 / 回复速度",
        "lore": "决定每秒 Energy/Magic 的回复与充能频率。新手阶段经典的 1:37500:1 (Cap : Power : Bars) 配比指南就是指这三个属性！",
        "type": "数值机制"
    },
    "rebirth": {
        "word": "Rebirth",
        "phonetic": "/ˌriːˈbɜːθ/",
        "pos": "n./v.",
        "cn": "转生 / 重生",
        "lore": "挂机游戏经典重置机制。清空当前临时进度（如基础攻击力、金币），换取永久性加成（Boss 击杀奖励的 EXP 和永久倍率）。",
        "type": "核心系统"
    },
    "exp": {
        "word": "EXP",
        "phonetic": "/ɪkˈspɪəriəns/",
        "pos": "n.",
        "cn": "经验值 (Experience)",
        "lore": "游戏中最宝贵的长期硬通货。击败 Boss 或通过某些系统产出，用来永久升级 E/M 的三大属性或购买 Adventure 属性与特殊特权。",
        "type": "核心系统"
    },
    "bb": {
        "word": "BB (Bar Boost / Bar Breakdown)",
        "phonetic": "",
        "pos": "n./abbr.",
        "cn": "满条充能 / 跑条拉满",
        "lore": "指分配足够的 Bars 使每秒充能达到 50 帧满帧率上限，实现瞬间填满 (Cap full in 1 tick)。",
        "type": "术语简写"
    },
    "gps": {
        "word": "GPS",
        "phonetic": "",
        "pos": "abbr.",
        "cn": "每秒金币 (Gold Per Second)",
        "lore": "挂机游戏常见缩写，Time Machine 系统升级能极大提升你的 GPS。",
        "type": "术语简写"
    },

    # === 冒险与装备属性 (Adventure & Gear) ===
    "toughness": {
        "word": "Toughness",
        "phonetic": "/ˈtʌfnəs/",
        "pos": "n.",
        "cn": "韧性 / 防御力",
        "lore": "冒险模式 (Adventure) 中两大核心属性之一（Power 决定伤害，Toughness 决定受击防御和减伤）。简称 P/T。",
        "type": "冒险属性"
    },
    "respawn": {
        "word": "Respawn",
        "phonetic": "/ˌriːˈspɔːn/",
        "pos": "n./v.",
        "cn": "怪物重生时间",
        "lore": "Adventure 模式中怪物死亡到下一只刷新的时间间隔。Respawn Reduction (减少刷新时间) 是刷掉落与升级的神级属性！",
        "type": "冒险属性"
    },
    "drop chance": {
        "word": "Drop Chance",
        "phonetic": "/drɒp tʃɑːns/",
        "pos": "n.",
        "cn": "掉落几率 (DC)",
        "lore": "怪物掉落装备、金币和强化道具的几率。经常缩写为 DC。",
        "type": "冒险属性"
    },
    "cooldown reduction": {
        "word": "Cooldown Reduction",
        "phonetic": "/ˈkuːldaʊn rɪˈdʌkʃn/",
        "pos": "n.",
        "cn": "冷却缩减 (CDR)",
        "lore": "缩短技能再次施放等待时间，打泰坦 Boss (Titans) 必不可少的战斗属性。",
        "type": "冒险属性"
    },
    "special boost": {
        "word": "Special Boost",
        "phonetic": "/ˈspeʃl buːst/",
        "pos": "n.",
        "cn": "特殊属性强化石",
        "lore": "用于装备吃狗粮强化 (Cube Boost)，能专门提升非基础攻防的次要属性（如 DC, Respawn, Gold 等）。",
        "type": "冒险属性"
    },
    "set bonus": {
        "word": "Set Bonus",
        "phonetic": "/set ˈbəʊnəs/",
        "pos": "n.",
        "cn": "套装效果 / 套装奖励",
        "lore": "NGU 的核心乐趣之一！将某一张图的全套装备全部升到 100 级 (Level 100)，会激活极具诱惑力且带搞笑说明的永久套装加成！",
        "type": "冒险属性"
    },
    "titans": {
        "word": "Titans",
        "phonetic": "/ˈtaɪtnz/",
        "pos": "n.",
        "cn": "泰坦 Boss",
        "lore": "各阶段的关底大 Boss（如 Gordon Ramsay 捏他的厨神 Boss、Jake、UUG 等），拥有独立倒计时、专属机制和巨量掉落。",
        "type": "游戏机制"
    },

    # === 特色子系统 ===
    "wandoos": {
        "word": "Wandoos",
        "phonetic": "",
        "pos": "n.",
        "cn": "Wandoos 系统 (致敬 Windows 98/XP)",
        "lore": "一个以经典 Windows 操作系统为原型的辅助挂机系统，给它分配能量/魔法算力可以大幅增加你的总攻防。",
        "type": "游戏系统"
    },
    "yggdrasil": {
        "word": "Yggdrasil",
        "phonetic": "/ˈɪɡdrəsɪl/",
        "pos": "n.",
        "cn": "世界树 (北欧神话)",
        "lore": "种下神话之树，结出赋予永久属性、金币、魔力和经验的果实。每次转生可以吃果子获得巨额 Buff。",
        "type": "游戏系统"
    },
    "digger": {
        "word": "Gold Digger",
        "phonetic": "/ˈɡəʊld dɪɡə(r)/",
        "pos": "n.",
        "cn": "金币挖掘机",
        "lore": "消耗持续金币以激活各种针对性加成（EXP加成、掉率加成、攻防加成等）。双关语：在俚语中 Gold Digger 也指“拜金女/傍大款”。",
        "type": "游戏系统"
    },
    "beards": {
        "word": "Beards",
        "phonetic": "/bɪədz/",
        "pos": "n.",
        "cn": "胡子系统",
        "lore": "转生时间越长，胡须长得越浓密，提供的加成也越强。作者恶搞设计的纯粹挂机收益系统。",
        "type": "游戏系统"
    },
    "macguffin": {
        "word": "MacGuffin",
        "phonetic": "/məˈɡʌfɪn/",
        "pos": "n.",
        "cn": "麦高芬 (电影叙事术语)",
        "lore": "希区柯克提出的经典电影术语：指推动剧情发展但本身其实没有实际意义的道具。在游戏中是后期提供细微长效递增数值的收集道具！",
        "type": "文化与梗"
    },
    "blood magic": {
        "word": "Blood Magic",
        "phonetic": "/blʌd ˈmædʒɪk/",
        "pos": "n.",
        "cn": "血魔法",
        "lore": "献祭大量魔法来产生血液，用于施展 Rituals、产出金币或获得临时攻防。",
        "type": "游戏系统"
    },
    "augmentation": {
        "word": "Augmentation",
        "phonetic": "/ˌɔːɡmenˈteɪʃn/",
        "pos": "n.",
        "cn": "机械改装 / 强化增幅",
        "lore": "简称 Augs。每次转生期通过分配能量强化义肢或装备，快速飙升攻击防御数值。",
        "type": "游戏系统"
    },

    # === 游戏常用数值与计算数学概念 ===
    "multiplicatively": {
        "word": "Multiplicatively",
        "phonetic": "/ˌmʌltɪˈplɪkətɪvli/",
        "pos": "adv.",
        "cn": "乘法叠加 / 按乘数累加",
        "lore": "与 Additively（加法叠加）相对。在 RPG 和放置游戏中，乘法加成 (×1.2) 的收益随层数呈指数级增长，远强于简单的加法！",
        "type": "数学/机制"
    },
    "additively": {
        "word": "Additively",
        "phonetic": "/ˈædətɪvli/",
        "pos": "adv.",
        "cn": "加法叠加 / 线性累加",
        "lore": "基础收益按照固定的数额或百分比相加 (+10%, +20%)，后期容易遇到稀释现象。",
        "type": "数学/机制"
    },
    "diminishing returns": {
        "word": "Diminishing Returns",
        "phonetic": "/dɪˈmɪnɪʃɪŋ rɪˈtɜːnz/",
        "pos": "n.",
        "cn": "边际收益递减",
        "lore": "投入越多资源，后续获得的单位提升越来越小。提醒玩家不要把所有资源孤注一掷在单一系统上。",
        "type": "数学/机制"
    },
    "threshold": {
        "word": "Threshold",
        "phonetic": "/ˈθreʃhəʊld/",
        "pos": "n.",
        "cn": "门槛 / 阈值",
        "lore": "达到某个特定数值时触发质变效果（例如攻防达到一定门槛才能击破下一关怪物的护甲）。",
        "type": "数学/机制"
    },
    "stacking": {
        "word": "Stacking",
        "phonetic": "/ˈstækɪŋ/",
        "pos": "n./v.",
        "cn": "叠加 / 堆叠层数",
        "lore": "反复触发同一个效果使其层数不断增加，获取更高增益。",
        "type": "数学/机制"
    },

    # === NGU 常见自嘲、幽默装备与西方俚语 (Memes & Slangs) ===
    "crappy": {
        "word": "Crappy",
        "phonetic": "/ˈkræpi/",
        "pos": "adj.",
        "cn": "蹩脚的、垃圾的、糟糕的 (口语俚语)",
        "lore": "NGU 前期装备经典词缀，如 'A crappy stick'、'A slightly less crappy helmet'。作者 4G 专门用来嘲讽其他 RPG 游戏一本正经的破烂新手装。",
        "type": "幽默与俚语"
    },
    "gross": {
        "word": "Gross",
        "phonetic": "/ɡrəʊs/",
        "pos": "adj.",
        "cn": "恶心的 / 令人反感的；粗略的",
        "lore": "游戏早期下水道地图专属词，如 'Gross sock'、'Gross club'，完全不掩饰战利品有多脏！",
        "type": "幽默与俚语"
    },
    "doodad": {
        "word": "Doodad",
        "phonetic": "/ˈduːdæd/",
        "pos": "n.",
        "cn": "小玩意儿 / 不起眼的小配件",
        "lore": "指叫不出名字或懒得正经命名的小零件、小饰品。在游戏装备描述中经常出现。",
        "type": "幽默与俚语"
    },
    "shenanigans": {
        "word": "Shenanigans",
        "phonetic": "/ʃɪˈnænɪɡənz/",
        "pos": "n.",
        "cn": "搞把戏 / 恶作剧 / 猫腻",
        "lore": "形容各种荒谬、胡闹的行为。常出现在剧情事件或成就描述中指责玩家或作者乱搞骚操作。",
        "type": "幽默与俚语"
    },
    "cheese": {
        "word": "Cheese",
        "phonetic": "/tʃiːz/",
        "pos": "v./n.",
        "cn": "卡Bug / 用偷鸡耍赖套路过关",
        "lore": "游戏术语！不靠堂堂正正的数值碾压，而是利用AI死角或某些机制漏洞轻松打败原本打不过的怪。",
        "type": "游戏黑话"
    },
    "grind": {
        "word": "Grind",
        "phonetic": "/ɡraɪnd/",
        "pos": "v./n.",
        "cn": "死刷 / 肝进度 / 枯燥重复积累",
        "lore": "放置游戏的核心日常！通过不断重复同一过程一点点积累资源。这游戏的名字 NGU (Never Grind... Wait, Number Goes Up) 本身就是对 Grind 的戏谑！",
        "type": "游戏黑话"
    },
    "nerf": {
        "word": "Nerf",
        "phonetic": "/nɜːf/",
        "pos": "v./n.",
        "cn": "削弱 / 砍数值",
        "lore": "指开发者将原本强力的技能或装备砍低。源于 Nerf 海绵玩具枪（把真枪砍成了软绵绵的玩具）。",
        "type": "游戏黑话"
    },
    "buff": {
        "word": "Buff",
        "phonetic": "/bʌf/",
        "pos": "v./n.",
        "cn": "增强 / 增益状态",
        "lore": "提升数值的临时或永久增益，与 Debuff (减益) 和 Nerf (削弱) 相对。",
        "type": "游戏黑话"
    },
    "rng": {
        "word": "RNG",
        "phonetic": "/ˌɑːr en ˈdʒiː/",
        "pos": "abbr.",
        "cn": "随机数生成器 (Random Number Generator)",
        "lore": "常用来指代游戏里的“运气/脸黑程度”。如 RNGesus (RNG + Jesus) 指玩家祈求保佑出好装备的“随机数之神”。",
        "type": "游戏黑话"
    },
    "loot": {
        "word": "Loot",
        "phonetic": "/luːt/",
        "pos": "n./v.",
        "cn": "战利品；搜刮",
        "lore": "打败敌人后爆出来的装备和道具的总称。",
        "type": "游戏黑话"
    },
    "idle": {
        "word": "Idle",
        "phonetic": "/ˈaɪdl/",
        "pos": "adj./v.",
        "cn": "放置 / 挂机 / 空闲",
        "lore": "指无需持续操作，依靠后台自动化运转增长数值的游戏流派。",
        "type": "核心系统"
    },
    "fluff": {
        "word": "Fluff",
        "phonetic": "/flʌf/",
        "pos": "n.",
        "cn": "废话梗 / 搞笑剧情 / 弱鸡毛团",
        "lore": "在 NGU 中，作者 4G 经常把纯搞笑无厘头的剧情调侃为「Fluff」（填充废话/闲聊梗）。这里也常用来戏谑主角虚弱得像个毛团。",
        "type": "游戏梗与俚语"
    }
}

def detect_ngu_terms(text: str):
    """
    在识别的文本中快速检测是否包含 NGU IDLE 专属术语或梗
    返回匹配到的词条列表
    """
    lower_text = text.lower()
    matches = []
    
    # 按关键词长度从长到短匹配，优先匹配长词组
    sorted_keys = sorted(NGU_GLOSSARY.keys(), key=lambda k: len(k), reverse=True)
    
    seen = set()
    for key in sorted_keys:
        import re
        if re.search(rf"\b{re.escape(key)}\b", lower_text) and key not in seen:
            matches.append(NGU_GLOSSARY[key])
            seen.add(key)
            
    return matches
