def allocate(target, grades, stock, consumed):
    compatible = [
        lot
        for lot in stock
        if grades[lot]["code"] is None
        and grades[lot]["color"] in target["colors"]
        and grades[lot]["grade"] in target["grades"]
    ]
    compatible.sort(
        key=lambda lot: (grades[lot]["impurity_ppm"], stock[lot]["ticket_rows"][0], lot)
    )
    sections = []
    loaded, burden = 0, 0
    limit = target["max_impurity_ppm"]
    limited = False
    for lot in compatible:
        remaining = stock[lot]["dry_g"] - consumed[lot]
        if remaining <= 0:
            continue
        load = min(remaining, target["target_g"] - loaded)
        if load <= 0:
            break
        grade = grades[lot]
        impurity = grade["impurity_ppm"]
        if impurity > limit:
            allowance = (limit * loaded - burden) // (impurity - limit)
            limited |= allowance < load
            load = min(load, allowance)
        if load <= 0:
            continue
        start = consumed[lot]
        consumed[lot] += load
        sections.append(
            {
                "lot": lot,
                "start_g": start,
                "end_g": start + load,
                "dry_g": load,
                "impurity_ppm": impurity,
                "color": grade["color"],
                "grade": grade["grade"],
                "ticket_rows": stock[lot]["ticket_rows"],
                "grade_rows": [item["row"] for item in grade["samples"]],
            }
        )
        loaded += load
        burden += load * impurity
    short = target["target_g"] - loaded
    code = (
        None
        if not short
        else (
            "IMPURITY_LIMIT"
            if limited
            else "GRADE_LIMIT"
            if not compatible and stock
            else "NO_STOCK"
        )
    )
    return dict(
        target,
        sections=sections,
        loaded_g=loaded,
        short_g=short,
        impurity_ppm_g=burden,
        code=code,
    )
