#!/usr/bin/env python3
"""
生成 IMA 知识库种子内容文件
将采集的政策法规和行业标准整理为 Markdown 文件，供上传到 IMA
"""

import json
import os
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / 'ima-seed-content'

# ============================================================
# 政策法规文件数据（17份）
# ============================================================
POLICIES = [
    {
        "category": "01-法规政策库",
        "filename": "01-无人驾驶航空器飞行管理暂行条例.md",
        "title": "无人驾驶航空器飞行管理暂行条例",
        "publisher": "国务院、中央军委",
        "publish_date": "2023-05-31",
        "doc_number": "国令第761号",
        "summary": "我国首部专门针对无人驾驶航空器的行政法规。确立'安全第一、服务发展、分类管理、协同监管'原则；将无人机按性能分为微型、轻型、小型、中型、大型五类管理；明确真高120米以上为管制空域，未经批准不得飞行；建立操控员执照、实名登记、运营合格证制度；规定飞行活动申请、避让规则及法律责任。2024年1月1日起施行。",
        "source_url": "https://www.gov.cn/zhengce/content/202306/content_6888799.htm",
        "tags": ["国家级法规", "无人机", "飞行管理", "空域", "国务院"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "02-民用无人驾驶航空器运行安全管理规则CCAR-92.md",
        "title": "民用无人驾驶航空器运行安全管理规则（CCAR-92部）",
        "publisher": "交通运输部（民航局制定）",
        "publish_date": "2024-01-01",
        "doc_number": "交通运输部令2024年第1号",
        "summary": "作为《无人驾驶航空器飞行管理暂行条例》的配套规章，共分总则、操控员管理、登记管理、适航管理、空中交通管理、运行管理、法律责任等章节。规范民用无人机运行安全管理，与上位法有效衔接，是无人机行业运行的核心技术规章。",
        "source_url": "https://www.gov.cn/zhengce/202401/content_6924198.htm",
        "tags": ["部门规章", "无人机", "运行安全", "民航局", "CCAR-92"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "03-通用机场管理规定.md",
        "title": "通用机场管理规定",
        "publisher": "交通运输部（民航局承办）",
        "publish_date": "2024-11-26",
        "doc_number": "交通运输部令2024年第11号",
        "summary": "进一步健全通用机场管理制度体系，规范通用机场建设、使用许可及备案、运营等各阶段行业管理要求。旨在促进通用机场安全有序发展，为低空经济基础设施建设提供制度支撑。2025年4月1日起施行。",
        "source_url": "https://www.gov.cn/zhengce/202412/content_6993562.htm",
        "tags": ["部门规章", "通用机场", "基础设施", "民航局"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "04-2024年政府工作报告-低空经济.md",
        "title": "2024年政府工作报告（低空经济相关）",
        "publisher": "国务院",
        "publish_date": "2024-03-05",
        "doc_number": "—",
        "summary": "低空经济首次写入政府工作报告。提出'积极培育新兴产业和未来产业……积极打造生物制造、商业航天、低空经济等新增长引擎'，将低空经济确立为国家战略性新兴产业和新增长引擎，具有标志性意义。",
        "source_url": "https://www.gov.cn/zhuanti/2024qglh/",
        "tags": ["政府工作报告", "国家战略", "新兴产业", "国务院"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "05-2025年政府工作报告-低空经济.md",
        "title": "2025年政府工作报告（低空经济相关）",
        "publisher": "国务院",
        "publish_date": "2025-03-00",
        "doc_number": "—",
        "summary": "连续第二年写入低空经济，表述由'打造'升级为'推动低空经济等新兴产业安全健康发展'，强调'安全'导向，并提出启动新技术新产品新场景大规模示范应用，培育低空经济等新兴产业安全健康发展。",
        "source_url": "https://www.gov.cn/",
        "tags": ["政府工作报告", "国家战略", "安全发展", "场景应用"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "06-国家发改委设立低空经济发展司.md",
        "title": "国家发改委设立'低空经济发展司'",
        "publisher": "国家发展和改革委员会",
        "publish_date": "2024-12-27",
        "doc_number": "—",
        "summary": "国家发改委新设'低空经济发展司'（简称'低空司'），负责拟订并组织实施低空经济发展战略、中长期发展规划，提出政策建议，协调重大问题。这是国家层面首个专司低空经济的职能部门，标志低空经济顶层管理体系正式成型。",
        "source_url": "https://www.ndrc.gov.cn/fzggw/jgsj/dks/wap_index.html",
        "tags": ["机构改革", "发改委", "低空司", "顶层管理"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "07-低空经济及其核心产业统计分类试行.md",
        "title": "低空经济及其核心产业统计分类（试行）",
        "publisher": "国家发展改革委、国家统计局",
        "publish_date": "2025-12-26",
        "doc_number": "发改低空〔2025〕1676号",
        "summary": "首次建立低空经济及其核心产业的统计分类标准，为低空经济规模测算、产业监测和政策制定提供统一口径，是低空经济进入规范化统计管理的重要标志。",
        "source_url": "https://www.ndrc.gov.cn/xxgk/wjk/wap_index.html?date=2025&tab=all",
        "tags": ["统计分类", "发改委", "产业监测", "标准化"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "08-关于推动低空保险高质量发展的实施意见.md",
        "title": "关于推动低空保险高质量发展的实施意见",
        "publisher": "国家发展改革委、金融监管总局、中国民航局",
        "publish_date": "2026-02-12",
        "doc_number": "发改低空〔2026〕123号",
        "summary": "三部委联合发文推动低空保险发展，构建覆盖低空飞行器研制、运营、应用全链条的保险服务体系，为低空经济提供风险保障支撑，系首份针对低空保险领域的国家级专项政策。",
        "source_url": "http://www.caac.gov.cn/",
        "tags": ["低空保险", "三部委", "风险保障", "金融"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "09-关于加快场景培育和开放推动新场景大规模应用的实施意见.md",
        "title": "关于加快场景培育和开放推动新场景大规模应用的实施意见",
        "publisher": "国务院办公厅",
        "publish_date": "2025-11-00",
        "doc_number": "国办〔2025〕37号",
        "summary": "聚焦5方面提出22类场景培育和开放重点，明确'稳妥有序拓展低空经济等领域场景应用'，将低空经济列为新场景大规模应用示范的重点领域，推动低空经济从政策规划走向场景落地。",
        "source_url": "https://www.zzyuam.com/news/detail/b3fbb70b8af4af3e0578d74fadd63851",
        "tags": ["场景应用", "国务院", "示范应用", "落地"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "10-低空经济标准体系建设指南2025年版.md",
        "title": "低空经济标准体系建设指南（2025年版）",
        "publisher": "市场监管总局、中央空管办等十部门",
        "publish_date": "2025-12-00",
        "doc_number": "—",
        "summary": "重点围绕低空航空器、低空基础设施、低空空中交通管理等核心领域构建标准供给体系。明确到2030年，低空经济领域标准供给体系基本健全，填补低空经济标准化空白。",
        "source_url": "http://m.chinanews.com/wap/detail/cht/zw/10623895.shtml",
        "tags": ["标准体系", "十部门", "市场监管总局", "顶层设计"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "11-通用航空装备创新应用实施方案2024-2030.md",
        "title": "通用航空装备创新应用实施方案（2024-2030年）",
        "publisher": "工业和信息化部、科学技术部、财政部、中国民用航空局",
        "publish_date": "2024-03-27",
        "doc_number": "—",
        "summary": "提出到2027年通用航空装备创新应用若干突破、到2030年通用航空装备成为低空经济增长强大推动力、形成万亿级市场规模。从增强技术创新能力、提升产业链竞争力、深化重点领域示范应用、推动基础支撑体系建设、构建高效融合产业生态五方面部署20项具体任务。",
        "source_url": "https://www.gov.cn/zhengce/zhengceku/202403/P020240328724691408759.pdf",
        "tags": ["产业政策", "工信部", "万亿市场", "通用航空装备", "四部门"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "12-空中游览和跳伞飞行服务市场管理暂行办法.md",
        "title": "空中游览市场管理暂行办法 / 跳伞飞行服务市场管理暂行办法",
        "publisher": "中国民用航空局",
        "publish_date": "2025-09-00",
        "doc_number": "—",
        "summary": "民航局制定两项规范性文件，进一步加强和规范低空旅游业态监管，促进空中游览、跳伞飞行服务等低空旅游新业态健康有序发展，优化低空消费环境。其中《空中游览市场管理暂行办法》共计29条。",
        "source_url": "https://www.gov.cn/lianbo/bumen/202509/content_7041373.htm",
        "tags": ["低空旅游", "民航局", "空中游览", "跳伞", "消费"],
        "importance": "★★★☆☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "13-深圳经济特区低空经济产业促进条例.md",
        "title": "深圳经济特区低空经济产业促进条例",
        "publisher": "深圳市人民代表大会常务委员会",
        "publish_date": "2023-12-29",
        "doc_number": "深圳市第七届人大常委会公告第一二八号",
        "summary": "全国首部低空经济产业促进专项法规。围绕基础设施建设、飞行服务、产业应用、技术创新、安全管理等作出系统规定，为低空经济产业提供法治保障，助力深圳打造'天空之城'和全球低空经济第一城。2024年2月1日起施行。",
        "source_url": "https://www.szrd.gov.cn/v2/zx/szfg/content/post_1123253.html",
        "tags": ["地方性法规", "深圳", "产业促进", "全国首部"],
        "importance": "★★★★★"
    },
    {
        "category": "01-法规政策库",
        "filename": "14-深圳市低空基础设施高质量建设方案2024-2026.md",
        "title": "深圳市低空基础设施高质量建设方案（2024—2026年）",
        "publisher": "深圳市发展和改革委员会",
        "publish_date": "2025-08-00",
        "doc_number": "—",
        "summary": "明确推进通用机场规划建设，除龙华樟坑径直升机场外，还规划建设深汕通用机场，力争2026年底前稳定场址。全力打造'全球低空经济第一城'，系统性布局低空起降、通信、监视等基础设施网络。",
        "source_url": "http://www.gd.gov.cn/gdywdt/dsdt/content/mpost_4755458.html",
        "tags": ["地方政策", "深圳", "基础设施", "通用机场"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "15-苏州市低空经济高质量发展实施方案2024-2026.md",
        "title": "苏州市低空经济高质量发展实施方案（2024-2026年）",
        "publisher": "苏州市人民政府",
        "publish_date": "2024-02-06",
        "doc_number": "—",
        "summary": "明确4项发展目标、部署14项重点任务、4点保障措施。立足自主创新、瞄准高端制造、拓展应用场景。提出到2026年打造全国低空经济示范区，充分发挥制造业长板优势，服务长三角一体化战略。",
        "source_url": "https://www.zzyuam.com/news/detail/1f07f0f119ca24b8796d209bc300d89f",
        "tags": ["地方政策", "苏州", "高质量发展", "长三角"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "16-苏州市低空经济促进条例.md",
        "title": "苏州市低空经济促进条例",
        "publisher": "苏州市人大常委会",
        "publish_date": "2025-10-01",
        "doc_number": "—",
        "summary": "以立法筑基，开启低空经济规范化发展新阶段。精准聚焦产业核心需求，支持低空航空器整机制造企业发展，发挥其产业链核心集聚带动作用，重点推进大中型无人驾驶航空器、电动垂直起降航空器（eVTOL）等装备研制和产业化。",
        "source_url": "https://chejiahao.m.autohome.com.cn/info/24769885",
        "tags": ["地方性法规", "苏州", "eVTOL", "产业促进"],
        "importance": "★★★★☆"
    },
    {
        "category": "01-法规政策库",
        "filename": "17-成都市加快提升低空飞行能力培育低空经济市场若干政策措施.md",
        "title": "成都市加快提升低空飞行能力培育低空经济市场的若干政策措施",
        "publisher": "成都市发展和改革委员会联合七部门",
        "publish_date": "2025-06-00",
        "doc_number": "—",
        "summary": "围绕完善基础设施保障体系、提升低空飞行服务监管能力、拓展低空市场应用场景、做强低空产业支撑四大关键领域，推出14条具体政策措施，涵盖载人航线票价补贴、低空起降基础设施建设补贴等亮点举措，真金白银全方位'护航'低空经济发展。",
        "source_url": "http://www.sc.xinhuanet.com/20250625/3e9b0f0a30894efa9910765854b1e996/c.html",
        "tags": ["地方政策", "成都", "补贴", "政策措施", "14条"],
        "importance": "★★★★☆"
    }
]

# ============================================================
# 行业标准数据（16项）
# ============================================================
STANDARDS = [
    {
        "category": "02-行业标准库",
        "filename": "01-GB46761-2025民用无人驾驶航空器实名登记和激活要求.md",
        "title": "GB 46761-2025 民用无人驾驶航空器实名登记和激活要求",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "publish_date": "2025-10-31",
        "doc_number": "GB 46761-2025（强制性国家标准）",
        "summary": "适用于中国境内从事飞行或相关活动的民用无人驾驶航空器的实名登记和激活管理。规定了民用无人驾驶航空器系统、生产者系统、实名登记系统在处理'登记'和'激活'等不同状态之间的关系、流程和技术要求及测试方法，并统一了各系统间数据交互要求。2026年5月1日实施。",
        "source_url": "http://www.caac.gov.cn/XXGK/XXGK/BZGF/BZGF_GJBZ/202601/t20260120_229784.html",
        "tags": ["强制性国标", "无人机", "实名登记", "激活", "2026年实施"],
        "importance": "★★★★★"
    },
    {
        "category": "02-行业标准库",
        "filename": "02-GB46750-2025民用无人驾驶航空器系统运行识别规范.md",
        "title": "GB 46750-2025 民用无人驾驶航空器系统运行识别规范",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "publish_date": "2025-10-31",
        "doc_number": "GB 46750-2025（强制性国家标准）",
        "summary": "规定民用无人驾驶航空器系统应在运行全过程主动报送自身身份、位置、速度、状态等运行识别信息。从'运行识别发送—通信链路传输与接收'三段提出详细技术要求，涵盖发送功能、传输协议、更新间隔、链路可靠性、接收处理容量等，为无人机设计、生产、检测、审定和运行提供统一技术标准。2026年5月1日实施。",
        "source_url": "http://www.caac.gov.cn/XWZX/MHYW/202512/t20251222_229506.html",
        "tags": ["强制性国标", "无人机", "运行识别", "远程识别"],
        "importance": "★★★★★"
    },
    {
        "category": "02-行业标准库",
        "filename": "03-GB46860-2025民用无人驾驶航空器唯一产品识别码.md",
        "title": "GB 46860-2025 民用无人驾驶航空器唯一产品识别码",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "publish_date": "2025-12-02",
        "doc_number": "GB 46860-2025（强制性国家标准）",
        "summary": "规范民用无人机唯一产品识别码的编码规则、登记备案、产品外包装标识、机体表面标识、存储与安全、报送与查询等全流程要求，旨在实现无人机产品全生命周期可追溯管理。2027年1月1日实施。",
        "source_url": "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=26257D27F546360A98C814D079D32C2E",
        "tags": ["强制性国标", "无人机", "产品识别码", "追溯管理"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "04-MHT2017-2025无人机系统分布式操作自动化等级测试.md",
        "title": "MH/T 2017—2025 民用无人驾驶航空器系统分布式操作 自动化等级测试",
        "publisher": "中国民用航空局",
        "publish_date": "2025-06-20",
        "doc_number": "MH/T 2017—2025",
        "summary": "规定民用无人机系统分布式操作自动化等级测试的测试范围、测试对象、测试环境与仿真测试系统要求、测试科目和指标要求、测试结果评估与报告等。适用于真高120m以下隔离空域运行的轻、小、中型多旋翼无人机系统。2025年7月1日实施。",
        "source_url": "https://www.caac.gov.cn/XXGK/XXGK/BZGF/HYBZ/202506/P020250627521128936456.pdf",
        "tags": ["民航行业标准", "自动化测试", "分布式操作", "多旋翼"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "05-MHT5026-2026通用机场规划建设指南第1部分.md",
        "title": "MH/T 5026.1—2026 通用机场规划建设指南（第1部分：跑道型机场）",
        "publisher": "中国民用航空局",
        "publish_date": "2026-04-00",
        "doc_number": "MH/T 5026.1—2026",
        "summary": "通用机场跑道型机场的规划与建设技术指南，服务低空经济基础设施中的通用机场建设。由华设设计集团北京民航设计研究院有限公司主编。",
        "source_url": "http://www.caac.gov.cn/PHONE/XXGK_17/XXGK/BZGF/HYBZ/202607/P020260706349265043390.pdf",
        "tags": ["民航行业标准", "通用机场", "规划建设", "基础设施"],
        "importance": "★★★☆☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "06-MH5013-2023民用直升机场飞行场地技术标准.md",
        "title": "MH 5013-2023 民用直升机场飞行场地技术标准",
        "publisher": "中国民用航空局",
        "publish_date": "2023-00-00",
        "doc_number": "MH 5013-2023",
        "summary": "规定民用直升机场飞行场地的技术标准，其中停机坪（apron）定义为机场内划定的硬质铺装区域，专供直升机、eVTOL等载人垂直起降航空器停放、上下客、装卸货物及地面保障作业，是eVTOL起降设施建设的重要依据。",
        "source_url": "http://m.sensha.com.cn/h-nd-1198.html",
        "tags": ["民航标准", "直升机场", "eVTOL", "起降设施"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "07-MHT4054-2022城市场景无人机物流航线划设规范.md",
        "title": "MH/T 4054-2022 城市场景轻小型无人驾驶航空器物流航线划设规范",
        "publisher": "中国民用航空局空管行业管理办公室",
        "publish_date": "2022-08-01",
        "doc_number": "MH/T 4054-2022",
        "summary": "规范城市场景下轻小型无人机物流配送航线的划设，包括标称航迹、飞行区+应急区双空间结构、航线优化等，是城市低空物流航线审批的核心依据。",
        "source_url": "http://aircraft.work/Standards/MH",
        "tags": ["民航标准", "物流配送", "航线划设", "城市场景"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "08-MHT4055-2022低空飞行服务系统技术规范.md",
        "title": "MH/T 4055.1-2022 低空飞行服务系统技术规范 第1部分：架构与配置",
        "publisher": "中国民用航空局空管行业管理办公室",
        "publish_date": "2022-10-28",
        "doc_number": "MH/T 4055.1-2022",
        "summary": "规定低空飞行服务系统的总体架构与配置技术要求，是低空飞行服务保障体系建设的行业基础标准。",
        "source_url": "http://aircraft.work/Standards/MH",
        "tags": ["民航标准", "低空飞行", "服务系统", "架构"],
        "importance": "★★★☆☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "09-动力提升航空器适航标准征求意见稿.md",
        "title": "动力提升航空器适航标准（征求意见稿）— 全球首个eVTOL专用适航标准",
        "publisher": "中国民用航空局航空器适航审定司",
        "publish_date": "2025-12-15",
        "doc_number": "AC-21-AA-2025-XX",
        "summary": "适用于可有人驾驶的、纯电供能分布式电推进系统的、最大起飞重量不超过5700公斤、最大乘客数不超过9座、非增压座舱、最大使用限制速度小于463公里/小时的动力提升航空器（即eVTOL）。涵盖飞行、结构、设计和构造、动力装置、系统和设备等全部章节的适航要求。作为全球首个eVTOL专用适航标准，填补了eVTOL型号合格审定专用规章空白。",
        "source_url": "http://www.caac.gov.cn/HDJL/YJZJ/202512/P020251215491814715130.pdf",
        "tags": ["适航标准", "eVTOL", "全球首个", "征求意见稿", "民航局"],
        "importance": "★★★★★"
    },
    {
        "category": "02-行业标准库",
        "filename": "10-限用类无人驾驶航空器系统适航标准征求意见稿.md",
        "title": "限用类无人驾驶航空器系统适航标准（征求意见稿）",
        "publisher": "中国民用航空局航空器适航审定司",
        "publish_date": "2025-12-15",
        "doc_number": "AC-21-AA-2025-XX",
        "summary": "指导和规范限用类无人驾驶航空器系统（中大型无人机）的型号合格审定工作。涵盖基本要求、术语定义、设计特征及运行场景、整机要求等，填补了中大型无人机适航审定专用标准空白。",
        "source_url": "http://www.caac.gov.cn/HDJL/YJZJ/202512/P020251215491814531403.pdf",
        "tags": ["适航标准", "中大型无人机", "限用类", "征求意见稿"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "11-中型民用无人驾驶航空器适航审定指南试行.md",
        "title": "中型民用无人驾驶航空器适航审定指南（试行）",
        "publisher": "中国民用航空局",
        "publish_date": "2025-12-00",
        "doc_number": "—",
        "summary": "明确针对最大起飞重量在25kg至150kg之间的中型物流无人机的'限制类适航证'审定要求，继CCAR-92部后进一步细化中型物流无人机适航认证路径。",
        "source_url": "https://www.docin.com/touch_new/preview_new.do?id=4934348628",
        "tags": ["适航审定", "中型无人机", "物流", "限制类适航证"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "12-GBT44235-2025移动通信系统通感融合技术要求.md",
        "title": "GB/T 44235–2025 移动通信系统通感融合技术要求与测试方法",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "publish_date": "2025-03-01",
        "doc_number": "GB/T 44235–2025（推荐性国家标准）",
        "summary": "全球首个覆盖Sub-6GHz与毫米波双频段、支持静态目标识别精度优于0.5米、动态目标测速误差小于±0.3m/s的通感融合技术规范。为5G-A通感一体化在低空经济中的应用提供标准化技术依据。",
        "source_url": "https://www.docin.com/touch_new/preview_new.do?id=4990409572",
        "tags": ["推荐性国标", "5G-A", "通感融合", "低空智联网", "全球首个"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "13-TFJIOT001-2024低空经济5G空中传输专网技术规范.md",
        "title": "T/FJIOT 001-2024 低空经济 5G空中传输专网（'低空智联网'）典型应用场景技术规范",
        "publisher": "福建省物联网团体标准",
        "publish_date": "2024-09-30",
        "doc_number": "T/FJIOT 001-2024（团体标准）",
        "summary": "基于5G-A技术增强传统连接能力与拓展通信能力边界，规定低空智联网端到端网络架构、通感融合、高精定位等技术要求，契合低空飞行对高速率、低时延、大连接数的基本需求。",
        "source_url": "https://www.ttbz.org.cn/upload/file/20240930/6386330839468303256725955.pdf",
        "tags": ["团体标准", "5G-A", "低空智联网", "通感融合"],
        "importance": "★★★☆☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "14-民用轻小型无人机物流配送试运行审定指南.md",
        "title": "民用轻小型无人驾驶航空器物流配送试运行审定指南",
        "publisher": "中国民用航空局",
        "publish_date": "2024-00-00",
        "doc_number": "—",
        "summary": "针对城市物流场景，要求划设'飞行区+应急区'双空间结构，通过航线优化使地表人口密度≤300人/km²。要求分布式操作、无人机具备空域保持能力、配备整机降落伞等缓控措施，是轻小型无人机物流配送试运行审定的核心指南。",
        "source_url": "https://www.sohu.com/a/924261235_120664764",
        "tags": ["民航指南", "物流配送", "试运行审定", "城市物流"],
        "importance": "★★★★☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "15-军民通用低空物流配送服务管理规范征求意见稿.md",
        "title": "军民通用低空物流配送服务管理规范（征求意见稿）",
        "publisher": "中国和平利用军工技术协会",
        "publish_date": "2026-03-00",
        "doc_number": "T/CPUMT-P-2025（团体标准）",
        "summary": "贯彻军民融合发展战略，规范军民通用低空物流配送服务管理，涵盖配送服务流程、安全管理、军民协同等要求。",
        "source_url": "https://www.ttbz.org.cn/upload/file/20260313/6390901842483226058288515.pdf",
        "tags": ["团体标准", "军民融合", "物流配送", "征求意见稿"],
        "importance": "★★★☆☆"
    },
    {
        "category": "02-行业标准库",
        "filename": "16-低空经济标准体系建设指南2025年版.md",
        "title": "低空经济标准体系建设指南（2025年版）",
        "publisher": "国家市场监督管理总局、国家标准化管理委员会",
        "publish_date": "2026-00-00",
        "doc_number": "—",
        "summary": "非单一标准，而是低空经济标准化顶层规划文件。系统提出贯穿技术研发、装备制造、运营服务、基础设施的全链条标准体系框架，统筹推进低空经济标准化建设，形成全国'一盘棋'工作格局。明确到2030年，低空经济领域标准供给体系基本健全。",
        "source_url": "https://www.samr.gov.cn/cms_files/filemanager/1647978232/attach/20261/3b6e572b8bec4ecfb627bd306807e85a.pdf",
        "tags": ["标准体系", "顶层设计", "十部门", "2030目标"],
        "importance": "★★★★★"
    }
]


def generate_markdown(doc, doc_type="政策法规"):
    """生成单个文档的 Markdown 内容"""
    tags_str = " ".join(f"#{t}" for t in doc.get("tags", []))

    md = f"""# {doc['title']}

> **文档类型**: {doc_type}
> **发布机构**: {doc['publisher']}
> **发布日期**: {doc['publish_date']}
> **文号**: {doc['doc_number']}
> **重要程度**: {doc['importance']}
> **原文链接**: [{doc['source_url']}]({doc['source_url']})

---

## 核心内容摘要

{doc['summary']}

---

## 标签

{tags_str}

---

*本文档由低空经济情报服务系统自动生成，供 IMA 知识库使用*
*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    return md


def generate_upload_list(all_docs):
    """生成上传清单 JSON"""
    upload_list = []
    for doc in all_docs:
        upload_list.append({
            "id": doc['filename'].replace('.md', ''),
            "title": doc['title'],
            "category": doc['category'],
            "filename": doc['filename'],
            "publisher": doc['publisher'],
            "publish_date": doc['publish_date'],
            "doc_number": doc['doc_number'],
            "importance": doc['importance'],
            "tags": doc['tags'],
            "source_url": doc['source_url'],
            "uploaded": False,
            "uploaded_date": None,
            "ima_library": None
        })
    return upload_list


def main():
    """生成所有种子内容文件"""
    all_docs = POLICIES + STANDARDS

    print(f"开始生成 {len(all_docs)} 份种子内容文件...")

    # 生成 Markdown 文件
    for doc in all_docs:
        category_dir = OUTPUT_DIR / doc['category']
        category_dir.mkdir(parents=True, exist_ok=True)

        filepath = category_dir / doc['filename']
        doc_type = "政策法规" if doc['category'].startswith("01") else "行业标准"
        md_content = generate_markdown(doc, doc_type)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"  ✓ {doc['category']}/{doc['filename']}")

    # 生成上传清单
    upload_list = generate_upload_list(all_docs)
    list_file = OUTPUT_DIR / 'upload-list.json'
    with open(list_file, 'w', encoding='utf-8') as f:
        json.dump(upload_list, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ 上传清单: {list_file}")

    # 统计
    policies_count = len(POLICIES)
    standards_count = len(STANDARDS)
    print(f"\n生成完成:")
    print(f"  政策法规: {policies_count} 份 → 01-法规政策库/")
    print(f"  行业标准: {standards_count} 份 → 02-行业标准库/")
    print(f"  总计: {len(all_docs)} 份")

    # 按重要程度统计
    star5 = sum(1 for d in all_docs if '★★★★★' in d['importance'])
    star4 = sum(1 for d in all_docs if '★★★★☆' in d['importance'])
    star3 = sum(1 for d in all_docs if '★★★☆☆' in d['importance'])
    print(f"\n  ★★★★★ 核心文件: {star5} 份")
    print(f"  ★★★★☆ 重要文件: {star4} 份")
    print(f"  ★★★☆☆ 参考文件: {star3} 份")


if __name__ == '__main__':
    main()
