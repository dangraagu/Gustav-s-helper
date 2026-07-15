/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.overlay;

import com.osirisguide.OsirisGuideConfig;
import com.osirisguide.OsirisGuideState;
import com.osirisguide.engine.RouteStep;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import javax.inject.Inject;
import net.runelite.api.widgets.WidgetItem;
import net.runelite.client.ui.overlay.WidgetItemOverlay;

/**
 * Highlights the item the current step wants you to get/use, wherever it appears in your inventory
 * or bank — the Quest-Helper-style item marker. Read-only rendering; never interacts with items.
 */
public class OsirisItemOverlay extends WidgetItemOverlay
{
	private final OsirisGuideConfig config;
	private final OsirisGuideState state;

	@Inject
	public OsirisItemOverlay(OsirisGuideConfig config, OsirisGuideState state)
	{
		this.config = config;
		this.state = state;
		showOnInventory();
		showOnBank();
		showOnEquipment();
	}

	@Override
	public void renderItemOverlay(Graphics2D graphics, int itemId, WidgetItem widgetItem)
	{
		if (!config.highlightItems())
		{
			return;
		}
		RouteStep step = state.getCurrentStep();
		if (step == null || step.getHighlightItemId() != itemId)
		{
			return;
		}
		Rectangle bounds = widgetItem.getCanvasBounds();
		if (bounds == null)
		{
			return;
		}
		Color color = config.highlightColor();
		graphics.setColor(color);
		graphics.draw(bounds);
		graphics.setColor(new Color(color.getRed(), color.getGreen(), color.getBlue(), 60));
		graphics.fill(bounds);
	}
}
