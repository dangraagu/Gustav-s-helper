/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.teleport;

import com.google.gson.Gson;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;

/**
 * The teleport catalogue (extracted from the Shortest Path plugin's transport data — BSD-2, see
 * NOTICE). Each teleport carries a destination and machine-checkable UNLOCK requirements, so the
 * plugin only ever suggests a teleport the player can actually use ({@link #best}).
 *
 * <p>Consumables (jewellery/tabs) count as unlocked when OWNED; spell teleports gate on magic level +
 * spellbook varbit + any quest, not on carrying runes.</p>
 */
@Slf4j
public final class TeleportDb
{
	/** A teleport must land at least this many tiles closer to the target than the player already is,
	 *  otherwise walking is just as good and no teleport is suggested. */
	private static final int MIN_SAVING = 15;

	private final List<Teleport> teleports;

	private TeleportDb(List<Teleport> teleports)
	{
		this.teleports = teleports;
	}

	public boolean isEmpty()
	{
		return teleports.isEmpty();
	}

	public int size()
	{
		return teleports.size();
	}

	/** Loads the bundled catalogue; returns an empty DB (never null) if it's missing/unreadable. */
	public static TeleportDb load(Gson gson)
	{
		try (InputStream in = TeleportDb.class.getResourceAsStream("/com/osirisguide/data/teleports.json"))
		{
			if (in == null)
			{
				log.warn("Gustav's Helper: teleports.json not found on the classpath");
				return new TeleportDb(new ArrayList<>());
			}
			return fromDtos(gson.fromJson(new InputStreamReader(in, StandardCharsets.UTF_8), Dto[].class));
		}
		catch (Exception e) // noqa: broad — a bad data file must never break plugin start-up
		{
			log.warn("Gustav's Helper: could not load teleports.json: {}", e.getMessage());
			return new TeleportDb(new ArrayList<>());
		}
	}

	/** Build from a JSON array string (used by tests). */
	static TeleportDb parse(Gson gson, String json)
	{
		return fromDtos(gson.fromJson(json, Dto[].class));
	}

	private static TeleportDb fromDtos(Dto[] raw)
	{
		List<Teleport> out = new ArrayList<>();
		if (raw != null)
		{
			for (Dto d : raw)
			{
				if (d != null && d.dest != null && d.dest.length >= 2 && d.name != null)
				{
					out.add(new Teleport(d));
				}
			}
		}
		return new TeleportDb(out);
	}

	/**
	 * The best UNLOCKED teleport for reaching {@code target} from {@code player}: the available teleport
	 * whose destination is nearest the target, but only when it lands meaningfully ({@link #MIN_SAVING})
	 * closer than the player already is. Returns null if the player is already close, or nothing is
	 * both unlocked and closer.
	 */
	public Teleport best(WorldPoint target, WorldPoint player, GameSnapshot snap)
	{
		if (teleports.isEmpty() || target == null)
		{
			return null;
		}
		int playerDist = player == null ? Integer.MAX_VALUE : chebyshev(player, target);
		Teleport best = null;
		int bestDist = playerDist - MIN_SAVING;   // must beat this to be worth a teleport
		for (Teleport t : teleports)
		{
			WorldPoint dest = t.getDest();
			// A teleport that lands on a different floor than the target isn't a walkable arrival, and a
			// daily-charge teleport can't be verified as usable (charges aren't in the data) — skip both.
			if (dest.getPlane() != target.getPlane() || t.isDailyLimited())
			{
				continue;
			}
			int d = chebyshev(dest, target);
			if (d < bestDist && t.available(snap))
			{
				best = t;
				bestDist = d;
			}
		}
		return best;
	}

	private static int chebyshev(WorldPoint a, WorldPoint b)
	{
		return Math.max(Math.abs(a.getX() - b.getX()), Math.abs(a.getY() - b.getY()));
	}

	// ---- data ---------------------------------------------------------------

	/** A single teleport with its unlock requirements. */
	public static final class Teleport
	{
		private final Dto d;
		private final WorldPoint dest;

		Teleport(Dto d)
		{
			this.d = d;
			int plane = d.dest.length >= 3 ? d.dest[2] : 0;
			this.dest = new WorldPoint(d.dest[0], d.dest[1], plane);
		}

		public String getName()
		{
			return d.name;
		}

		public WorldPoint getDest()
		{
			return dest;
		}

		public String getReqText()
		{
			return d.req;
		}

		/** True if this teleport has a finite daily charge count (which the data can't verify), so it
		 *  must not be suggested as always-usable. */
		public boolean isDailyLimited()
		{
			return d.req != null && d.req.toLowerCase().contains("daily charge");
		}

		/** True if every requirement is satisfied for the given player state (unknown -> not met). */
		public boolean available(GameSnapshot snap)
		{
			Reqs r = d.reqs;
			if (r == null)
			{
				return true; // no requirements -> always usable
			}
			if (r.skills != null)
			{
				for (Map.Entry<String, Integer> e : r.skills.entrySet())
				{
					Skill sk = parseSkill(e.getKey());
					if (sk == null || snap.skillLevel(sk) < e.getValue())
					{
						return false;
					}
				}
			}
			if (r.varbits != null)
			{
				for (Cmp c : r.varbits)
				{
					if (!c.test(snap.varbit(c.id)))
					{
						return false;
					}
				}
			}
			if (r.varplayers != null)
			{
				for (Cmp c : r.varplayers)
				{
					if (!c.test(snap.varp(c.id)))
					{
						return false;
					}
				}
			}
			if (r.quests != null)
			{
				for (String q : r.quests)
				{
					if (!snap.questFinished(q))
					{
						return false;
					}
				}
			}
			if (r.items != null && !r.items.isEmpty() && !snap.ownsAnyItem(r.items))
			{
				return false;
			}
			return snap.totalLevel() >= r.totalLevel
				&& snap.questPoints() >= r.questPoints
				&& snap.combatLevel() >= r.combatLevel;
		}

		private static Skill parseSkill(String name)
		{
			try
			{
				return Skill.valueOf(name);
			}
			catch (IllegalArgumentException e)
			{
				return null;
			}
		}
	}

	private static final class Dto
	{
		String name;
		int[] dest;
		String type;
		String req;
		Reqs reqs;
	}

	private static final class Reqs
	{
		Map<String, Integer> skills;
		List<Cmp> varbits;
		List<Cmp> varplayers;
		List<String> quests;
		List<Integer> items;
		int totalLevel;
		int questPoints;
		int combatLevel;
	}

	private static final class Cmp
	{
		int id;
		String op;
		int value;

		boolean test(int actual)
		{
			if (op == null)
			{
				return actual >= value;
			}
			switch (op)
			{
				case "=":
				case "==":
					return actual == value;
				case "<":
					return actual < value;
				case "<=":
					return actual <= value;
				case ">":
					return actual > value;
				case ">=":
				default:
					return actual >= value;
			}
		}
	}
}
