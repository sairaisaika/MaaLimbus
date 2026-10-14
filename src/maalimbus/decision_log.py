"""Human-readable traces of actual decision inputs, never invented model scores."""
import json

def lines(event, fields):
    if event in ('floor_gift_ranking','floor_gift_bounded_exploration_ranking'):
        result=['藏品评分：规则分，越低越优先；同分按名称。学习模型未参与此评分。']
        for n,row in enumerate(fields.get('ranking') or [],1):
            parts=row.get('score_components')
            detail=' '.join(f'{k}={v:+g}' for k,v in parts.items()) if parts else '旧记录未提供分项'
            result.append(f"候选{n} {row['title']}：{detail}；最终分={row['score']}"+('；首选候选' if n==1 else ''))
        return result
    if event=='theme_pack_recommendation':
        chosen=(fields.get('chosen') or {}).get('name')
        result=['主题评分：保存权重，越高越优先；同分按画面从左到右。']
        for row in fields.get('ranking') or []:
            result.append(f"{row['name']}：权重={row['weight']}；最终分={row['weight']}；来源={row['reason']}"+('；选择' if row['name']==chosen else ''))
        return result
    if event=='shop_decision_ranking':
        result=[f"商店选择：{fields.get('reason')}；金币={fields.get('currency')}；保留={fields.get('reserve')}；刷新上限={fields.get('refresh_limit')}。队列分越高越优先，不代表藏品强度。"]
        for row in fields.get('ranking') or []:
            result.append(f"{row['name']}：价格={row['price']}；手动权重={row.get('manual_weight',0)}；队列分={row.get('score')}；{row['status']}"+('；选择购买' if row.get('chosen') else ''))
        trace=fields.get('learning') or {}
        result.append('学习参与：'+('仅影子预测，不改变购买顺序' if trace.get('neural_value_shadow_applied') else '未使用神经价值模型')+'；'+str(trace.get('refresh_reason') or trace.get('reason') or '规则回退'))
        return result
    return []

def signature(event,fields):
    return json.dumps([event,fields],sort_keys=True,ensure_ascii=False,default=str)
