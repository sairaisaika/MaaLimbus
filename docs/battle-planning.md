# 实验性原生战斗准备

单独的 `BattlePlanStart` / PI 任务 **Prepare battle plan (development)** 默认不勾选。
它只在英语战斗规划页尝试一次 Maa `ClickKey`（虚拟键 80，即 P），等待并保存新图，
随后在待验收边界停止。不按 Enter、不选择 E.G.O、不循环战斗、不更新通关账本。

参考为固定 Lix `431b432e22f0b0da08b95d7c478fa213be20b3e8` 的
`workflow/task_execution.py::exec_battle_winrate`、`config/task/battle.json`
及 `utils/get_save_skill_icon.py`。上游先按 P，再检查有风险的选招并尝试 E.G.O；
当前只迁移 P 的原生执行和后续证据记录，没有把上游不确定的恢复点击/重复按键引入本项目。

仅导入四个小 UI 图标：英语胜率图标和斩击/突刺/打击标记。
`battle-catalog.json` 保存源路径、提交、每文件哈希和 AGPL 来源，不导入上游控制器、
模型或整张战斗背景。源代码给出技能图标中心参考 y560..600；胜率图标区域和整体组合
仍是实验性几何，未由真实游戏画面确认。模板缺少、重复、比例异常或日语资源时拒绝。
资源/过期/战败和已有明确页面分类优先，不能靠战斗图标覆盖这些停止条件。

新画面记录 `frame_changed` 与局部 OCR 的 Hopeless/Struggling/Neutral/Favored/Dominating
诊断标签。前三类在上游被列为需要关注。当前文本识别既不是上游的图标分类器，
也未覆盖全部技能与目标，因此 `plan_verified`、`clash_coverage_verified`、
`turn_submitted`、`victory_verified`、`verified_clear` 均为 false。
画面变化和几个有利标签不足以允许自动提交困难回合。

```powershell
python tools/import_battle_catalog.py
python tools/verify_battle_plan_replay.py --binary <Maa原生库目录>
```

112项测试通过。真实 Maa 图像识别/OCR/ClickKey/Pipeline 在七组派生画面中：
正常/卡住各一次 P，缺少标记、重复按钮、付费弹窗、战败、日语各零输入；
正常派生画面变化及 Neutral 文本已记录，卡住不重试，没有 Enter/鼠标/E.G.O。
证据为 `build/battle-plan-replay-verification.json`，没有 Win32 游戏控制器。
导航回归使用先前保留的归一化 Maa 图，来源在
`build/battle-navigation-regression-refs/provenance.json`，以 `--prepared-frames`
避免二次缩放损失小字；入口/变封面两次点击及 UNKNOWN 零输入通过。

尚需真实英语/日语规划页、完整技能覆盖、目标/冲突与生存判断、E.G.O 成本/侵蚀策略、
回合提交及胜败/地图回归后置条件。此独立节点未接入五层主循环，当前冻结开发包仍为
旧 `ded609b`，没有因为源码回放通过而成为已安装实机功能。
