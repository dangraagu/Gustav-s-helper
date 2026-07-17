/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.teleport;

import java.util.Collection;
import net.runelite.api.Client;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemContainer;
import net.runelite.api.Player;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.Skill;
import net.runelite.api.gameval.VarPlayerID;

/** Live {@link GameSnapshot} backed by the RuneLite client. Construct and use on the client thread. */
public class ClientGameSnapshot implements GameSnapshot
{
	private final Client client;

	public ClientGameSnapshot(Client client)
	{
		this.client = client;
	}

	@Override
	public int skillLevel(Skill skill)
	{
		return client.getRealSkillLevel(skill);
	}

	@Override
	public int totalLevel()
	{
		return client.getTotalLevel();
	}

	@Override
	public int combatLevel()
	{
		Player p = client.getLocalPlayer();
		return p == null ? 3 : p.getCombatLevel();
	}

	@Override
	public int questPoints()
	{
		return client.getVarpValue(VarPlayerID.QP);
	}

	@Override
	public int varbit(int id)
	{
		try
		{
			return client.getVarbitValue(id);
		}
		catch (RuntimeException e)
		{
			// Fail CLOSED: a sentinel that satisfies no "= value" or ">= value" check, so an
			// unresolvable varbit never makes a teleport look available (e.g. spellbook 4070 = 0).
			return Integer.MIN_VALUE;
		}
	}

	@Override
	public int varp(int id)
	{
		try
		{
			return client.getVarpValue(id);
		}
		catch (RuntimeException e)
		{
			return Integer.MIN_VALUE;
		}
	}

	@Override
	public boolean questFinished(String questConstName)
	{
		if (questConstName == null)
		{
			return false;
		}
		try
		{
			return Quest.valueOf(questConstName).getState(client) == QuestState.FINISHED;
		}
		catch (IllegalArgumentException e)
		{
			return false; // unknown quest constant -> can't verify -> treat as not unlocked
		}
	}

	@Override
	public boolean ownsAnyItem(Collection<Integer> itemIds)
	{
		for (InventoryID inv : new InventoryID[]{InventoryID.INVENTORY, InventoryID.EQUIPMENT, InventoryID.BANK})
		{
			ItemContainer c = client.getItemContainer(inv);
			if (c == null)
			{
				continue;
			}
			for (int id : itemIds)
			{
				if (c.count(id) > 0)
				{
					return true;
				}
			}
		}
		return false;
	}
}
