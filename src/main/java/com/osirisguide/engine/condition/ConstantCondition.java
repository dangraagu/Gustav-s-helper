/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;

/**
 * Always-true or always-false condition. {@link #MANUAL} (always false) is used for steps
 * with no auto-detection — they only complete when the user ticks them in the panel.
 */
public class ConstantCondition implements Condition
{
	public static final ConstantCondition ALWAYS_TRUE = new ConstantCondition(true);
	public static final ConstantCondition MANUAL = new ConstantCondition(false);

	private final boolean value;

	public ConstantCondition(boolean value)
	{
		this.value = value;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return value;
	}

	@Override
	public String describe()
	{
		return value ? "always" : "manual";
	}
}
