/*
 * Copyright (c) 2021, Zoinkwiz <https://github.com/Zoinkwiz>
 * Copyright (c) 2026, dangraagu (adaptation)
 * All rights reserved.
 *
 * Adapted from RuneLite Quest Helper's DirectionArrow. The self-contained arrow-drawing
 * primitives are reused; Quest-Helper-specific world-map/perspective helpers were removed.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
 * ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
 * ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
package com.gustavguide.overlay;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.Polygon;
import java.awt.geom.AffineTransform;
import java.awt.geom.Line2D;
import net.runelite.api.Client;
import net.runelite.api.Perspective;
import net.runelite.api.Point;
import net.runelite.api.coords.LocalPoint;

/**
 * Arrow drawing primitives adapted from Quest Helper. Draws a bobbing world arrow and a
 * minimap arrow. See file header for attribution.
 */
public final class DirectionArrow
{
	private DirectionArrow()
	{
	}

	/** Draws the downward-pointing arrow above a canvas point (the classic Quest Helper marker). */
	public static void drawWorldArrow(Graphics2D graphics, Color color, int startX, int startY)
	{
		Line2D.Double line = new Line2D.Double(startX, startY - 13, startX, startY);
		drawArrow(graphics, line, color, 9, 4, 5);
	}

	/** Draws a small minimap arrow along the given line. */
	private static void drawMinimapArrow(Graphics2D graphics, Line2D.Double line, Color color)
	{
		drawArrow(graphics, line, color, 6, 2, 2);
	}

	/** Renders a minimap arrow at the given in-scene local point, if it projects to the minimap. */
	public static void renderMinimapArrow(Graphics2D graphics, Client client, LocalPoint localPoint, Color color)
	{
		if (localPoint == null)
		{
			return;
		}
		Point posOnMinimap = Perspective.localToMinimap(client, localPoint);
		if (posOnMinimap == null)
		{
			return;
		}
		Line2D.Double line = new Line2D.Double(posOnMinimap.getX(), posOnMinimap.getY() - 18,
			posOnMinimap.getX(), posOnMinimap.getY() - 8);
		drawMinimapArrow(graphics, line, color);
	}

	private static void drawArrow(Graphics2D graphics, Line2D.Double line, Color color, int width,
								  int tipHeight, int tipWidth)
	{
		graphics.setColor(Color.BLACK);
		graphics.setStroke(new BasicStroke(width));
		graphics.draw(line);
		drawArrowHead(graphics, line, tipHeight, tipWidth);

		graphics.setColor(color);
		graphics.setStroke(new BasicStroke(Math.max(1, width - 3)));
		graphics.draw(line);
		drawArrowHead(graphics, line, tipHeight - 2, tipWidth - 2);
		graphics.setStroke(new BasicStroke(1));
	}

	private static void drawArrowHead(Graphics2D g2d, Line2D.Double line, int extraHeight, int extraWidth)
	{
		Polygon arrowHead = new Polygon();
		arrowHead.addPoint(0, 6 + extraHeight);
		arrowHead.addPoint(-6 - extraWidth, -1 - extraHeight);
		arrowHead.addPoint(6 + extraWidth, -1 - extraHeight);

		AffineTransform tx = new AffineTransform();
		tx.setToIdentity();
		double angle = Math.atan2(line.y2 - line.y1, line.x2 - line.x1);
		tx.translate(line.x2, line.y2);
		tx.rotate(angle - Math.PI / 2d);

		Graphics2D g = (Graphics2D) g2d.create();
		g.setTransform(tx);
		g.fill(arrowHead);
		g.dispose();
	}
}
