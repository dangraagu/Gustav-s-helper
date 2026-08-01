/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.gson.Gson;
import com.gustavguide.IronmanMode;
import com.gustavguide.requirement.Requirement;
import java.util.Collections;
import java.util.Set;
import org.junit.Test;
import net.runelite.api.Client;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemContainer;

/**
 * An "Inventory check: A, B, C" step lists every item it wants as a requirement, so the panel can show
 * each one green (carried) or red (missing) and the item overlay can highlight ALL of them — not just
 * one. This pins that end-to-end: the JSON parses into item requirements, the requirements evaluate
 * per-item against live inventory, and the step exposes every id for highlighting.
 */
public class InventoryCheckTest
{
	private static final String STEP_JSON =
		"{\"section\":\"S\",\"steps\":[{"
			+ "\"id\":\"inv-1\",\"title\":\"Inventory check\",\"text\":\"Inventory check: Rope, Spade\","
			+ "\"manual\":true,"
			+ "\"requirements\":["
			+ "  {\"type\":\"item\",\"id\":954,\"qty\":1,\"name\":\"Rope\",\"scope\":\"ANY\"},"
			+ "  {\"type\":\"item\",\"id\":952,\"qty\":2,\"name\":\"Spade\",\"scope\":\"ANY\"}"
			+ "]}]}";

	private static Route load()
	{
		return RouteLoader.fromSectionJson(new Gson(), Collections.singletonList(STEP_JSON));
	}

	@Test
	public void inventoryCheckItemsBecomeRequirements()
	{
		RouteStep s = load().getById("inv-1");
		assertEquals(2, s.getRequirements().size());
		assertEquals("Rope", s.getRequirements().get(0).getText());
		assertEquals("Spade x2", s.getRequirements().get(1).getText());   // quantity shown
	}

	@Test
	public void eachItemReportsCarriedOrMissingIndependently()
	{
		Client client = mock(Client.class);
		ItemContainer inv = mock(ItemContainer.class);
		when(client.getItemContainer(InventoryID.INVENTORY)).thenReturn(inv);
		when(inv.count(954)).thenReturn(1);   // has the rope
		when(inv.count(952)).thenReturn(1);   // only 1 spade, needs 2 -> missing
		ConditionContext ctx = new ConditionContext(client);

		RouteStep s = load().getById("inv-1");
		Requirement rope = s.getRequirements().get(0);
		Requirement spade = s.getRequirements().get(1);
		assertTrue("carried item shows as met (green)", rope.check(ctx));
		assertFalse("short quantity shows as missing (red)", spade.check(ctx));
	}

	@Test
	public void everyRequiredItemIsHighlighted()
	{
		// The overlay highlights the whole checklist, not just the single legacy highlight id.
		Set<Integer> ids = load().getById("inv-1").getHighlightItemIds();
		assertTrue("rope highlighted", ids.contains(954));
		assertTrue("spade highlighted", ids.contains(952));
		assertEquals(2, ids.size());
	}

	@Test
	public void aStepWithNoItemsHighlightsNothing()
	{
		String json = "{\"section\":\"S\",\"steps\":[{\"id\":\"x\",\"title\":\"t\",\"manual\":true}]}";
		Route r = RouteLoader.fromSectionJson(new Gson(), Collections.singletonList(json));
		assertTrue(r.getById("x").getHighlightItemIds().isEmpty());
	}

	@Test
	public void legacySingleHighlightItemStillWorks()
	{
		String json = "{\"section\":\"S\",\"steps\":[{\"id\":\"y\",\"title\":\"t\",\"item\":1059,\"manual\":true}]}";
		Route r = RouteLoader.fromSectionJson(new Gson(), Collections.singletonList(json));
		Set<Integer> ids = r.getById("y").getHighlightItemIds();
		assertEquals(1, ids.size());
		assertTrue(ids.contains(1059));
	}

	@Test
	public void modeFilterIsUnaffected()
	{
		RouteStep s = load().getById("inv-1");
		assertTrue(s.appliesTo(IronmanMode.UIM));
	}
}
