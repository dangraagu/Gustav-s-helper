/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.overlay;

import java.awt.Color;

/** Small shared color helpers for the overlays. */
final class OverlayColors
{
	private OverlayColors()
	{
	}

	/** Returns {@code c} with its alpha replaced by {@code alpha} (0-255), for translucent fills. */
	static Color translucent(Color c, int alpha)
	{
		return new Color(c.getRed(), c.getGreen(), c.getBlue(), alpha);
	}
}
