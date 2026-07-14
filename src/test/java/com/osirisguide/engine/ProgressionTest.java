/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;

import com.osirisguide.IronmanMode;
import com.osirisguide.engine.condition.Condition;
import com.osirisguide.engine.condition.ConstantCondition;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumSet;
import java.util.Set;
import net.runelite.api.Client;
import org.junit.Test;

public class ProgressionTest
{
	private static RouteStep step(String id, Condition complete, boolean manual, Set<IronmanMode> modes)
	{
		return new RouteStep(id, "Section", id, "", null, null, -1, -1, -1, manual,
			modes, Collections.emptyList(), complete);
	}

	private static ConditionContext ctx()
	{
		// All conditions used here are constants and never touch the client.
		return new ConditionContext(mock(Client.class));
	}

	@Test
	public void autoCompletesSatisfiedStepsAndAdvances()
	{
		RouteStep a = step("a", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		RouteStep b = step("b", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep c = step("c", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, b, c)), IronmanMode.REGULAR);

		assertEquals("a", p.getCurrentStep().getId());

		assertTrue(p.process(ctx()));            // a and c auto-complete; b (manual) does not
		assertEquals("b", p.getCurrentStep().getId());
		assertTrue(p.isComplete("a"));
		assertTrue(p.isComplete("c"));
		assertFalse(p.isComplete("b"));
		assertEquals(67, p.progressPercent());   // 2 of 3
	}

	@Test
	public void manualCompletionFinishesRoute()
	{
		RouteStep a = step("a", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Collections.singletonList(a)), IronmanMode.REGULAR);

		assertEquals("a", p.getCurrentStep().getId());
		p.markComplete("a");
		assertNull(p.getCurrentStep());
		assertEquals(100, p.progressPercent());
	}

	@Test
	public void modeFilteringSkipsInapplicableSteps()
	{
		RouteStep hcOnly = step("hc", ConstantCondition.MANUAL, true, EnumSet.of(IronmanMode.HCIM));
		RouteStep any = step("any", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(hcOnly, any)), IronmanMode.REGULAR);

		// hcOnly does not apply in REGULAR, so current is "any"
		assertEquals("any", p.getCurrentStep().getId());
		assertEquals(1, p.applicableCount());

		p.setMode(IronmanMode.HCIM);
		assertEquals("hc", p.getCurrentStep().getId());
		assertEquals(2, p.applicableCount());
	}

	@Test
	public void resetAndPersistenceRoundTrip()
	{
		RouteStep a = step("a", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		RouteStep b = step("b", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, b)), IronmanMode.REGULAR);

		p.process(ctx());
		p.markComplete("b");
		assertEquals(2, p.getCompletedIds().size());

		Progression restored = new Progression(new Route(Arrays.asList(a, b)), IronmanMode.REGULAR);
		restored.setCompletedIds(p.getCompletedIds());
		assertTrue(restored.isComplete("a"));
		assertTrue(restored.isComplete("b"));
		assertNull(restored.getCurrentStep());

		restored.reset();
		assertEquals("a", restored.getCurrentStep().getId());
		assertEquals(0, restored.getCompletedIds().size());
	}
}
