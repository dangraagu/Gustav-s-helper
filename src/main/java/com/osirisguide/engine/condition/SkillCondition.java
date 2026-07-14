/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import com.osirisguide.engine.Op;
import net.runelite.api.Skill;

public class SkillCondition implements Condition
{
	private final Skill skill;
	private final int level;
	private final Op op;

	public SkillCondition(Skill skill, int level, Op op)
	{
		this.skill = skill;
		this.level = level;
		this.op = op;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return op.test(ctx.skillLevel(skill), level);
	}

	@Override
	public String describe()
	{
		return skill.getName() + " " + op.getSymbol() + " " + level;
	}
}
