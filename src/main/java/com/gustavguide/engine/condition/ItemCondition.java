/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.condition;

import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.ItemScope;
import java.util.Collections;
import java.util.Set;

public class ItemCondition implements Condition
{
	private final int itemId;
	private final int quantity;
	private final ItemScope scope;

	public ItemCondition(int itemId, int quantity, ItemScope scope)
	{
		this.itemId = itemId;
		this.quantity = Math.max(1, quantity);
		this.scope = scope;
	}

	@Override
	public boolean isMet(ConditionContext ctx)
	{
		return ctx.itemCount(scope, itemId) >= quantity;
	}

	@Override
	public String describe()
	{
		return "item " + itemId + " x" + quantity + " (" + scope + ")";
	}

	@Override
	public Set<Integer> itemIds()
	{
		return Collections.singleton(itemId);
	}
}
