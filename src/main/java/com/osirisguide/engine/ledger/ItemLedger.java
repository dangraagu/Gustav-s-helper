/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.ledger;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Tracks item flow purely from observed container snapshots — no game automation, no reflection,
 * just read-only bookkeeping over {@code ItemContainerChanged} data (the same mechanism every
 * loot/bank tracker on the RuneLite Plugin Hub uses).
 *
 * <p>Per tracked item it maintains a monotonic <b>acquired</b> total, the current <b>owned</b> count
 * (sum of live container snapshots), and derives <b>spent</b> = acquired − owned.</p>
 *
 * <h3>How acquisitions are counted (and why transfers don't inflate them)</h3>
 * <ul>
 *   <li>The first snapshot of a container <b>seeds</b> a baseline without counting it — so an
 *       existing account's held items aren't miscounted as freshly obtained.</li>
 *   <li>Each {@link #observe} records the net per-item change of a container into a per-tick
 *       accumulator (positive <i>and</i> negative). {@link #commit}, called once per game tick,
 *       adds only the net positive change to {@code acquired}. Because a withdrawal fires
 *       inventory +N and bank −N in the same tick, the two cancel and no phantom acquisition is
 *       recorded; a genuine pickup (only a rise) accrues.</li>
 *   <li>The full state (acquired totals, live snapshots, seeded containers) is exported/imported so
 *       {@code owned}/{@code spent} are correct immediately after login instead of undercounting
 *       until the bank is next opened.</li>
 * </ul>
 *
 * <p>Not thread-safe; all access happens on the client thread.</p>
 */
public class ItemLedger
{
	/** containerId -> (itemId -> count), filtered to tracked items. */
	private final Map<Integer, Map<Integer, Integer>> current = new HashMap<>();
	/** itemId -> cumulative acquired count. */
	private final Map<Integer, Integer> acquired = new HashMap<>();
	/** itemId -> net change accumulated since the last commit. */
	private final Map<Integer, Integer> pending = new HashMap<>();
	/** container ids that have a baseline snapshot. */
	private final Set<Integer> seeded = new HashSet<>();
	/** null = track everything; otherwise only these ids are tracked. */
	private Set<Integer> itemsOfInterest;

	public void setItemsOfInterest(Set<Integer> ids)
	{
		this.itemsOfInterest = ids == null ? null : new HashSet<>(ids);
	}

	private boolean tracked(int id)
	{
		return itemsOfInterest == null || itemsOfInterest.contains(id);
	}

	private Map<Integer, Integer> filter(Map<Integer, Integer> counts)
	{
		Map<Integer, Integer> m = new HashMap<>();
		if (counts == null)
		{
			return m;
		}
		if (itemsOfInterest == null)
		{
			for (Map.Entry<Integer, Integer> e : counts.entrySet())
			{
				if (e.getValue() != null && e.getValue() > 0)
				{
					m.put(e.getKey(), e.getValue());
				}
			}
		}
		else
		{
			for (int id : itemsOfInterest)
			{
				Integer c = counts.get(id);
				if (c != null && c > 0)
				{
					m.put(id, c);
				}
			}
		}
		return m;
	}

	/**
	 * Record a fresh full snapshot of a container. Does not change {@code acquired} directly — call
	 * {@link #commit} once per tick to fold the accumulated net change in.
	 *
	 * @param containerId the container id (inventory/bank/equipment)
	 * @param counts      itemId -> count for the whole container
	 */
	public void observe(int containerId, Map<Integer, Integer> counts)
	{
		Map<Integer, Integer> next = filter(counts);
		if (!seeded.contains(containerId))
		{
			current.put(containerId, next);
			seeded.add(containerId);
			return;
		}
		Map<Integer, Integer> prev = current.getOrDefault(containerId, new HashMap<>());
		Set<Integer> ids = new HashSet<>(prev.keySet());
		ids.addAll(next.keySet());
		for (int id : ids)
		{
			int delta = next.getOrDefault(id, 0) - prev.getOrDefault(id, 0);
			if (delta != 0)
			{
				pending.merge(id, delta, Integer::sum);
			}
		}
		current.put(containerId, next);
	}

	/**
	 * Fold this tick's net container changes into the acquired totals. Only net-positive changes
	 * accrue, so intra-tick transfers between the player's own containers cancel out.
	 *
	 * @return true if any acquired total increased (caller may persist)
	 */
	public boolean commit()
	{
		boolean changed = false;
		for (Map.Entry<Integer, Integer> e : pending.entrySet())
		{
			if (e.getValue() > 0)
			{
				acquired.merge(e.getKey(), e.getValue(), Integer::sum);
				changed = true;
			}
		}
		pending.clear();
		return changed;
	}

	public int acquired(int id)
	{
		return acquired.getOrDefault(id, 0);
	}

	public int owned(int id)
	{
		int total = 0;
		for (Map<Integer, Integer> c : current.values())
		{
			total += c.getOrDefault(id, 0);
		}
		return total;
	}

	/** Current count of an item in one specific container (0 if that container is unseen). */
	public int ownedIn(int containerId, int id)
	{
		Map<Integer, Integer> c = current.get(containerId);
		return c == null ? 0 : c.getOrDefault(id, 0);
	}

	/** Acquired but no longer held in any observed container — i.e. used, dropped, sold, or consumed. */
	public int spent(int id)
	{
		return Math.max(0, acquired(id) - owned(id));
	}

	/** Ids that have an acquired total, plus any explicitly-of-interest ids — for the ledger view. */
	public Set<Integer> ledgerItems()
	{
		Set<Integer> ids = new HashSet<>(acquired.keySet());
		if (itemsOfInterest != null)
		{
			ids.addAll(itemsOfInterest);
		}
		return ids;
	}

	// ---- persistence --------------------------------------------------------

	/** Serializable snapshot of the whole ledger (persisted per account via Gson). */
	public static class State
	{
		public Map<Integer, Integer> acquired = new HashMap<>();
		public Map<Integer, Map<Integer, Integer>> snapshots = new HashMap<>();
		public Set<Integer> seeded = new HashSet<>();
	}

	public State exportState()
	{
		State s = new State();
		s.acquired = new HashMap<>(acquired);
		s.seeded = new HashSet<>(seeded);
		s.snapshots = new HashMap<>();
		for (Map.Entry<Integer, Map<Integer, Integer>> e : current.entrySet())
		{
			s.snapshots.put(e.getKey(), new HashMap<>(e.getValue()));
		}
		return s;
	}

	public void importState(State s)
	{
		reset();
		if (s == null)
		{
			return;
		}
		if (s.acquired != null)
		{
			acquired.putAll(s.acquired);
		}
		if (s.seeded != null)
		{
			seeded.addAll(s.seeded);
		}
		if (s.snapshots != null)
		{
			for (Map.Entry<Integer, Map<Integer, Integer>> e : s.snapshots.entrySet())
			{
				if (e.getValue() != null)
				{
					current.put(e.getKey(), new HashMap<>(e.getValue()));
				}
			}
		}
	}

	/** Clears everything (used on reset). */
	public void reset()
	{
		acquired.clear();
		current.clear();
		pending.clear();
		seeded.clear();
	}
}
