/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.condition;

import com.gustavguide.engine.ConditionContext;
import java.util.Collections;
import java.util.Set;

/**
 * Met once the player has <b>ever acquired</b> at least {@code quantity} of the item (tracked by the
 * ledger). Unlike {@link ItemCondition} (current ownership), this stays true after the item is used,
 * which is the correct signal for "collect / buy / pick up N of X" steps.
 */
public class ItemAcquiredCondition implements Condition
{
	private final int itemId;
	private final int quantity;

	public ItemAcquiredCondition(int itemId, int quantity)
	{
		this.itemId = itemId;
		this.quantity = Math.max(1, quantity);
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return ctx.itemAcquired(itemId) >= quantity;
	}

	@Override
	public String describe()
	{
		return "acquired item " + itemId + " x" + quantity;
	}

	@Override
	public Set<Integer> itemIds()
	{
		return Collections.singleton(itemId);
	}
}
