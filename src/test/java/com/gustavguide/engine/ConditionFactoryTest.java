/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import com.gustavguide.engine.condition.Condition;
import com.gustavguide.engine.ledger.ItemLedger;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import org.junit.Test;
import net.runelite.api.Client;
import net.runelite.api.InventoryID;
import net.runelite.api.ItemContainer;
import net.runelite.api.Player;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;

public class ConditionFactoryTest
{
	private static Condition parse(String json)
	{
		JsonElement el = new JsonParser().parse(json);
		return ConditionFactory.parse(el, "test");
	}

	@Test
	public void skillConditionMet()
	{
		Client client = mock(Client.class);
		when(client.getRealSkillLevel(Skill.PRAYER)).thenReturn(45);
		ConditionContext ctx = new ConditionContext(client);

		assertTrue(parse("{\"op\":\"skill\",\"skill\":\"PRAYER\",\"level\":43}").isMet(ctx));
		assertFalse(parse("{\"op\":\"skill\",\"skill\":\"PRAYER\",\"level\":50}").isMet(ctx));
	}

	@Test
	public void itemConditionMet()
	{
		Client client = mock(Client.class);
		ItemContainer inv = mock(ItemContainer.class);
		when(client.getItemContainer(InventoryID.INVENTORY)).thenReturn(inv);
		when(inv.count(1059)).thenReturn(2);
		ConditionContext ctx = new ConditionContext(client);

		assertTrue(parse("{\"op\":\"item\",\"id\":1059,\"qty\":2,\"scope\":\"INVENTORY\"}").isMet(ctx));
		assertFalse(parse("{\"op\":\"item\",\"id\":1059,\"qty\":3,\"scope\":\"INVENTORY\"}").isMet(ctx));
	}

	@Test
	public void varbitCondition()
	{
		Client client = mock(Client.class);
		when(client.getVarbitValue(1234)).thenReturn(5);
		ConditionContext ctx = new ConditionContext(client);

		assertTrue(parse("{\"op\":\"varbit\",\"id\":1234,\"value\":5,\"cmp\":\"=\"}").isMet(ctx));
		assertTrue(parse("{\"op\":\"varbit\",\"id\":1234,\"value\":3,\"cmp\":\">=\"}").isMet(ctx));
		assertFalse(parse("{\"op\":\"varbit\",\"id\":1234,\"value\":6,\"cmp\":\"=\"}").isMet(ctx));
	}

	@Test
	public void andOrNotCombinators()
	{
		Client client = mock(Client.class);
		when(client.getRealSkillLevel(Skill.ATTACK)).thenReturn(60);
		when(client.getVarbitValue(10)).thenReturn(1);
		ConditionContext ctx = new ConditionContext(client);

		String skill = "{\"op\":\"skill\",\"skill\":\"ATTACK\",\"level\":40}";
		String badSkill = "{\"op\":\"skill\",\"skill\":\"ATTACK\",\"level\":99}";
		String varbit = "{\"op\":\"varbit\",\"id\":10,\"value\":1,\"cmp\":\"=\"}";

		assertTrue(parse("{\"op\":\"and\",\"of\":[" + skill + "," + varbit + "]}").isMet(ctx));
		assertFalse(parse("{\"op\":\"and\",\"of\":[" + badSkill + "," + varbit + "]}").isMet(ctx));
		assertTrue(parse("{\"op\":\"or\",\"of\":[" + badSkill + "," + varbit + "]}").isMet(ctx));
		assertTrue(parse("{\"op\":\"not\",\"of\":" + badSkill + "}").isMet(ctx));
		assertFalse(parse("{\"op\":\"not\",\"of\":" + skill + "}").isMet(ctx));
	}

	@Test
	public void unknownOpAndNullDegradeToManual()
	{
		ConditionContext ctx = new ConditionContext(mock(Client.class));
		// unknown op -> MANUAL (never auto-completes)
		assertFalse(parse("{\"op\":\"frobnicate\"}").isMet(ctx));
		// explicit manual
		assertFalse(parse("{\"op\":\"manual\"}").isMet(ctx));
		// null element -> MANUAL
		assertFalse(ConditionFactory.parse(null, "test").isMet(ctx));
		// always -> true
		assertTrue(parse("{\"op\":\"always\"}").isMet(ctx));
	}

	@Test
	public void itemAcquiredAndConsumedUseLedger()
	{
		ItemLedger ledger = new ItemLedger();
		ledger.observe(93, Collections.emptyMap());     // seed inventory
		ledger.commit();
		Map<Integer, Integer> five = new HashMap<>();
		five.put(1939, 5);
		ledger.observe(93, five);                        // acquire 5 swamp tar
		ledger.commit();
		ConditionContext ctx = new ConditionContext(mock(Client.class), ledger);

		assertTrue(parse("{\"op\":\"itemAcquired\",\"id\":1939,\"qty\":5}").isMet(ctx));
		assertFalse(parse("{\"op\":\"itemAcquired\",\"id\":1939,\"qty\":6}").isMet(ctx));

		ledger.observe(93, Collections.emptyMap());      // use all 5
		ledger.commit();
		assertTrue(parse("{\"op\":\"itemConsumed\",\"id\":1939,\"qty\":5}").isMet(ctx));
		// acquired stays sticky after spending
		assertTrue(parse("{\"op\":\"itemAcquired\",\"id\":1939,\"qty\":5}").isMet(ctx));

		// Without a ledger, acquired/consumed read as 0 (never met) rather than throwing.
		ConditionContext noLedger = new ConditionContext(mock(Client.class));
		assertFalse(parse("{\"op\":\"itemAcquired\",\"id\":1939,\"qty\":1}").isMet(noLedger));
	}

	@Test
	public void positionConditionWithinRadius()
	{
		Client client = mock(Client.class);
		Player player = mock(Player.class);
		when(client.getLocalPlayer()).thenReturn(player);
		when(player.getWorldLocation()).thenReturn(new WorldPoint(3222, 3218, 0));
		ConditionContext ctx = new ConditionContext(client);

		// within radius (3 tiles away, radius 8)
		assertTrue(parse("{\"op\":\"position\",\"x\":3225,\"y\":3220,\"z\":0,\"radius\":8}").isMet(ctx));
		// on the exact tile
		assertTrue(parse("{\"op\":\"position\",\"x\":3222,\"y\":3218,\"z\":0,\"radius\":8}").isMet(ctx));
		// outside radius (~78 tiles east)
		assertFalse(parse("{\"op\":\"position\",\"x\":3300,\"y\":3218,\"z\":0,\"radius\":8}").isMet(ctx));
		// different plane -> never met even if x/y match
		assertFalse(parse("{\"op\":\"position\",\"x\":3222,\"y\":3218,\"z\":1,\"radius\":8}").isMet(ctx));
	}

	@Test
	public void positionMissingCoordsDegradesToManual()
	{
		// Without x/y the factory must build MANUAL, not a condition that reads garbage coords.
		assertEquals("manual", parse("{\"op\":\"position\"}").describe());
		assertEquals("manual", parse("{\"op\":\"position\",\"x\":3222}").describe());
		// a valid position builds a real (non-manual) condition
		assertNotEquals("manual", parse("{\"op\":\"position\",\"x\":3222,\"y\":3218}").describe());
	}

	@Test
	public void positionNullPlayerNotMet()
	{
		Client client = mock(Client.class);
		when(client.getLocalPlayer()).thenReturn(null);
		assertFalse(parse("{\"op\":\"position\",\"x\":1,\"y\":1}").isMet(new ConditionContext(client)));
	}

	@Test
	public void varbitVarpMissingIdDegradesToManual()
	{
		// A missing/invalid id would index the varps array out of range at eval; the factory must
		// degrade these to MANUAL at parse time instead of building a throwing condition.
		assertEquals("manual", parse("{\"op\":\"varbit\"}").describe());
		assertEquals("manual", parse("{\"op\":\"varp\",\"id\":-5,\"value\":1}").describe());
		// A valid id still builds a real condition.
		assertNotEquals("manual", parse("{\"op\":\"varbit\",\"id\":100,\"value\":1}").describe());
	}
}
