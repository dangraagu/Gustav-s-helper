/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import net.runelite.api.coords.WorldPoint;

/**
 * Met once the player stands within {@code radius} tiles of {@code target} on the same plane —
 * i.e. "you've arrived". Used to auto-complete pure-travel steps ("go to X"). Not used for
 * talk/interact steps, where mere proximity would wrongly complete a step you walked past.
 */
public class PositionCondition implements Condition
{
	private final WorldPoint target;
	private final int radius;

	public PositionCondition(WorldPoint target, int radius)
	{
		this.target = target;
		this.radius = Math.max(0, radius);
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		WorldPoint player = ctx.playerLocation();
		if (player == null || target == null)
		{
			return false;
		}
		// WorldPoint.distanceTo is Chebyshev distance, and Integer.MAX_VALUE across different planes,
		// so a plane mismatch can never satisfy the radius check.
		return target.distanceTo(player) <= radius;
	}

	@Override
	public String describe()
	{
		return "within " + radius + " of (" + target.getX() + ", " + target.getY()
			+ ", " + target.getPlane() + ")";
	}
}
