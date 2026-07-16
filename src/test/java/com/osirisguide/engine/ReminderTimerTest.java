/*
 * Copyright (c) 2026, dangraagu
 * Licensed under the BSD 2-Clause License. See LICENSE.
 */
package com.osirisguide.engine;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ReminderTimerTest
{
	@Test
	public void firesOncePerCycleAndRearmsOnVisit()
	{
		ReminderTimer t = new ReminderTimer(1000, 0);
		assertFalse(t.due(5000));           // never armed -> never due

		t.visit(10_000);
		assertFalse(t.due(10_500));         // interval not elapsed
		assertTrue(t.due(11_000));          // elapsed -> due exactly once
		assertFalse(t.due(12_000));         // does not repeat until re-armed

		t.visit(20_000);                    // visiting the spot re-arms the cycle
		assertFalse(t.due(20_500));
		assertTrue(t.due(21_000));
	}

	@Test
	public void restoresFromPersistedVisit()
	{
		// A relog restores the last-visit timestamp, so the reminder survives sessions.
		ReminderTimer t = new ReminderTimer(1000, 5000);
		assertTrue(t.due(6001));
		assertFalse(t.due(7000));
	}
}
