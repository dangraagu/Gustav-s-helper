/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;
import java.util.Collections;
import java.util.Set;

/**
 * Met once the player has acquired then <b>spent/used</b> at least {@code quantity} of the item
 * (ledger: acquired − owned). The signal for "use N of X on the quest" steps.
 */
public class ItemConsumedCondition implements Condition
{
	private final int itemId;
	private final int quantity;

	public ItemConsumedCondition(int itemId, int quantity)
	{
		this.itemId = itemId;
		this.quantity = Math.max(1, quantity);
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return ctx.itemSpent(itemId) >= quantity;
	}

	@Override
	public String describe()
	{
		return "spent item " + itemId + " x" + quantity;
	}

	@Override
	public Set<Integer> itemIds()
	{
		return Collections.singleton(itemId);
	}
}
