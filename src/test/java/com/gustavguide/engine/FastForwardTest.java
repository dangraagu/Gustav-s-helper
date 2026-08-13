/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import com.gustavguide.IronmanMode;
import com.gustavguide.engine.condition.Condition;
import com.gustavguide.engine.condition.ConstantCondition;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import net.runelite.api.coords.WorldPoint;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * Fast-forward candidates: the flavour steps a user-CONFIRMED sync may mark complete. The boundary is
 * the furthest completed real gate; it must never propose interaction steps, arrival steps, suppressed
 * (explicitly undone) steps, or anything at/after the boundary.
 */
public class FastForwardTest
{
	private static final Set<IronmanMode> ALL = EnumSet.allOf(IronmanMode.class);

	private static RouteStep manual(String id)
	{
		return new RouteStep(id, "S", id, "", null, null, -1, -1, -1, true,
			ALL, Collections.emptyList(), ConstantCondition.MANUAL);
	}

	private static RouteStep npcStep(String id)
	{
		return new RouteStep(id, "S", id, "", null, null, 42, -1, -1, true,
			ALL, Collections.emptyList(), ConstantCondition.MANUAL);
	}

	private static RouteStep gate(String id, Condition c)
	{
		return new RouteStep(id, "S", id, "", null, null, -1, -1, -1, false,
			ALL, Collections.emptyList(), c);
	}

	private static RouteStep arrival(String id)
	{
		return new RouteStep(id, "S", id, "", null, new WorldPoint(3222, 3218, 0), -1, -1, -1, false,
			ALL, Collections.emptyList(),
			new com.gustavguide.engine.condition.PositionCondition(new WorldPoint(3222, 3218, 0), 8));
	}

	@Test
	public void candidatesAreTheFlavourStepsBeforeTheFurthestCompletedGate()
	{
		RouteStep a = manual("a");
		RouteStep talk = npcStep("talk");          // interaction target — never proposed
		RouteStep g = gate("g", ConstantCondition.ALWAYS_TRUE);
		RouteStep after = manual("after");         // after the boundary — never proposed
		Progression p = new Progression(new Route(Arrays.asList(a, talk, g, after)), IronmanMode.REGULAR);
		p.markComplete("g");

		List<String> c = p.fastForwardCandidates();
		assertEquals(Collections.singletonList("a"), c);
	}

	@Test
	public void anArrivalIsNotAGateBoundary()
	{
		// A completed ARRIVAL must not anchor fast-forward — the automatic fold already owns that
		// boundary, and using it here would double up the two mechanisms.
		RouteStep a = manual("a");
		RouteStep arrive = arrival("arrive");
		Progression p = new Progression(new Route(Arrays.asList(a, arrive)), IronmanMode.REGULAR);
		p.markComplete("arrive");
		assertTrue(p.fastForwardCandidates().isEmpty());
	}

	@Test
	public void suppressedStepsStaySuppressed()
	{
		RouteStep a = manual("a");
		RouteStep g = gate("g", ConstantCondition.ALWAYS_TRUE);
		Progression p = new Progression(new Route(Arrays.asList(a, g)), IronmanMode.REGULAR);
		p.markComplete("g");
		p.setSuppressedIds(Collections.singletonList("a"));   // the user explicitly undid "a"
		assertTrue(p.fastForwardCandidates().isEmpty());
	}

	@Test
	public void freshAccountProposesNothing()
	{
		RouteStep a = manual("a");
		RouteStep g = gate("g", ConstantCondition.ALWAYS_TRUE);
		Progression p = new Progression(new Route(Arrays.asList(a, g)), IronmanMode.REGULAR);
		assertTrue(p.fastForwardCandidates().isEmpty());
	}
}
