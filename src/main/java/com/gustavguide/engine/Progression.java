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
	 * Auto-completes <b>manual</b> steps that sit before the furthest milestone the player has already
	 * reached. Rationale: you cannot have completed a later step without passing the earlier flavour
	 * steps ("sell bronze", "drop runes") that have no detectable trigger — so a manual step behind a
	 * reached milestone is folded done. A step with its own real (non-manual) trigger is <b>never</b>
	 * folded, even if it sits before the milestone: that would skip real work whose condition simply is
	 * not met yet. Call this after {@link #process}; it is what gives the "steps advance by themselves"
	 * feel for the ~60% of steps that carry no game-state trigger.
	 *
	 * @return true if any step was folded complete (caller should refresh UI / persist)
	 */
	public boolean foldManualBehindMilestones()
	{
		List<RouteStep> steps = route.getSteps();
		int furthest = -1;
		for (int i = 0; i < steps.size(); i++)
		{
			RouteStep s = steps.get(i);
			if (s.appliesTo(mode) && completed.contains(s.getId()))
			{
				furthest = i;
			}
		}
		if (furthest < 0)
		{
			return false;
		}
		boolean changed = false;
		for (int i = 0; i < furthest; i++)
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
