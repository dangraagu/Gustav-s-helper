/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import com.gustavguide.IronmanMode;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Tracks which route steps are complete and which step the player is currently on.
 *
 * <p>Completion is <b>sticky</b>: once a step is marked complete it stays complete even if
 * the underlying condition later becomes false (e.g. a required item is consumed). The
 * "current" step is always the first not-yet-complete step that applies to the active mode.</p>
 *
 * <p>Not thread-safe; all mutation happens on the client thread (or the Swing thread for
 * manual actions, which the plugin marshals onto the client thread).</p>
 */
public class Progression
{
	private final Route route;
	private final Set<String> completed = new LinkedHashSet<>();
	private IronmanMode mode;

	public Progression(Route route, IronmanMode mode)
	{
		this.route = route;
		this.mode = mode == null ? IronmanMode.REGULAR : mode;
	}

	public Route getRoute()
	{
		return route;
	}

	public IronmanMode getMode()
	{
		return mode;
	}

	public void setMode(IronmanMode mode)
	{
		this.mode = mode == null ? IronmanMode.REGULAR : mode;
	}

	public boolean isComplete(String id)
	{
		return completed.contains(id);
	}

	public boolean isComplete(RouteStep step)
	{
		return step != null && completed.contains(step.getId());
	}

	/** @return the first incomplete step applicable to the current mode, or null if finished. */
	public RouteStep getCurrentStep()
	{
		for (RouteStep s : route.getSteps())
		{
			if (s.appliesTo(mode) && !completed.contains(s.getId()))
			{
				return s;
			}
		}
		return null;
	}

	/**
	 * Evaluates every incomplete step that applies to the current mode and marks complete any whose
	 * condition is now met. A condition that throws is treated as not-met (degrades to manual) so one
	 * malformed step can never abort the pass. Runs each tick; cost is a few hundred cheap booleans,
	 * and evaluating the whole list (not a window) means transient conditions are never missed.
	 *
	 * @return true if anything changed (caller should refresh UI / persist)
	 */
	public boolean process(ConditionContext ctx)
	{
		boolean changed = false;
		// A position (arrival) trigger only means "you're standing here", NOT "you did everything up to
		// here" — and travel destinations recur across a route, so a far-future waypoint can sit right
		// where you are now. Only trust an arrival while no earlier REAL gate (a non-manual, non-position
		// step whose condition isn't met) is still pending; otherwise a nearby late waypoint would complete
		// out of order and the milestone-fold would wipe the guide. Skill/quest/item conditions still
		// complete anywhere they're genuinely true (an existing account legitimately already has them).
		boolean realGatePending = false;
		for (RouteStep s : route.getSteps())
		{
			if (!s.appliesTo(mode) || completed.contains(s.getId()))
			{
				continue;
			}
			boolean met = isAutoCompleteSafe(s, ctx);
			if (s.isPositionTriggered())
			{
				if (met && !realGatePending)
				{
					completed.add(s.getId());
					changed = true;
				}
				// an un-arrived position step is "soft" — it never blocks later steps
			}
			else if (met)
			{
				completed.add(s.getId());
				changed = true;
			}
			else if (!s.isManual())
			{
				realGatePending = true; // a genuine unmet gate: don't trust arrivals beyond this point
			}
		}
		return changed;
	}

	/**
	 * Auto-completes <b>manual</b> flavour steps ("sell bronze", "drop runes") that sit before a point the
	 * player has <b>provably reached by walking there</b>. This is what gives the "steps advance by
	 * themselves" feel for the steps that carry no detectable trigger.
	 *
	 * <p>The fold boundary is the furthest completed <b>arrival</b> — a position/travel step. An arrival
	 * is the only safe proof of sequential reach: {@link #process} refuses to complete a position step
	 * while any earlier real gate is still unmet ({@code realGatePending}), so a completed arrival
	 * guarantees you physically passed everything before it. A skill/quest/item completion is
	 * <b>deliberately NOT</b> a fold boundary — those conditions can be satisfied OUT OF ORDER (a quest
	 * done long ago, referenced again deep in the route), and folding behind them wipes every flavour
	 * step before the reference. That out-of-order cascade was the "162 steps complete on a fresh route"
	 * bug; keying the fold to arrivals removes it for every under-progressed account. The remaining
	 * guarantee rests on a DATA invariant as well as this code: {@link #process} only completes an
	 * arrival when no earlier real gate is unmet, so a completed arrival implies the earlier gates are
	 * met — but two overlapping arrival waypoints (a recurring bank/GE tile) with NO unmet gate between
	 * them could still complete the deeper one out of order. Guide data must not place two such
	 * waypoints in an all-flavour stretch; a fresh account is safe regardless (an early real gate trips
	 * realGatePending, so nothing arrives at spawn — pinned by FreshAccountInvariantTest).</p>
	 *
	 * <p>A step with its own real (non-manual) trigger, or a manual step that highlights an NPC/object
	 * ("talk to the Duke"), is real work and is never folded. Call after {@link #process}.</p>
	 *
	 * @return true if any step was folded complete (caller should refresh UI / persist)
	 */
	public boolean foldManualBehindMilestones()
	{
		List<RouteStep> steps = route.getSteps();
		int reached = -1;
		for (int i = 0; i < steps.size(); i++)
		{
			RouteStep s = steps.get(i);
			if (s.appliesTo(mode) && s.isPositionTriggered() && completed.contains(s.getId()))
			{
				reached = i;  // furthest ARRIVAL — proof you walked through everything before it
			}
		}
		if (reached < 0)
		{
			return false;
		}
		boolean changed = false;
		for (int i = 0; i < reached; i++)
		{
			RouteStep s = steps.get(i);
			// Fold only genuine flavour steps: manual, no NPC/object to interact with. A manual step that
			// highlights an NPC/object ("talk to the Duke") is real work and is never skipped.
			if (s.appliesTo(mode) && s.isManual() && !s.hasInteractionTarget() && !completed.contains(s.getId()))
			{
				completed.add(s.getId());
				changed = true;
			}
		}
		return changed;
	}

	/**
	 * Full pass used on login / mode-change so an existing account resumes at the right place.
	 * Identical to {@link #process} (every applicable step is evaluated); kept as a named entry
	 * point for readability at those call sites.
	 *
	 * @return true if anything changed
	 */
	public boolean reconcileAll(ConditionContext ctx)
	{
		return process(ctx);
	}

	private static boolean isAutoCompleteSafe(RouteStep step, ConditionContext ctx)
	{
		try
		{
			return step.isAutoComplete(ctx);
		}
		catch (RuntimeException ex)
		{
			// A bad condition (e.g. an out-of-range varbit id) degrades to manual, never wedges the pass.
			return false;
		}
	}

	// ---- Manual actions -----------------------------------------------------

	public void markComplete(String id)
	{
		if (route.getById(id) != null)
		{
			completed.add(id);
		}
	}

	/**
	 * "Undo": go back one step. Un-completes the nearest <b>completed</b> step (applicable to the current
	 * mode) that sits before the current step, so a mis-clicked Done/Skip — or a step you want to redo —
	 * becomes current again. With the route finished, the last completed step is reopened.
	 *
	 * <p>Note a step whose real condition is genuinely met (a finished quest, a reached level) will simply
	 * auto-complete again on the next evaluation: you cannot un-earn game progress. Undo is meaningful for
	 * the manual steps, which is where mis-clicks happen.</p>
	 *
	 * @return true if a step was reopened (caller should refresh UI / persist)
	 */
	public boolean stepBack()
	{
		List<RouteStep> steps = route.getSteps();
		RouteStep current = getCurrentStep();
		int from = current == null ? steps.size() - 1 : route.indexOf(current.getId()) - 1;
		for (int i = from; i >= 0; i--)
		{
			RouteStep s = steps.get(i);
			if (s.appliesTo(mode) && completed.remove(s.getId()))
			{
				return true;
			}
		}
		return false;
	}

	public void reset()
	{
		completed.clear();
	}

	// ---- Progress / persistence --------------------------------------------

	public int completedCount()
	{
		int n = 0;
		for (RouteStep s : route.getSteps())
		{
			if (s.appliesTo(mode) && completed.contains(s.getId()))
			{
				n++;
			}
		}
		return n;
	}

	public int applicableCount()
	{
		int n = 0;
		for (RouteStep s : route.getSteps())
		{
			if (s.appliesTo(mode))
			{
				n++;
			}
		}
		return n;
	}

	public int progressPercent()
	{
		int total = applicableCount();
		return total == 0 ? 0 : (int) Math.round(100.0 * completedCount() / total);
	}

	public Set<String> getCompletedIds()
	{
		return new LinkedHashSet<>(completed);
	}

	public void setCompletedIds(Collection<String> ids)
	{
		completed.clear();
		if (ids != null)
		{
			completed.addAll(ids);
		}
	}
}
