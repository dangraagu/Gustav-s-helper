/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;

public class QuestCondition implements Condition
{
	private final Quest quest;
	private final QuestState desired;

	public QuestCondition(Quest quest, QuestState desired)
	{
		this.quest = quest;
		this.desired = desired;
	}

	/** The quest this condition gates on — used to drive Quest Helper / look up quest-start coords. */
	public Quest getQuest()
	{
		return quest;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		QuestState state = ctx.questState(quest);
		if (desired == QuestState.IN_PROGRESS)
		{
			// "started or finished" is the useful interpretation of IN_PROGRESS as a gate
			return state == QuestState.IN_PROGRESS || state == QuestState.FINISHED;
		}
		return state == desired;
	}

	@Override
	public String describe()
	{
		return quest.getName() + " = " + desired;
	}
}
