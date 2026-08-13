/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

import java.util.ArrayList;
import java.util.List;

/**
 * Immutable snapshot the plugin builds on the client thread and hands to the panel to render
 * on the Swing thread. Keeps game-state reads off the Swing thread.
 */
public class PanelModel
{
	public static class ReqView
	{
		public final String text;
		public final boolean met;

		public ReqView(String text, boolean met)
		{
			this.text = text;
			this.met = met;
		}
	}

	public String mode = "";
	public int completed;
	public int total;
	/** 1-based position of the CURRENT step among the applicable steps (0 when there is none). */
	public int stepNumber;
	/** Everything the "report this step" button needs — prebuilt on the client thread. */
	public String reportBody;
	public boolean canReport;
	public int percent;
	public boolean loggedIn;
	public boolean finished;
	public boolean routeEmpty;

	public String section = "";
	public String title = "";
	public String text = "";
	public String note;          // optional tip shown under the step text (e.g. a skill-training method)
	public String teleportHint;  // "Fastest: <teleport>" for the current step, or null
	public String completesOn;   // human description of the auto-complete condition, or null when manual
	public String userNote;      // the player's own note for the current step, or null
	public String wikiUrl;

	public List<ReqView> requirements = new ArrayList<>();
	public List<String> upcoming = new ArrayList<>();
}
