/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.panel;

/**
 * Callbacks the side panel invokes on user action. Implemented by the plugin, which marshals
 * the work onto the client thread.
 */
public interface PanelActions
{
	/** Mark the current step complete (manual advance / "Done"). */
	void completeCurrent();

	/** Skip the current step (also marks it complete). */
	void skipCurrent();

	/** Undo: reopen the previous step, so a mis-clicked Done/Skip can be taken back. */
	void undoLast();

	/** Send a "this step is wrong / something is missing" report — the exact body the user was shown. */
	void reportStep(String reportBody);

	/**
	 * The player's current tile as "x, y, plane p", or null when not logged in. Used ONLY when the
	 * user ticks "attach my position" on a report, so a wrong step coordinate can be fixed from the
	 * spot the step actually happens — the report never carries a position otherwise.
	 */
	String playerTile();

	/** The player's own saved note for the current step, or null. */
	String userNote();

	/** Save (or clear, when blank) the player's note for the current step. */
	void setUserNote(String note);

	/**
	 * Offer to mark the flavour steps behind the furthest completed real gate as done ("sync to my
	 * account"). The implementation MUST show the count and get explicit confirmation first — this is
	 * the fold the engine refuses to do automatically, safe only as an informed user action.
	 */
	void fastForward();

	/** Clear all saved progress for the current account. */
	void resetProgress();
}
