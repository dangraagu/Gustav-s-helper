/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.overlay;

import com.gustavguide.GustavGuideConfig;
import com.gustavguide.GustavGuideState;
import com.gustavguide.engine.RouteStep;
import java.awt.Dimension;
import java.awt.Graphics2D;
import javax.inject.Inject;
import net.runelite.client.ui.overlay.OverlayPanel;
import net.runelite.client.ui.overlay.OverlayPosition;
import net.runelite.client.ui.overlay.components.LineComponent;
import net.runelite.client.ui.overlay.components.TitleComponent;

/**
 * The current step as an on-screen panel, so the route can be followed without keeping the sidebar
 * open. Text only — completion still comes from the engine or the panel buttons. Movable like any
 * RuneLite overlay; hidden entirely via the "On-screen step text" config toggle.
 */
public class StepTextOverlay extends OverlayPanel
{
	private static final int MAX_CHARS = 220;
	private static final int PANEL_WIDTH = 220;

	private final GustavGuideConfig config;
	private final GustavGuideState state;

	@Inject
	public StepTextOverlay(GustavGuideConfig config, GustavGuideState state)
	{
		this.config = config;
		this.state = state;
		setPosition(OverlayPosition.TOP_LEFT);
	}

	@Override
	public Dimension render(Graphics2D graphics)
	{
		if (!config.showStepOverlay())
		{
			return null;
		}
		RouteStep step = state.getCurrentStep();
		if (step == null)
		{
			return null;
		}
		panelComponent.setPreferredSize(new Dimension(PANEL_WIDTH, 0));
		String section = step.getSection();
		if (section != null && !section.isEmpty())
		{
			panelComponent.getChildren().add(TitleComponent.builder().text(section).build());
		}
		String text = step.getText() == null ? "" : step.getText().replace('\n', ' ');
		if (text.length() > MAX_CHARS)
		{
			text = text.substring(0, MAX_CHARS - 1) + "…";
		}
		panelComponent.getChildren().add(LineComponent.builder().left(text).build());
		return super.render(graphics);
	}
}
