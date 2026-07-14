/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.overlay;

import com.osirisguide.OsirisGuideConfig;
import com.osirisguide.OsirisGuideState;
import com.osirisguide.engine.RouteStep;
import java.awt.Dimension;
import java.awt.Graphics2D;
import javax.inject.Inject;
import net.runelite.api.Client;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;

/**
 * Draws a minimap arrow toward the current step's destination when it is within the loaded
 * scene (i.e. close enough to project onto the minimap).
 */
public class OsirisMinimapOverlay extends Overlay
{
	private final Client client;
	private final OsirisGuideConfig config;
	private final OsirisGuideState state;

	@Inject
	public OsirisMinimapOverlay(Client client, OsirisGuideConfig config, OsirisGuideState state)
	{
		this.client = client;
		this.config = config;
		this.state = state;
		setPosition(OverlayPosition.DYNAMIC);
		setLayer(OverlayLayer.ABOVE_WIDGETS);
	}

	@Override
	public Dimension render(Graphics2D graphics)
	{
		if (!config.showMinimapArrow())
		{
			return null;
		}
		RouteStep step = state.getCurrentStep();
		if (step == null || step.getWorldPoint() == null)
		{
			return null;
		}
		WorldPoint wp = step.getWorldPoint();
		LocalPoint lp = LocalPoint.fromWorld(client, wp);
		if (lp == null)
		{
			return null;
		}
		DirectionArrow.renderMinimapArrow(graphics, client, lp, config.highlightColor());
		return null;
	}
}
