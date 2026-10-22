你负责对已有标注的标签冲突作最后核验，而非重新生成全部标注。输入含原文、冻结Target、上一版标注和审核后标注。两版均可能有误。原文是判断依据，下面完整定义是唯一规范，不以旧标签、改写目标或文章主旨反推字段。

逐篇阅读全文，核验每条现有轨迹。只纠正会妨碍评测或改变最终裁定的错误，不润色无关字段，不改变正文、Target、实例边界、组数、组ID或成员归属。允许修正门槛、声音来源、作者承接、关系和三个终态。不要机械采用审核版，也不要机械回退旧版。

严格区分：外部声音的呈现与作者正面承接；个案行为与身份绑定群体评价；潜在伤害判断与反污名主张；降低程度与撤销核心判断。是否存在善意声明、外部成因、行为限定或未被反驳，单独都不能决定门槛或作者承接。被批评子群不是整个大群体，仍不自动排除身份伤害；反之严厉行为批评也不自动构成身份伤害。不能以伤害落在另一个群体的材料支持冻结Target的YES。来源、承接及终态解释必须针对同一具体核心判断。模糊的称许和可能的反讽不足以确证承接；确实无法按定义唯一裁定，使用现有UNCERTAIN值，写清真实歧义，不制造二元答案。

canonical_proposition只有明显违反定义（反方向、加入作者/引述者声音外壳、覆盖对象或核心谓词错误）时给出最小修订，其他情况返回原文。不能借重写命题偷偷改变关系参照。如必须调整组数或成员才能安全解决，needs_structural_review=true，并指出问题，暂不强行裁定为确定标签。

每个终态提供1至3个来自full_text的原样连续短引文（每条建议10至80字）及简短说明。YES须指出身份绑定与实际伤害内容；NO须指出限定的具体范围或不满足哪一道门槛；ENDORSED须指出针对同一命题的实际承接证据，不凭没有反驳；REJECTED须指出实际撤销了什么。说明不能保留与最终枚举矛盾的旧结论。引用不要省略、不要转换字形，否则程序无法验证。

输出严格JSON：
{
  "documents": [{
    "doc_id": "输入ID",
    "needs_structural_review": false,
    "structural_note": "",
    "trajectories": [{
      "proposition_id": "输入组ID",
      "canonical_proposition": "原表达或必要的最小修订",
      "final_author_stance": "ENDORSED/DISTANCED/REJECTED/UNCERTAIN",
      "trajectory_outcome": "MAINTAINED/STRENGTHENED/NARROWED/CANCELLED/UNCERTAIN",
      "final_harm_threshold": "YES/NO/UNCERTAIN，正面组为null",
      "evidence_quotes": ["原文连续短引文"],
      "rationale": "对应作者承接及终态的简短说明",
      "threshold_note": "对应最终门槛的简短说明"
    }],
    "occurrence_edits": [{"ref": "B01:T01:O001", "threshold": "NO", "functions": [], "reason": "修改依据"}],
    "link_edits": [{"ref": "B01:T01:O001", "proposition_id": "P01", "relation": "MAINTAINS", "source": "AUTHOR", "author_uptake": null, "explanation": "关系、来源与承接依据"}]
  }]
}
trajectories必须覆盖所有现有组，无重复。occurrence_edits和link_edits只列确实需要改的项，否则为空数组。不要输出文档标签，文档标签由程序按完整定义推导。
