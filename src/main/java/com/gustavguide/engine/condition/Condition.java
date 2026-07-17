/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine.condition;

import com.gustavguide.engine.ConditionContext;
import java.util.Collections;
import java.util.Set;

/**
 * A boolean predicate over game state that decides whether a route step is complete.
 * Evaluated on the client thread.
 */
public interface Condition
{
	boolean isMet(ConditionContext ctx);

	/** Human-readable description, for the panel/debugging. */
	String describe();

	/**
	 * Item ids this condition (and its children) reference. Used to build the ledger's
	 * items-of-interest set. Defaults to none; item/combinator conditions override.
	 */
	default Set<Integer> itemIds()
	{
		return Collections.emptySet();
	}
}
