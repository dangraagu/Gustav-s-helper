/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

import static org.junit.Assert.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.gson.Gson;
import com.gustavguide.Guide;
import com.gustavguide.IronmanMode;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import net.runelite.api.Client;
import net.runelite.api.Player;
import net.runelite.api.coords.WorldPoint;

/**
 * Invariant: a brand-new account (fresh off Tutorial Island) must NOT have any route step
 * auto-complete. Every skill is level 1, no quest/diary is done, no items are owned, and the
 * player has no location — so nothing in any bundled guide should evaluate as met, and the
 * milestone-fold (which keys off the furthest reached step) must therefore fold nothing.
 *
 * <p>This pins the mechanism behind "a fresh account showed lots of pre-completed steps": a
 * scraped condition that is trivially true on every account (e.g. a mis-parsed "1 Prayer point"
 * read as {@code skill PRAYER >= 1}) auto-completes at login and cascades the fold. If this test
 * ever goes red, a guide's data has a universally-true / mis-grounded completion condition.</p>
 */
public class FreshAccountInvariantTest
{
	/** A logged-in-but-accomplished-nothing account: skills 1, all vars 0, no items, no location. */
	private ConditionContext freshAccount()
	{
		Client client = mock(Client.class);
		when(client.getRealSkillLevel(any())).thenReturn(1);
		when(client.getVarbitValue(anyInt())).thenReturn(0);
		when(client.getVarpValue(anyInt())).thenReturn(0);
		// getItemContainer(...) -> null (Mockito default) => 0 of everything
		// A fresh account is STANDING at the Tutorial-Island exit (Lumbridge, 3222,3218). Model that
		// real location — a null player would hide any position/arrival step that auto-completes at
		// spawn and then cascades the milestone-fold over the manual flavour steps before it.
		Player player = mock(Player.class);
		when(player.getWorldLocation()).thenReturn(new WorldPoint(3222, 3218, 0));
		when(client.getLocalPlayer()).thenReturn(player);
		return new ConditionContext(client);
	}

	@Test
	public void freshAccountAutoCompletesNothing()
	{
		Gson gson = new Gson();
		List<String> violations = new ArrayList<>();
		for (Guide g : Guide.values())
		{
			Route route = RouteLoader.load(gson, g.getId());
			for (IronmanMode mode : IronmanMode.values())
			{
				Progression p = new Progression(route, mode);
				p.process(freshAccount());
				p.foldManualBehindMilestones();
				int done = p.completedCount();
				if (done != 0)
				{
					StringBuilder sb = new StringBuilder();
					int shown = 0;
					for (RouteStep s : route.getSteps())
					{
						if (s.appliesTo(mode) && p.isComplete(s))
						{
							sb.append("\n      ").append(g.getId()).append(" [").append(mode).append("] ")
								.append(s.getId()).append("  cond=").append(s.getComplete().describe())
								.append("  title=").append(s.getTitle());
							if (++shown >= 6)
							{
								sb.append("\n      ...");
								break;
							}
						}
					}
					violations.add(g.getId() + " [" + mode + "] auto-completed " + done + " step(s):" + sb);
				}
			}
		}
		assertEquals("A fresh account must auto-complete nothing. Offenders:\n  "
			+ String.join("\n  ", violations) + "\n", 0, violations.size());
	}
}
