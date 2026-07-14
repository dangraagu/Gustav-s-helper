/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;

public class NotCondition implements Condition
{
	private final Condition inner;

	public NotCondition(Condition inner)
	{
		this.inner = inner;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return !inner.isMet(ctx);
	}

	@Override
	public String describe()
	{
		return "NOT " + inner.describe();
	}
}
