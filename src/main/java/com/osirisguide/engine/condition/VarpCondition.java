/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import com.osirisguide.engine.Op;

public class VarpCondition implements Condition
{
	private final int varpId;
	private final int value;
	private final Op op;

	public VarpCondition(int varpId, int value, Op op)
	{
		this.varpId = varpId;
		this.value = value;
		this.op = op;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return op.test(ctx.varp(varpId), value);
	}

	@Override
	public String describe()
	{
		return "varp " + varpId + " " + op.getSymbol() + " " + value;
	}
}
