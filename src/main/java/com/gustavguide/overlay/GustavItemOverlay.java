/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.overlay;

import com.gustavguide.GustavGuideConfig;
import com.gustavguide.GustavGuideState;
import com.gustavguide.engine.RouteStep;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import javax.inject.Inject;
import net.runelite.api.gameval.InterfaceID;
import net.runelite.api.widgets.WidgetItem;
import net.runelite.client.ui.overlay.WidgetItemOverlay;

/**
 * Highlights the item the current step wants you to get/use, wherever it appears — inventory, bank,
 * equipment, and the SHOP stock interface (so "Buy X from Y" outlines X in the shop) — the
 * Quest-Helper-style item marker. Read-only rendering; never interacts with items.
 */
public class GustavItemOverlay extends WidgetItemOverlay
{
	private final GustavGuideConfig config;
	private final GustavGuideState state;

	@Inject
	public GustavItemOverlay(GustavGuideConfig config, GustavGuideState state)
	{
		this.config = config;
		this.state = state;
		showOnInventory();
		showOnBank();
		showOnEquipment();
		showOnInterfaces(InterfaceID.SHOPMAIN);  // 300 — the shop's stock grid
	}

	@Override
	public void renderItemOverlay(Graphics2D graphics, int itemId, WidgetItem widgetItem)
	{
		// This runs for EVERY item slot (inventory + bank + equipment) every frame. Keep the hot path
		// to a volatile read + int compares; only touch the config proxy for the one matching item —
		// otherwise a full bank at 50fps floods the client thread and freezes the game.
		RouteStep step = state.getCurrentStep();
		if (step == null)
		{
			return;
		}
		int wantId = step.getHighlightItemId();
		if (wantId < 0 || wantId != itemId)
		{
			return;
		}
		if (!config.highlightItems())
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
