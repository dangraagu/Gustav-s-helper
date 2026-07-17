/*
 * Copyright (c) 2026, dangraagu
 * Requirement display model adapted from RuneLite Quest Helper (BSD 2-Clause). See NOTICE.
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.requirement;

import com.gustavguide.engine.ConditionContext;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;

public class QuestRequirement implements Requirement
{
	private final Quest quest;
	private final QuestState required;

	public QuestRequirement(Quest quest, QuestState required)
	{
		this.quest = quest;
		this.required = required;
	}

	@Override
	public boolean check(ConditionContext ctx)
	{
		QuestState state = ctx.questState(quest);
		if (required == QuestState.IN_PROGRESS)
		{
			return state == QuestState.IN_PROGRESS || state == QuestState.FINISHED;
		}
		return state == required;
	}

	@Override
	public String getText()
	{
		String prefix = required == QuestState.FINISHED ? "" : "Start ";
		return prefix + quest.getName();
	}
}
