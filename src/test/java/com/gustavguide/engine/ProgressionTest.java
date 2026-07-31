/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.gustavguide.IronmanMode;
import com.gustavguide.engine.condition.Condition;
import com.gustavguide.engine.condition.ConstantCondition;
import com.gustavguide.engine.condition.PositionCondition;
import com.gustavguide.engine.condition.SkillCondition;
import java.util.Arrays;
import java.util.Collections;
import java.util.EnumSet;
import java.util.Set;
import net.runelite.api.Client;
import net.runelite.api.Player;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;
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

	private static ConditionContext ctxAt(int x, int y, int plane)
	{
		Client c = mock(Client.class);
		Player p = mock(Player.class);
		when(c.getLocalPlayer()).thenReturn(p);
		when(p.getWorldLocation()).thenReturn(new WorldPoint(x, y, plane));
		return new ConditionContext(c);
	}

	private static RouteStep positionStep(String id, int x, int y, int radius)
	{
		return new RouteStep(id, "Section", id, "", null, null, -1, -1, -1, false,
			Collections.emptySet(), Collections.emptyList(), new PositionCondition(new WorldPoint(x, y, 0), radius));
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
	public void foldsManualFlavourBehindAnArrival()
	{
		// a,b are manual flavour; 'go' is a travel/arrival step the player physically reaches; d is manual
		// and comes AFTER it. Arriving (a position step completing, in-order per process()) is the only
		// thing that proves you walked past a,b — so a,b fold and d (past the arrival) does not.
		RouteStep a = step("a", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep b = step("b", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep go = positionStep("go", 3200, 3200, 10);
		RouteStep d = step("d", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, b, go, d)), IronmanMode.REGULAR);

		assertTrue(p.process(ctxAt(3200, 3200, 0)));        // 'go' completes on arrival (only soft manuals precede)
		assertEquals("a", p.getCurrentStep().getId());      // still stuck on the first manual step

		assertTrue(p.foldManualBehindMilestones());         // a,b fold (before the arrival); d must NOT
		assertTrue(p.isComplete("a"));
		assertTrue(p.isComplete("b"));
		assertTrue(p.isComplete("go"));
		assertFalse(p.isComplete("d"));
		assertEquals("d", p.getCurrentStep().getId());      // advanced to the next real work

		assertFalse(p.foldManualBehindMilestones());        // idempotent: nothing left to fold
	}

	@Test
	public void skillOrQuestMilestoneDoesNotDriveTheFold()
	{
		// A skill/quest satisfied OUT OF ORDER (here ALWAYS_TRUE stands in) is NOT a fold boundary — only
		// an arrival is. So a manual flavour step is NOT folded merely because a later non-position step
		// is complete. This is the structural guarantee against the "162" cascade.
		RouteStep a = step("a", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep questDoneOutOfOrder = step("q", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, questDoneOutOfOrder)), IronmanMode.REGULAR);

		p.process(ctx());                                   // q completes (out of order); a manual
		assertFalse(p.foldManualBehindMilestones());        // no arrival -> nothing folds
		assertFalse(p.isComplete("a"));
		assertEquals("a", p.getCurrentStep().getId());
	}

	@Test
	public void foldStopsAtFirstUnmetGateAndNeverSkipsRealWork()
	{
		// a = manual flavour BEFORE an unmet gate; gate = real (non-manual) work NOT met; c = a step that
		// is satisfied (here ALWAYS_TRUE, standing in for a quest/skill met OUT OF ORDER) sitting AFTER
		// the gate. The fold frontier must STOP at the unmet gate: neither the gate (real work) nor the
		// flavour before it may be folded on the strength of an out-of-order completion after the gate.
		RouteStep a = step("a", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep gate = step("gate", new SkillCondition(Skill.ATTACK, 99, Op.GE), false, Collections.emptySet());
		RouteStep c = step("c", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, gate, c)), IronmanMode.REGULAR);

		p.process(ctx());                                   // c completes; gate unmet (level 0 < 99); a manual
		assertFalse(p.foldManualBehindMilestones());        // nothing reached in sequence -> nothing folds
		assertFalse(p.isComplete("a"));                     // flavour before an un-passed gate is NOT folded
		assertFalse(p.isComplete("gate"));                  // real work is NEVER skipped
		assertEquals("a", p.getCurrentStep().getId());      // still at the first real step
	}

	@Test
	public void foldDoesNotCascadeBehindAnOutOfOrderDeepMilestone()
	{
		// The 162-bug repro: an early UNMET gate (e.g. the optional "43 Prayer" step the player skipped),
		// then a run of manual flavour steps, then a step whose quest/skill is satisfied OUT OF ORDER far
		// ahead. The old fold treated that deep completion as "you reached here" and folded every manual
		// before it (~150 steps). It must NOT: the unmet gate bounds the reachable frontier.
		RouteStep done = step("done", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet()); // step 1 reached
		RouteStep gate = step("gate", new SkillCondition(Skill.PRAYER, 43, Op.GE), false, Collections.emptySet());
		RouteStep m1 = step("m1", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep m2 = step("m2", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep deepQuest = step("deep", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		RouteStep m3 = step("m3", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(
			new Route(Arrays.asList(done, gate, m1, m2, deepQuest, m3)), IronmanMode.REGULAR);

		p.process(ctx());                                   // done + deep auto-complete; gate unmet; m* manual
		p.foldManualBehindMilestones();
		assertFalse("manual after an unmet gate must not fold behind a deep out-of-order completion",
			p.isComplete("m1"));
		assertFalse(p.isComplete("m2"));
		assertFalse(p.isComplete("m3"));
		assertEquals("gate", p.getCurrentStep().getId());   // stays at the real work, not leapt to the end
	}

	@Test
	public void foldDoesNothingWhenNoMilestoneReached()
	{
		RouteStep a = step("a", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep b = step("b", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(a, b)), IronmanMode.REGULAR);

		assertFalse(p.foldManualBehindMilestones());        // nothing completed yet -> no fold
		assertEquals("a", p.getCurrentStep().getId());
	}

	@Test
	public void recurringArrivalDoesNotCompleteOrFoldPastAnUnmetGate()
	{
		// Two arrival waypoints on the SAME tile (a recurring bank/GE), with an unmet real gate + flavour
		// between them. Standing on the tile, process() completes the FIRST arrival but must NOT complete
		// the DEEP one (realGatePending from the unmet gate) — so the fold, keyed to arrivals, cannot
		// cascade over the flavour. This is the actual danger surface the arrival-keyed fold must survive.
		RouteStep p1 = positionStep("p1", 3200, 3200, 10);
		RouteStep gate = step("gate", new SkillCondition(Skill.ATTACK, 99, Op.GE), false, Collections.emptySet());
		RouteStep f1 = step("f1", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep f2 = step("f2", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep p2 = positionStep("p2", 3200, 3200, 10);
		RouteStep f3 = step("f3", ConstantCondition.MANUAL, true, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(p1, gate, f1, f2, p2, f3)), IronmanMode.REGULAR);

		p.process(ctxAt(3200, 3200, 0));    // p1 arrives; gate unmet -> realGatePending; p2 must NOT complete
		assertTrue(p.isComplete("p1"));
		assertFalse("deep recurring waypoint must not complete out of order", p.isComplete("p2"));

		p.foldManualBehindMilestones();     // only p1 reached (index 0) -> nothing before it to fold
		assertFalse(p.isComplete("f1"));
		assertFalse(p.isComplete("f2"));
		assertFalse(p.isComplete("f3"));
		assertEquals("gate", p.getCurrentStep().getId());
	}

	@Test
	public void positionStepDoesNotCompleteBehindAnUnmetHardGate()
	{
		// The catastrophic case: a far travel waypoint the player happens to stand on must NOT complete
		// while a real (skill/quest/item) gate before it is unmet — else fold would wipe the guide.
		RouteStep gate = step("gate", new SkillCondition(Skill.ATTACK, 99, Op.GE), false, Collections.emptySet());
		RouteStep go = positionStep("go", 3200, 3200, 10);
		Progression p = new Progression(new Route(Arrays.asList(gate, go)), IronmanMode.REGULAR);

		p.process(ctxAt(3200, 3200, 0));    // player standing ON 'go', but 'gate' (level 99) is unmet
		assertFalse(p.isComplete("go"));
		assertEquals("gate", p.getCurrentStep().getId());
	}

	@Test
	public void positionStepCompletesWhenOnlySoftStepsPrecede()
	{
		// A manual flavour step before a travel step is "soft": arriving legitimately completes the travel.
		RouteStep sell = step("sell", ConstantCondition.MANUAL, true, Collections.emptySet());
		RouteStep go = positionStep("go", 3200, 3200, 10);
		Progression p = new Progression(new Route(Arrays.asList(sell, go)), IronmanMode.REGULAR);

		p.process(ctxAt(3200, 3200, 0));    // arrived; only a manual step precedes
		assertTrue(p.isComplete("go"));
	}

	@Test
	public void foldDoesNotFoldAManualInteractionStep()
	{
		// A manual step that highlights an NPC/object is real interaction ("talk to the Duke"), not
		// "sell/drop" flavour — it must never be folded away behind a milestone.
		RouteStep talk = new RouteStep("talk", "S", "talk", "", null, null, 100, -1, -1, true,
			Collections.emptySet(), Collections.emptyList(), ConstantCondition.MANUAL);
		RouteStep milestone = step("m", ConstantCondition.ALWAYS_TRUE, false, Collections.emptySet());
		Progression p = new Progression(new Route(Arrays.asList(talk, milestone)), IronmanMode.REGULAR);

		p.process(ctx());                   // milestone completes
		p.foldManualBehindMilestones();
		assertFalse(p.isComplete("talk"));  // interaction step preserved
		assertEquals("talk", p.getCurrentStep().getId());
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
