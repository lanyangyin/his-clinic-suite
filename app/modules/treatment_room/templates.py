"""治疗室处置模板：小术式结构化记录字段。"""

TEMPLATES = [
    {
        "code": "debridement",
        "name": "清创缝合",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "size", "label": "伤口大小/深度"},
            {"key": "contamination", "label": "污染程度"},
            {"key": "suture", "label": "缝合方式/针数"},
            {"key": "drainage", "label": "引流"},
        ],
    },
    {
        "code": "dressing",
        "name": "换药",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "wound", "label": "创面情况"},
            {"key": "drainage", "label": "渗出/引流"},
            {"key": "dressing", "label": "敷料"},
        ],
    },
    {
        "code": "excision",
        "name": "小肿物切除/活检",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "size", "label": "肿物大小"},
            {"key": "margin", "label": "切缘"},
            {"key": "specimen", "label": "标本送检"},
            {"key": "suture", "label": "缝合"},
        ],
    },
    {
        "code": "abscess",
        "name": "脓肿切开引流",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "size", "label": "脓腔大小"},
            {"key": "drainage", "label": "引流物/填塞"},
            {"key": "culture", "label": "脓液培养"},
        ],
    },
    {
        "code": "nail",
        "name": "拔甲/甲沟炎",
        "fields": [
            {"key": "site", "label": "指/趾及侧别"},
            {"key": "procedure", "label": "拔甲/切开"},
            {"key": "dressing", "label": "包扎"},
        ],
    },
    {
        "code": "burn",
        "name": "烧伤/烫伤换药",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "area", "label": "面积(%)"},
            {"key": "depth", "label": "深度"},
            {"key": "dressing", "label": "敷料/药物"},
        ],
    },
    {
        "code": "circumcision",
        "name": "包皮环切",
        "fields": [
            {"key": "indication", "label": "指征"},
            {"key": "technique", "label": "术式"},
            {"key": "anesthesia", "label": "麻醉"},
            {"key": "suture", "label": "缝合/吻合器"},
            {"key": "dressing", "label": "包扎"},
        ],
    },
    {
        "code": "other",
        "name": "其他小处置",
        "fields": [
            {"key": "site", "label": "部位"},
            {"key": "procedure", "label": "操作"},
            {"key": "note", "label": "备注"},
        ],
    },
]
