/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.panel;

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

	/** Clear all saved progress for the current account. */
	void resetProgress();
}
