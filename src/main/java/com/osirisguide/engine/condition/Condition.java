/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine.condition;

import com.osirisguide.engine.ConditionContext;

/**
 * A boolean predicate over game state that decides whether a route step is complete.
 * Evaluated on the client thread.
 */
public interface Condition
{
	boolean isMet(ConditionContext ctx);

	/** Human-readable description, for the panel/debugging. */
	String describe();
}
