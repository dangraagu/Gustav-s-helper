/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.google.gson.Gson;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import org.junit.Test;

/**
 * Loads the bundled route resources (scraped from ironman.guide) and validates the JSON:
 * every step parses to a well-formed {@link RouteStep} with a non-null completion condition,
 * ids are unique, all sections are present, and the skill auto-detection produced conditions.
 */
public class RouteLoaderTest
{
	private Route load()
	{
		return RouteLoader.load(new Gson());
	}

	@Test
	public void bundledRouteLoadsFullGuide()
	{
		Route route = load();
		assertFalse("route should not be empty", route.isEmpty());
		// The guide is ~575 steps; allow some drift if the site is updated, but catch a broken scrape.
		assertTrue("expected the full guide (~575 steps), got " + route.size(), route.size() >= 550);
		assertEquals("expected 7 sections", 7, route.getSectionOrder().size());
		assertTrue(route.getSectionOrder().contains("Early Game"));
		assertTrue(route.getSectionOrder().contains("Sailing (optional)"));
	}

	@Test
	public void idsAreUnique()
	{
		Route route = load();
		Set<String> ids = new HashSet<>();
		for (RouteStep s : route.getSteps())
		{
			assertTrue("duplicate id: " + s.getId(), ids.add(s.getId()));
		}
	}

	@Test
	public void everyStepIsWellFormed()
	{
		Route route = load();
		for (RouteStep s : route.getSteps())
		{
			assertNotNull("null id", s.getId());
			assertFalse("empty id", s.getId().isEmpty());
			assertFalse("empty title for " + s.getId(), s.getTitle().isEmpty());
			assertNotNull("null section for " + s.getId(), s.getSection());
			// A step always has a non-null condition (ConstantCondition.MANUAL for manual steps).
			assertNotNull("null condition for " + s.getId(), s.getComplete());
		}
	}

	@Test
	public void skillAutoDetectionProducedConditions()
	{
		Route route = load();
		int auto = 0;
		boolean sawHerblore = false;
		for (RouteStep s : route.getSteps())
		{
			String desc = s.getComplete().describe();
			if (!"manual".equals(desc))
			{
				auto++;
			}
			if (desc.contains("Herblore"))
			{
				sawHerblore = true;
			}
		}
		assertTrue("expected several auto-detected steps, got " + auto, auto >= 20);
		assertTrue("expected at least one Herblore skill condition from the guide text", sawHerblore);
	}

	@Test
	public void duplicateIdsAreDropped()
	{
		String json = "{\"section\":\"S\",\"steps\":["
			+ "{\"id\":\"x\",\"title\":\"first\"},"
			+ "{\"id\":\"x\",\"title\":\"dup\"},"
			+ "{\"id\":\"y\",\"title\":\"second\"}]}";
		Route r = RouteLoader.fromSectionJson(new Gson(), Collections.singletonList(json));
		assertEquals("duplicate id must be dropped", 2, r.size());
		assertEquals("first occurrence is kept", "first", r.getById("x").getTitle());
	}
}
