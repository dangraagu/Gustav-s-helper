/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import com.osirisguide.IronmanMode;
import java.util.Collection;
import java.util.LinkedHashSet;
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

	public int getCurrentIndex()
	{
		RouteStep s = getCurrentStep();
		return s == null ? -1 : route.indexOf(s.getId());
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
		for (RouteStep s : route.getSteps())
		{
			if (!s.appliesTo(mode) || completed.contains(s.getId()))
			{
				continue;
			}
			if (isAutoCompleteSafe(s, ctx))
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

	public void uncomplete(String id)
	{
		completed.remove(id);
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
