/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.overlay;

import java.awt.image.BufferedImage;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.worldmap.WorldMapPoint;
import net.runelite.client.ui.overlay.worldmap.WorldMapPointManager;

/**
 * Owns the single world-map marker that points at the current step's destination. {@link #show}
 * replaces any existing marker; {@link #clear} removes it. Keeping this in one place guarantees the
 * marker is always added and removed as a pair (no leaks, no duplicates).
 */
public class WorldMapMarker
{
	private final WorldMapPointManager manager;
	private WorldMapPoint point;

	public WorldMapMarker(WorldMapPointManager manager)
	{
		this.manager = manager;
	}

	/**
	 * Replace any current marker with one at {@code target}, labelled {@code tooltip}. No-op (and the
	 * old marker is removed) if {@code target} or {@code icon} is null.
	 */
	public void show(WorldPoint target, BufferedImage icon, String tooltip)
	{
		clear();
		if (target == null || icon == null)
		{
			return;
		}
		point = new WorldMapPoint(target, icon);
		// setName is REQUIRED whenever jumpOnClick is set: WorldMapOverlay asserts a non-null name on
		// hover, and with -ea (RuneLite dev mode) a null name throws an AssertionError that escapes the
		// render loop and freezes the client. This is the fix for the world-map-open freeze.
		point.setName("Gustav's Helper");
		point.setTooltip(tooltip);
		point.setTarget(target);
		point.setJumpOnClick(true);
		point.setSnapToEdge(true);
		manager.add(point);
	}

	/** Remove the current marker, if any. */
	public void clear()
	{
		if (point != null)
		{
			manager.remove(point);
			point = null;
		}
	}
}
