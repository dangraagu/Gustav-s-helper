/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The full ordered route: a flat list of {@link RouteStep}s, grouped into ordered sections.
 */
public class Route
{
	private final List<RouteStep> steps;
	private final List<String> sectionOrder;
	private final Map<String, Integer> indexById;

	public Route(List<RouteStep> steps)
	{
		this.steps = Collections.unmodifiableList(new ArrayList<>(steps));
		this.sectionOrder = new ArrayList<>();
		this.indexById = new LinkedHashMap<>();
		for (int i = 0; i < this.steps.size(); i++)
		{
			RouteStep s = this.steps.get(i);
			indexById.put(s.getId(), i);
			if (!sectionOrder.contains(s.getSection()))
			{
				sectionOrder.add(s.getSection());
			}
		}
	}

	public List<RouteStep> getSteps()
	{
		return steps;
	}

	public int size()
	{
		return steps.size();
	}

	public boolean isEmpty()
	{
		return steps.isEmpty();
	}

	public List<String> getSectionOrder()
	{
		return Collections.unmodifiableList(sectionOrder);
	}

	public RouteStep get(int index)
	{
		return steps.get(index);
	}

	public RouteStep getById(String id)
	{
		Integer i = indexById.get(id);
		return i == null ? null : steps.get(i);
	}

	public int indexOf(String id)
	{
		Integer i = indexById.get(id);
		return i == null ? -1 : i;
	}

	/** All item ids referenced by any step's completion condition — the ledger's items of interest. */
	public Set<Integer> referencedItemIds()
	{
		Set<Integer> ids = new HashSet<>();
		for (RouteStep s : steps)
		{
			if (s.getComplete() != null)
			{
				ids.addAll(s.getComplete().itemIds());
			}
		}
		return ids;
	}

	public List<RouteStep> stepsInSection(String section)
	{
		List<RouteStep> out = new ArrayList<>();
		for (RouteStep s : steps)
		{
			if (s.getSection().equals(section))
			{
				out.add(s);
			}
		}
		return out;
	}
}
