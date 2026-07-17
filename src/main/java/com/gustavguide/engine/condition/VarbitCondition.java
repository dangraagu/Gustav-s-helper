/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.condition;

import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.Op;

public class VarbitCondition implements Condition
{
	private final int varbitId;
	private final int value;
	private final Op op;

	public VarbitCondition(int varbitId, int value, Op op)
	{
		this.varbitId = varbitId;
		this.value = value;
		this.op = op;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return op.test(ctx.varbit(varbitId), value);
	}

	@Override
	public String describe()
	{
		return "varbit " + varbitId + " " + op.getSymbol() + " " + value;
	}
}
