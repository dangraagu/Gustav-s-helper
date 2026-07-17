/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.gustavguide.engine;

/**
 * A visit-armed interval reminder: {@link #visit} marks "you were here, cycle started"; {@link #due}
 * returns true exactly once when the interval has elapsed since the last visit, then stays quiet until
 * the next visit re-arms it. Used for the birdhouse-run reminder (visit the birdhouses -> notified
 * ~50 minutes later). Never armed (last visit 0) means never due.
 */
public class ReminderTimer
{
	private final long intervalMs;
	private long lastVisitMs;
	private boolean notified;

	public ReminderTimer(long intervalMs, long persistedLastVisitMs)
	{
		this.intervalMs = intervalMs;
		this.lastVisitMs = persistedLastVisitMs;
	}

	/** The player is at the spot now: (re)start the cycle. */
	public void visit(long nowMs)
	{
		lastVisitMs = nowMs;
		notified = false;
	}

	/** True exactly once per cycle, when the interval since the last visit has elapsed. */
	public boolean due(long nowMs)
	{
		if (lastVisitMs <= 0 || notified || nowMs - lastVisitMs < intervalMs)
		{
			return false;
		}
		notified = true;
		return true;
	}

	/** Last visit timestamp (ms epoch), for persistence across sessions. */
	public long getLastVisit()
	{
		return lastVisitMs;
	}
}
