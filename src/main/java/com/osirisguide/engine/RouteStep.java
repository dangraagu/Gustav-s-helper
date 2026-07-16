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
	private final List<Integer> highlightNpcIds; // empty = none; several ids = "any of these" (e.g. Man variants)
	private final int highlightObjectId;   // -1 = none
	private final int highlightItemId;     // -1 = none
	private final boolean manual;
	private final Set<IronmanMode> modes;  // empty = all modes
	private final List<Requirement> requirements;
	private final Condition complete;

	/** Single-npc convenience overload (also what the tests use). */
	public RouteStep(String id, String section, String title, String text, String wikiUrl,
					 WorldPoint worldPoint, int highlightNpcId, int highlightObjectId, int highlightItemId,
					 boolean manual, Set<IronmanMode> modes, List<Requirement> requirements, Condition complete)
	{
		this(id, section, title, text, wikiUrl, worldPoint,
			highlightNpcId >= 0 ? Collections.singletonList(highlightNpcId) : Collections.emptyList(),
			highlightObjectId, highlightItemId, manual, modes, requirements, complete);
	}

	public RouteStep(String id, String section, String title, String text, String wikiUrl,
					 WorldPoint worldPoint, List<Integer> highlightNpcIds, int highlightObjectId,
					 int highlightItemId, boolean manual, Set<IronmanMode> modes,
					 List<Requirement> requirements, Condition complete)
	{
		this.id = id;
		this.section = section;
		this.title = title;
		this.text = text;
		this.wikiUrl = wikiUrl;
		this.worldPoint = worldPoint;
		this.highlightNpcIds = highlightNpcIds == null ? Collections.emptyList() : highlightNpcIds;
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

	/** First highlight NPC id, or -1 — kept for single-target call sites. */
	public int getHighlightNpcId()
	{
		return highlightNpcIds.isEmpty() ? -1 : highlightNpcIds.get(0);
	}

	/** All acceptable NPC ids for this step (empty = none) — "talk to any man" carries several. */
	public List<Integer> getHighlightNpcIds()
	{
		return highlightNpcIds;
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

	/** The quest this step is about, if it's a quest step (top-level quest condition); else null.
	 *  Used to drive Quest Helper's walkthrough (fork) and to look up the quest-start tile. */
	public net.runelite.api.Quest getQuest()
	{
		return complete instanceof com.osirisguide.engine.condition.QuestCondition
			? ((com.osirisguide.engine.condition.QuestCondition) complete).getQuest()
			: null;
	}

	/** True if this step auto-completes on ARRIVAL (a position trigger). Such steps must only complete
	 *  in route order — never from standing near a far-future waypoint (see Progression.process). */
	public boolean isPositionTriggered()
	{
		return complete instanceof com.osirisguide.engine.condition.PositionCondition;
	}

	/** True if this step points at a specific NPC/object to interact with — real work, not flavour, so
	 *  it must not be folded away as a passed-by step. */
	public boolean hasInteractionTarget()
	{
		return !highlightNpcIds.isEmpty() || highlightObjectId >= 0;
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
