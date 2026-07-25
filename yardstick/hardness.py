"""Spider query-difficulty (hardness) classification.

These functions are copied VERBATIM from the official Spider evaluation script
(taoyds/spider `evaluation.py`, CC BY-SA 4.0) and operate on Spider's parsed
`sql` dict, the structure already present in train_spider.json / dev.json.
Vendoring just this slice avoids pulling in `nltk` (which process_sql.py needs).

Using the official algorithm means our complexity tiers are externally defined,
not our own judgement (spec §4.3), and gives the difficulty-predictor a real
external validation target (spec §11.5).

Tier mapping (spec §4.3):  easy → simple, medium → moderate, hard+extra → complex
"""
from __future__ import annotations

# Constants from process_sql.py / evaluation.py (verbatim).
WHERE_OPS = ('not', 'between', '=', '>', '<', '>=', '<=', '!=', 'in', 'like', 'is', 'exists')
AGG_OPS = ('none', 'max', 'min', 'count', 'sum', 'avg')

DIFFICULTY_TO_TIER = {
    "easy": "simple",
    "medium": "moderate",
    "hard": "complex",
    "extra": "complex",
}


def has_agg(unit) -> bool:
    return unit[0] != AGG_OPS.index('none')


def count_agg(units) -> int:
    return len([unit for unit in units if has_agg(unit)])


def get_nestedSQL(sql):
    nested = []
    for cond_unit in sql['from']['conds'][::2] + sql['where'][::2] + sql['having'][::2]:
        if type(cond_unit[3]) is dict:
            nested.append(cond_unit[3])
        if type(cond_unit[4]) is dict:
            nested.append(cond_unit[4])
    if sql['intersect'] is not None:
        nested.append(sql['intersect'])
    if sql['except'] is not None:
        nested.append(sql['except'])
    if sql['union'] is not None:
        nested.append(sql['union'])
    return nested


def count_component1(sql) -> int:
    count = 0
    if len(sql['where']) > 0:
        count += 1
    if len(sql['groupBy']) > 0:
        count += 1
    if len(sql['orderBy']) > 0:
        count += 1
    if sql['limit'] is not None:
        count += 1
    if len(sql['from']['table_units']) > 0:  # JOIN
        count += len(sql['from']['table_units']) - 1

    ao = sql['from']['conds'][1::2] + sql['where'][1::2] + sql['having'][1::2]
    count += len([token for token in ao if token == 'or'])
    cond_units = sql['from']['conds'][::2] + sql['where'][::2] + sql['having'][::2]
    count += len([cond_unit for cond_unit in cond_units if cond_unit[1] == WHERE_OPS.index('like')])

    return count


def count_component2(sql) -> int:
    nested = get_nestedSQL(sql)
    return len(nested)


def count_others(sql) -> int:
    count = 0
    # number of aggregation
    agg_count = count_agg(sql['select'][1])
    agg_count += count_agg(sql['where'][::2])
    agg_count += count_agg(sql['groupBy'])
    if len(sql['orderBy']) > 0:
        agg_count += count_agg([unit[1] for unit in sql['orderBy'][1] if unit[1]] +
                               [unit[2] for unit in sql['orderBy'][1] if unit[2]])
    agg_count += count_agg(sql['having'])
    if agg_count > 1:
        count += 1

    # number of select columns
    if len(sql['select'][1]) > 1:
        count += 1

    # number of where conditions
    if len(sql['where']) > 1:
        count += 1

    # number of group by clauses
    if len(sql['groupBy']) > 1:
        count += 1

    return count


def eval_hardness(sql) -> str:
    """Return one of: 'easy', 'medium', 'hard', 'extra' (verbatim official logic)."""
    count_comp1_ = count_component1(sql)
    count_comp2_ = count_component2(sql)
    count_others_ = count_others(sql)

    if count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ == 0:
        return "easy"
    elif (count_others_ <= 2 and count_comp1_ <= 1 and count_comp2_ == 0) or \
            (count_comp1_ <= 2 and count_others_ < 2 and count_comp2_ == 0):
        return "medium"
    elif (count_others_ > 2 and count_comp1_ <= 2 and count_comp2_ == 0) or \
            (2 < count_comp1_ <= 3 and count_others_ <= 2 and count_comp2_ == 0) or \
            (count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ <= 1):
        return "hard"
    else:
        return "extra"


def tier_of(sql) -> str:
    """Map a parsed Spider sql dict to our complexity tier: simple/moderate/complex."""
    return DIFFICULTY_TO_TIER[eval_hardness(sql)]
