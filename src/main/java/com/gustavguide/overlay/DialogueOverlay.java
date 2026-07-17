/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.overlay;

import com.gustavguide.GustavGuideConfig;
import com.gustavguide.GustavGuideState;
import com.gustavguide.engine.DialogueDb;
import com.gustavguide.engine.RouteStep;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import java.util.Set;
import javax.inject.Inject;
import net.runelite.api.Client;
import net.runelite.api.widgets.ComponentID;
import net.runelite.api.widgets.Widget;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;

/**
 * Highlights the NPC-dialogue option the current step wants you to click. The expected options come
 * from the build-time Quest-Helper dialogue DB ({@link DialogueDb}); a live option is boxed only when
 * its text exactly matches a known option, so a wrong choice is never highlighted and steps with no
 * known options get no box ("named-match only").
 */
public class DialogueOverlay extends Overlay
{
	private final Client client;
	private final GustavGuideConfig config;
	private final GustavGuideState state;
	private final DialogueDb dialogueDb;

	// Expected options are recomputed only when the current step changes, not every frame.
	private String cachedStepId;
	private Set<String> cachedExpected;

	@Inject
	public DialogueOverlay(Client client, GustavGuideConfig config, GustavGuideState state, DialogueDb dialogueDb)
	{
		this.client = client;
		this.config = config;
		this.state = state;
		this.dialogueDb = dialogueDb;
		setPosition(OverlayPosition.DYNAMIC);
		setLayer(OverlayLayer.ABOVE_WIDGETS);
	}

	@Override
	public Dimension render(Graphics2D graphics)
	{
		if (!config.dialogueHighlight() || dialogueDb.isEmpty())
		{
			return null;
		}
		Widget options = client.getWidget(ComponentID.DIALOG_OPTION_OPTIONS);
		if (options == null || options.isHidden())
		{
			return null;
		}
		RouteStep step = state.getCurrentStep();
		if (step == null)
		{
			return null;
		}
		Set<String> expected = expectedFor(step);
		if (expected.isEmpty())
		{
			return null; // no known option for this step -> highlight nothing
		}

		Widget[] children = options.getChildren();
		if (children == null || children.length == 0)
		{
			children = options.getDynamicChildren();
		}
		if (children == null)
		{
			return null;
		}
		for (Widget child : children)
		{
			if (child == null || child.isHidden())
			{
				continue;
			}
			String text = child.getText();
			if (text == null || text.isEmpty())
			{
				continue;
			}
			if (expected.contains(DialogueDb.normalize(text)))
			{
				highlight(graphics, child.getBounds(), config.highlightColor());
			}
		}
		return null;
	}

	/** Expected options for the current step, cached until the step changes. */
	private Set<String> expectedFor(RouteStep step)
	{
		if (!step.getId().equals(cachedStepId))
		{
			cachedStepId = step.getId();
			cachedExpected = dialogueDb.expectedNormalized(step.getQuest(), step.getText());
		}
		return cachedExpected;
	}

	private static void highlight(Graphics2D graphics, Rectangle bounds, Color color)
	{
		if (bounds == null)
		{
			return;
		}
		// alpha 60: dialogue/item boxes use a stronger fill than the world tile (40), on purpose
		graphics.setColor(OverlayColors.translucent(color, 60));
		graphics.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
		graphics.setColor(color);
		graphics.drawRect(bounds.x, bounds.y, bounds.width, bounds.height);
	}
}
