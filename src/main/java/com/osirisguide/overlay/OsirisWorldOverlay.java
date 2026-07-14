/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.overlay;

import com.osirisguide.OsirisGuideConfig;
import com.osirisguide.OsirisGuideState;
import com.osirisguide.engine.RouteStep;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Polygon;
import java.awt.Shape;
import javax.inject.Inject;
import net.runelite.api.Client;
import net.runelite.api.NPC;
import net.runelite.api.Perspective;
import net.runelite.api.Point;
import net.runelite.api.TileObject;
import net.runelite.api.coords.LocalPoint;
import net.runelite.api.coords.WorldPoint;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;

/**
 * Draws in-world guidance for the current step: a bobbing arrow + tile outline at the
 * destination, and highlights for the target object/NPC.
 */
public class OsirisWorldOverlay extends Overlay
{
	private final Client client;
	private final OsirisGuideConfig config;
	private final OsirisGuideState state;

	@Inject
	public OsirisWorldOverlay(Client client, OsirisGuideConfig config, OsirisGuideState state)
	{
		this.client = client;
		this.config = config;
		this.state = state;
		setPosition(OverlayPosition.DYNAMIC);
		setLayer(OverlayLayer.ABOVE_SCENE);
	}

	@Override
	public Dimension render(Graphics2D graphics)
	{
		RouteStep step = state.getCurrentStep();
		if (step == null)
		{
			return null;
		}

		Color color = config.highlightColor();
		Color fill = new Color(color.getRed(), color.getGreen(), color.getBlue(), 40);

		WorldPoint wp = step.getWorldPoint();
		if (wp != null)
		{
			LocalPoint lp = LocalPoint.fromWorld(client, wp);
			if (lp != null)
			{
				if (config.showTile())
				{
					Polygon poly = Perspective.getCanvasTilePoly(client, lp);
					if (poly != null)
					{
						graphics.setColor(color);
						graphics.drawPolygon(poly);
						graphics.setColor(fill);
						graphics.fillPolygon(poly);
					}
				}
				if (config.showWorldArrow())
				{
					Point base = Perspective.localToCanvas(client, lp, 0);
					if (base != null)
					{
						int bob = (int) (6.0 * Math.sin(client.getGameCycle() / 10.0));
						DirectionArrow.drawWorldArrow(graphics, color, base.getX(), base.getY() - 80 + bob);
					}
				}
			}
		}

		if (config.highlightObjects())
		{
			TileObject obj = state.getTargetObject();
			if (obj != null)
			{
				Shape clickbox = obj.getClickbox();
				if (clickbox != null)
				{
					graphics.setColor(color);
					graphics.draw(clickbox);
					graphics.setColor(fill);
					graphics.fill(clickbox);
				}
			}
		}

		if (config.highlightNpcs())
		{
			NPC npc = state.getTargetNpc();
			if (npc != null)
			{
				Shape hull = npc.getConvexHull();
				if (hull != null)
				{
					graphics.setColor(color);
					graphics.draw(hull);
					graphics.setColor(fill);
					graphics.fill(hull);
				}
			}
		}

		return null;
	}
}
