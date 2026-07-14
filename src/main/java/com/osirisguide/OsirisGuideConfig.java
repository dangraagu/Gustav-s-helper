/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide;

import java.awt.Color;
import net.runelite.client.config.Alpha;
import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;
import net.runelite.client.config.ConfigSection;

@ConfigGroup(OsirisGuideConfig.GROUP)
public interface OsirisGuideConfig extends Config
{
	String GROUP = "osirisguide";

	@ConfigSection(
		name = "General",
		description = "Route tracking behaviour",
		position = 0
	)
	String generalSection = "general";

	@ConfigSection(
		name = "Overlays",
		description = "In-world guidance",
		position = 1
	)
	String overlaySection = "overlays";

	@ConfigItem(
		keyName = "mode",
		name = "Ironman mode",
		description = "Which account type to follow the route as. Filters mode-specific steps.",
		section = generalSection,
		position = 0
	)
	default IronmanMode mode()
	{
		return IronmanMode.REGULAR;
	}

	@ConfigItem(
		keyName = "autoAdvance",
		name = "Auto-advance",
		description = "Automatically mark steps complete when the game state shows they are done.",
		section = generalSection,
		position = 1
	)
	default boolean autoAdvance()
	{
		return true;
	}

	@ConfigItem(
		keyName = "hideCompleted",
		name = "Hide completed steps",
		description = "Collapse completed steps in the side panel.",
		section = generalSection,
		position = 2
	)
	default boolean hideCompleted()
	{
		return true;
	}

	@ConfigItem(
		keyName = "showWorldArrow",
		name = "World arrow",
		description = "Draw an arrow over the current step's destination tile.",
		section = overlaySection,
		position = 0
	)
	default boolean showWorldArrow()
	{
		return true;
	}

	@ConfigItem(
		keyName = "showTile",
		name = "Highlight destination tile",
		description = "Outline the current step's destination tile.",
		section = overlaySection,
		position = 1
	)
	default boolean showTile()
	{
		return true;
	}

	@ConfigItem(
		keyName = "showMinimapArrow",
		name = "Minimap arrow",
		description = "Draw an arrow on the minimap toward the current step (when in range).",
		section = overlaySection,
		position = 2
	)
	default boolean showMinimapArrow()
	{
		return true;
	}

	@ConfigItem(
		keyName = "highlightObjects",
		name = "Highlight objects",
		description = "Highlight the object the current step wants you to interact with.",
		section = overlaySection,
		position = 3
	)
	default boolean highlightObjects()
	{
		return true;
	}

	@ConfigItem(
		keyName = "highlightNpcs",
		name = "Highlight NPCs",
		description = "Highlight the NPC the current step wants you to interact with.",
		section = overlaySection,
		position = 4
	)
	default boolean highlightNpcs()
	{
		return true;
	}

	@Alpha
	@ConfigItem(
		keyName = "highlightColor",
		name = "Highlight colour",
		description = "Colour for arrows and highlights.",
		section = overlaySection,
		position = 5
	)
	default Color highlightColor()
	{
		return new Color(0, 200, 255);
	}
}
