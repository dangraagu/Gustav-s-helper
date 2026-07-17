/*
 * Copyright (c) 2026, dangraagu
 * Requirement display model adapted from RuneLite Quest Helper (BSD 2-Clause). See NOTICE.
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.requirement;

import com.gustavguide.engine.ConditionContext;
import net.runelite.api.Skill;

public class SkillRequirement implements Requirement
{
	private final Skill skill;
	private final int level;

	public SkillRequirement(Skill skill, int level)
	{
		this.skill = skill;
		this.level = level;
	}

	@Override
	public boolean check(ConditionContext ctx)
	{
		return ctx.skillLevel(skill) >= level;
	}

	@Override
	public String getText()
	{
		return level + " " + skill.getName();
	}
}
