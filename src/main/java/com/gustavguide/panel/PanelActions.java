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

	/** Clear all saved progress for the current account. */
	void resetProgress();
}
