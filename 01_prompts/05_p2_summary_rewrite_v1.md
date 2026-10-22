# 合并实例的简述重写

边界复核把若干相邻实例合成了一条。你只为这些合并后的实例各写一句新的 `normalized_proposition`，不改 span，不判断伤害，不评价作者立场。

规则（与 P2A 第四节相同）：

- 一句话忠实说明整条实例对 Target 做了什么：提出了什么评价，或呈现／支持／限定／反驳了什么评价；
- 保留范围、条件、否定、个案／群体层级和正反方向；
- 案例要说明它呈现或支持什么 Target 判断，不把具体个案改写成群体规律；
- 引述或反驳不改写成作者自己的主张；
- 不新增原文没有的动机、因果或道德标签；
- 不超过 60 字。

输入是 `{"tasks":[{"task_key","target","items":[{"occurrence_id","quote","old_summaries":[...]}]}]}`。`old_summaries` 是被合并各条原来的简述，只作参考，新简述要覆盖整条 quote。

只输出严格 JSON：

```json
{"results": [{"task_key": "…", "summaries": [{"occurrence_id": "O001", "normalized_proposition": "…"}]}]}
```

`results` 与输入 `tasks` 顺序、数量一致；每个 `summaries` 覆盖该任务全部 `items`。
