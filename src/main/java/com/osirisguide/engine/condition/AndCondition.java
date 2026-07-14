/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import java.util.List;
import java.util.stream.Collectors;

public class AndCondition implements Condition
{
	private final List<Condition> conditions;

	public AndCondition(List<Condition> conditions)
	{
		this.conditions = conditions;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		for (Condition c : conditions)
		{
			if (!c.isMet(ctx))
			{
				return false;
			}
		}
		return true;
	}

	@Override
	public String describe()
	{
		return "(" + conditions.stream().map(Condition::describe).collect(Collectors.joining(" AND ")) + ")";
	}
}
