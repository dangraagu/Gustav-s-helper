/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide;

import java.awt.Color;
import net.runelite.client.config.Alpha;
import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;
import net.runelite.client.config.ConfigSection;
import net.runelite.client.config.Range;

@ConfigGroup(GustavGuideConfig.GROUP)
public interface GustavGuideConfig extends Config
{
	String GROUP = "gustavguide";

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
		keyName = "guide",
		name = "Guide",
		description = "Which guide to follow. Progress and the item ledger are tracked separately per guide.",
		section = generalSection,
		position = 0
	)
	default Guide guide()
	{
		return Guide.OSIRIS_IRONMAN;
	}

	@ConfigItem(
		keyName = "mode",
		name = "Ironman mode",
		description = "Which account type to follow the route as. Filters mode-specific steps.",
		section = generalSection,
		position = 1
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
		position = 2
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
		position = 3
	)
	default boolean hideCompleted()
	{
		return true;
	}

	@ConfigItem(
		keyName = "birdhouseReminder",
		name = "Birdhouse run reminder",
		description = "Notify when ~50 minutes have passed since you last visited the Fossil Island birdhouses.",
		section = generalSection,
		position = 4
	)
	default boolean birdhouseReminder()
	{
		return true;
	}

	@ConfigItem(
		keyName = "teleportHint",
		name = "Teleport hint",
		description = "Suggest the fastest teleport you have UNLOCKED to reach the current step.",
		section = generalSection,
		position = 5
	)
	default boolean teleportHint()
	{
		return true;
	}

	@ConfigItem(
		keyName = "driveShortestPath",
		name = "Drive Shortest Path",
		description = "If the Shortest Path plugin is installed, auto-path it to the current step's destination.",
		section = generalSection,
		position = 6
	)
	default boolean driveShortestPath()
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

	@ConfigItem(
		keyName = "highlightItems",
		name = "Highlight items",
		description = "Highlight the current step's item in your inventory/bank.",
		section = overlaySection,
		position = 6
	)
	default boolean highlightItems()
	{
		return true;
	}

	@ConfigItem(
		keyName = "dialogueHighlight",
		name = "Highlight dialogue option",
		description = "During NPC dialogue, highlight the option the step wants you to choose.",
		section = overlaySection,
		position = 7
	)
	default boolean dialogueHighlight()
	{
		return true;
	}

	@ConfigItem(
		keyName = "showStepOverlay",
		name = "On-screen step text",
		description = "Show the current step's text as an on-screen panel, so the sidebar can stay closed.",
		section = overlaySection,
		position = 8
	)
	default boolean showStepOverlay()
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

	@ConfigItem(
		keyName = "highlightStyle",
		name = "Highlight style",
		description = "How to mark the target NPC/object: a Glow outline that hugs the model "
			+ "(the 'click-blue' look), a Hull box, or the ground Tile.",
		section = overlaySection,
		position = 8
	)
	default HighlightStyle highlightStyle()
	{
		return HighlightStyle.GLOW;
	}

	@Range(min = 1, max = 8)
	@ConfigItem(
		keyName = "outlineThickness",
		name = "Outline thickness",
		description = "Width in pixels of the glow outline (used when Highlight style = Glow).",
		section = overlaySection,
		position = 9
	)
	default int outlineThickness()
	{
		return 2;
	}

	@Range(min = 0, max = 4)
	@ConfigItem(
		keyName = "outlineFeather",
		name = "Outline feathering",
		description = "Softness of the glow outline's edge (0 = hard, higher = softer). "
			+ "Used when Highlight style = Glow.",
		section = overlaySection,
		position = 10
	)
	default int outlineFeather()
	{
		return 4;
	}

	// Plugin Hub requirement: networking to a 3rd-party server must be ENTIRELY opt-in — a boolean
	// that defaults to false and fully disables the calls, with this exact warning text. The warning
	// makes RuneLite show a confirmation dialog before the toggle can be enabled.
	@ConfigItem(
		keyName = "enableStepReports",
		name = "Enable step reports",
		description = "Allow the \"Report wrong / missing info\" button to send step reports. Nothing is "
			+ "ever sent unless this is on AND you press the button and confirm the previewed text.",
		warning = "This feature submits your IP address and various account data to a 3rd-party server "
			+ "not controlled or verified by Runelite developers.",
		position = 89
	)
	default boolean enableStepReports()
	{
		return false;
	}

	@ConfigItem(
		keyName = "reportEndpoint",
		name = "Report endpoint (advanced)",
		description = "Where the \"Report wrong / missing info\" button sends step reports. Leave blank to "
			+ "use the project's own reporting channel. Set your own Discord webhook URL here to send "
			+ "reports to your channel instead.",
		position = 90
	)
	default String reportEndpoint()
	{
		return "";
	}

	/** How the target NPC / object is marked in the world. */
	enum HighlightStyle
	{
		GLOW("Glow outline"),
		HULL("Hull box"),
		TILE("Tile");

		private final String label;

		HighlightStyle(String label)
		{
			this.label = label;
		}

		@Override
		public String toString()
		{
			return label;
		}
	}
}
