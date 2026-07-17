/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.teleport;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import com.google.gson.Gson;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;
import org.junit.Test;

public class TeleportDbTest
{
	// Varrock spell (needs 25 Magic + standard spellbook varbit 4070=0); Camelot (45 Magic);
	// a far unrestricted teleport; and a locked one gated on an unfinished quest.
	private static final String JSON =
		"[{\"name\":\"Varrock\",\"dest\":[3213,3424,0],\"type\":\"spell\","
		+ "\"reqs\":{\"skills\":{\"MAGIC\":25},\"varbits\":[{\"id\":4070,\"op\":\"=\",\"value\":0}]}},"
		+ "{\"name\":\"Camelot\",\"dest\":[2757,3479,0],\"type\":\"spell\","
		+ "\"reqs\":{\"skills\":{\"MAGIC\":45},\"varbits\":[{\"id\":4070,\"op\":\"=\",\"value\":0}]}},"
		+ "{\"name\":\"Faraway\",\"dest\":[1600,3500,0],\"type\":\"other\"},"
		+ "{\"name\":\"LockedNearVarrock\",\"dest\":[3214,3425,0],\"type\":\"item\","
		+ "\"reqs\":{\"quests\":[\"NOT_DONE_QUEST\"]}}]";

	private static TeleportDb db()
	{
		return TeleportDb.parse(new Gson(), JSON);
	}

	private static Snap snap(int magic)
	{
		Snap s = new Snap();
		s.magic = magic;
		s.varbits.put(4070, 0);     // standard spellbook
		return s;
	}

	@Test
	public void picksNearestUnlockedTeleport()
	{
		// Target = Varrock, player far west. Varrock spell is unlocked (30 magic) and nearest.
		TeleportDb.Teleport t = db().best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), snap(30));
		assertEquals("Varrock", t.getName());
	}

	@Test
	public void skipsLockedTeleportEvenIfNearest()
	{
		// LockedNearVarrock sits 1 tile from the target but its quest isn't finished -> must be skipped;
		// falls back to the Varrock spell (also unlocked).
		TeleportDb.Teleport t = db().best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), snap(30));
		assertEquals("Varrock", t.getName());
	}

	@Test
	public void spellSkippedWhenLevelTooLow()
	{
		// 20 magic: Varrock (25) and Camelot (45) both locked; only "Faraway" is unrestricted, but it's
		// nowhere near the Varrock target -> no worthwhile teleport.
		assertNull(db().best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), snap(20)));
	}

	@Test
	public void noTeleportWhenAlreadyClose()
	{
		// Player already standing on the target -> a teleport saves nothing.
		assertNull(db().best(new WorldPoint(3213, 3424, 0), new WorldPoint(3213, 3424, 0), snap(99)));
	}

	@Test
	public void wrongSpellbookLocksSpell()
	{
		Snap s = snap(99);
		s.varbits.put(4070, 2);     // lunar spellbook -> standard Varrock teleport unavailable
		assertNull(db().best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), s));
	}

	@Test
	public void skipsTeleportOnADifferentFloor()
	{
		// Same x/y as the target but plane 2 -> not a walkable arrival; must not be chosen even though
		// its (plane-blind) distance would be 0.
		String json = "[{\"name\":\"UpstairsClone\",\"dest\":[3213,3424,2],\"type\":\"other\"}]";
		assertNull(TeleportDb.parse(new Gson(), json)
			.best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), snap(99)));
	}

	@Test
	public void skipsDailyChargeTeleport()
	{
		// A daily-charge teleport (charges not in the data) must never be claimed usable, even when
		// nearest and its item is owned.
		String json = "[{\"name\":\"Ardy cloak farm\",\"dest\":[3213,3424,0],\"type\":\"jewellery\","
			+ "\"req\":\"Ardougne cloak, limited daily charges\",\"reqs\":{\"items\":[13122]}}]";
		Snap s = snap(99);
		s.owned.add(13122);
		assertNull(TeleportDb.parse(new Gson(), json)
			.best(new WorldPoint(3213, 3424, 0), new WorldPoint(2000, 3200, 0), s));
	}

	private static final class Snap implements GameSnapshot
	{
		int magic;
		final Map<Integer, Integer> varbits = new HashMap<>();
		final Set<Integer> owned = new HashSet<>();

		public int skillLevel(Skill skill)
		{
			return skill == Skill.MAGIC ? magic : 1;
		}

		public int totalLevel()
		{
			return 500;
		}

		public int combatLevel()
		{
			return 50;
		}

		public int questPoints()
		{
			return 50;
		}

		public int varbit(int id)
		{
			return varbits.getOrDefault(id, 0);
		}

		public int varp(int id)
		{
			return 0;
		}

		public boolean questFinished(String questConstName)
		{
			return false;   // no quests finished in these tests
		}

		public boolean ownsAnyItem(Collection<Integer> itemIds)
		{
			for (int id : itemIds)
			{
				if (owned.contains(id))
				{
					return true;
				}
			}
			return false;
		}
	}
}
