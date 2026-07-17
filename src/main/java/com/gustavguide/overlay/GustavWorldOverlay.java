/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.overlay;

import com.gustavguide.GustavGuideConfig;
import com.gustavguide.GustavGuideState;
import com.gustavguide.engine.RouteStep;
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
import net.runelite.client.ui.overlay.outline.ModelOutlineRenderer;

/**
 * Draws in-world guidance for the current step: a bobbing arrow + tile outline at the
 * destination, and a highlight on the target object/NPC.
 *
 * <p>The entity highlight style is configurable: {@code GLOW} traces the model silhouette with a
 * feathered outline (the "click-blue" look, via RuneLite's own {@link ModelOutlineRenderer} — no
 * third-party plugin code involved), {@code HULL} draws the convex-hull/clickbox box, and
 * {@code TILE} outlines the ground tile the entity stands on.
 */
public class GustavWorldOverlay extends Overlay
{
	private final Client client;
	private final GustavGuideConfig config;
	private final GustavGuideState state;
	private final ModelOutlineRenderer outlineRenderer;

	@Inject
	public GustavWorldOverlay(Client client, GustavGuideConfig config, GustavGuideState state,
							  ModelOutlineRenderer outlineRenderer)
	{
		this.client = client;
		this.config = config;
		this.state = state;
		this.outlineRenderer = outlineRenderer;
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

		// Destination: tile outline + bobbing arrow at the step's world point.
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
						// alpha 40: world tiles use a fainter fill than item/dialogue boxes (60), on purpose
						graphics.setColor(OverlayColors.translucent(color, 40));
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

		// Target object ("click-blue" the thing to use).
		if (config.highlightObjects())
		{
			TileObject obj = state.getTargetObject();
			if (obj != null)
			{
				drawObject(graphics, obj, color);
			}
		}

		// Target NPC ("click-blue" the person to talk to / attack).
		if (config.highlightNpcs())
		{
			NPC npc = state.getTargetNpc();
			if (npc != null)
			{
				drawNpc(graphics, npc, color);
			}
		}

		return null;
	}

	private void drawNpc(Graphics2D graphics, NPC npc, Color color)
	{
		switch (config.highlightStyle())
		{
			case GLOW:
				outlineRenderer.drawOutline(npc, config.outlineThickness(), color, config.outlineFeather());
				break;
			case HULL:
				fillShape(graphics, npc.getConvexHull(), color);
				break;
			case TILE:
				fillShape(graphics, npc.getCanvasTilePoly(), color);
				break;
			default:
				break;
		}
	}

	private void drawObject(Graphics2D graphics, TileObject obj, Color color)
	{
		switch (config.highlightStyle())
		{
			case GLOW:
				outlineRenderer.drawOutline(obj, config.outlineThickness(), color, config.outlineFeather());
				break;
			case HULL:
				fillShape(graphics, obj.getClickbox(), color);
				break;
			case TILE:
				LocalPoint lp = obj.getLocalLocation();
				fillShape(graphics, lp == null ? null : Perspective.getCanvasTilePoly(client, lp), color);
				break;
			default:
				break;
		}
	}

	/** Draw an outline + translucent fill of a shape; no-op when the shape is off-screen (null). */
	private static void fillShape(Graphics2D graphics, Shape shape, Color color)
	{
		if (shape == null)
		{
			return;
		}
		graphics.setColor(color);
		graphics.draw(shape);
		// alpha 40: world tiles use a fainter fill than item/dialogue boxes (60), on purpose
		graphics.setColor(OverlayColors.translucent(color, 40));
		graphics.fill(shape);
	}
}
