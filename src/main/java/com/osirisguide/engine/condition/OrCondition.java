/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import java.util.List;
import java.util.stream.Collectors;

public class OrCondition implements Condition
{
	private final List<Condition> conditions;

	public OrCondition(List<Condition> conditions)
	{
		this.conditions = conditions;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		for (Condition c : conditions)
		{
			if (c.isMet(ctx))
			{
				return true;
			}
		}
		return false;
	}

	@Override
	public String describe()
	{
		return "(" + conditions.stream().map(Condition::describe).collect(Collectors.joining(" OR ")) + ")";
	}
}
