# 横评：Limbus Company 自动化项目（只读研究，2026-10-06 取样）

## ① LimbusCompanySRA 拆解（21★，AGPL-3.0，2025-01-27 后停更）
- 口径：`config.py` 默认 conf=0.7/iou=0.6/device=cuda:0，但运行期 `utils.py:1765 getDetectionTRT()` 只走 `src/common/tensorrt/infer.py:21 class YoloTRT`（有 LBC.plan 就反序列化，否则从 onnx 构建）。**README 的「YOLO11」只体现在被注释掉的 ultralytics 分支与 onnx 权重来源；运行时是 TensorRT。**是「README 声称」而非代码路径。
- YOLO 检测 55 类（`src/data/Labels.py:1` bidict，`tensorrt/config.py:8 kNumClass=55`，输入 1280×1280，NMS 0.45/conf 0.25）：UI 按钮 + 镜牢 11 种节点（Active/Available/Battle/Boss/Current/End/Event/Explored/Safe/Start/Unavailable Node）+ 语义物体（Advantage-High、E.G.O、Enkephalin、Themes Pack…）。
- PaddleOCR 读中文文本做状态机锚点：`utils.py:745 text_exists(img, text, flag=False, confidence_threshold=0.5)` 用 `re.compile(text)` 命中，`utils.py:807 text_list_exists(match_mode="any"/"all"/"not")`。判「是否进战斗/是否结算/是否选完包」全靠中文正则。
- 编排：`src/script/Mirror_Dungeon.py` 的 `class EventType(Enum)` 12 事件 + `event_handlers` 表 → `src/common/actions.py`。镜牢支持选主题包/初始饰品/星之恩惠/商店/领奖/退回主菜单（`actions.py:972 def run()` 串 镜像迷宫→EXP→Thread）。
- **选节点无地图**：`actions.py:484 choose_path()` 只按 `NODE_PRIORITY = {Safe Node:4.0, Event Node:3.0, Battle Node:2.0, ...}` 贪心点屏幕内最高优先级，失败 `mouse_scroll(-200)` 重扫。不寻路。
- 配队：`actions.py:380 team_formation()` 只点「确认」，`battle_choose_characters()` 检测 `12/12` 后开打；缺人时弹窗要人确认。**无按关键词筛人格、不读预设队。**
- 部署：`requirements.txt` 强依赖 tensorrt 10.6 / cuda-python 12.6（非 torch 运行期）；README 要求 Windows + Python 3.12+ + CUDA≥11.8、**1920×1200、仅中文**；`utils.py:1393 getWindowShot()` 用 mss 前台截图，窗口不可遮挡；PathFind.py 读注册表找 Steam 游戏 → PC 端非模拟器。
- 权重：`onnx_model/LBC.onnx` 在仓库内是 **Git LFS 指针**（oid sha256:e4d49f15…，size 101,557,644），克隆后不可用；无 .pt/plan、无训练脚本（全历史仅 3 个匹配文件）。但 **releases 里 v1.0.3（2024-12-20）有 `LBCSRA-1.0.3.zip` 231 MB**，模型与 PaddleOCR-json 运行时应在此包内（未解包核实）。

## ② 项目横评（★ / 最近提交 / 识别 / 范围 / 语言 / 许可）
| 项目 | ★ | 最近提交 | 识别 | 范围 | 中文界面 | 许可 |
|---|---|---|---|---|---|---|
| KIYI671/AhabAssistantLimbusCompany | 2111 | 2026-09-28 | 模板 642 张 + RapidOCR + **ONNX 检测仅用于寻路** | 全流程（日常/狂气换体/镜牢/邮件）+ 模拟器 | zh_cn+en | AGPL-3.0 |
| HSLix/LixAssistantLimbusCompany | 1318 | 2026-10-03 | 模板多策略 + RapidOCR + **3 个自研 ONNX 分类器** | 全流程 | zh+en | AGPL-3.0 |
| Walpth/Charge-Grinder | 256 | 2026-09-17 | README 标榜「no OCR required」，纯模板/像素 | 镜牢专精（MD6、Luxcavation） | 英文关键词图标 | GPL-3.0 |
| MaaXYZ/MAALimbusCompany | 66 | 2024-08-11（弃坑） | 仅 TemplateMatch（9 个 pipeline，无 OCR/无模型） | 启动/日常/活动/合成/任务 | 未核实 | AGPL-3.0 |
| Xie-Tiao/Limbus-Scripts | 59 | 2024-07-25 | OCR（自述打包有问题） | 日常 | 未核实 | GPL-3.0 |
| Janrilw/limbus-company-auto | 40 | 2025-01-12 | 模板 + `Windows.Graphics.Capture` 后台截图 | 日常 | 未核实 | MIT |
| GALIAIS/LimbusCompanySRA | 21 | 2025-01-27 | YOLO11→TensorRT + PaddleOCR | 镜牢+采光 | 仅中文 | AGPL-3.0 |
| Bonkier/workerbeev2 | 12 | 2026-10-04 | 派生自 Charge-Grinder | 镜牢+采光+调度 | 英文 | GPL-3.0 |
| LoGundes/AutoLuxcavation | 5 | 2025-01-28 | 模板 | 仅采光/日常 | 未核实 | 无 |
活跃仅 AALC / LALC（+ Charge-Grinder、workerbeev2）；MaaXYZ 确认弃坑（hxdnshx 已重定向到 MaaXYZ）。

## ③ YOLO 检测 vs 模板匹配 vs OCR 语义锚点（含作者原话）
- **AALC 的路线是「模板为主、模型兜底且可关」**：`tasks/mirror/search_road.py:1072 search_road()` 先键盘简单寻路，再 onnx 寻路（异常日志 `使用onnx模型寻路出错`），失败回退纯模板几何法 `search_road_default_distance()`。镜牢节点类目 `["battle","boss_battle","event","focused_encounter","risky_encounter","shop","abnormality_focused_encounter"]`，输入 960×544，conf 0.4/NMS 0.5。→ 版本更新时真会崩的是**模板**，模型只承担节点/连线这种形状稳定的目标。
- **OCR 当语义锚点最抗版本更新**：AALC 2026-09-21 提交原文「扩展赛季文本识别关键词以兼容OCR误识别」，把季节文本从 `"season"` 扩成 `["season","seasun"]`；同日 `get_prize.py` 引入 `last_try` 备用重试。LALC 2026-06-21「修复了无文本版 rewards_acquired_confirm 很容易误识别的问题，分为了中英文素材」/ 2026-06-20「如果没识别出来会报错，而不是永远拖下去」。→ 反证：**「缺图即崩」比 OCR 误识别更难修**。
- **YOLO 的代价被 SRA 作者自己承认**：README 顶部「本项目的更新速度较慢，且代码质量可能不尽人意」；更新计划里「支持多分辨率屏幕」「支持多语言切换」全部未打勾。且 LBC.onnx 只以 LFS 指针存在、README 不给权重下载 → 新版本游戏一改 UI，作者没有公开训练闭环可复用。
- **LALC 的折中值得抄**：小模型（MobileNetV3-small）只做「分类」不做「检测」，且**推理前对六个道路区域注入随机涂鸦**（`utils/get_save_mirror_path.py:36 generate_random_graffiti`，7~12 条亮色线/点/圆）逼模型只看线条结构——这是对「贴纸/涂鸦遮挡」的对抗式增强，比单纯模板匹配稳。
- 模板匹配的极限由 LALC 自己写出来：`recognize/` 下有 template/precise/pyramid/edge/color/brightness/feature 七种匹配器 + `img/en`、`img/zh`、`img/general` 三套素材。更新成本是「重新截一套图」，但作者要维护 761 张素材。

## ④ 自动配队 / 按关键词筛人格 / 读预设队
- **AALC（最完整）**：`tasks/teams/team_formation.py:52 team_formation(sinner_team)` 按配置罪人顺序用固定坐标**重建**队伍；`select_battle_team(num)` 按**队伍名 OCR**（`编队#N` / `["TEAMS #N","TEAMS#N","TFAMS#N"]`，后者是英文误识别容错）或按序号几何定位（`ORDERED_TEAM_COUNT=40`、`PAGE_SIZE=5`、`VISIBLE_ROWS=6`、`ROW_HEIGHT=72.5`）；**`load_team_code_in_game(team_code)`（:282）能把游戏内分享编队码粘贴进游戏**（点队伍代码按钮→加载→`input_text`→确认，重试 3 次），配置 `use_team_code` / `team_code`。→「读游戏内预设队」是靠队名/序号/编队码三条路，**不是按人格关键词检索**。
- **LALC**：`task_action/mirror.py:414 keyword_refresh_map` 固定坐标点选体系标签（Burn/Bleed/Tremor/Rupture/Sinking/Poise/Charge/Slash/Pierce/Blunt），默认 `mirror_team_styles: ["Bleed"]`；无按人格名筛选。
- **Charge-Grinder（唯一「按关键词」派）**：README 原文「The bot determines the team to select based on the **keyword icon** assigned to that team」——支持单/双关键词（SLASH、PIERCE、BLUNT、BURN、BLEED、TREMOR、RUPTURE、SINKING、POISE、CHARGE + 七宗罪）、`SINKING#2` 取第 n 个同名队、找不到回落默认队。**靠队名/图标关键词而非读人格列表。**
- 结论：**没有任何项目做「按人格关键词从全员里现拼队伍」**；共同做法都是「玩家预先在游戏里建好队，脚本按名/序号/编队码/关键词图标选中」。

## ⑤ 可复用的公开资产（数据集 / 权重 / 地图结构）
- **LALC 是唯一把训练产物全公开的**（`lalc_backend/ai/model/`，均为 `best_model.onnx` + `classes.txt` + `training_config.json`）：
  - `mirror_legend`：8 类镜牢节点分类（node_abnormality_encounter / node_boss_encounter / node_elite_encounter / node_empty / node_event / node_focused_encounter / node_regular_encounter / node_shop），110×130，MobileNetV3-small，epochs 50。
  - `mirror_path`：9 条连线多标签分类（00/01/02/10/11/12/20/21/22），224×224 全图，epochs 80，输出 9 个 bool（阈值 `best_thresholds`）→ **这就是公开的镜牢拓扑判定模型**。
  - `skill_icon`：7 类拼点优劣势（dominating/favored/hopeless/neutral/struggling/unopposed/unselected），80×80。
  - （`sinner_avatar` 仅存训练脚本 `obsolete_resources/ai/learn_sinner_avatar.py`，模型已删）
  - 训练数据自动采集：`utils/get_save_mirror_legend.py:24 save_to_dataset_mirror_legend(img, class_name)` 存 `img/dataset/mirror_legend/<class>/<时间戳>.png`，类别含 `unclassified`。
- **AALC 节点代价表（公开的镜牢拓扑语义，可直接借用）** `search_road.py:601 all_node_weight = {"battle":4,"boss_battle":6,"event":1,"focused_encounter":6,"risky_encounter":7,"shop":2,"abnormality_focused_encounter":6}`，`DEFAULT_WEIGHT = 999  # 默认不可达权重`；列距 `ROAD_COLUMN_GAP=520`、行距 `ROAD_ROW_GAP=437`；末列无 shop/boss 时自动补权重 1 的 shop 与 boss_battle。`class RouteGraph` 按 列×{Row.TOP,MID,BOTTOM} 建图后 `find_min_weight_route()`。模板 `mirror/road_in_mir/*.png` 负责连线确认。
- **AALC 的 ONNX 模型可读**：`assets/model/best.onnx` 9,798,396 B，二进制含 `pytorch 2.1.0` 头、`ultralytics` 字符串、YOLO 典型节点名 `model.23`(×423)/`model.22`(×170)/`Detect`/`stride` → **确认是 ultralytics YOLO 架构导出**（具体代次未标注，非 YOLO11 证据）。来源未公开，无训练集。
- **LALC OCR 权重也在仓库**：`recognize/models/ch_PP-OCRv5_det_mobile.onnx`(4.8 MB)、`ch_PP-OCRv5_rec_mobile.onnx`(16.6 MB)。
- **SRA 无任何公开数据集/标注/训练脚本**；唯一权重是 LFS 指针。**所有项目都没有公开完整的镜牢地图拓扑数据集或截图标注集；地图信息都以「运行时识别 + 代码内权重表/连线列表」形式存在。** 未发现公开的节点样本图集（LALC 的 `img/dataset/mirror_legend` 只在用户本地累积，未随仓库发布）。

## ⑥ URL
- https://github.com/GALIAIS/LimbusCompanySRA ；权重 https://github.com/GALIAIS/LimbusCompanySRA/blob/master/src/common/tensorrt/onnx_model/LBC.onnx ；发布包 https://github.com/GALIAIS/LimbusCompanySRA/releases/tag/v1.0.3 ；标签定义 https://github.com/GALIAIS/LimbusCompanySRA/blob/master/src/data/Labels.py
- https://github.com/KIYI671/AhabAssistantLimbusCompany ；寻路 https://github.com/KIYI671/AhabAssistantLimbusCompany/blob/main/tasks/mirror/search_road.py ；配队/编队码 https://github.com/KIYI671/AhabAssistantLimbusCompany/blob/main/tasks/teams/team_formation.py ；主题包 https://github.com/KIYI671/AhabAssistantLimbusCompany/blob/main/tasks/mirror/select_theme_pack.py
- https://github.com/HSLix/LixAssistantLimbusCompany ；节点权重 https://github.com/HSLix/LixAssistantLimbusCompany/tree/master/lalc_backend/ai/model/mirror_legend ；连线权重 https://github.com/HSLix/LixAssistantLimbusCompany/tree/master/lalc_backend/ai/model/mirror_path ；分类器 https://github.com/HSLix/LixAssistantLimbusCompany/blob/master/lalc_backend/recognize/nn_classifier.py ；涂鸦增强 https://github.com/HSLix/LixAssistantLimbusCompany/blob/master/lalc_backend/utils/get_save_mirror_path.py ；数据集采集 https://github.com/HSLix/LixAssistantLimbusCompany/blob/master/lalc_backend/utils/get_save_mirror_legend.py
- https://github.com/Walpth/Charge-Grinder （README 队伍关键词规则）；https://github.com/Bonkier/workerbeev2 ；https://github.com/MaaXYZ/MAALimbusCompany ；https://github.com/Xie-Tiao/Limbus-Scripts ；https://github.com/Janrilw/limbus-company-auto ；https://github.com/LoGundes/AutoLuxcavation-Limbus-Company ；https://github.com/Schirke/limbus-archive （镜牢队伍构建器，未核实）
