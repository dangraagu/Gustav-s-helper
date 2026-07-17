/*
 * Copyright (c) 2026, dangraagu
 * Requirement display model adapted from RuneLite Quest Helper (BSD 2-Clause). See NOTICE.
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.requirement;

import com.gustavguide.engine.ConditionContext;
import com.gustavguide.engine.ItemScope;

public class ItemRequirement implements Requirement
{
	private final int itemId;
	private final int quantity;
	private final String name;
	private final ItemScope scope;

	public ItemRequirement(int itemId, int quantity, String name, ItemScope scope)
	{
		this.itemId = itemId;
		this.quantity = Math.max(1, quantity);
		this.name = name;
		this.scope = scope;
	}

	@Override
	public boolean check(ConditionContext ctx)
	{
		return ctx.itemCount(scope, itemId) >= quantity;
	}

	@Override
	public String getText()
	{
		String label = (name == null || name.isEmpty()) ? ("Item " + itemId) : name;
		return quantity > 1 ? (label + " x" + quantity) : label;
	}
}
