/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import net.runelite.api.Client;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemContainer;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;
import net.runelite.api.gameval.VarPlayerID;

/**
 * Thin, read-only view over live game state that {@link com.osirisguide.engine.condition.Condition}s
 * evaluate against. Must be constructed and used on the client thread.
 *
 * <p>Bank contents are only available once the player has opened their bank this session;
 * before that {@link #itemCount(ItemScope, int)} for {@link ItemScope#BANK}/{@link ItemScope#ANY}
 * sees whatever RuneLite last cached (possibly nothing). This is an inherent limitation of the
 * client, not a bug.</p>
 */
public class ConditionContext
{
	private final Client client;

	public ConditionContext(Client client)
	{
		this.client = client;
	}

	public Client getClient()
	{
		return client;
	}

	public int skillLevel(Skill skill)
	{
		return client.getRealSkillLevel(skill);
	}

	public QuestState questState(Quest quest)
	{
		return quest.getState(client);
	}

	public int varbit(int varbitId)
	{
		return client.getVarbitValue(varbitId);
	}

	public int varp(int varpId)
	{
		return client.getVarpValue(varpId);
	}

	public int questPoints()
	{
		return client.getVarpValue(VarPlayerID.QP);
	}

	/**
	 * Total count of {@code itemId} in the requested scope. Missing/unseen containers count as 0.
	 */
	public int itemCount(ItemScope scope, int itemId)
	{
		switch (scope)
		{
			case BANK:
				return countIn(InventoryID.BANK, itemId);
			case EQUIPMENT:
				return countIn(InventoryID.EQUIPMENT, itemId);
			case ANY:
				return countIn(InventoryID.INVENTORY, itemId)
					+ countIn(InventoryID.EQUIPMENT, itemId)
					+ countIn(InventoryID.BANK, itemId);
			case INVENTORY:
			default:
				return countIn(InventoryID.INVENTORY, itemId);
		}
	}

	private int countIn(InventoryID inventory, int itemId)
	{
		ItemContainer container = client.getItemContainer(inventory);
		if (container == null)
		{
			return 0;
		}
		return container.count(itemId);
	}
}
