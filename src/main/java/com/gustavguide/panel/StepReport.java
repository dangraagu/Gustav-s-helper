/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import com.gustavguide.engine.RouteStep;
import java.util.List;
import net.runelite.api.coords.WorldPoint;

/**
 * Builds the "this step is wrong" report the user sends from the panel.
 *
 * <p>The point of a report is that it says <b>what</b> is wrong and <b>where</b> — so everything needed
 * to fix a bad coordinate or highlight is captured automatically (guide, step id + number, the step text,
 * the tile and the NPC/object/item ids the plugin pointed at) and the user only types the problem.</p>
 *
 * <p>Deliberately carries <b>no account information</b>: no player name, no account hash, no location of
 * the player — only the guide data the plugin itself shipped, plus what the user typed. The user sees the
 * exact text before it is sent.</p>
 */
public final class StepReport
{
	/** Discord rejects a webhook message over 2000 chars; stay clear of it. */
	private static final int MAX_MESSAGE = 1800;
	private static final int MAX_TEXT = 300;
	private static final int MAX_USER_NOTE = 700;

	private StepReport()
	{
	}

	/**
	 * The human-readable report body, shown to the user for confirmation and sent verbatim.
	 *
	 * @param userNote what the player typed (may be empty)
	 */
	public static String body(String guideId, String guideName, RouteStep step, int stepNumber, int stepTotal,
							  String userNote, String pluginVersion)
	{
		return withProblem(details(guideId, guideName, step, stepNumber, stepTotal, pluginVersion), userNote);
	}

	/**
	 * Everything except the user's description — built once when the panel refreshes, shown as the
	 * preview, and sent verbatim. Keeping the preview and the payload the SAME string means a step that
	 * auto-completes while the dialog is open cannot change what gets sent behind the user's back.
	 */
	public static String details(String guideId, String guideName, RouteStep step, int stepNumber,
								 int stepTotal, String pluginVersion)
	{
		StringBuilder sb = new StringBuilder();
		sb.append("**Step report** — ").append(nz(guideName)).append(" (`").append(nz(guideId)).append("`)\n");
		if (step != null)
		{
			sb.append("Step ").append(stepNumber).append('/').append(stepTotal)
				.append("  `").append(step.getId()).append("`\n");
			line(sb, "Section", step.getSection());
			line(sb, "Text", clip(step.getText(), MAX_TEXT));
			WorldPoint w = step.getWorldPoint();
			line(sb, "Points at", w == null ? "(no location)"
				: (w.getX() + ", " + w.getY() + ", plane " + w.getPlane()));
			List<Integer> npcs = step.getHighlightNpcIds();
			if (!npcs.isEmpty())
			{
				line(sb, "NPC id", npcs.toString());
			}
			if (step.getHighlightObjectId() >= 0)
			{
				line(sb, "Object id", String.valueOf(step.getHighlightObjectId()));
			}
			if (!step.getHighlightItemIds().isEmpty())
			{
				line(sb, "Item id", step.getHighlightItemIds().toString());
			}
			line(sb, "Completes on", step.getComplete() == null ? "manual" : step.getComplete().describe());
		}
		else
		{
			sb.append("(no current step)\n");
		}
		if (pluginVersion != null && !pluginVersion.isEmpty())
		{
			line(sb, "Plugin", pluginVersion);
		}
		return sb.toString();
	}

	/** Appends what the user typed to the previewed details, and caps the whole thing for Discord. */
	public static String withProblem(String details, String userNote)
	{
		return clip((details == null ? "" : details)
			+ "\n**Problem:** " + clip(blankToDash(userNote), MAX_USER_NOTE), MAX_MESSAGE);
	}

	/**
	 * The report wrapped as a Discord webhook payload. Kept minimal on purpose: a single {@code content}
	 * field, and {@code allowed_mentions} empty so a report can never ping a role or @everyone even if the
	 * user types one.
	 */
	public static String discordPayload(String body)
	{
		return "{\"content\":" + jsonString(clip(body, MAX_MESSAGE))
			+ ",\"allowed_mentions\":{\"parse\":[]}}";
	}

	private static void line(StringBuilder sb, String label, String value)
	{
		sb.append("• ").append(label).append(": ").append(nz(value)).append('\n');
	}

	private static String nz(String s)
	{
		return s == null ? "" : s;
	}

	private static String blankToDash(String s)
	{
		return (s == null || s.trim().isEmpty()) ? "(not described)" : s.trim();
	}

	private static String clip(String s, int max)
	{
		if (s == null)
		{
			return "";
		}
		String flat = s.replace("\r", "");
		return flat.length() <= max ? flat : flat.substring(0, max) + "…";
	}

	/** Minimal JSON string escaping — no dependency, and the payload is a single field. */
	static String jsonString(String s)
	{
		StringBuilder out = new StringBuilder(s.length() + 16).append('"');
		for (int i = 0; i < s.length(); i++)
		{
			char c = s.charAt(i);
			switch (c)
			{
				case '"':
					out.append("\\\"");
					break;
				case '\\':
					out.append("\\\\");
					break;
				case '\n':
					out.append("\\n");
					break;
				case '\t':
					out.append("\\t");
					break;
				default:
					if (c < 0x20)
					{
						out.append(String.format("\\u%04x", (int) c));
					}
					else
					{
						out.append(c);
					}
			}
		}
		return out.append('"').toString();
	}
}
