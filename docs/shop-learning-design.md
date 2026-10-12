# 商店策略学习的实现与验收

MaaFramework 的 native OCR/NNDetect 负责感知，ProjectInterface/MXU 启动同一
Python Agent Custom Action；购买策略由 Agent 决策，事务仍负责执行与后继对账。
官方 MAA 的 RoguelikeShoppingTaskPlugin 目前读取人工 priority 与队伍条件，
不是可直接移植的在线购买强化学习器：
https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/master/src/MaaCore/Task/Roguelike/RoguelikeShoppingTaskPlugin.cpp

已接通的层次：

- `shop-priorities.json` 给通用经济品显式人工权重。它们在关键词过滤前成为候选，
  但仍受 saved-team block、已购买名单、实际报价、金币保留和刷新上限约束。
  黑色卡面的 Prestige Card 优先 100；其他经济预设是人工策略，不是学出的收益。
  暂不自动购买只有强化/技能替换收益的商品，因为对应消费策略尚未完整验收。
- `shop_outcomes.sync` 从已验证购买生成内容寻址样本，保存报价/购买问句/GET/
  货架的 PNG、JSON、哈希、决策上下文及后续同 scope 的完成观察。未知效果不
  填零，不把购买成功标成购买有益，不把未购买商品标成负样本。
- `shop_learning` 只从完整货架和真实经费差学习刷新产出；买入价值当前仍回退
  规则。执行成功、刷新产出、战斗/结算结果、人工评价是不同标签。

购买价值神经模型仍待实现和训练。输入要包含队伍/体系、持有藏品、当前楼层、
  可见经费与完整报价、保留额、刷新次数、动作，以及这些字段的缺失掩码；输出
  是候选动作的预期后续收益与不确定度。训练按独立 run scope 划分，不能把同局
  邻近帧分到训练和测试两侧；验证要对照人工/规则基线，且记录失败或未知样本。

上线顺序是先收集、离线训练、原生/Agent shadow 复播、独立局测试，最后在硬
  预算内应用。神经策略只能排序已允许且可支付的动作，不得绕过 Purchase/GET/
  Purchased 对账、增加刷新上限、篡改保留额、把自标签直接当真实效果或提高消费。
  小样本没有模型时继续有界规则执行并记录样本，不因模型缺失停止整条镜牢。

验收同时要求真实 GUI Start 整条镜牢、交易收据与规则/神经各自的决策 trace。
测试通过、训练文件存在、标签目录增长，都不等于学习策略生效或五层通关。
