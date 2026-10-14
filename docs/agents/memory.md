# Memory: 结论写回 agentmemory

本文件规定一件事：**一次会话得出结论之后，把它写进仓库外的 agentmemory**。

## 为什么有这条纪律

agentmemory 里其实不缺本仓库的原始会话记录，缺的是**结论**。检索 `MaaLimbus` 往往只能捞到 tool_use
壳子（读了哪个文件、跑了哪条命令），捞不到「这件事最后是怎么定的」「哪个做法被证明不行」。原因是没有任何
规则要求写回去。所以结果是：同一个坑下一个会话再踩一次，同一次调查的结论没人能复用。

这条纪律补的就是这个缺口，它只管写入，不管读取。

## 什么时候沉淀

三个触发点，出现任意一个，就在**会话收尾**时写一次：

- **功能落地之后** —— 一次改动的验收真的通过了（有命令输出或测试结果作证）。
- **一次调查有了结论** —— 查清了某个事实（例如「源数据里这个字段本来就是空的」），或者否掉了某个假设。
- **踩坑修好之后** —— 坑是什么、为什么会踩进去、什么做法被证明不行。

没到这三个点的中间过程不要写：那属于会话日志，不是结论。同一件事反复写也会稀释检索结果 —— 内容重复时
`memory_lesson_save` 会自动加强既有那条，不必手写第二遍。

## 沉淀什么

写**结论与判据**，不写流水账，不复制 diff：

- **做了什么** —— 一句话说清。
- **为什么这么做** —— 选它的理由；被否掉的方案也带一句为什么被否。
- **什么做法被证明不行** —— 带上最特征的那句报错原文或症状，下次检索得到。
- **判据 / 数值 / 路径** —— 验收口径、阈值、版本号、关键文件路径。这些丢了结论就没有可复现性。

> 反例：读了 A、改了 B、跑了测试。
> 正例：X 走不通，因为 Y（报错原文 `...`）；改走 Z，判据是 W 命令输出 P。

## 用哪个工具

三个工具按结论性质选一个，不要同一段话三处都写：

| 工具 | 放什么 | 必填 / 建议 |
| --- | --- | --- |
| `memory_save` | 决定、洞察、可复用的模式 | 必填 `content`；建议 `type`、`concepts`、`files`、`project` |
| `memory_lesson_save` | 经验教训（复现会加强、不用会衰减） | 必填 `content`；建议 `context`、`confidence`、`tags`、`project` |
| `memory_observe` | 一次性原始观测，暂不归类 | 必填 `hookType`、`content`；**不吃 `project`** |

**`project` 一律填 `MaaLimbus`。** 检索靠这个字段分流；留空或者填默认工作区、仓库绝对路径，都会让本仓库的
结论散进别的项目，等于没写。

`concepts` / `files` / `tags` 都是逗号分隔的字符串，不是数组。

写完读回来核对一遍：用 `memory_lesson_recall` 或 `memory_smart_search` 查一下，确认它能被检索到、`project`
没填错。这条与 `docs/agents/issue-tracker.md` 里「写完读回来核对」是同一条规矩。

### 照抄示例

一条决定：

```json
{
  "content": "MaaLimbus 的记忆沉淀纪律落在 docs/agents/memory.md，并在 AGENTS.md 的 ## Agent skills 下加一节 ### Memory 指向它，而不是新建独立文档：AGENTS.md 是索引文件，每节只做一行指针。",
  "type": "decision",
  "concepts": "agentmemory,文档纪律,AGENTS.md",
  "files": "docs/agents/memory.md,AGENTS.md",
  "project": "MaaLimbus"
}
```

一条教训（踩坑修好之后）：

```json
{
  "content": "在 <模块> 里用 <做法 A> 走不通，因为 <报错原文/症状>；改走 <做法 C> 可行，判据是 <命令> 输出 <结果>。",
  "context": "MaaLimbus <子系统/路径>，<什么情况下会碰到>",
  "confidence": 0.8,
  "tags": "MaaLimbus,<子系统>",
  "project": "MaaLimbus"
}
```

## 与 PROJECT.md 的分工

- **`PROJECT.md`（仓库内）** —— 当前进度、continuation 记录与 development contract。它是给这个仓库自己用的
  时序台账：这一轮做到哪、下一步接什么、还有哪些没关的洞。改代码前先读它（`AGENTS.md` 第 8 行）。
- **agentmemory（仓库外）** —— 跨会话、可检索的结论库。它回答的是「这件事上次是怎么定的」「什么做法不行」，
  入口是全文检索 + `project` 过滤。
- **不要互抄同一段**：PROJECT.md 里已经写过的进度，不要在 agentmemory 里再抄一遍正文；agentmemory 里已落下的
  结论，PROJECT.md 只在需要 continuation 时用一行指针带过（一句话摘要 + 指向 agentmemory）。
- 结论已经属于仓库内某份文档（`docs/design.md`、`docs/acceptance.md`、`docs/agents/*.md`）时，写一行指针即可，
  别把正文复制进 agentmemory。

## 不适用的情况

- 没产生结论的会话（纯浏览、纯问答）。
- 结论只是别人已写下的重复 —— 改去加强那条既有记忆，或者干脆不写。
