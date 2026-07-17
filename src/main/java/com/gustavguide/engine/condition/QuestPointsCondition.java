/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.condition;

import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.Op;

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
