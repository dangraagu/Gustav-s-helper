/*
 * Copyright (c) 2026, dangraagu
 * Requirement display model adapted from RuneLite Quest Helper
 * (https://github.com/Zoinkwiz/quest-helper), Copyright (c) 2019-2024 Zoinkwiz and
 * contributors, BSD 2-Clause License. See NOTICE.
 *
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.requirement;

import com.osirisguide.engine.ConditionContext;

/**
 * A prerequisite shown in the side panel for a step, rendered green when satisfied and
 * red when not. Requirements are informational — they do not gate step completion.
 */
public interface Requirement
{
	/** @return true if the player currently satisfies this requirement. */
	boolean check(ConditionContext ctx);

	/** @return label shown in the panel, e.g. "43 Prayer" or "Coins x1000". */
	String getText();
}
