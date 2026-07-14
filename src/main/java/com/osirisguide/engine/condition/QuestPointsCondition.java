/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import com.osirisguide.engine.Op;

public class QuestPointsCondition implements Condition
{
	private final int points;
	private final Op op;

	public QuestPointsCondition(int points, Op op)
	{
		this.points = points;
		this.op = op;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return op.test(ctx.questPoints(), points);
	}

	@Override
	public String describe()
	{
		return "quest points " + op.getSymbol() + " " + points;
	}
}
