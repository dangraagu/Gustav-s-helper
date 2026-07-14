/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import com.osirisguide.IronmanMode;
import com.osirisguide.engine.condition.Condition;
import com.osirisguide.requirement.Requirement;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import net.runelite.api.coords.WorldPoint;

/**
 * One runtime step of the route. Immutable once built by {@link RouteLoader}.
 */
public class RouteStep
{
	private final String id;
	private final String section;
	private final String title;
	private final String text;
	private final String wikiUrl;
	private final WorldPoint worldPoint;   // nullable
	private final int highlightNpcId;      // -1 = none
	private final int highlightObjectId;   // -1 = none
	private final int highlightItemId;     // -1 = none
	private final boolean manual;
	private final Set<IronmanMode> modes;  // empty = all modes
	private final List<Requirement> requirements;
	private final Condition complete;

	public RouteStep(String id, String section, String title, String text, String wikiUrl,
					 WorldPoint worldPoint, int highlightNpcId, int highlightObjectId, int highlightItemId,
					 boolean manual, Set<IronmanMode> modes, List<Requirement> requirements, Condition complete)
	{
		this.id = id;
		this.section = section;
		this.title = title;
		this.text = text;
		this.wikiUrl = wikiUrl;
		this.worldPoint = worldPoint;
		this.highlightNpcId = highlightNpcId;
		this.highlightObjectId = highlightObjectId;
		this.highlightItemId = highlightItemId;
		this.manual = manual;
		this.modes = modes == null ? Collections.emptySet() : modes;
		this.requirements = requirements == null ? Collections.emptyList() : requirements;
		this.complete = complete;
	}

	public String getId()
	{
		return id;
	}

	public String getSection()
	{
		return section;
	}

	public String getTitle()
	{
		return title;
	}

	public String getText()
	{
		return text;
	}

	public String getWikiUrl()
	{
		return wikiUrl;
	}

	public WorldPoint getWorldPoint()
	{
		return worldPoint;
	}

	public int getHighlightNpcId()
	{
		return highlightNpcId;
	}

	public int getHighlightObjectId()
	{
		return highlightObjectId;
	}

	public int getHighlightItemId()
	{
		return highlightItemId;
	}

	public boolean isManual()
	{
		return manual;
	}

	public Set<IronmanMode> getModes()
	{
		return modes;
	}

	public List<Requirement> getRequirements()
	{
		return requirements;
	}

	public Condition getComplete()
	{
		return complete;
	}

	/** @return true if this step applies to the given account mode (empty modes = all). */
	public boolean appliesTo(IronmanMode mode)
	{
		return modes.isEmpty() || modes.contains(mode);
	}

	/** @return true if the step's auto-detect condition is currently satisfied. */
	public boolean isAutoComplete(ConditionContext ctx)
	{
		return complete != null && complete.isMet(ctx);
	}
}
